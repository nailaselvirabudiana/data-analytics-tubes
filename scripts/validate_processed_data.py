"""
Validate the processed poverty and social-vulnerability panel.

This is a quality-gate script for the preprocessing lead. It does not clean data;
it checks whether the processed output is structurally safe for analysis.

Outputs:
- reports/preprocessing/processed_validation_checks.csv
- reports/preprocessing/metric_coverage_by_year.csv
- reports/preprocessing/processed_validation_report.md
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PANEL_PATH = PROJECT_ROOT / "data" / "processed" / "panel_kemiskinan_jabar_preprocessed.csv"
REPORT_DIR = PROJECT_ROOT / "reports" / "preprocessing"
KEY_COLS = ["kode_kabupaten_kota", "tahun"]
DIM_COLS = ["kode_provinsi", "nama_provinsi", "kode_kabupaten_kota", "nama_kabupaten_kota"]
METRIC_COLS = [
    "garis_kemiskinan",
    "persentase_penduduk_miskin",
    "indeks_keparahan_kemiskinan",
    "indeks_pembangunan_manusia",
    "tingkat_pengangguran_terbuka",
]
RISK_COMPONENT_COUNT = 4
EXPECTED_START_YEAR = 2010
EXPECTED_END_YEAR = 2024


def add_check(checks: List[Dict[str, Any]], name: str, status: str, value: Any, expectation: str) -> None:
    checks.append(
        {
            "check": name,
            "status": status,
            "value": value,
            "expectation": expectation,
        }
    )


def status_from_bool(condition: bool, warn: bool = False) -> str:
    if condition:
        return "PASS"
    return "WARN" if warn else "FAIL"


def markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    columns = list(df.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[col]).replace("|", "/") for col in columns) + " |")
    return "\n".join(lines)


def validate() -> Dict[str, Path]:
    if not PANEL_PATH.exists():
        raise FileNotFoundError(f"Processed panel not found: {PANEL_PATH}")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(PANEL_PATH)
    checks: List[Dict[str, Any]] = []

    required_cols = DIM_COLS + ["tahun"] + METRIC_COLS
    missing_required = [col for col in required_cols if col not in df.columns]
    add_check(
        checks,
        "required_columns_present",
        status_from_bool(not missing_required),
        ", ".join(missing_required) if missing_required else "all present",
        "All required dimension, key, and metric columns exist.",
    )

    duplicate_keys = int(df.duplicated(KEY_COLS).sum())
    add_check(
        checks,
        "unique_kabupaten_kota_year_key",
        status_from_bool(duplicate_keys == 0),
        duplicate_keys,
        "No duplicate kode_kabupaten_kota + tahun rows.",
    )

    exact_duplicates = int(df.duplicated().sum())
    add_check(
        checks,
        "no_exact_duplicate_rows",
        status_from_bool(exact_duplicates == 0),
        exact_duplicates,
        "No exact duplicate rows.",
    )

    missing_key_values = int(df[KEY_COLS].isna().sum().sum())
    add_check(
        checks,
        "no_missing_key_values",
        status_from_bool(missing_key_values == 0),
        missing_key_values,
        "No missing kode_kabupaten_kota or tahun.",
    )

    missing_dim_values = int(df[DIM_COLS].isna().sum().sum())
    add_check(
        checks,
        "no_missing_dimension_values",
        status_from_bool(missing_dim_values == 0),
        missing_dim_values,
        "No missing geographic dimension values.",
    )

    region_count = int(df["kode_kabupaten_kota"].nunique())
    add_check(
        checks,
        "expected_region_count",
        status_from_bool(region_count == 27, warn=True),
        region_count,
        "Expected 27 kabupaten/kota in Jawa Barat panel.",
    )

    year_min = int(df["tahun"].min())
    year_max = int(df["tahun"].max())
    add_check(
        checks,
        "year_range_available",
        "PASS",
        f"{year_min}-{year_max}",
        "Record the available year range; not all metrics must cover every year.",
    )
    add_check(
        checks,
        "analysis_period_matches_scope",
        status_from_bool(year_min == EXPECTED_START_YEAR and year_max == EXPECTED_END_YEAR),
        f"{year_min}-{year_max}",
        f"Processed panel should use the obtain-stage scope {EXPECTED_START_YEAR}-{EXPECTED_END_YEAR}.",
    )

    range_rules = {
        "garis_kemiskinan": df["garis_kemiskinan"].dropna().gt(0),
        "persentase_penduduk_miskin": df["persentase_penduduk_miskin"].dropna().between(0, 100, inclusive="both"),
        "indeks_keparahan_kemiskinan": df["indeks_keparahan_kemiskinan"].dropna().ge(0),
        "indeks_pembangunan_manusia": df["indeks_pembangunan_manusia"].dropna().between(0, 100, inclusive="both"),
        "tingkat_pengangguran_terbuka": df["tingkat_pengangguran_terbuka"].dropna().between(0, 100, inclusive="both"),
    }
    for metric, valid_mask in range_rules.items():
        invalid_count = int((~valid_mask).sum())
        add_check(
            checks,
            f"{metric}_domain_range",
            status_from_bool(invalid_count == 0),
            invalid_count,
            "Non-null metric values are inside expected domain range.",
        )

    zero_counts = {
        metric: int((df[metric].notna() & df[metric].eq(0)).sum())
        for metric in METRIC_COLS
    }
    zero_total = sum(zero_counts.values())
    add_check(
        checks,
        "no_zero_placeholders_remaining",
        status_from_bool(zero_total == 0),
        zero_counts,
        "Source zero placeholders should be converted to missing values during preprocessing.",
    )

    coverage = (
        df.groupby("tahun")[METRIC_COLS]
        .apply(lambda frame: frame.notna().sum())
        .reset_index()
    )

    scored_mask = df["skor_kerentanan_sosial"].notna()
    latest_scored_year = int(df.loc[scored_mask, "tahun"].max()) if scored_mask.any() else None
    add_check(
        checks,
        "latest_scored_year_exists",
        status_from_bool(latest_scored_year is not None),
        latest_scored_year,
        "At least one year has complete vulnerability-score components.",
    )

    if "jumlah_komponen_skor_kerentanan" in df.columns and "skor_kerentanan_sosial" in df.columns:
        incomplete_with_score = int(
            (
                df["jumlah_komponen_skor_kerentanan"].lt(RISK_COMPONENT_COUNT)
                & df["skor_kerentanan_sosial"].notna()
            ).sum()
        )
        complete_without_score = int(
            (
                df["jumlah_komponen_skor_kerentanan"].eq(RISK_COMPONENT_COUNT)
                & df["skor_kerentanan_sosial"].isna()
            ).sum()
        )
        add_check(
            checks,
            "score_only_when_components_complete",
            status_from_bool(incomplete_with_score == 0 and complete_without_score == 0),
            f"incomplete_with_score={incomplete_with_score}; complete_without_score={complete_without_score}",
            "Vulnerability score is populated only when all 4 risk components are available.",
        )

    if "peringkat_prioritas_intervensi" in df.columns:
        score_without_rank = int(
            (df["skor_kerentanan_sosial"].notna() & df["peringkat_prioritas_intervensi"].isna()).sum()
        )
        rank_without_score = int(
            (df["skor_kerentanan_sosial"].isna() & df["peringkat_prioritas_intervensi"].notna()).sum()
        )
        add_check(
            checks,
            "priority_rank_matches_score_availability",
            status_from_bool(score_without_rank == 0 and rank_without_score == 0),
            f"score_without_rank={score_without_rank}; rank_without_score={rank_without_score}",
            "Priority rank exists exactly when vulnerability score exists.",
        )

    checks_df = pd.DataFrame(checks)
    checks_path = REPORT_DIR / "processed_validation_checks.csv"
    coverage_path = REPORT_DIR / "metric_coverage_by_year.csv"
    report_path = REPORT_DIR / "processed_validation_report.md"

    checks_df.to_csv(checks_path, index=False)
    coverage.to_csv(coverage_path, index=False)

    failed = checks_df.loc[checks_df["status"].eq("FAIL")]
    warned = checks_df.loc[checks_df["status"].eq("WARN")]

    report_lines = [
        "# Processed Data Validation Report",
        "",
        f"Generated at: {datetime.utcnow().isoformat()}Z",
        "",
        "## Verdict",
        "",
        f"- FAIL checks: {len(failed)}",
        f"- WARN checks: {len(warned)}",
        f"- PASS checks: {int(checks_df['status'].eq('PASS').sum())}",
        "",
        "## Panel Summary",
        "",
        f"- Rows: {len(df)}",
        f"- Columns: {len(df.columns)}",
        f"- Kabupaten/kota count: {region_count}",
        f"- Year range: {year_min}-{year_max}",
        f"- Latest scored year: {latest_scored_year}",
        "",
        "## Checks",
        "",
        markdown_table(checks_df),
        "",
        "## Metric Coverage By Year",
        "",
        markdown_table(coverage),
        "",
        "## Interpretation Notes",
        "",
        "- Missing metric values are acceptable when a source dataset does not cover that year.",
        "- For intervention-priority analysis, use rows where `skor_kerentanan_sosial` is not missing.",
        "- For latest complete priority analysis in the current data, use the latest scored year shown above.",
        "",
    ]
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    print(f"Validation selesai: {len(failed)} FAIL, {len(warned)} WARN")
    print(f"- checks: {checks_path.relative_to(PROJECT_ROOT)}")
    print(f"- coverage: {coverage_path.relative_to(PROJECT_ROOT)}")
    print(f"- report: {report_path.relative_to(PROJECT_ROOT)}")

    if not failed.empty:
        raise SystemExit("Processed data validation failed. See report for details.")

    return {
        "checks": checks_path,
        "coverage": coverage_path,
        "report": report_path,
    }


if __name__ == "__main__":
    validate()

"""
Preprocess poverty and social-vulnerability datasets for West Java analytics.

Role fit in OSEMN:
- Main responsibility: Scrub (clean, standardize, integrate, engineer features).
- Supporting responsibility: light Explore for data-quality profiling only.

Outputs:
- data/processed/panel_kemiskinan_jabar_preprocessed.csv
- data/processed/feature_dictionary.csv
- data/processed/preprocess_manifest.csv
- reports/preprocessing/data_quality_summary.csv
- reports/preprocessing/preprocessing_quality_report.md

Default analysis period:
- 2010-2024, matching the obtain-stage scope.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_ARCHIVE_DIR = PROJECT_ROOT / "data" / "archive"
DEFAULT_INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "reports" / "preprocessing"
DEFAULT_START_YEAR = 2010
DEFAULT_END_YEAR = 2024
LOG_DIR = PROJECT_ROOT / "logs"

BASE_URL = "https://data.jabarprov.go.id"
KEY_COLS = ["kode_kabupaten_kota", "tahun"]
DIM_COLS = ["kode_provinsi", "nama_provinsi", "kode_kabupaten_kota", "nama_kabupaten_kota"]


@dataclass(frozen=True)
class DatasetSpec:
    logical_name: str
    metric_col: str
    metric_label: str
    unit_hint: str
    risk_direction: str
    zero_is_missing: bool = True


DATASETS: List[DatasetSpec] = [
    DatasetSpec(
        logical_name="raw_garis_kemiskinan",
        metric_col="garis_kemiskinan",
        metric_label="Garis kemiskinan",
        unit_hint="rupiah/kapita/bulan",
        risk_direction="context_only",
    ),
    DatasetSpec(
        logical_name="raw_persentase_miskin",
        metric_col="persentase_penduduk_miskin",
        metric_label="Persentase penduduk miskin",
        unit_hint="persen",
        risk_direction="high_is_risky",
    ),
    DatasetSpec(
        logical_name="raw_keparahan_kemiskinan",
        metric_col="indeks_keparahan_kemiskinan",
        metric_label="Indeks keparahan kemiskinan",
        unit_hint="indeks",
        risk_direction="high_is_risky",
    ),
    DatasetSpec(
        logical_name="raw_ipm_sp2010",
        metric_col="indeks_pembangunan_manusia",
        metric_label="Indeks pembangunan manusia",
        unit_hint="indeks",
        risk_direction="low_is_risky",
    ),
    DatasetSpec(
        logical_name="raw_pengangguran_terbuka",
        metric_col="tingkat_pengangguran_terbuka",
        metric_label="Tingkat pengangguran terbuka",
        unit_hint="persen",
        risk_direction="high_is_risky",
    ),
]


class PreprocessingInputError(RuntimeError):
    """Raised when raw inputs do not contain usable statistical records."""


def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logfile = LOG_DIR / "preprocess.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(logfile, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return logging.getLogger("preprocess")


logger = setup_logging()


def snake_case(value: str) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"[^0-9a-zA-Z]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def normalize_name(value: Any) -> Any:
    if pd.isna(value):
        return pd.NA
    text = re.sub(r"\s+", " ", str(value).strip())
    return text.upper()


def coerce_numeric(series: pd.Series) -> pd.Series:
    def parse_one(value: Any) -> float:
        if pd.isna(value):
            return np.nan
        text = str(value).strip()
        if not text or text.lower() in {"nan", "none", "null", "-"}:
            return np.nan

        text = (
            text.replace("%", "")
            .replace("Rp", "")
            .replace("rp", "")
            .replace("\u00a0", " ")
            .strip()
        )
        if "," in text and "." in text:
            if text.rfind(",") > text.rfind("."):
                text = text.replace(".", "").replace(",", ".")
            else:
                text = text.replace(",", "")
        elif "," in text:
            text = text.replace(",", ".")

        text = re.sub(r"[^0-9.\-]", "", text)
        if not text or text in {".", "-", "-."}:
            return np.nan
        try:
            return float(text)
        except ValueError:
            return np.nan

    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    return series.map(parse_one)


def read_csv_safely(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [snake_case(col) for col in out.columns]
    return out


def newest_matching_file(search_dirs: Iterable[Path], patterns: Iterable[str]) -> Optional[Path]:
    candidates: List[Path] = []
    for directory in search_dirs:
        if not directory.exists():
            continue
        for pattern in patterns:
            candidates.extend(directory.glob(pattern))

    if not candidates:
        return None

    def sort_key(path: Path) -> Tuple[float, str]:
        return (path.stat().st_mtime, path.name)

    return sorted(candidates, key=sort_key, reverse=True)[0]


def extract_records_from_json(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, list):
        return [row for row in obj if isinstance(row, dict)]

    if not isinstance(obj, dict):
        return []

    if "openapi" in obj and "paths" in obj:
        return []

    data = obj.get("data")
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        return [data]

    for value in obj.values():
        if isinstance(value, list):
            rows = [row for row in value if isinstance(row, dict)]
            if rows:
                return rows

    return []


def openapi_endpoint_from_doc(path: Path) -> str:
    with path.open("r", encoding="utf-8") as handle:
        obj = json.load(handle)

    if "openapi" not in obj or "paths" not in obj:
        raise PreprocessingInputError(f"{path} is not an OpenAPI document.")

    server_url = "/api-backend/bigdata/bps/"
    servers = obj.get("servers") or []
    if servers and isinstance(servers[0], dict):
        server_url = servers[0].get("url") or server_url

    data_paths = [key for key in obj.get("paths", {}) if "{id}" not in key]
    if not data_paths:
        raise PreprocessingInputError(f"No collection endpoint found in {path}.")

    collection_path = sorted(data_paths)[0]
    if server_url.startswith("http"):
        return server_url.rstrip("/") + "/" + collection_path.lstrip("/")
    return BASE_URL.rstrip("/") + "/" + server_url.strip("/") + "/" + collection_path.lstrip("/")


def fetch_openapi_records(endpoint: str, limit: int, timeout: int) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    skip = 0
    session = requests.Session()

    while True:
        params = {"limit": limit, "skip": skip}
        response = session.get(endpoint, params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        batch = extract_records_from_json(payload)

        if not batch:
            break

        rows.extend(batch)
        logger.info("Fetched %s rows from %s", len(rows), endpoint)

        if len(batch) < limit:
            break
        skip += len(batch)

    if not rows:
        raise PreprocessingInputError(f"Endpoint returned no data rows: {endpoint}")

    return pd.json_normalize(rows)


def source_is_usable(df: pd.DataFrame, spec: DatasetSpec) -> bool:
    cols = set(standardize_columns(df).columns)
    required = set(KEY_COLS + ["nama_kabupaten_kota", spec.metric_col])
    return required.issubset(cols)


def load_source_dataframe(
    spec: DatasetSpec,
    source_dir: Path,
    archive_dir: Path,
    interim_dir: Path,
    fetch_openapi_if_needed: bool,
    fetch_limit: int,
    fetch_timeout: int,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    search_dirs = [source_dir, archive_dir]
    csv_path = newest_matching_file(
        search_dirs,
        [f"{spec.logical_name}.csv", f"{spec.logical_name}_*.csv"],
    )
    json_path = newest_matching_file(
        search_dirs,
        [f"{spec.logical_name}.json", f"{spec.logical_name}_*.json"],
    )

    source_info: Dict[str, Any] = {
        "logical_name": spec.logical_name,
        "metric": spec.metric_col,
        "source_mode": "none",
        "source_file": "",
        "api_endpoint": "",
        "records_cache_file": "",
    }

    if csv_path is not None:
        df = read_csv_safely(csv_path)
        if source_is_usable(df, spec):
            source_info.update(source_mode="csv", source_file=str(csv_path.relative_to(PROJECT_ROOT)))
            return df, source_info
        source_info.update(source_mode="csv_unusable", source_file=str(csv_path.relative_to(PROJECT_ROOT)))

    if json_path is not None:
        with json_path.open("r", encoding="utf-8") as handle:
            obj = json.load(handle)
        rows = extract_records_from_json(obj)
        if rows:
            df = pd.json_normalize(rows)
            if source_is_usable(df, spec):
                source_info.update(source_mode="json", source_file=str(json_path.relative_to(PROJECT_ROOT)))
                return df, source_info

    if fetch_openapi_if_needed and json_path is not None:
        endpoint = openapi_endpoint_from_doc(json_path)
        logger.info("Raw source for %s is not records; fetching %s", spec.logical_name, endpoint)
        df = fetch_openapi_records(endpoint, limit=fetch_limit, timeout=fetch_timeout)

        interim_dir.mkdir(parents=True, exist_ok=True)
        cache_path = interim_dir / f"{spec.logical_name}_api_records.csv"
        df.to_csv(cache_path, index=False)

        source_info.update(
            source_mode="openapi_fetch",
            source_file=str(json_path.relative_to(PROJECT_ROOT)),
            api_endpoint=endpoint,
            records_cache_file=str(cache_path.relative_to(PROJECT_ROOT)),
        )
        return df, source_info

    raw_hint = source_info.get("source_file") or f"{spec.logical_name}.csv/json"
    raise PreprocessingInputError(
        "Raw input for "
        f"{spec.logical_name} does not contain expected statistical columns "
        f"{KEY_COLS + ['nama_kabupaten_kota', spec.metric_col]}. "
        f"Detected source: {raw_hint}. If it is an OpenAPI document, rerun with "
        "--fetch-openapi-if-needed."
    )


def clean_dataset(df: pd.DataFrame, spec: DatasetSpec) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    raw_rows = len(df)
    df = standardize_columns(df)

    required_cols = KEY_COLS + ["nama_kabupaten_kota", spec.metric_col]
    missing_required_cols = [col for col in required_cols if col not in df.columns]
    if missing_required_cols:
        raise PreprocessingInputError(
            f"{spec.logical_name} missing required columns: {missing_required_cols}"
        )

    if "kode_provinsi" not in df.columns:
        df["kode_provinsi"] = 32
    if "nama_provinsi" not in df.columns:
        df["nama_provinsi"] = "JAWA BARAT"

    keep_cols = list(dict.fromkeys(DIM_COLS + ["tahun", "id", "satuan", spec.metric_col]))
    keep_cols = [col for col in keep_cols if col in df.columns]
    df = df[keep_cols].copy()

    missing_before = int(df.isna().sum().sum())

    df["kode_kabupaten_kota"] = coerce_numeric(df["kode_kabupaten_kota"]).astype("Int64")
    df["kode_provinsi"] = coerce_numeric(df["kode_provinsi"]).astype("Int64")
    df["tahun"] = coerce_numeric(df["tahun"]).astype("Int64")
    df[spec.metric_col] = coerce_numeric(df[spec.metric_col])
    df["nama_kabupaten_kota"] = df["nama_kabupaten_kota"].map(normalize_name)
    df["nama_provinsi"] = df["nama_provinsi"].map(normalize_name).fillna("JAWA BARAT")

    if "satuan" in df.columns:
        df["satuan"] = df["satuan"].map(lambda value: normalize_name(value) if not pd.isna(value) else pd.NA)

    rows_before_key_drop = len(df)
    df = df.dropna(subset=KEY_COLS)
    rows_dropped_missing_keys = rows_before_key_drop - len(df)

    if "nama_provinsi" in df.columns:
        province_mask = df["nama_provinsi"].isna() | df["nama_provinsi"].eq("JAWA BARAT")
        df = df.loc[province_mask].copy()

    if "id" in df.columns:
        df = df.sort_values(["kode_kabupaten_kota", "tahun", "id"])
    else:
        df = df.sort_values(["kode_kabupaten_kota", "tahun"])

    duplicate_key_rows = int(df.duplicated(KEY_COLS, keep=False).sum())
    exact_duplicates = int(df.duplicated().sum())
    df = df.drop_duplicates()
    df = df.drop_duplicates(KEY_COLS, keep="last")

    invalid_zero_values = 0
    if spec.zero_is_missing:
        invalid_zero_mask = df[spec.metric_col].notna() & df[spec.metric_col].eq(0)
        invalid_zero_values = int(invalid_zero_mask.sum())
        df.loc[invalid_zero_mask, spec.metric_col] = np.nan

    flag_col = f"{spec.metric_col}_was_imputed"
    df[flag_col] = df[spec.metric_col].isna()
    missing_metric_before_impute = int(df[spec.metric_col].isna().sum())

    df = df.sort_values(["kode_kabupaten_kota", "tahun"]).reset_index(drop=True)
    df[spec.metric_col] = (
        df.groupby("kode_kabupaten_kota", group_keys=False)[spec.metric_col]
        .apply(lambda values: values.interpolate(method="linear", limit_area="inside"))
        .reset_index(drop=True)
    )

    df[flag_col] = df[flag_col] & df[spec.metric_col].notna()
    imputed_values = int(df[flag_col].sum())
    missing_after = int(df.isna().sum().sum())

    output_cols = DIM_COLS + ["tahun", spec.metric_col, flag_col]
    output_cols = [col for col in output_cols if col in df.columns]
    cleaned = df[output_cols].copy()

    profile = {
        "logical_name": spec.logical_name,
        "metric": spec.metric_col,
        "rows_raw": raw_rows,
        "rows_clean": len(cleaned),
        "missing_values_before": missing_before,
        "missing_values_after": missing_after,
        "missing_metric_before_impute": missing_metric_before_impute,
        "imputed_values": imputed_values,
        "invalid_zero_values": invalid_zero_values,
        "rows_dropped_missing_keys": rows_dropped_missing_keys,
        "duplicate_key_rows": duplicate_key_rows,
        "exact_duplicate_rows": exact_duplicates,
    }
    return cleaned, profile


def first_non_null(series: pd.Series) -> Any:
    values = series.dropna()
    if values.empty:
        return pd.NA
    return values.iloc[0]


def integrate_datasets(cleaned_by_metric: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    dim_frames = []
    metric_frames = []

    for spec in DATASETS:
        df = cleaned_by_metric[spec.metric_col]
        dim_frames.append(df[DIM_COLS].drop_duplicates())
        metric_cols = KEY_COLS + [spec.metric_col, f"{spec.metric_col}_was_imputed"]
        metric_frames.append(df[metric_cols].copy())

    panel = metric_frames[0]
    for frame in metric_frames[1:]:
        panel = panel.merge(frame, on=KEY_COLS, how="outer")

    dims = pd.concat(dim_frames, ignore_index=True)
    dims = (
        dims.sort_values(["kode_kabupaten_kota", "nama_kabupaten_kota"])
        .groupby("kode_kabupaten_kota", as_index=False)
        .agg(
            {
                "kode_provinsi": first_non_null,
                "nama_provinsi": first_non_null,
                "nama_kabupaten_kota": first_non_null,
            }
        )
    )

    panel = panel.merge(dims, on="kode_kabupaten_kota", how="left")
    ordered_cols = DIM_COLS + ["tahun"]
    remaining_cols = [col for col in panel.columns if col not in ordered_cols]
    panel = panel[ordered_cols + remaining_cols]
    panel = panel.sort_values(["tahun", "kode_kabupaten_kota"]).reset_index(drop=True)
    return panel


def filter_analysis_period(panel: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    if start_year > end_year:
        raise ValueError("start_year must be less than or equal to end_year.")

    filtered = panel.loc[
        panel["tahun"].between(start_year, end_year, inclusive="both")
    ].copy()
    if filtered.empty:
        raise RuntimeError(f"No rows available for analysis period {start_year}-{end_year}.")

    return filtered.sort_values(["tahun", "kode_kabupaten_kota"]).reset_index(drop=True)


def within_year_zscore(series: pd.Series) -> pd.Series:
    valid = series.notna()
    out = pd.Series(np.nan, index=series.index)

    if valid.sum() == 0:
        return out

    std = series.loc[valid].std(ddof=0)
    if pd.isna(std) or std == 0:
        out.loc[valid] = 0.0
        return out

    out.loc[valid] = (series.loc[valid] - series.loc[valid].mean()) / std
    return out


def add_features(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    out = out.sort_values(["kode_kabupaten_kota", "tahun"]).reset_index(drop=True)

    metric_cols = [spec.metric_col for spec in DATASETS]
    for metric in metric_cols:
        out[f"{metric}_yoy_change"] = out.groupby("kode_kabupaten_kota")[metric].diff()
        out[f"{metric}_yoy_pct_change"] = (
            out.groupby("kode_kabupaten_kota")[metric].pct_change(fill_method=None) * 100
        )

    poverty_metric = "persentase_penduduk_miskin"
    out["persentase_miskin_rolling_3y"] = (
        out.groupby("kode_kabupaten_kota")[poverty_metric]
        .rolling(window=3, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True)
    )

    poverty_delta = out[f"{poverty_metric}_yoy_change"]
    out["arah_tren_kemiskinan"] = np.select(
        [poverty_delta > 0.1, poverty_delta < -0.1, poverty_delta.notna()],
        ["naik", "turun", "stabil"],
        default="belum_ada_pembanding",
    )

    risk_cols: List[str] = []
    for spec in DATASETS:
        if spec.risk_direction == "context_only":
            continue
        z_col = f"{spec.metric_col}_risk_z"
        z_score = out.groupby("tahun")[spec.metric_col].transform(within_year_zscore)
        if spec.risk_direction == "low_is_risky":
            z_score = -z_score
        out[z_col] = z_score
        risk_cols.append(z_col)

    out["jumlah_komponen_skor_kerentanan"] = out[risk_cols].notna().sum(axis=1).astype(int)
    out["skor_kerentanan_sosial"] = (
        out[risk_cols]
        .mean(axis=1, skipna=True)
        .where(out["jumlah_komponen_skor_kerentanan"].eq(len(risk_cols)))
        .round(4)
    )
    out["peringkat_prioritas_intervensi"] = (
        out.groupby("tahun")["skor_kerentanan_sosial"]
        .rank(ascending=False, method="dense")
        .astype("Int64")
    )
    out["_priority_pct_rank"] = out.groupby("tahun")["skor_kerentanan_sosial"].rank(
        ascending=False,
        pct=True,
        method="min",
    )
    out["prioritas_intervensi"] = pd.cut(
        out["_priority_pct_rank"],
        bins=[0, 0.2, 0.5, 0.8, 1.0],
        labels=["sangat_tinggi", "tinggi", "sedang", "rendah"],
        include_lowest=True,
    ).astype("string")
    out = out.drop(columns=["_priority_pct_rank"])

    impute_cols = [f"{metric}_was_imputed" for metric in metric_cols if f"{metric}_was_imputed" in out.columns]
    out["jumlah_indikator_diimputasi"] = out[impute_cols].sum(axis=1).astype(int)
    out["jumlah_indikator_tersedia"] = out[metric_cols].notna().sum(axis=1).astype(int)

    return out.sort_values(["tahun", "peringkat_prioritas_intervensi", "kode_kabupaten_kota"]).reset_index(drop=True)


def validate_panel(panel: pd.DataFrame) -> None:
    duplicate_keys = int(panel.duplicated(KEY_COLS).sum())
    if duplicate_keys:
        raise RuntimeError(f"Integrated panel has duplicate kabupaten/kota-year keys: {duplicate_keys}")

    missing_keys = int(panel[KEY_COLS].isna().sum().sum())
    if missing_keys:
        raise RuntimeError(f"Integrated panel still has missing keys: {missing_keys}")

    required_metrics = [spec.metric_col for spec in DATASETS]
    missing_metric_cols = [col for col in required_metrics if col not in panel.columns]
    if missing_metric_cols:
        raise RuntimeError(f"Integrated panel missing metric columns: {missing_metric_cols}")


def feature_dictionary_rows() -> List[Dict[str, str]]:
    rows = [
        {
            "column": "kode_provinsi",
            "description": "Province code; expected value for Jawa Barat is 32.",
            "source_or_logic": "standardized dimension",
        },
        {
            "column": "nama_provinsi",
            "description": "Province name standardized to uppercase.",
            "source_or_logic": "standardized dimension",
        },
        {
            "column": "kode_kabupaten_kota",
            "description": "Kabupaten/kota code used as the main geographic join key.",
            "source_or_logic": "standardized dimension",
        },
        {
            "column": "nama_kabupaten_kota",
            "description": "Kabupaten/kota name standardized to uppercase.",
            "source_or_logic": "standardized dimension",
        },
        {
            "column": "tahun",
            "description": "Observation year.",
            "source_or_logic": "standardized time key",
        },
    ]

    for spec in DATASETS:
        rows.append(
            {
                "column": spec.metric_col,
                "description": f"{spec.metric_label} ({spec.unit_hint}).",
                "source_or_logic": spec.logical_name,
            }
        )
        rows.append(
            {
                "column": f"{spec.metric_col}_was_imputed",
                "description": "True when the original metric value was missing and filled during preprocessing.",
                "source_or_logic": "zero placeholders are treated as missing; internal gaps are filled with linear interpolation by kabupaten/kota",
            }
        )
        rows.append(
            {
                "column": f"{spec.metric_col}_yoy_change",
                "description": "Year-over-year absolute change by kabupaten/kota.",
                "source_or_logic": "feature engineering",
            }
        )
        rows.append(
            {
                "column": f"{spec.metric_col}_yoy_pct_change",
                "description": "Year-over-year percentage change by kabupaten/kota.",
                "source_or_logic": "feature engineering",
            }
        )

    rows.extend(
        [
            {
                "column": "persentase_miskin_rolling_3y",
                "description": "Three-year rolling average of poverty percentage.",
                "source_or_logic": "feature engineering",
            },
            {
                "column": "arah_tren_kemiskinan",
                "description": "naik/turun/stabil based on poverty percentage YoY movement with 0.1 point tolerance.",
                "source_or_logic": "feature engineering",
            },
            {
                "column": "skor_kerentanan_sosial",
                "description": "Composite vulnerability score; higher means more vulnerable.",
                "source_or_logic": "mean of yearly z-scores: poverty %, severity, unemployment, and inverse IPM; only populated when all components are available",
            },
            {
                "column": "jumlah_komponen_skor_kerentanan",
                "description": "Count of risk-score components available for a row.",
                "source_or_logic": "data quality feature for skor_kerentanan_sosial",
            },
            {
                "column": "peringkat_prioritas_intervensi",
                "description": "Within-year intervention priority rank; 1 is highest priority.",
                "source_or_logic": "rank of skor_kerentanan_sosial by year",
            },
            {
                "column": "prioritas_intervensi",
                "description": "Priority bucket: sangat_tinggi, tinggi, sedang, rendah.",
                "source_or_logic": "within-year percentile rank of skor_kerentanan_sosial",
            },
            {
                "column": "jumlah_indikator_diimputasi",
                "description": "Count of metric values imputed for the row.",
                "source_or_logic": "data quality feature",
            },
            {
                "column": "jumlah_indikator_tersedia",
                "description": "Count of non-null source metrics available after preprocessing.",
                "source_or_logic": "data quality feature",
            },
        ]
    )
    return rows


def markdown_table(rows: List[Dict[str, Any]], columns: List[str]) -> str:
    if not rows:
        return ""
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in rows:
        values = [str(row.get(col, "")).replace("|", "/") for col in columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def write_quality_outputs(
    profiles: List[Dict[str, Any]],
    source_infos: List[Dict[str, Any]],
    panel: pd.DataFrame,
    output_dir: Path,
    report_dir: Path,
) -> Tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    summary_path = report_dir / "data_quality_summary.csv"
    report_path = report_dir / "preprocessing_quality_report.md"

    summary = pd.DataFrame(profiles).merge(pd.DataFrame(source_infos), on=["logical_name", "metric"], how="left")
    summary.to_csv(summary_path, index=False)

    output_files = [
        str((output_dir / "panel_kemiskinan_jabar_preprocessed.csv").relative_to(PROJECT_ROOT)),
        str((output_dir / "feature_dictionary.csv").relative_to(PROJECT_ROOT)),
        str((output_dir / "preprocess_manifest.csv").relative_to(PROJECT_ROOT)),
        str(summary_path.relative_to(PROJECT_ROOT)),
    ]

    scored_years = panel.loc[panel["skor_kerentanan_sosial"].notna(), "tahun"]
    latest_year = scored_years.max() if not scored_years.empty else panel["tahun"].max()
    latest_snapshot = (
        panel.loc[panel["tahun"].eq(latest_year) & panel["skor_kerentanan_sosial"].notna()]
        .sort_values("peringkat_prioritas_intervensi")
        .head(10)
    )
    top_priority_rows = latest_snapshot[
        [
            "tahun",
            "peringkat_prioritas_intervensi",
            "nama_kabupaten_kota",
            "skor_kerentanan_sosial",
            "prioritas_intervensi",
            "persentase_penduduk_miskin",
            "indeks_keparahan_kemiskinan",
            "tingkat_pengangguran_terbuka",
            "indeks_pembangunan_manusia",
        ]
    ].to_dict("records")

    report_lines = [
        "# Preprocessing Quality Report",
        "",
        f"Generated at: {datetime.utcnow().isoformat()}Z",
        "",
        "## Scope",
        "",
        "This report covers the Scrub stage for poverty and social-vulnerability analytics in Jawa Barat.",
        "The light exploration included here is limited to data-quality profiling and output validation.",
        "",
        "## Output Files",
        "",
    ]
    report_lines.extend([f"- `{path}`" for path in output_files])
    report_lines.extend(
        [
            "",
            "## Integrated Panel",
            "",
            f"- Rows: {len(panel)}",
            f"- Kabupaten/kota count: {panel['kode_kabupaten_kota'].nunique()}",
            f"- Analysis year range: {int(panel['tahun'].min())} - {int(panel['tahun'].max())}",
            f"- Latest year with complete intervention-priority score: {int(latest_year)}",
            f"- Duplicate kabupaten/kota-year keys: {int(panel.duplicated(KEY_COLS).sum())}",
            "",
            "## Source Quality Summary",
            "",
            markdown_table(
                summary.to_dict("records"),
                [
                    "logical_name",
                    "source_mode",
                    "rows_raw",
                    "rows_clean",
                    "missing_metric_before_impute",
                    "invalid_zero_values",
                    "imputed_values",
                    "duplicate_key_rows",
                    "rows_dropped_missing_keys",
                ],
            ),
            "",
            "## Latest Scored-Year Top Priority Preview",
            "",
            markdown_table(
                top_priority_rows,
                [
                    "tahun",
                    "peringkat_prioritas_intervensi",
                    "nama_kabupaten_kota",
                    "skor_kerentanan_sosial",
                    "prioritas_intervensi",
                    "persentase_penduduk_miskin",
                    "indeks_keparahan_kemiskinan",
                    "tingkat_pengangguran_terbuka",
                    "indeks_pembangunan_manusia",
                ],
            ),
            "",
            "## Preprocessing Notes",
            "",
            "- Zero placeholders in source metrics are treated as missing because they usually represent unavailable historical records, especially for newer administrative regions.",
            "- Missing metric values are imputed only for internal gaps with linear interpolation within each kabupaten/kota; leading/trailing structural missing values remain blank.",
            "- Geographic names are standardized to uppercase to stabilize joins.",
            "- The intervention priority score excludes garis_kemiskinan from the composite because it is better treated as economic context than direct vulnerability incidence.",
            "- If `source_mode` is `openapi_fetch`, the raw CSV in `data/raw` was not statistical records and the script fetched records from the endpoint documented in the raw JSON.",
            "",
        ]
    )

    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    return summary_path, report_path


def append_manifest(output_dir: Path, panel_path: Path, source_infos: List[Dict[str, Any]], panel: pd.DataFrame) -> Path:
    manifest_path = output_dir / "preprocess_manifest.csv"
    manifest_exists = manifest_path.exists()
    source_refs = ";".join(
        info.get("records_cache_file") or info.get("source_file") or info.get("api_endpoint", "")
        for info in source_infos
    )

    with manifest_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if not manifest_exists:
            writer.writerow(
                [
                    "processed_time",
                    "output_file",
                    "row_count",
                    "kabupaten_kota_count",
                    "year_min",
                    "year_max",
                    "source_refs",
                ]
            )
        writer.writerow(
            [
                datetime.utcnow().isoformat() + "Z",
                str(panel_path.relative_to(PROJECT_ROOT)),
                len(panel),
                panel["kode_kabupaten_kota"].nunique(),
                int(panel["tahun"].min()),
                int(panel["tahun"].max()),
                source_refs,
            ]
        )
    return manifest_path


def run(args: argparse.Namespace) -> Dict[str, Path]:
    source_dir = Path(args.source_dir).resolve()
    archive_dir = Path(args.archive_dir).resolve()
    interim_dir = Path(args.interim_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    report_dir = Path(args.report_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    cleaned_by_metric: Dict[str, pd.DataFrame] = {}
    profiles: List[Dict[str, Any]] = []
    source_infos: List[Dict[str, Any]] = []

    for spec in DATASETS:
        logger.info("Loading %s", spec.logical_name)
        raw_df, source_info = load_source_dataframe(
            spec=spec,
            source_dir=source_dir,
            archive_dir=archive_dir,
            interim_dir=interim_dir,
            fetch_openapi_if_needed=args.fetch_openapi_if_needed,
            fetch_limit=args.fetch_limit,
            fetch_timeout=args.fetch_timeout,
        )
        cleaned, profile = clean_dataset(raw_df, spec)
        cleaned_by_metric[spec.metric_col] = cleaned
        profiles.append(profile)
        source_infos.append(source_info)
        logger.info("Cleaned %s rows for %s", len(cleaned), spec.logical_name)

    panel = integrate_datasets(cleaned_by_metric)
    panel = filter_analysis_period(panel, args.start_year, args.end_year)
    panel = add_features(panel)
    validate_panel(panel)

    panel_path = output_dir / "panel_kemiskinan_jabar_preprocessed.csv"
    dictionary_path = output_dir / "feature_dictionary.csv"
    panel.to_csv(panel_path, index=False)
    pd.DataFrame(feature_dictionary_rows()).to_csv(dictionary_path, index=False)
    manifest_path = append_manifest(output_dir, panel_path, source_infos, panel)
    summary_path, report_path = write_quality_outputs(profiles, source_infos, panel, output_dir, report_dir)

    logger.info("Preprocessing completed: %s", panel_path)
    return {
        "panel": panel_path,
        "dictionary": dictionary_path,
        "manifest": manifest_path,
        "summary": summary_path,
        "report": report_path,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clean, integrate, and engineer features for Jawa Barat poverty analytics."
    )
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR), help="Raw source directory.")
    parser.add_argument("--archive-dir", default=str(DEFAULT_ARCHIVE_DIR), help="Fallback archive directory.")
    parser.add_argument("--interim-dir", default=str(DEFAULT_INTERIM_DIR), help="Directory for fetched source caches.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Processed output directory.")
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR), help="Preprocessing report directory.")
    parser.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR, help="First year included in processed output.")
    parser.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR, help="Last year included in processed output.")
    parser.add_argument(
        "--fetch-openapi-if-needed",
        action="store_true",
        default=True,
        help="Fetch data records from OpenAPI docs when raw CSV/JSON only contains documentation.",
    )
    parser.add_argument(
        "--no-fetch-openapi",
        action="store_false",
        dest="fetch_openapi_if_needed",
        help="Disable OpenAPI fallback and only use local statistical records.",
    )
    parser.add_argument("--fetch-limit", type=int, default=5000, help="Rows per API request for OpenAPI fallback.")
    parser.add_argument("--fetch-timeout", type=int, default=30, help="API request timeout in seconds.")
    return parser.parse_args()


if __name__ == "__main__":
    try:
        outputs = run(parse_args())
        print("Preprocessing selesai. Output:")
        for name, path in outputs.items():
            print(f"- {name}: {path.relative_to(PROJECT_ROOT)}")
    except Exception as exc:
        logger.exception("Preprocessing failed")
        raise SystemExit(str(exc))

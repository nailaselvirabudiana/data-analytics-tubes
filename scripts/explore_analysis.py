# Explore stage analytical tables

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Dict, List

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PANEL_PATH = PROJECT_ROOT / "data" / "processed" / "panel_kemiskinan_jabar_preprocessed.csv"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "reports" / "exploration"
LOG_DIR = PROJECT_ROOT / "logs"

SCORE_COL = "skor_kerentanan_sosial"
HIGH_CORR_THRESHOLD = 0.8

# Metrics shared across stages
METRIC_COLS = [
    "garis_kemiskinan",
    "persentase_penduduk_miskin",
    "indeks_keparahan_kemiskinan",
    "indeks_pembangunan_manusia",
    "tingkat_pengangguran_terbuka",
]
METRIC_LABELS = {
    "garis_kemiskinan": "Poverty line (rupiah/capita/month)",
    "persentase_penduduk_miskin": "Poverty rate (percent)",
    "indeks_keparahan_kemiskinan": "Poverty severity index",
    "indeks_pembangunan_manusia": "Human development index",
    "tingkat_pengangguran_terbuka": "Open unemployment rate (percent)",
}


def setup_logging() -> logging.Logger:
    # Configure file and console logging
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_DIR / "explore.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return logging.getLogger("explore")


logger = setup_logging()


def load_panel(panel_path: Path) -> pd.DataFrame:
    # Load processed analytical panel
    if not panel_path.exists():
        raise FileNotFoundError(f"Processed panel not found: {panel_path}")
    return pd.read_csv(panel_path)


def latest_scored_year(panel: pd.DataFrame) -> int:
    # Latest fully scored year
    scored = panel.loc[panel[SCORE_COL].notna(), "tahun"]
    if scored.empty:
        raise RuntimeError("No scored year available in panel")
    return int(scored.max())


def cross_section(panel: pd.DataFrame, year: int) -> pd.DataFrame:
    # Single-year region snapshot for analysis
    frame = panel.loc[panel["tahun"].eq(year)].copy()
    if frame.empty:
        raise RuntimeError(f"No rows for year {year}")
    return frame.reset_index(drop=True)


def descriptive_stats(frame: pd.DataFrame) -> pd.DataFrame:
    # Summary statistics for main indicators
    cols = [col for col in METRIC_COLS + [SCORE_COL] if col in frame.columns]
    stats = frame[cols].describe().T
    stats.insert(0, "label", [METRIC_LABELS.get(col, col) for col in stats.index])
    stats.index.name = "indicator"
    return stats.reset_index()


def correlation_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    # Pearson correlation across main indicators
    corr = frame[METRIC_COLS].corr(method="pearson")
    corr.index.name = "indicator"
    return corr.reset_index()


def high_correlation_pairs(frame: pd.DataFrame, threshold: float = HIGH_CORR_THRESHOLD) -> List[Dict[str, object]]:
    # Flag near-collinear indicator pairs
    corr = frame[METRIC_COLS].corr(method="pearson")
    pairs: List[Dict[str, object]] = []
    for i, left in enumerate(METRIC_COLS):
        for right in METRIC_COLS[i + 1 :]:
            value = corr.loc[left, right]
            if pd.notna(value) and abs(value) >= threshold:
                pairs.append({"indicator_a": left, "indicator_b": right, "pearson_r": round(float(value), 4)})
    return pairs


def poverty_trend_by_year(panel: pd.DataFrame) -> pd.DataFrame:
    # Province-wide yearly mean of indicators
    trend = panel.groupby("tahun")[METRIC_COLS].mean().round(4)
    trend["regions_with_score"] = panel.loc[panel[SCORE_COL].notna()].groupby("tahun").size()
    return trend.reset_index()


def region_change_summary(panel: pd.DataFrame) -> pd.DataFrame:
    # Earliest-to-latest change per region
    metric = "persentase_penduduk_miskin"
    rows: List[Dict[str, object]] = []
    for code, group in panel.groupby("kode_kabupaten_kota"):
        valid = group.loc[group[metric].notna()].sort_values("tahun")
        if valid.empty:
            continue
        first, last = valid.iloc[0], valid.iloc[-1]
        rows.append(
            {
                "kode_kabupaten_kota": code,
                "nama_kabupaten_kota": last["nama_kabupaten_kota"],
                "tahun_awal": int(first["tahun"]),
                "tahun_akhir": int(last["tahun"]),
                "persentase_miskin_awal": round(float(first[metric]), 4),
                "persentase_miskin_akhir": round(float(last[metric]), 4),
                "perubahan_poin": round(float(last[metric] - first[metric]), 4),
            }
        )
    return pd.DataFrame(rows).sort_values("perubahan_poin").reset_index(drop=True)


def kota_vs_kabupaten(frame: pd.DataFrame) -> pd.DataFrame:
    # Crude administrative-type comparison only
    out = frame.copy()
    out["tipe_administratif"] = out["nama_kabupaten_kota"].str.startswith("KOTA").map(
        {True: "kota", False: "kabupaten"}
    )
    grouped = out.groupby("tipe_administratif")[METRIC_COLS].mean().round(4)
    grouped["jumlah_wilayah"] = out.groupby("tipe_administratif").size()
    return grouped.reset_index()


def top_bottom_regions(frame: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    # Most and least vulnerable regions
    cols = ["nama_kabupaten_kota", SCORE_COL, "persentase_penduduk_miskin", "indeks_pembangunan_manusia"]
    scored = frame.loc[frame[SCORE_COL].notna(), cols].copy()
    ranked = scored.sort_values(SCORE_COL, ascending=False).reset_index(drop=True)
    most = ranked.head(n).assign(kelompok="paling_rentan")
    least = ranked.tail(n).assign(kelompok="paling_tidak_rentan")
    return pd.concat([most, least], ignore_index=True)


def run(args: argparse.Namespace) -> Dict[str, Path]:
    # Execute exploration and write outputs
    panel_path = Path(args.panel_path).resolve()
    report_dir = Path(args.report_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    panel = load_panel(panel_path)
    year = args.year if args.year is not None else latest_scored_year(panel)
    frame = cross_section(panel, year)

    outputs: Dict[str, Path] = {
        "descriptive": report_dir / "descriptive_stats_latest.csv",
        "correlation": report_dir / "correlation_matrix_latest.csv",
        "trend": report_dir / "poverty_trend_by_year.csv",
        "change": report_dir / "region_change_summary.csv",
        "admin": report_dir / "kota_vs_kabupaten_latest.csv",
        "extremes": report_dir / "top_bottom_regions_latest.csv",
    }

    descriptive_stats(frame).to_csv(outputs["descriptive"], index=False)
    correlation_matrix(frame).to_csv(outputs["correlation"], index=False)
    poverty_trend_by_year(panel).to_csv(outputs["trend"], index=False)
    region_change_summary(panel).to_csv(outputs["change"], index=False)
    kota_vs_kabupaten(frame).to_csv(outputs["admin"], index=False)
    top_bottom_regions(frame).to_csv(outputs["extremes"], index=False)

    logger.info("Exploration completed for year %s", year)
    return outputs


def parse_args() -> argparse.Namespace:
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Exploratory analysis for Jawa Barat poverty panel")
    parser.add_argument("--panel-path", default=str(DEFAULT_PANEL_PATH), help="Processed panel CSV path")
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR), help="Exploration report directory")
    parser.add_argument("--year", type=int, default=None, help="Snapshot year; default is latest scored year")
    return parser.parse_args()


if __name__ == "__main__":
    results = run(parse_args())
    print("Exploration outputs:")
    for name, path in results.items():
        print(f"- {name}: {path.relative_to(PROJECT_ROOT)}")

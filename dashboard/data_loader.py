from pathlib import Path

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]

FILES = {
    "panel": "data/processed/panel_kemiskinan_jabar_preprocessed.csv",
    "clusters": "data/processed/region_clusters_2024.csv",
    "feature_dictionary": "data/processed/feature_dictionary.csv",
    "trend": "reports/exploration/poverty_trend_by_year.csv",
    "changes": "reports/exploration/region_change_summary.csv",
    "top_bottom": "reports/exploration/top_bottom_regions_latest.csv",
    "admin_comparison": "reports/exploration/kota_vs_kabupaten_latest.csv",
    "correlation": "reports/exploration/correlation_matrix_latest.csv",
    "cluster_profiles": "reports/modeling/cluster_profiles.csv",
    "feature_importance": "reports/modeling/feature_importance.csv",
    "urban_rural": "reports/modeling/urban_rural_comparison.csv",
    "priority_matrix": "reports/modeling/priority_matrix.csv",
    "model_selection": "reports/modeling/model_selection.csv",
    "validation": "reports/preprocessing/processed_validation_checks.csv",
    "coverage": "reports/preprocessing/metric_coverage_by_year.csv",
    "quality": "reports/preprocessing/data_quality_summary.csv",
}


@st.cache_data(show_spinner=False)
def load_csv(key: str) -> pd.DataFrame:
    path = ROOT / FILES[key]
    if not path.exists():
        raise FileNotFoundError(
            f"File `{path.relative_to(ROOT)}` belum tersedia. Jalankan pipeline analisis terlebih dahulu."
        )
    return pd.read_csv(path)


def load_many(*keys: str) -> dict[str, pd.DataFrame]:
    return {key: load_csv(key) for key in keys}


def latest_year(frame: pd.DataFrame, year_column: str = "tahun") -> int:
    return int(frame[year_column].dropna().max())


def region_options(panel: pd.DataFrame) -> list[str]:
    return sorted(panel["nama_kabupaten_kota"].dropna().unique().tolist())


def format_region_name(name: str) -> str:
    return name.title().replace("Kabupaten", "Kab.").replace("Kota", "Kota")

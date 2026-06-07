# Model stage region clustering

from __future__ import annotations

import argparse
import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.preprocessing import StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PANEL_PATH = PROJECT_ROOT / "data" / "processed" / "panel_kemiskinan_jabar_preprocessed.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "reports" / "modeling"
LOG_DIR = PROJECT_ROOT / "logs"

DIM_COLS = ["kode_provinsi", "nama_provinsi", "kode_kabupaten_kota", "nama_kabupaten_kota"]
SCORE_COL = "skor_kerentanan_sosial"
# Context only, collinear with HDI
CONTEXT_COL = "garis_kemiskinan"
TREND_METRIC = "persentase_penduduk_miskin"
# Trailing pre-pandemic baseline window
TREND_WINDOW = 6
TREND_SLOPE_TOLERANCE = 0.05
TERTILE_LOW = 0.33
TERTILE_HIGH = 0.67

# Standardized clustering features
CLUSTER_FEATURES = [
    "persentase_penduduk_miskin",
    "indeks_keparahan_kemiskinan",
    "indeks_pembangunan_manusia",
    "tingkat_pengangguran_terbuka",
]
FEATURE_LABELS = {
    "persentase_penduduk_miskin": "Poverty rate",
    "indeks_keparahan_kemiskinan": "Poverty severity index",
    "indeks_pembangunan_manusia": "Human development index",
    "tingkat_pengangguran_terbuka": "Open unemployment rate",
}
DEFAULT_K = 3
DEFAULT_K_MAX = 6
RANDOM_STATE = 42

# Background face-validity expectation
EXPECTED_LOW_VULNERABILITY = ["KOTA BEKASI", "KOTA DEPOK", "KOTA BANDUNG", "KABUPATEN BEKASI"]
EXPECTED_HIGH_VULNERABILITY = ["KABUPATEN GARUT", "KABUPATEN CIANJUR", "KABUPATEN TASIKMALAYA", "KABUPATEN KUNINGAN"]


def setup_logging() -> logging.Logger:
    # Configure file and console logging
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_DIR / "model.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return logging.getLogger("model")


logger = setup_logging()


def load_panel(panel_path: Path) -> pd.DataFrame:
    # Load processed analytical panel
    if not panel_path.exists():
        raise FileNotFoundError(f"Processed panel not found: {panel_path}")
    return pd.read_csv(panel_path)


def resolve_model_year(panel: pd.DataFrame, requested: Optional[int]) -> int:
    # Pick snapshot year for clustering
    if requested is not None:
        return requested
    scored = panel.loc[panel[SCORE_COL].notna(), "tahun"]
    if scored.empty:
        raise RuntimeError("No scored year available for modeling")
    return int(scored.max())


def trend_label(slope: float) -> str:
    # Map poverty slope to direction
    if pd.isna(slope):
        return "tidak_diketahui"
    if slope > TREND_SLOPE_TOLERANCE:
        return "memburuk"
    if slope < -TREND_SLOPE_TOLERANCE:
        return "membaik"
    return "stabil"


def poverty_slope(panel: pd.DataFrame, year: int, window: int) -> pd.DataFrame:
    # Poverty slope over window
    years = list(range(year - window + 1, year + 1))
    span = panel.loc[panel["tahun"].isin(years), ["kode_kabupaten_kota", "tahun", TREND_METRIC]]
    rows: List[Dict[str, object]] = []
    for code, group in span.groupby("kode_kabupaten_kota"):
        valid = group.dropna(subset=[TREND_METRIC])
        slope = (
            float(np.polyfit(valid["tahun"], valid[TREND_METRIC], 1)[0]) if len(valid) >= 3 else np.nan
        )
        rows.append({"kode_kabupaten_kota": code, "tren_slope_poin_per_tahun": round(slope, 4)})
    return pd.DataFrame(rows)


def build_model_frame(panel: pd.DataFrame, year: int, trend_window: int) -> pd.DataFrame:
    # Build region snapshot with trend
    snapshot = panel.loc[panel["tahun"].eq(year)].copy()
    if snapshot.empty:
        raise RuntimeError(f"No rows for snapshot year {year}")

    usable = snapshot.dropna(subset=CLUSTER_FEATURES).copy()
    dropped = len(snapshot) - len(usable)
    if dropped:
        logger.warning("Dropped %s regions missing clustering features", dropped)
    if len(usable) < DEFAULT_K:
        raise RuntimeError("Too few complete regions for clustering")

    slopes = poverty_slope(panel, year, trend_window)
    usable = usable.merge(slopes, on="kode_kabupaten_kota", how="left")
    usable["tren_kemiskinan"] = usable["tren_slope_poin_per_tahun"].map(trend_label)
    usable["tipe_administratif"] = usable["nama_kabupaten_kota"].str.startswith("KOTA").map(
        {True: "kota", False: "kabupaten"}
    )
    return usable.reset_index(drop=True)


def select_k(scaled: np.ndarray, k_max: int) -> pd.DataFrame:
    # Score candidate cluster counts
    rows: List[Dict[str, object]] = []
    upper = min(k_max, len(scaled) - 1)
    for k in range(2, upper + 1):
        model = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE)
        labels = model.fit_predict(scaled)
        rows.append(
            {
                "k": k,
                "silhouette": round(float(silhouette_score(scaled, labels)), 4),
                "calinski_harabasz": round(float(calinski_harabasz_score(scaled, labels)), 4),
                "davies_bouldin": round(float(davies_bouldin_score(scaled, labels)), 4),
                "inertia": round(float(model.inertia_), 4),
            }
        )
    return pd.DataFrame(rows)


def order_labels_by_vulnerability(frame: pd.DataFrame, raw_labels: np.ndarray) -> np.ndarray:
    # Relabel clusters by descending vulnerability
    temp = frame.assign(_raw=raw_labels)
    order = (
        temp.groupby("_raw")[SCORE_COL]
        .mean()
        .sort_values(ascending=False)
        .index.tolist()
    )
    remap = {raw: new for new, raw in enumerate(order)}
    return np.array([remap[label] for label in raw_labels])


def tier_name(cluster_id: int, k: int) -> str:
    # Name vulnerability tier by rank
    if k == 3:
        return ["kerentanan_tinggi", "kerentanan_menengah", "kerentanan_rendah"][cluster_id]
    if cluster_id == 0:
        return "kerentanan_tertinggi"
    if cluster_id == k - 1:
        return "kerentanan_terendah"
    return f"kerentanan_menengah_{cluster_id}"


def economic_profile(cluster_means: pd.Series, thresholds: Dict[str, float]) -> str:
    # Classify archetype from indicator tertiles
    high_dev = cluster_means["indeks_pembangunan_manusia"] >= thresholds["ipm_high"]
    low_dev = cluster_means["indeks_pembangunan_manusia"] <= thresholds["ipm_low"]
    low_poverty = cluster_means["persentase_penduduk_miskin"] <= thresholds["poverty_low"]
    high_poverty = cluster_means["persentase_penduduk_miskin"] >= thresholds["poverty_high"]
    if high_dev and low_poverty:
        return "urban_industri"
    if low_dev and high_poverty:
        return "rural_agraris"
    return "campuran"


def profile_clusters(frame: pd.DataFrame, k: int) -> Tuple[pd.DataFrame, Dict[int, str], Dict[int, str]]:
    # Summarize each cluster profile
    thresholds = {
        "ipm_low": frame["indeks_pembangunan_manusia"].quantile(TERTILE_LOW),
        "ipm_high": frame["indeks_pembangunan_manusia"].quantile(TERTILE_HIGH),
        "poverty_low": frame["persentase_penduduk_miskin"].quantile(TERTILE_LOW),
        "poverty_high": frame["persentase_penduduk_miskin"].quantile(TERTILE_HIGH),
    }
    profile_cols = CLUSTER_FEATURES + [CONTEXT_COL, SCORE_COL]

    rows: List[Dict[str, object]] = []
    tier_map: Dict[int, str] = {}
    profile_map: Dict[int, str] = {}
    for cluster_id, group in frame.groupby("cluster_id"):
        means = group[profile_cols].mean()
        tier = tier_name(int(cluster_id), k)
        profile = economic_profile(means, thresholds)
        tier_map[int(cluster_id)] = tier
        profile_map[int(cluster_id)] = profile
        row: Dict[str, object] = {
            "cluster_id": int(cluster_id),
            "cluster_vulnerability_tier": tier,
            "profil_ekonomi": profile,
            "jumlah_wilayah": int(len(group)),
            "jumlah_kota": int(group["tipe_administratif"].eq("kota").sum()),
            "jumlah_kabupaten": int(group["tipe_administratif"].eq("kabupaten").sum()),
        }
        for col in profile_cols:
            row[f"mean_{col}"] = round(float(means[col]), 4)
        row["anggota"] = "; ".join(sorted(group["nama_kabupaten_kota"]))
        rows.append(row)
    return pd.DataFrame(rows).sort_values("cluster_id").reset_index(drop=True), tier_map, profile_map


def feature_importance(frame: pd.DataFrame, scaled_df: pd.DataFrame) -> pd.DataFrame:
    # Rank cluster-separating features
    labels = frame["cluster_id"].to_numpy()
    rows: List[Dict[str, object]] = []
    for feature in CLUSTER_FEATURES:
        values = scaled_df[feature].to_numpy()
        grand_mean = values.mean()
        ss_total = float(((values - grand_mean) ** 2).sum())
        ss_between = 0.0
        groups: List[np.ndarray] = []
        for cluster_id in np.unique(labels):
            member = values[labels == cluster_id]
            groups.append(member)
            ss_between += len(member) * (member.mean() - grand_mean) ** 2
        eta_squared = ss_between / ss_total if ss_total > 0 else 0.0
        f_stat, p_value = scipy_stats.f_oneway(*groups)
        rows.append(
            {
                "feature": feature,
                "label": FEATURE_LABELS[feature],
                "eta_squared": round(float(eta_squared), 4),
                "anova_f": round(float(f_stat), 4),
                "anova_p": round(float(p_value), 6),
            }
        )
    return pd.DataFrame(rows).sort_values("eta_squared", ascending=False).reset_index(drop=True)


def cohens_d(group_a: np.ndarray, group_b: np.ndarray) -> float:
    # Standardized mean difference between groups
    n_a, n_b = len(group_a), len(group_b)
    if n_a < 2 or n_b < 2:
        return float("nan")
    var_a, var_b = group_a.var(ddof=1), group_b.var(ddof=1)
    pooled = np.sqrt(((n_a - 1) * var_a + (n_b - 1) * var_b) / (n_a + n_b - 2))
    if pooled == 0:
        return 0.0
    return float((group_a.mean() - group_b.mean()) / pooled)


def urban_rural_comparison(frame: pd.DataFrame) -> pd.DataFrame:
    # Compare urban-industri versus rural-agraris archetypes
    urban = frame.loc[frame["profil_ekonomi"].eq("urban_industri")]
    rural = frame.loc[frame["profil_ekonomi"].eq("rural_agraris")]
    if urban.empty or rural.empty:
        logger.warning("Urban or rural archetype empty; comparison limited")

    rows: List[Dict[str, object]] = []
    for feature in CLUSTER_FEATURES + [CONTEXT_COL]:
        a = urban[feature].dropna().to_numpy()
        b = rural[feature].dropna().to_numpy()
        row: Dict[str, object] = {
            "feature": feature,
            "label": FEATURE_LABELS.get(feature, "Poverty line"),
            "mean_urban_industri": round(float(a.mean()), 4) if len(a) else None,
            "mean_rural_agraris": round(float(b.mean()), 4) if len(b) else None,
            "cohens_d": round(cohens_d(a, b), 4) if len(a) and len(b) else None,
        }
        if len(a) >= 2 and len(b) >= 2:
            _, p_value = scipy_stats.ttest_ind(a, b, equal_var=False)
            row["welch_p"] = round(float(p_value), 6)
        else:
            row["welch_p"] = None
        rows.append(row)
    frame_out = pd.DataFrame(rows)
    frame_out["abs_d"] = frame_out["cohens_d"].abs()
    return frame_out.sort_values("abs_d", ascending=False, na_position="last").drop(columns="abs_d").reset_index(
        drop=True
    )


PRIORITY_ACTION = {
    ("tinggi", "memburuk"): "prioritas_segera",
    ("tinggi", "stabil"): "intervensi_intensif",
    ("tinggi", "membaik"): "intervensi_intensif",
    ("tinggi", "tidak_diketahui"): "intervensi_intensif",
    ("sedang", "memburuk"): "peringatan_dini",
    ("sedang", "stabil"): "pemantauan",
    ("sedang", "membaik"): "pemantauan",
    ("sedang", "tidak_diketahui"): "pemantauan",
    ("rendah", "memburuk"): "pantau",
    ("rendah", "stabil"): "rutin",
    ("rendah", "membaik"): "rutin",
    ("rendah", "tidak_diketahui"): "rutin",
}


def assign_priority(frame: pd.DataFrame) -> pd.DataFrame:
    # Add level and priority
    out = frame.copy()
    out["level_kerentanan"] = pd.qcut(
        out[SCORE_COL], q=3, labels=["rendah", "sedang", "tinggi"]
    ).astype("string")
    out["prioritas_aksi"] = [
        PRIORITY_ACTION.get((level, trend), "rutin")
        for level, trend in zip(out["level_kerentanan"], out["tren_kemiskinan"])
    ]
    return out


def build_priority_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    # Cross vulnerability level by trend
    level_order = ["tinggi", "sedang", "rendah"]
    trend_order = ["memburuk", "stabil", "membaik", "tidak_diketahui"]
    rows: List[Dict[str, object]] = []
    for level in level_order:
        for trend in trend_order:
            cell = frame.loc[frame["level_kerentanan"].eq(level) & frame["tren_kemiskinan"].eq(trend)]
            if cell.empty:
                continue
            dominant_cluster = int(cell["cluster_id"].mode().iloc[0])
            rows.append(
                {
                    "level_kerentanan": level,
                    "tren_kemiskinan": trend,
                    "prioritas_aksi": PRIORITY_ACTION.get((level, trend), "rutin"),
                    "jumlah_wilayah": int(len(cell)),
                    "dominant_cluster_id": dominant_cluster,
                    "wilayah": "; ".join(sorted(cell["nama_kabupaten_kota"])),
                }
            )
    return pd.DataFrame(rows)


def face_validity(frame: pd.DataFrame) -> Dict[str, object]:
    # Check clusters against background expectation
    high_tier = frame.loc[frame["cluster_id"].eq(0), "nama_kabupaten_kota"].tolist()
    low_tier_id = int(frame["cluster_id"].max())
    low_tier = frame.loc[frame["cluster_id"].eq(low_tier_id), "nama_kabupaten_kota"].tolist()
    expected_high_hit = [name for name in EXPECTED_HIGH_VULNERABILITY if name in high_tier]
    expected_low_hit = [name for name in EXPECTED_LOW_VULNERABILITY if name in low_tier]
    expected_high_miss = [name for name in EXPECTED_HIGH_VULNERABILITY if name not in high_tier]
    passed = len(expected_high_hit) >= 2 and len(expected_low_hit) >= 2
    return {
        "passed": passed,
        "expected_high_in_top_tier": expected_high_hit,
        "expected_high_outside_top_tier": expected_high_miss,
        "expected_low_in_bottom_tier": expected_low_hit,
    }


def append_manifest(output_dir: Path, region_path: Path, year: int, k: int, silhouette: float, ari: float, n_regions: int) -> Path:
    # Log run to model manifest
    manifest_path = output_dir / "cluster_model_manifest.csv"
    exists = manifest_path.exists()
    with manifest_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if not exists:
            writer.writerow(
                ["model_time", "output_file", "snapshot_year", "k", "silhouette", "kmeans_ward_ari", "region_count"]
            )
        writer.writerow(
            [
                datetime.now(tz=None).isoformat(),
                str(region_path.relative_to(PROJECT_ROOT)),
                year,
                k,
                round(silhouette, 4),
                round(ari, 4),
                n_regions,
            ]
        )
    return manifest_path


def run(args: argparse.Namespace) -> Dict[str, Path]:
    # Execute pipeline, write outputs
    panel_path = Path(args.panel_path).resolve()
    output_dir = Path(args.output_dir).resolve()
    report_dir = Path(args.report_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    panel = load_panel(panel_path)
    year = resolve_model_year(panel, args.year)
    frame = build_model_frame(panel, year, args.trend_window)
    logger.info("Modeling %s regions for year %s", len(frame), year)

    scaler = StandardScaler()
    scaled = scaler.fit_transform(frame[CLUSTER_FEATURES])
    scaled_df = pd.DataFrame(scaled, columns=CLUSTER_FEATURES, index=frame.index)

    selection = select_k(scaled, args.k_max)
    k = args.k if args.k is not None else int(selection.sort_values("silhouette", ascending=False).iloc[0]["k"])

    kmeans = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE)
    raw_labels = kmeans.fit_predict(scaled)
    ordered = order_labels_by_vulnerability(frame, raw_labels)
    frame["cluster_id"] = ordered

    ward_labels = AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(scaled)
    ari = float(adjusted_rand_score(raw_labels, ward_labels))
    silhouette = float(silhouette_score(scaled, raw_labels))

    components = PCA(n_components=2, random_state=RANDOM_STATE).fit_transform(scaled)
    frame["pc1"] = components[:, 0].round(4)
    frame["pc2"] = components[:, 1].round(4)

    profiles, tier_map, profile_map = profile_clusters(frame, k)
    frame["cluster_vulnerability_tier"] = frame["cluster_id"].map(tier_map)
    frame["profil_ekonomi"] = frame["cluster_id"].map(profile_map)

    importance = feature_importance(frame, scaled_df)
    comparison = urban_rural_comparison(frame)
    frame = assign_priority(frame)
    matrix = build_priority_matrix(frame)
    validity = face_validity(frame)
    if not validity["passed"]:
        logger.warning("Face-validity check needs review: %s", validity)

    region_cols = (
        DIM_COLS
        + ["tahun"]
        + CLUSTER_FEATURES
        + [CONTEXT_COL, SCORE_COL]
        + [
            "cluster_id",
            "cluster_vulnerability_tier",
            "profil_ekonomi",
            "tipe_administratif",
            "pc1",
            "pc2",
            "tren_slope_poin_per_tahun",
            "tren_kemiskinan",
            "level_kerentanan",
            "prioritas_aksi",
        ]
    )
    region_table = frame[region_cols].sort_values(["cluster_id", SCORE_COL], ascending=[True, False]).reset_index(
        drop=True
    )

    outputs: Dict[str, Path] = {
        "regions": output_dir / f"region_clusters_{year}.csv",
        "selection": report_dir / "model_selection.csv",
        "profiles": report_dir / "cluster_profiles.csv",
        "importance": report_dir / "feature_importance.csv",
        "comparison": report_dir / "urban_rural_comparison.csv",
        "matrix": report_dir / "priority_matrix.csv",
    }

    region_table.to_csv(outputs["regions"], index=False)
    selection.to_csv(outputs["selection"], index=False)
    profiles.to_csv(outputs["profiles"], index=False)
    importance.to_csv(outputs["importance"], index=False)
    comparison.to_csv(outputs["comparison"], index=False)
    matrix.to_csv(outputs["matrix"], index=False)
    outputs["manifest"] = append_manifest(output_dir, outputs["regions"], year, k, silhouette, ari, len(region_table))

    logger.info("Modeling completed: k=%s silhouette=%.4f ari=%.4f", k, silhouette, ari)
    return outputs


def parse_args() -> argparse.Namespace:
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Cluster Jawa Barat regions by poverty and vulnerability")
    parser.add_argument("--panel-path", default=str(DEFAULT_PANEL_PATH), help="Processed panel CSV path")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Processed output directory")
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR), help="Modeling report directory")
    parser.add_argument("--year", type=int, default=None, help="Snapshot year; default is latest scored year")
    parser.add_argument("--k", type=int, default=DEFAULT_K, help="Cluster count; pass 0 to auto-select by silhouette")
    parser.add_argument("--k-max", type=int, default=DEFAULT_K_MAX, help="Maximum k evaluated during selection")
    parser.add_argument("--trend-window", type=int, default=TREND_WINDOW, help="Trailing years for the poverty trend slope")
    return parser.parse_args()


if __name__ == "__main__":
    parsed = parse_args()
    if parsed.k == 0:
        parsed.k = None
    results = run(parsed)
    print("Modeling outputs:")
    for name, path in results.items():
        print(f"- {name}: {path.relative_to(PROJECT_ROOT)}")

import streamlit as st

from dashboard.charts import METRIC_LABELS, poverty_ipm_scatter, province_trend
from dashboard.data_loader import load_many


def _delta(frame, metric: str) -> float:
    return float(frame.iloc[-1][metric] - frame.iloc[-2][metric])


def render() -> None:
    st.title("Ringkasan Kemiskinan Jawa Barat")
    st.caption("Indikator utama kabupaten/kota, tren terkini, dan wilayah prioritas intervensi.")

    data = load_many("trend", "clusters", "priority_matrix")
    trend = data["trend"].sort_values("tahun")
    clusters = data["clusters"]
    latest = trend.iloc[-1]
    year = int(latest["tahun"])

    immediate = int((clusters["prioritas_aksi"] == "prioritas_segera").sum())
    columns = st.columns(5)
    cards = [
        ("Penduduk miskin", latest["persentase_penduduk_miskin"], _delta(trend, "persentase_penduduk_miskin"), "{:.2f}%"),
        ("Indeks keparahan", latest["indeks_keparahan_kemiskinan"], _delta(trend, "indeks_keparahan_kemiskinan"), "{:.3f}"),
        ("IPM", latest["indeks_pembangunan_manusia"], _delta(trend, "indeks_pembangunan_manusia"), "{:.2f}"),
        ("Pengangguran terbuka", latest["tingkat_pengangguran_terbuka"], _delta(trend, "tingkat_pengangguran_terbuka"), "{:.2f}%"),
    ]
    for index, (column, (label, value, delta, pattern)) in enumerate(zip(columns[:4], cards)):
        column.metric(
            label,
            pattern.format(value),
            pattern.format(delta),
            delta_color="normal" if index == 2 else "inverse",
        )
    columns[4].metric("Prioritas segera", f"{immediate} wilayah")

    st.info(
        f"Snapshot terbaru adalah **{year}** dan mencakup **{len(clusters)} kabupaten/kota**. "
        "Data tingkat desa tidak tersedia. Delta pada kartu membandingkan rata-rata "
        "dengan tahun sebelumnya."
    )

    left, right = st.columns([1.35, 1])
    with left:
        metric = st.selectbox(
            "Indikator tren",
            list(METRIC_LABELS)[:5],
            format_func=METRIC_LABELS.get,
            key="overview_metric",
        )
        st.plotly_chart(province_trend(trend, metric), width="stretch")
    with right:
        counts = (
            clusters["cluster_vulnerability_tier"]
            .value_counts()
            .rename_axis("Cluster")
            .reset_index(name="Jumlah wilayah")
        )
        st.subheader("Komposisi Cluster")
        st.dataframe(counts, hide_index=True, width="stretch")
        st.subheader("Wilayah Prioritas Segera")
        urgent = clusters.loc[
            clusters["prioritas_aksi"] == "prioritas_segera",
            ["nama_kabupaten_kota", "skor_kerentanan_sosial", "tren_kemiskinan"],
        ].sort_values("skor_kerentanan_sosial", ascending=False)
        st.dataframe(urgent, hide_index=True, width="stretch")

    st.plotly_chart(poverty_ipm_scatter(clusters), width="stretch")

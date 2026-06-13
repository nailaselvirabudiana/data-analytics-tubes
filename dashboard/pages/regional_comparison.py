import streamlit as st

from dashboard.charts import correlation_heatmap, poverty_ipm_scatter, vulnerability_ranking
from dashboard.data_loader import load_many


def render() -> None:
    st.title("Perbandingan Wilayah")
    st.caption("Bandingkan posisi kabupaten/kota berdasarkan indikator terbaru.")

    data = load_many("clusters", "top_bottom", "admin_comparison", "correlation")
    clusters = data["clusters"]

    st.plotly_chart(poverty_ipm_scatter(clusters), width="stretch")

    with st.container(border=True):
        st.plotly_chart(vulnerability_ranking(data["top_bottom"]), width="stretch")

    with st.container(border=True):
        st.subheader("Kabupaten vs Kota")
        comparison = data["admin_comparison"].rename(
            columns={
                "tipe_administratif": "Tipe",
                "garis_kemiskinan": "Garis Kemiskinan",
                "persentase_penduduk_miskin": "Kemiskinan (%)",
                "indeks_keparahan_kemiskinan": "Keparahan",
                "indeks_pembangunan_manusia": "IPM",
                "tingkat_pengangguran_terbuka": "Pengangguran (%)",
                "jumlah_wilayah": "Jumlah wilayah",
            }
        )
        st.dataframe(
            comparison,
            hide_index=True,
            width="stretch",
            column_config={
                "Garis Kemiskinan": st.column_config.NumberColumn(
                    "Garis Kemiskinan", format="Rp %,.0f"
                ),
                "Kemiskinan (%)": st.column_config.NumberColumn("Kemiskinan (%)", format="%.2f"),
                "Keparahan": st.column_config.NumberColumn("Keparahan", format="%.3f"),
                "IPM": st.column_config.NumberColumn("IPM", format="%.2f"),
                "Pengangguran (%)": st.column_config.NumberColumn(
                    "Pengangguran (%)", format="%.2f"
                ),
            },
        )

    with st.container(border=True):
        st.plotly_chart(correlation_heatmap(data["correlation"]), width="stretch")
        st.caption("Korelasi menunjukkan hubungan statistik, bukan sebab-akibat.")

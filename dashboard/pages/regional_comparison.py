import streamlit as st

from dashboard.charts import poverty_ipm_scatter, vulnerability_ranking
from dashboard.data_loader import load_many


def render() -> None:
    st.title("Perbandingan Wilayah")
    st.caption("Bandingkan posisi kabupaten/kota berdasarkan indikator terbaru.")

    data = load_many("clusters", "top_bottom", "admin_comparison", "correlation")
    clusters = data["clusters"]

    st.plotly_chart(poverty_ipm_scatter(clusters), width="stretch")

    left, right = st.columns([1.3, 1])
    with left:
        st.plotly_chart(vulnerability_ranking(data["top_bottom"]), width="stretch")
    with right:
        st.subheader("Kabupaten vs Kota")
        comparison = data["admin_comparison"].rename(
            columns={
                "tipe_administratif": "Tipe",
                "persentase_penduduk_miskin": "Kemiskinan (%)",
                "indeks_keparahan_kemiskinan": "Keparahan",
                "indeks_pembangunan_manusia": "IPM",
                "tingkat_pengangguran_terbuka": "Pengangguran (%)",
                "jumlah_wilayah": "Jumlah wilayah",
            }
        )
        st.dataframe(comparison, hide_index=True, width="stretch")
        st.subheader("Korelasi Indikator")
        st.dataframe(data["correlation"].round(2), hide_index=True, width="stretch")
        st.caption("Korelasi menunjukkan hubungan statistik, bukan sebab-akibat.")

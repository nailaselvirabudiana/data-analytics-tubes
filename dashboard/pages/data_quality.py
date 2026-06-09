import streamlit as st

from dashboard.charts import coverage_heatmap
from dashboard.data_loader import load_many


def render() -> None:
    st.title("Kualitas Data")
    st.caption("Transparansi cakupan, validasi, nilai kosong, dan imputasi sumber data.")

    data = load_many("panel", "validation", "coverage", "quality")
    panel = data["panel"]
    validation = data["validation"]
    quality = data["quality"]

    passed = int((validation["status"] == "PASS").sum())
    total_imputed = int(panel["jumlah_indikator_diimputasi"].sum())
    columns = st.columns(4)
    columns[0].metric("Jumlah observasi", f"{len(panel):,}")
    columns[1].metric("Wilayah", panel["kode_kabupaten_kota"].nunique())
    columns[2].metric("Periode", f"{panel['tahun'].min()}-{panel['tahun'].max()}")
    columns[3].metric("Pemeriksaan lulus", f"{passed}/{len(validation)}")

    if total_imputed:
        st.warning(f"Terdapat {total_imputed} nilai hasil imputasi pada panel analisis.")
    else:
        st.success("Tidak ada nilai hasil imputasi pada panel analisis saat ini.")

    st.plotly_chart(coverage_heatmap(data["coverage"]), width="stretch")

    left, right = st.columns(2)
    with left:
        st.subheader("Hasil Validasi")
        st.dataframe(validation, hide_index=True, width="stretch")
    with right:
        st.subheader("Ringkasan Sumber")
        source_summary = quality[
            [
                "logical_name",
                "rows_clean",
                "missing_metric_before_impute",
                "imputed_values",
                "invalid_zero_values",
                "duplicate_key_rows",
            ]
        ]
        st.dataframe(source_summary, hide_index=True, width="stretch")

    st.info(
        "Nilai kosong tidak otomatis berarti kesalahan. Beberapa indikator memang tidak tersedia "
        "untuk seluruh tahun. Dashboard mempertahankan kondisi tersebut agar pengguna mengetahui "
        "batas cakupan data."
    )

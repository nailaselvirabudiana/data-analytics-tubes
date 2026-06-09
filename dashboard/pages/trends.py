import streamlit as st

from dashboard.charts import METRIC_LABELS, change_ranking, regional_trend
from dashboard.data_loader import load_many, region_options


def render() -> None:
    st.title("Tren Indikator")
    st.caption("Eksplorasi perubahan indikator sosial-ekonomi selama 2010-2024.")

    data = load_many("panel", "changes")
    panel = data["panel"]
    metric = st.selectbox(
        "Pilih indikator",
        list(METRIC_LABELS)[:5],
        format_func=METRIC_LABELS.get,
        key="trend_metric",
    )
    default_regions = [
        "KABUPATEN INDRAMAYU",
        "KABUPATEN KUNINGAN",
        "KOTA DEPOK",
    ]
    regions = st.multiselect(
        "Pilih wilayah",
        region_options(panel),
        default=[region for region in default_regions if region in region_options(panel)],
        max_selections=8,
    )
    year_min, year_max = int(panel["tahun"].min()), int(panel["tahun"].max())
    year_range = st.slider("Rentang tahun", year_min, year_max, (year_min, year_max))

    filtered = panel[
        panel["nama_kabupaten_kota"].isin(regions)
        & panel["tahun"].between(year_range[0], year_range[1])
    ]
    if regions:
        st.plotly_chart(regional_trend(filtered, metric), width="stretch")
    else:
        st.warning("Pilih minimal satu wilayah untuk menampilkan tren.")

    st.plotly_chart(change_ranking(data["changes"]), width="stretch")
    st.caption(
        "Perubahan dihitung dari persentase penduduk miskin tahun awal ke tahun akhir. "
        "Nilai negatif berarti persentase kemiskinan menurun."
    )

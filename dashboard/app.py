from pathlib import Path
import sys

import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.pages import data_quality, overview, regional_comparison, trends, vulnerability


st.set_page_config(
    page_title="Kemiskinan Jawa Barat",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    [data-testid="stMetric"] {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 0.75rem;
        padding: 0.85rem;
    }
    .block-container {padding-top: 2rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

PAGES = {
    "Ringkasan": overview.render,
    "Tren Indikator": trends.render,
    "Perbandingan Wilayah": regional_comparison.render,
    "Jawaban Rumusan Masalah": vulnerability.render,
    "Kualitas Data": data_quality.render,
}

with st.sidebar:
    st.title("Kemiskinan Jabar")
    st.caption("Dashboard indikator sosial-ekonomi kabupaten/kota")
    selected_page = st.radio("Navigasi", PAGES, label_visibility="collapsed")
    st.divider()
    st.caption("Sumber: Open Data Jabar")
    st.caption("Periode analisis: 2010-2024")

try:
    PAGES[selected_page]()
except FileNotFoundError as error:
    st.error(str(error))
    st.code("uv run python scripts/preprocess_data.py\nuv run python scripts/explore_analysis.py\nuv run python scripts/model_clustering.py")

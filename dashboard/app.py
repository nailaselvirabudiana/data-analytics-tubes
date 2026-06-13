from pathlib import Path
import sys

import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.pages import data_quality, overview, regional_comparison, trends


st.set_page_config(
    page_title="Kemiskinan Jawa Barat",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #172554 100%);
    }
    [data-testid="stSidebar"] * {
        color: #f8fafc;
    }
    [data-testid="stSidebar"] [role="radiogroup"] label {
        border-radius: 0.65rem;
        padding: 0.45rem 0.65rem;
        margin-bottom: 0.2rem;
    }
    [data-testid="stSidebar"] [role="radiogroup"] label:hover {
        background: rgba(255, 255, 255, 0.10);
    }
    [data-testid="stMetric"] {
        background: linear-gradient(145deg, #ffffff, #f8fafc);
        border: 1px solid #e2e8f0;
        border-radius: 1rem;
        padding: 1rem;
        box-shadow: 0 6px 20px rgba(15, 23, 42, 0.06);
    }
    .block-container {
        padding-top: 1.6rem;
        padding-bottom: 3rem;
        max-width: 1500px;
    }
    .hero {
        padding: 1.5rem 1.7rem;
        border-radius: 1.2rem;
        background: linear-gradient(120deg, #172554 0%, #1d4ed8 65%, #0ea5e9 100%);
        color: white;
        margin-bottom: 1.2rem;
        box-shadow: 0 12px 30px rgba(29, 78, 216, 0.18);
    }
    .hero h1 {margin: 0; color: white; font-size: 2rem;}
    .hero p {margin: 0.45rem 0 0; color: #dbeafe; font-size: 1rem;}
    .indicator-card {
        padding: 1.25rem 1.4rem;
        border-radius: 1rem;
        border: 1px solid #bfdbfe;
        background: linear-gradient(135deg, #eff6ff 0%, #ffffff 70%);
        box-shadow: 0 5px 18px rgba(37, 99, 235, 0.08);
        margin-top: 0.35rem;
    }
    .indicator-card h3 {
        margin: 0 0 0.45rem;
        color: #1e3a8a;
        font-size: 1.15rem;
    }
    .indicator-card p {margin: 0.25rem 0; color: #334155;}
    .indicator-card .reading {
        margin-top: 0.7rem;
        padding-top: 0.65rem;
        border-top: 1px solid #dbeafe;
        color: #1e40af;
        font-weight: 600;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 1rem;
        box-shadow: 0 5px 18px rgba(15, 23, 42, 0.05);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

PAGES = {
    "Ringkasan": overview.render,
    "Tren Indikator": trends.render,
    "Perbandingan Wilayah": regional_comparison.render,
    "Kualitas Data": data_quality.render,
}

with st.sidebar:
    st.title("Kemiskinan Jabar")
    st.caption("Dashboard analitik kabupaten/kota")
    selected_page = st.radio("Navigasi", PAGES, label_visibility="collapsed")
    st.divider()
    st.caption("Sumber: Open Data Jabar")
    st.caption("Periode analisis: 2010-2024")

try:
    PAGES[selected_page]()
except FileNotFoundError as error:
    st.error(str(error))
    st.code("uv run python scripts/preprocess_data.py\nuv run python scripts/explore_analysis.py\nuv run python scripts/model_clustering.py")

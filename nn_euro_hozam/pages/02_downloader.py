import streamlit as st
import time
from streamlit_lightweight_charts import renderLightweightCharts
from nn_euro_hozam.config import COLORS
from loguru import logger


if "df" not in st.session_state:
    st.error("Please import data first. Redirecting...")
    time.sleep(1)
    st.switch_page("pages/01_settings.py")

st.markdown(
    "<h1 style='text-align: center;'>Downloader</h1>",
    unsafe_allow_html=True
)


st.subheader("NN Euro Data Downloader")


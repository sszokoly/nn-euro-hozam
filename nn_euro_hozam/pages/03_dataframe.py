import streamlit as st
import time
from nn_euro_hozam.config import COLORS
from loguru import logger

if "df" not in st.session_state:
    st.error("Please import data first. Redirecting...")
    time.sleep(1)
    st.switch_page("pages/01_settings.py")

st.markdown(
    "<h1 style='text-align: center;'>Dataframe</h1>",
    unsafe_allow_html=True
)

st.dataframe(st.session_state.chart_df, width='stretch')

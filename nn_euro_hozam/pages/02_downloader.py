import streamlit as st
import time
from nn_euro_hozam.config import COLORS
from loguru import logger
from downloader import download_multiple_xls

if "df" not in st.session_state:
    st.error("Please import data first. Redirecting...")
    time.sleep(1)
    st.switch_page("pages/01_settings.py")

st.markdown(
    "<h1 style='text-align: center;'>Downloader</h1>",
    unsafe_allow_html=True
)

st.subheader("NN Euro Data Downloader")

col1, col2, col3, col4 = st.columns([1, 1, 1, 4])

with col1:
    st.write(st.session_state.df_start)

with col2:
    st.write(st.session_state.df_end)

with col3:
    if st.button("Download", width='stretch'):
        pass
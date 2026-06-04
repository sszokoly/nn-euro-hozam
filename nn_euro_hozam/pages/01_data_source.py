import streamlit as st
from streamlit_lightweight_charts import renderLightweightCharts
import streamlit_lightweight_charts.dataSamples as data
from loguru import logger
from importer import import_from_xls, import_from_csv


st.title("Data Source")

if st.button("Import data"):
    if st.session_state.init_db:
        logger.opt(colors=True).info("Initializing from XLS files...")
        df = import_from_xls()
    else:
        df = import_from_csv()
        if df is None:
            logger.opt(colors=True).info("CSV file not found. Initializing from XLS files...")
            df = import_from_xls() 

    st.session_state.df = df
    st.rerun()

if "df" in st.session_state:
    st.success("Setup complete! Other pages are now available.")
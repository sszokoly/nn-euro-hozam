import streamlit as st
from streamlit_lightweight_charts import renderLightweightCharts
import streamlit_lightweight_charts.dataSamples as data
from loguru import logger
from importer import load_nn_from_db, import_nn_from_csv, import_nn_from_xls


st.title("Settings")
st.subheader("Data Source")

if "df" not in st.session_state:
    df = load_nn_from_db()
    logger.opt(colors=True).info("Dataframe loaded from Database")
    st.session_state.df = df

col1, col2, col3, col4 = st.columns([1, 1, 1, 5])
with col1:
    ok = "✅" if st.session_state.df is not None else "❌"
    st.write(f"🛢 Database {ok}")

with col2:
    if st.button("Re-import from CSV"):
        logger.opt(colors=True).info("Initializing from CSV files")
        df = import_nn_from_csv()
        if df is None:
            logger.opt(colors=True).info("CSV file not found. Initializing from XLS files")
            df = import_nn_from_xls()

        if df is not None:
            st.session_state.df = df
            st.rerun()

with col3:
    if st.button("Re-import from XLS"):
        logger.opt(colors=True).info("Initializing from XLS files")
        df = import_nn_from_xls()
        
        if df is not None:
            st.session_state.df = df
            st.rerun()
           

if "df" in st.session_state:
    st.success("Setup complete! Other pages are now available.")
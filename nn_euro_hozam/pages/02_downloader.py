from loguru import logger

import streamlit as st
import streamlit.components.v1 as components
import time
from config import COLORS
from downloader import download_multiple_xls
from datetime import date, datetime
from queue import Queue
from threading import Thread


progress_queue = Queue()

@st.fragment(run_every=2)  # Poll every 2 seconds
def progress_monitor():
    if not st.session_state.get("task_running"):
        return

    # Drain the queue for the latest update
    latest = None
    while not progress_queue.empty():
        latest = progress_queue.get()

    if latest is None and not progress_queue.empty():
        return

    if latest is not None:
        if latest == "done" or latest is None:
            st.session_state.task_running = False
            st.session_state.progress = 100
            st.success("Task complete!")
            st.rerun()
        else:
            st.session_state.progress = latest

    pct = st.session_state.get("progress", 0)
    st.progress(pct, text=f"Progress: {pct}%")


if "df" not in st.session_state:
    st.error("Please import data first. Redirecting...")
    time.sleep(1)
    st.switch_page("pages/01_settings.py")

st.markdown(
    "<h1 style='text-align: center;'>Downloader</h1>",
    unsafe_allow_html=True
)

col1, col2, col3, col4, col5 = st.columns([1.5, 0.5, 1.5, 2, 4])

with col1:
    st.write("Dataset Starts")
    st.markdown(
        f"<p style='font-size:38px; font-weight:500; margin:0; padding:0; color: #87CEFA'>"
        f"{st.session_state.df_start}</p>",
        unsafe_allow_html=True
    )

with col3:
    st.write("Dataset Ends")
    st.markdown(
        f"<p style='font-size:38px; font-weight:500; margin:0; padding:0; color: #87CEFA'>"
        f"{st.session_state.df_end}</p>",
        unsafe_allow_html=True
    )

st.divider(width=800)

col1, col2, col3, col4, col5 = st.columns([1.5, 0.5, 1.5, 2, 4], vertical_alignment="bottom")

with col1:
    download_start = st.date_input(
        "Set Download Start Date",
        value=date.fromisoformat(st.session_state.df_end)
    )
    
with col3:
    download_end = st.date_input(
        "Set Download End Date",
        value=datetime.now().date()
    )

if download_end > datetime.now().date():
    with col4:
        st.error("End Date cannot be in the future!")
        if "download_start" in st.session_state:
            del st.session_state["download_start"]

elif download_end <= download_start:
    with col4:
        st.error("Start and End Date must be different!")
        if "download_start" in st.session_state:
            del st.session_state["download_start"]

else:
    st.session_state.download_start = download_start.isoformat()
    st.session_state.download_end = download_end.isoformat()
    
if "download_start" in st.session_state and "download_end" in st.session_state:
    
    # Initialize state
    if "task_running" not in st.session_state:
        st.session_state.task_running = False
    if "progress" not in st.session_state:
        st.session_state.progress = 0
    
    with col4:
        st.markdown("""
            <style>
            div.stButton > button[kind="primary"] {
                background-color: darkblue;
                color: white;
                border: none;
            }
            div.stButton > button[kind="primary"]:hover {
                background-color: blue;
                color: white;
                border: none;
            }
            </style>
        """, unsafe_allow_html=True)
        
        if st.button("Download", disabled=st.session_state.task_running):
            st.session_state.task_running = True
            st.session_state.progress = 0
            while not progress_queue.empty():
                progress_queue.get()
            
            kwargs = {
                "start_date": st.session_state.download_start,
                "end_date": st.session_state.download_end,
                "interval": "daily",
                "min_sleep_secs": 5,
                "progress_queue": progress_queue
            }
            
            logger.opt(colors=True).info(f"<green>Starting</green> thread with {kwargs}")
            
            t = Thread(target=download_multiple_xls, kwargs=kwargs, daemon=True)
            t.start()
            st.rerun()

col1, col2, col3 = st.columns([3.5, 2, 4])

with col1:
    if st.session_state.task_running:
        progress_monitor()

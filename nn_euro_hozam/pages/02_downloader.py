from loguru import logger

import streamlit as st
import streamlit.components.v1 as components
import time
from config import COLORS
from downloader import download_multiple_xls
from datetime import date, datetime
from queue import Queue, Empty
from threading import Thread, Event
from importer import merge_xls_with_nn, load_nn_from_db


if "progress_queue" not in st.session_state:
    st.session_state.progress_queue = Queue()

if "result_queue" not in st.session_state:
    st.session_state.result_queue = Queue()

if "stop_event" not in st.session_state:
    st.session_state.stop_event = Event()


@st.fragment(run_every=1)  # Poll every 2 seconds
def progress_monitor():
    if not st.session_state.get("task_running"):
        return

    # Drain the queue for the latest update
    latest = None
    q = st.session_state.progress_queue
    
    # SAFE: Drain the queue using get_nowait() instead of checking .empty()
    while True:
        try:
            latest = q.get_nowait()
        except Empty:
            break

    if latest is not None:
        if latest == "done":
            st.session_state.stop_event.clear()
            st.session_state.task_running = False
            st.session_state.progress = 100
            st.success("Task complete!")
            # Force FULL app rerun to reset buttons/state properly
            st.rerun() 
        else:
            try:
                val = int(latest)
                st.session_state.progress = val
            except (ValueError, TypeError):
                pass

    # Display
    pct = st.session_state.get("progress", 0)
    # Ensure float between 0.0 and 1.0
    st.progress(pct / 100.0, text=f"Progress: {pct}%")


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

col1, col2, col3, col4, col5, col6 = st.columns([1.5, 0.5, 1.5, 2, 1, 3], vertical_alignment="bottom")

with col1:
    download_start = st.date_input(
        "Download Start Date",
        value=date.fromisoformat(st.session_state.df_end),
        disabled=True
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
        st.error("End Date must be past Start Date!")
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
    
    if not st.session_state.result_queue.empty():
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
            
            if st.button("Merge", disabled=st.session_state.task_running, type="primary", width="stretch"):
                rq = st.session_state.result_queue
                downloaded_files = []
                
                while True:
                    try:
                        files = rq.get_nowait()
                        downloaded_files.extend(files)
                    except Empty:
                        break
                
                merge_xls_with_nn(downloaded_files)
                st.session_state.df = load_nn_from_db(st.session_state.selected_db_file)
                st.rerun()
    
    elif not st.session_state.task_running:
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
            
            if st.button("Download", disabled=st.session_state.task_running, type="primary", width="stretch"):
                st.session_state.task_running = True
                st.session_state.progress = 0
                st.session_state.stop_event.clear()
                while not st.session_state.progress_queue.empty():
                    try:
                        st.session_state.progress_queue.get_nowait()
                    except Empty:
                        break
                
                kwargs = {
                    "start_date": st.session_state.download_start,
                    "end_date": st.session_state.download_end,
                    "interval": "daily",
                    "min_sleep_secs": 5,
                    "progress_queue": st.session_state.progress_queue,
                    "result_queue": st.session_state.result_queue,
                    "stop_event": st.session_state.stop_event,
                }
                
                logger.opt(colors=True).info(f"<green>Starting</green> thread with {kwargs}")
                
                t = Thread(target=download_multiple_xls, kwargs=kwargs, daemon=True)
                t.start()
                st.rerun()

    else:
        with col4:
            st.markdown("""
                <style>
                div.stButton > button[kind="secondary"] {
                    background-color: darkred;
                    color: white;
                    border: none;
                }
                div.stButton > button[kind="secondary"]:hover {
                    background-color: red;
                    color: white;
                    border: none;
                }
                </style>
            """, unsafe_allow_html=True)
            
            if st.button("Cancel", disabled=st.session_state.stop_event.is_set(), type="secondary", width="stretch"):
                st.session_state.stop_event.set()
                logger.opt(colors=True).info(f"<green>Stop event</green> {st.session_state.stop_event.is_set()}")

            
col1, col2, col3 = st.columns([3.5, 2, 4])

with col1:  
    if st.session_state.task_running:       
        progress_monitor()
    elif not st.session_state.result_queue.empty():
        st.warning("Click on 'Merge' when download is completed!")

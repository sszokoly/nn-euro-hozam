#!/usr/bin/env python3

import streamlit as st
import time
from streamlit_lightweight_charts import renderLightweightCharts
import streamlit_lightweight_charts.dataSamples as data
from loguru import logger
from datetime import date, datetime

from config import DB_DIR
from database import backup_db, save_settings, load_settings
from importer import load_nn_from_db, import_nn_from_csv, import_nn_from_xls
from pathlib import Path


db_files = sorted(Path(DB_DIR).rglob("*.db"))

if "settings_loaded" not in st.session_state:
    settings = load_settings()
    if settings:
        for key in settings:
            value = settings[key]
            setattr(st.session_state, key, value)
            logger.opt(colors=True).debug(f"<green>Restored</green> <yellow>{key}</yellow> to <cyan>{value}</cyan>")
        logger.opt(colors=True).info(f"<green>Restored</green> settings")
    st.session_state.settings_loaded = True

if "selected_db_file" not in st.session_state:
    st.session_state.selected_db_file = db_files[0]

def change_db_file():
    st.session_state.selected_db_file = st.session_state._db_picker

@st.dialog("Confirm Action")
def confirm_dialog(fn, msg="OK to Proceed?"):
    st.warning(
        "This will erase ALL NN Euro data from Database!\n\n"
        "Data will be lost if backup is not available!"
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Proceed", width='content'):
            logger.opt(colors=True).info("Reloading")
            with st.spinner("Processing..."):
                df = fn()
                if df is not None:
                    logger.opt(colors=True).info("<green>Reloaded</green>")
                    st.session_state.df = df
            st.rerun()
    with col2:
        if st.button("Cancel", width='content'):
            st.rerun()


st.markdown(
    "<h1 style='text-align: center;'>Settings</h1>",
    unsafe_allow_html=True
)

if "df" not in st.session_state:
    st.session_state.df = load_nn_from_db(st.session_state.selected_db_file)
    logger.opt(colors=True).info("Dataframe loaded from Database")

############################## DB SELECTOR BLOCK ##############################

st.subheader("NN Euro Data Source")

col1, col2, col3, col4, col5, col6 = st.columns([6, 1.4, 0.4, 1.4, 0.4, 5])

with col1:
    ok = "✅" if st.session_state.df is not None else "❌"
    st.write(f"🛢 Database {ok}")

with col2:
    st.markdown("""
        <style>
        div.stButton > button[kind="primary"] {
            background-color: darkgreen;
            color: white;
            border: none;
        }
        div.stButton > button[kind="primary"]:hover {
            background-color: green;
            color: white;
            border: none;
        }
        </style>
    """, unsafe_allow_html=True)
    
    if st.button("Reload from CSV", type="primary", width='stretch'):
        confirm_dialog(import_nn_from_csv)

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
    
    if st.button("Reload from XLS", type="secondary", width='stretch'):
        confirm_dialog(import_nn_from_xls)

with col1:
    st.write("")
    st.selectbox(
        "Database file",
        options=db_files,
        index=db_files.index(st.session_state.selected_db_file),
        key="_db_picker",
        on_change=change_db_file,
        placeholder="Select an DB file...",
        width=600,
    )

with col2:
    st.markdown("""
        <style>
        div.stButton > button[kind="tertiary"] {
            background-color: darkblue;
            color: white;
            border: none;
        }
        div.stButton > button[kind="tertiary"]:hover {
            background-color: blue;
            color: white;
            border: none;
        }
        </style>
    """, unsafe_allow_html=True)
    
    if st.button("Load Database", type="tertiary", width='stretch'):
        st.session_state.df = load_nn_from_db(st.session_state.selected_db_file)
        db_file_name = st.session_state.selected_db_file.name
        logger.opt(colors=True).info(f"Loaded <yellow>{db_file_name}</yellow>")
        with col3:
            placeholder = st.empty()
            placeholder.markdown(
                "<div style='padding-top: 5.6rem; font-size: 1.5rem;'>✅</div>",
                unsafe_allow_html=True
            )
            time.sleep(0.2)
            placeholder.empty()

with col4:
    st.markdown("""
        <style>
        div.stButton > button[kind="tertiary"] {
            background-color: darkblue;
            color: white;
            border: none;
        }
        div.stButton > button[kind="tertiary"]:hover {
            background-color: blue;
            color: white;
            border: none;
        }
        </style>
    """, unsafe_allow_html=True)
    
    if st.button("Backup Database", type="tertiary", width='stretch'):
        backup_db()
        with col5:
            placeholder = st.empty()
            placeholder.markdown(
                "<div style='padding-top: 5.6rem; font-size: 1.5rem;'>✅</div>",
                unsafe_allow_html=True
            )
            time.sleep(0.2)
            placeholder.empty()

# End columns section
st.container()  # forces column context to close
st.divider(width=1250)

############################# DATE SELECTOR BLOCK #############################

st.subheader("Start/End Date")

df_start, df_end = st.session_state.df["opening_date"].iloc[[0, -1]]
df_start_date = datetime.strptime(df_start, "%Y-%m-%d").date()
df_end_date = datetime.strptime(df_end, "%Y-%m-%d").date()
restored_start_date = date.fromisoformat(st.session_state.get("start_date", df_start))
restored_end_date = date.fromisoformat(st.session_state.get("end_date", df_end))


col1, col2, col3, col4, col5, col6 = st.columns([1, 1, 1, 1, 1, 3])

with col1:
    start_year = st.selectbox(
        "Start Year",
        options=range(df_start_date.year, df_end_date.year + 1),
        index=list(range(df_start_date.year, df_end_date.year + 1)).index(restored_start_date.year),
    )

with col2:
    start_month = st.selectbox(
        "Start Month",
        options=range(1, 13),
        format_func=lambda m: date(2025, m, 1).strftime("%B"),
        index=restored_start_date.month - 1,
    )

start_date = date(start_year, start_month, 1)

with col4:
    end_year = st.selectbox(
        "End Year",
        options=range(df_start_date.year, df_end_date.year + 1),
        index=list(range(df_start_date.year, df_end_date.year + 1)).index(restored_end_date.year),
    )

with col5:
    end_month = st.selectbox(
        "End Month",
        options=range(1, 13),
        format_func=lambda m: date(2025, m, 1).strftime("%B"),
        index=restored_end_date.month - 1,
    )

end_date = date(end_year, end_month, 1)

st.session_state.start_date = start_date.isoformat()
st.session_state.end_date = end_date.isoformat()
st.session_state.chart_df = st.session_state.df.loc[
    (st.session_state.df['opening_date'] >= st.session_state.start_date) &
    (st.session_state.df['opening_date'] <= st.session_state.end_date)
]

# End columns section
st.container()  # forces column context to close
st.divider(width=1250)

############################# ASSET SELECTOR BLOCK ############################

st.subheader("Asset Selector")

assets = st.session_state.all_assets = st.session_state.df["asset"].unique().tolist()

# Initialize session state
if "available_assets" not in st.session_state:
    st.session_state.available_assets = assets.copy()
if "selected_assets" not in st.session_state:
    st.session_state.selected_assets = []
if "asset_percentages" not in st.session_state:
    st.session_state.asset_percentages = {}

def add_asset():
    chosen = st.session_state._asset_picker
    if chosen and chosen not in st.session_state.selected_assets:
        st.session_state.selected_assets.append(chosen)
        st.session_state.available_assets.remove(chosen)
        st.session_state.asset_percentages[chosen] = 0
    st.session_state._asset_picker = None
    #st.rerun()

def remove_asset(asset):
    st.session_state.selected_assets.remove(asset)
    st.session_state.available_assets.append(asset)
    st.session_state.available_assets.sort()
    del st.session_state.asset_percentages[asset]
    #st.rerun()

def update_percentage(asset):
    st.session_state.asset_percentages[asset] = st.session_state[f"pct_{asset}"]

st.selectbox(
    "Add an asset",
    options=[None] + st.session_state.available_assets,
    index=0,
    key="_asset_picker",
    on_change=add_asset,
    placeholder="Select an asset...",
    width=400,
)

st.subheader("Selected Assets")
if not st.session_state.selected_assets:
    st.info("No assets selected yet.", width=400)
else:
    # Header row
    h1, h2, h3, h4 = st.columns([4, 1, 1, 4])
    h1.write("**Asset**")
    h2.write("**% Owned**")

    for asset in st.session_state.selected_assets:
        col1, col2, col3, col4 = st.columns([4, 1, 1, 4])
        with col1:
            st.write(f"📌 {asset}")
        with col2:
            st.number_input(
                label=f"% for {asset}",
                min_value=0,
                max_value=100,
                value=st.session_state.asset_percentages[asset],
                step=1,
                key=f"pct_{asset}",
                on_change=update_percentage,
                args=(asset,),
                label_visibility="collapsed",
            )
        with col3:
            st.button("✕", key=f"remove_{asset}", on_click=remove_asset, args=(asset,))

    # Divider and total row
    total = sum(st.session_state.asset_percentages.values())
    t1, t2, t3, t4 = st.columns([4, 1, 1, 4])
    with t1:
        st.write("**Total**")
    with t2:
        # Color the total red if it exceeds 100, green if exactly 100
        if total > 100:
            st.markdown(f"**:red[{total}%]**")
        elif total == 100:
            st.markdown(f"**:green[{total}%]**")
        else:
            st.write(f"**{total}%**")

# End columns section
st.container()  # forces column context to close
st.divider(width=1250)

################################# SAVE BLOCK ##################################

col1, col2, col3, col4 = st.columns([8, 2, 1, 12])  

if (
    "selected_assets" in st.session_state and
    st.session_state.selected_assets and
    "start_date" in st.session_state and
    "end_date" in st.session_state and
    total == 100
):
    with col2:
        if st.button("Save", width='stretch'):
            data = []
            for key in (
                "available_assets",
                "selected_assets",
                "asset_percentages",
                "start_date",
                "end_date"
            ):
                value = st.session_state[key]
                data.append({
                    "key": key,
                    "value": value
                })
            save_settings(data)
            logger.opt(colors=True).info(f"<green>Saved</green> settings")
            with col3:
                placeholder = st.empty()
                placeholder.markdown(
                    "<div style='padding-top: 0.2rem; font-size: 1.5rem;'>✅</div>",
                    unsafe_allow_html=True
                )
                time.sleep(0.2)
                placeholder.empty()

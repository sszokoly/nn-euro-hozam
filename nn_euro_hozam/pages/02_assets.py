import streamlit as st
import time
from streamlit_lightweight_charts import renderLightweightCharts
import streamlit_lightweight_charts.dataSamples as data


if "df" not in st.session_state:
    st.error("Please import data first. Redirecting...")
    time.sleep(2)
    st.switch_page("01_data_source.py")

assets = st.session_state.df["asset_name"].unique().tolist()

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

def remove_asset(asset):
    st.session_state.selected_assets.remove(asset)
    st.session_state.available_assets.append(asset)
    st.session_state.available_assets.sort()
    del st.session_state.asset_percentages[asset]

def update_percentage(asset):
    st.session_state.asset_percentages[asset] = st.session_state[f"pct_{asset}"]

st.title("Asset Selector")

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
    st.divider(width=925)
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
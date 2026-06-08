import streamlit as st
import time
from streamlit_lightweight_charts import renderLightweightCharts
from config import COLORS
from loguru import logger


if "df" not in st.session_state:
    st.error("Please import data first. Redirecting...")
    time.sleep(1)
    st.switch_page("pages/01_settings.py")

st.markdown(
    "<h1 style='text-align: center;'>Asset Yields</h1>",
    unsafe_allow_html=True
)


seriesLineChart = []
legend_divs = []
legend = '<div style="display: flex; gap: 18px; align-items: center; margin-bottom: 6px;">{0}</div>'
legend_div = '<div><span style="display:inline-block; width:15px; height:5px; background:{1}; margin-right:6px;"></span>{0}</div>'

chartOptions = {
    "height": 800,
    "layout": {
        "textColor": 'white',
        "background": {
            "type": 'solid',
            "color": "#221E293A"
        },
        "fontSize": 16,
    },
    "crosshair": {
        "mode": 1,
        "vertLine": {
            "labelVisible": True,
        },
        "horzLine": {
            "labelVisible": True,
        },
    },
    "grid": {
        "vertLines": {
            "color": 'rgba(200, 200, 200, 0.4)',  # Increased alpha for visibility
            "style": 2,  # 0=Solid, 1=Dotted, 2=Dashed, 3=LargeDashed
            "visible": True
        },
        "horzLines": {
            "color": 'rgba(200, 200, 200, 0.4)',
            "style": 2,
            "visible": True
        }
    }
}

col1, col2, = st.columns([1, 6])
st.session_state.asset_groups = ["My Assets", "All Assets", "Top 5 Performers"]

def change_asset_group():
    st.session_state.selected_asset_group = st.session_state._asset_group_picker

with col1:
    asset_group = st.selectbox(
        "Asset Groups",
        options=[None] + st.session_state.asset_groups,
        index=0,
        key="_asset_group_picker",
        on_change=change_asset_group,
        placeholder="Select an Asset Group...",
    )


assets = []

if "selected_asset_group" in st.session_state:
    if st.session_state.selected_asset_group == "My Assets":
        assets = st.session_state.selected_assets
    elif st.session_state.selected_asset_group == "All Assets":
        assets = st.session_state.all_assets
    elif st.session_state.selected_asset_group == "Top 5 Performers":
        assets = st.session_state.selected_assets

for asset in assets:
    color = COLORS.get(asset, '#000000')  # Default to black if asset not in COLORS
    logger.opt(colors=True).info(f"Processing asset: <yellow>{asset}</yellow> with color <cyan>{color}</cyan>")
    logger.opt(colors=True).info(f"Shape of <yellow>chart_df</yellow> is <cyan>{st.session_state.chart_df.shape}</cyan>")
    
    chart_df = st.session_state.chart_df.loc[
        st.session_state.chart_df['asset'] == asset, 
        ['opening_date', 'period_yield_pct_cumprod']
    ].rename(columns={'opening_date': 'time', 'period_yield_pct_cumprod': 'value'})

    chart_df['time'] = chart_df['time'].astype(str)
    chart_df = chart_df.sort_values(by='time').reset_index(drop=True)
    data = chart_df.to_dict('records')
    legend_divs.append(legend_div.format(asset, color))
    
    seriesLineChart.append({
        "type": 'Line',
        "data": data,
        "options": {
            "color": color,
            "lineWidth": 2,
            "lastValueVisible": True,
            "priceLineVisible": False,
        }
    })

st.subheader("Cumprod of Yields in %")
st.write("Cumulative product of yields measures an investment fund's total percentage growth over a specified period, accounting for the compounding effect of all gains, losses.")

legend = legend.format(''.join(legend_divs))
st.markdown(legend, unsafe_allow_html=True)

if seriesLineChart:
    renderLightweightCharts([
        {
            "chart": chartOptions,
            "series": seriesLineChart
        }
    ], "chart_with_static_legend")
else:
    st.error("No data available")

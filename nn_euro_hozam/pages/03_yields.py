import streamlit as st
import time
from streamlit_lightweight_charts import renderLightweightCharts
from colors import COLORS
from loguru import logger


if "df" not in st.session_state:
    st.error("Please import data first. Redirecting...")
    time.sleep(2)
    st.switch_page("01_data_source.py")

selected_assets = st.session_state.selected_assets

chartOptions = {
    "layout": {
        "textColor": 'black',
        "background": {
            "type": 'solid',
            "color": 'white'
        }
    },
    "height": 800,
}

seriesLineChart = []

for asset in selected_assets:
    color = COLORS.get(asset, '#000000')  # Default to black if asset not in COLORS
    logger.opt(colors=True).info(f"Processing asset: <yellow>{asset}</yellow> with color <cyan>{color}</cyan>")
    
    chart_df = st.session_state.df.loc[
        st.session_state.df['asset_name'] == asset, 
        ['date', 'opening_value']
    ].rename(columns={'date': 'time', 'opening_value': 'value'})
    
    chart_df['time'] = chart_df['time'].astype(str)
    chart_df = chart_df.sort_values(by='time').reset_index(drop=True)
    data = chart_df.to_dict('records')
    data = data[:10]
    
    logger.opt(colors=True).info(f"Chart data for <yellow>{asset}</yellow>: <cyan>{len(data)}</cyan> rows")
    logger.opt(colors=True).info(f"<cyan>{data}</cyan>")

    seriesLineChart.append({
        "type": 'Line',
        "data": data,
        "options": {
            "color": color,
            "lineWidth": 2,
            "lastValueVisible": True,
            "priceLineVisible": True
        }
    })

st.subheader("NN Euro-based Asset Yields")

if seriesLineChart:
    renderLightweightCharts([
        {
            "chart": chartOptions,
            "series": seriesLineChart
        }
    ], key="nn_asset_chart")
else:
    st.error("No data available")

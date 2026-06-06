import streamlit as st
import time
from streamlit_lightweight_charts import renderLightweightCharts
from nn_euro_hozam.config import COLORS
from loguru import logger


if "df" not in st.session_state:
    st.error("Please import data first. Redirecting...")
    time.sleep(1)
    st.switch_page("pages/01_settings.py")

selected_assets = st.session_state.selected_assets


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

seriesLineChart = []

for asset in selected_assets:
    color = COLORS.get(asset, '#000000')  # Default to black if asset not in COLORS
    logger.opt(colors=True).info(f"Processing asset: <yellow>{asset}</yellow> with color <cyan>{color}</cyan>")
    
    chart_df = st.session_state.df.loc[
        st.session_state.df['asset'] == asset, 
        ['opening_date', 'period_yield_pct_cumprod']
    ].rename(columns={'opening_date': 'time', 'period_yield_pct_cumprod': 'value'})

    chart_df['time'] = chart_df['time'].astype(str)
    chart_df = chart_df.sort_values(by='time').reset_index(drop=True)
    data = chart_df.to_dict('records')
    title = st.session_state.df.at[0, 'asset']
    
    logger.opt(colors=True).debug(f"Chart data for <yellow>{asset}</yellow>: <cyan>{len(data)}</cyan> rows")
    logger.opt(colors=True).debug(f"<cyan>{data}</cyan>")

    seriesLineChart.append({
        "type": 'Line',
        "data": data,
        "options": {
            #"title": title,
            "color": color,
            "lineWidth": 2,
            "lastValueVisible": True,
            "priceLineVisible": True
        }
    })

st.subheader("Compound Yield %")


if seriesLineChart:
    renderLightweightCharts([
        {
            "chart": chartOptions,
            "series": seriesLineChart
        }
    ], "chart_with_static_legend")
else:
    st.error("No data available")


st.markdown(
    f"""
    <div style="display: flex; gap: 18px; align-items: center; margin-bottom: 6px;">
        <div>
            <span style="display:inline-block; width:12px; height:3px; background:#2962FF; margin-right:6px;"></span>
            {title}
        </div>
        <div>
            <span style="display:inline-block; width:12px; height:3px; background:#FF6D00; margin-right:6px;"></span>
            Memory Usage
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
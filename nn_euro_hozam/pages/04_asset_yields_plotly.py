import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
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


def contrasting_text_color(hex_color):
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "black" if luminance > 0.5 else "white"

assets = st.session_state.selected_assets
fig = go.Figure()

for asset in assets:
    color = COLORS.get(asset, '#000000')  # Default to black if asset not in COLORS
    logger.opt(colors=True).info(f"Processing asset: <yellow>{asset}</yellow> with color <cyan>{color}</cyan>")
    
    chart_df = st.session_state.df.loc[
        st.session_state.df['asset'] == asset, 
        ['opening_date', 'period_yield_pct_cumprod']
    ].rename(columns={'opening_date': 'time', 'period_yield_pct_cumprod': 'value'})

    chart_df['time'] = chart_df['time'].astype(str)
    chart_df = chart_df.sort_values(by='time').reset_index(drop=True)

    last_time = chart_df["time"].iloc[-1]
    last_value = chart_df["value"].iloc[-1]

    fig.add_trace(
        go.Scatter(
            x=chart_df["time"],
            y=chart_df["value"],
            mode="lines",
            name=asset,
            line=dict(color=color),
            hovertemplate=f"{asset}<extra></extra>",
        )
    )
    
    fig.add_annotation(
        x=last_time,
        y=last_value,
        text=f"{last_value:.1f}%",
        showarrow=False,
        xanchor="left",
        xshift=5,
        bgcolor=color,
        font=dict(color=contrasting_text_color(color), size=14),
    )

fig.update_layout(
    height=800,  # increase chart height
    hovermode="closest",
    dragmode="pan",
    margin=dict(l=20, r=60, t=30, b=40),
    showlegend=True,

    # Put Y scale on the right
    yaxis=dict(
        side="right",
        showgrid=True,
        title="Yield %",
        fixedrange=True
    ),

    xaxis=dict(
        title="Time",
        dtick="M1",              # show one tick per month
        tickformat="%b\n%Y",     # Jan / 2026 style labels
        showgrid=True,
        #rangeslider=dict(visible=True),
    ),
)

st.subheader("Cumprod of Yields in %")
st.write("Cumulative product of yields measures an investment fund's total percentage growth over a specified period, accounting for the compounding effect of all gains, losses.")

st.plotly_chart(
    fig,
    width='stretch',
    config={
        "scrollZoom": True,
        "displayModeBar": True,
    },
)

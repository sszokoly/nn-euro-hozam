import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time

if "df" not in st.session_state:
    st.error("Please import data first. Redirecting...")
    time.sleep(1)
    st.switch_page("pages/01_settings.py")


chart_df = st.session_state.df.loc[
        st.session_state.df['asset'] == 'USA részvény eszközalap', 
        ['opening_date', 'period_yield_pct_cumprod']
    ].rename(columns={'opening_date': 'time', 'period_yield_pct_cumprod': 'value'})


fig = go.Figure()

fig.add_trace(
    go.Scatter(
        x=chart_df["time"],
        y=chart_df["value"],
        mode="lines",
        name="USA részvény eszközalap",
        hovertemplate="USA részvény eszközalap<extra></extra>",
    )
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

st.plotly_chart(
    fig,
    use_container_width=True,
    config={
        "scrollZoom": True,
        "displayModeBar": True,
    },
)


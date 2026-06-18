import streamlit as st
import plotly.graph_objects as go
import time
from config import COLORS
from loguru import logger


if "df" not in st.session_state:
    st.error("Please import data first. Redirecting...")
    time.sleep(1)
    st.switch_page("pages/01_settings.py")

st.markdown(
    "<h1 style='text-align: center;'>Asset Values</h1>",
    unsafe_allow_html=True
)

def contrasting_text_color(hex_color):
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "black" if luminance > 0.5 else "white"

def change_asset_group():
    st.session_state.selected_asset_group = st.session_state._asset_group_picker

def change_ma_days():
    st.session_state.selected_ma_days = st.session_state._ma_picker

def get_growth_rate(group):
    if len(group) < 2:
        return 0
    start_val = group[st.session_state.ma_days_col].iloc[0]
    end_val = group[st.session_state.ma_days_col].iloc[-1]
    if start_val == 0:
        return 0
    return ((end_val - start_val) / start_val) * 100

assets = []
st.session_state.asset_groups = ["My Assets", "All Assets", "Top 5 Performers"]
st.session_state.moving_avg_days = ["50d", "100d", "200d"]
col1, col2, col3 = st.columns([1, 1, 5])

with col1:
    asset_group = st.selectbox(
        "Asset Groups",
        options=[None] + st.session_state.asset_groups,
        index=0,
        key="_asset_group_picker",
        on_change=change_asset_group,
        placeholder="Asset Group...",
    )

with col2:
    asset_group = st.selectbox(
        "Moving Avg of X Days",
        options=[None] + st.session_state.moving_avg_days,
        index=0,
        key="_ma_picker",
        on_change=change_ma_days,
        placeholder="Number of Days of Moving Avg...",
    )

if "selected_asset_group" in st.session_state:
    if st.session_state.selected_asset_group == "My Assets":
        assets = st.session_state.selected_assets
    elif st.session_state.selected_asset_group == "All Assets":
        assets = st.session_state.all_assets
    elif st.session_state.selected_asset_group == "Top 5 Performers":
        growth_rates = (
            st.session_state.chart_df
            .groupby('asset')
            .apply(get_growth_rate)
            .rename('growth_pct')
        )
        assets = growth_rates.sort_values(ascending=False).head(5).index.tolist()

if "selected_ma_days" in st.session_state:
    if st.session_state.selected_ma_days == "50":
        st.session_state.ma_days = 50
        st.session_state.ma_days_col = "value_ma_50d"
    elif st.session_state.selected_ma_days == "100":
        st.session_state.ma_days = 100
        st.session_state.ma_days_col = "value_ma_100d"
    elif st.session_state.selected_ma_days == "200":
        st.session_state.ma_days = 200
        st.session_state.ma_days_col = "value_ma_200d"
else:
    st.session_state.ma_days = 100
    st.session_state.ma_days_col = "value_ma_100d"

if "ma_days_col" in st.session_state:

    fig = go.Figure()

    for asset in assets:
        color = COLORS.get(asset, '#000000')  # Default to black if asset not in COLORS
        logger.opt(colors=True).info(
            f"Processing asset: <yellow>{asset}</yellow> with color <cyan>{color}</cyan>"
        )
        
        chart_df = st.session_state.chart_df.loc[
            st.session_state.chart_df['asset'] == asset, 
            ['opening_date', st.session_state.ma_days_col]
        ].rename(columns={'opening_date': 'time', st.session_state.ma_days_col: 'value'})

        chart_df['time'] = chart_df['time'].astype(str)
        chart_df = chart_df.sort_values(by='time').reset_index(drop=True)

        last_time = chart_df["time"].iloc[-1]
        last_value = chart_df["value"].iloc[-1]
        first_time = chart_df["time"].iloc[0]
        first_value = chart_df["value"].iloc[0]

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
            text=f"{last_value:.1f}",
            showarrow=False,
            xanchor="left",
            xshift=5,
            bgcolor=color,
            font=dict(color=contrasting_text_color(color), size=14),
        )
        
        fig.add_annotation(
            x=first_time,
            y=first_value,
            text=f"{first_value:.1f}",
            showarrow=False,
            xanchor="left",
            xshift=-5,
            bgcolor=color,
            font=dict(color=contrasting_text_color(color), size=14),
        )

    fig.update_layout(
        height=800,  # increase chart height
        hovermode="closest",
        dragmode="pan",
        margin=dict(l=20, r=60, t=30, b=40),
        showlegend=True,

        legend=dict(
            x=0,                # 0 = Left edge of the plot area
            y=1.05,             # >1 = Above the plot area (adjust as needed)
            xanchor='left',     # Anchor the left side of the legend to x=0
            yanchor='bottom',   # Anchor the bottom of the legend to y=1.05
            orientation="h",    # Optional: Horizontal layout looks better on top
            #bgcolor="rgba(255,255,255,0.5)",
            #bordercolor="rgba(0,0,0,0.2)",
            borderwidth=1,
            font=dict(size=16),
            itemsizing='trace'
        ),

        # Put Y scale on the right
        yaxis=dict(
            side="right",
            showgrid=True,
            title="Value €",
            fixedrange=True,
            title_font=dict(size=18)
        ),

        xaxis=dict(
            title="Time",
            dtick="M1",              # show one tick per month
            tickformat="%b\n%Y",     # Jan / 2026 style labels
            #tickformat="%d %b",
            showgrid=True,
            tickangle=0,
            title_font=dict(size=18)
        ),
    )

    st.subheader(f"{st.session_state.ma_days}-day Moving Average")
    st.write(f"A {st.session_state.ma_days}-day rolling average of asset values.")

    st.plotly_chart(
        fig,
        width='stretch',
        config={
            "scrollZoom": True,
            "displayModeBar": True,
        },
    )

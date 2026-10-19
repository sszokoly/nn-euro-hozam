import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
from config import COLORS
from loguru import logger
from analytics import daily_prices, comparison_growth, portfolio_growth, review_metrics
from portfolio_review import render_portfolio_review


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

def change_asset_group():
    st.session_state.selected_asset_group = st.session_state._asset_group_picker

try:
    prices = daily_prices(st.session_state.df)
except ValueError as exc:
    st.error(str(exc))
    st.stop()
growth = comparison_growth(
    prices,
    st.session_state.get("start_date"),
    st.session_state.get("end_date"),
)
if len(growth) < 2:
    st.info("Select a period with at least two dates of shared fund coverage.")
    st.stop()
st.caption(f"Shared comparison period: {growth.index[0]:%Y-%m-%d} to {growth.index[-1]:%Y-%m-%d}. Returns reset at the first date.")
ranking_period = st.selectbox("Top 5 ranking window", ["6 months", "3 months", "Selected period"])
ranking_prices = prices.loc[:growth.index[-1]]
if ranking_period != "Selected period":
    months = 6 if ranking_period == "6 months" else 3
    ranking_start = growth.index[-1] - pd.DateOffset(months=months)
    if ranking_prices.index[0] > ranking_start:
        st.info("Not enough history for this ranking window. Choose Selected period.")
        st.stop()
    ranking_prices = ranking_prices.loc[ranking_start:]
else:
    ranking_prices = ranking_prices.loc[growth.index[0]:]
ranking_growth = comparison_growth(ranking_prices)
top_assets = (ranking_growth.iloc[-1] - 1).sort_values(ascending=False).head(5).index.tolist()
with st.expander("Which funds are in the Top 5 mix?", expanded=True):
    st.caption(
        f"Ranked over {ranking_growth.index[0]:%Y-%m-%d}–{ranking_growth.index[-1]:%Y-%m-%d} "
        f"({ranking_period}). Chart returns below cover "
        f"{growth.index[0]:%Y-%m-%d}–{growth.index[-1]:%Y-%m-%d}. "
        "Each weight is applied at the chart start and then allowed to drift."
    )
    composition = pd.DataFrame({
        "Weight at chart start": 1 / len(top_assets),
        "Ranking-window return": ranking_growth[top_assets].iloc[-1] - 1,
        "Chart-period return": growth[top_assets].iloc[-1] - 1,
    })
    composition.index.name = "Fund"
    st.dataframe(composition.style.format("{:.2%}"), width="stretch")
assets = []
st.session_state.asset_groups = ["My Assets", "All Assets", "Top 5 Performers"]
col1, col2, = st.columns([1, 6])

with col1:
    asset_group = st.selectbox(
        "Asset Groups",
        options=[None] + st.session_state.asset_groups,
        index=0,
        key="_asset_group_picker",
        on_change=change_asset_group,
        placeholder="Select an Asset Group...",
    )

if "selected_asset_group" in st.session_state:
    if st.session_state.selected_asset_group == "My Assets":
        assets = st.session_state.selected_assets
    elif st.session_state.selected_asset_group == "All Assets":
        assets = st.session_state.all_assets
    elif st.session_state.selected_asset_group == "Top 5 Performers":
        assets = top_assets

comparison = growth.copy()
comparison["Top 5 equal-weight mix"] = growth[top_assets].mean(axis=1)
try:
    comparison["My allocation"] = portfolio_growth(
        growth, st.session_state.get("asset_percentages", {})
    )
except ValueError as exc:
    st.info(str(exc) + " Set your allocation in Settings to include it.")
show_comparison = st.checkbox("Overlay my allocation and Top 5 mix", value=True)
plot_assets = list(assets)
if show_comparison:
    plot_assets += [name for name in ("My allocation", "Top 5 equal-weight mix") if name in comparison]

fig = go.Figure()

for asset in plot_assets:
    color = {"My allocation": "#1565c0", "Top 5 equal-weight mix": "#ef6c00"}.get(asset, COLORS.get(asset, '#666666'))
    logger.opt(colors=True).info(f"Processing asset: <yellow>{asset}</yellow> with color <cyan>{color}</cyan>")
    
    chart_df = (comparison[asset] - 1).rename("value").rename_axis("time").reset_index()

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
            line=dict(color=color, width=4 if asset in ("My allocation", "Top 5 equal-weight mix") else 2),
            hovertemplate=f"{asset}<br>%{{x}}<br>%{{y:.2%}}<extra></extra>",
        )
    )
    
    fig.add_annotation(
        x=last_time,
        y=last_value,
        text=f"{last_value:.1%}",
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
        title="Yield %",
        tickformat=".1%",
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

st.subheader("Cumprod of Yields in %")
st.write("Cumulative product of yields measures the investment fund's total percentage growth over a specified period, accounting for the compounding effect of all gains, losses.")

st.plotly_chart(
    fig,
    width='stretch',
    config={
        "scrollZoom": True,
        "displayModeBar": True,
    },
)

st.subheader("Portfolio review — multi-month performance")
st.caption(
    "Current weights are applied at the comparison start and held without rebalancing. "
    "This is a historical comparison of today's mix, not an account statement. "
    "Top 5 funds are chosen using data available at the displayed end date; their earlier "
    "performance is a hindsight comparison, not a tested switching strategy. "
    "Fees, contributions and withdrawals are not included."
)
metric_assets = list(dict.fromkeys(
    [name for name in ("My allocation", "Top 5 equal-weight mix") if name in comparison]
    + assets + top_assets
))
metrics = review_metrics(comparison[metric_assets])
st.dataframe(metrics.style.format("{:.2%}", na_rep="Insufficient history"), width="stretch")
st.caption("3- and 6-month returns require that much history within the selected comparison period. Review sustained performance and drawdowns together before using one of your four annual allocation changes.")

drawdown = go.Figure()
for asset in plot_assets:
    series = comparison[asset] / comparison[asset].cummax() - 1
    drawdown.add_trace(go.Scatter(
        x=series.index, y=series, name=asset, mode="lines",
        hovertemplate="%{x|%Y-%m-%d}<br>%{y:.2%}<extra>%{fullData.name}</extra>",
    ))
drawdown.update_layout(height=350, yaxis=dict(title="Drawdown", tickformat=".1%"), hovermode="x unified")
st.subheader("Drawdown over the same period")
st.plotly_chart(drawdown, width="stretch")

st.divider()
render_portfolio_review(
    prices, growth.index[-1], st.session_state.get("asset_percentages", {})
)

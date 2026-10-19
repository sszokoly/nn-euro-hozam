import streamlit as st
import plotly.graph_objects as go
import time
from config import COLORS
from loguru import logger
from analytics import (
    daily_prices, comparison_growth, price_moving_average,
    moving_average_growth, price_trend_summary,
)


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

try:
    prices = daily_prices(st.session_state.df)
except ValueError as exc:
    st.error(str(exc))
    st.stop()
start = st.session_state.get("start_date")
end = st.session_state.get("end_date")
window = prices.loc[start:end]
if len(window) < 2:
    st.info("Select a period with at least two dates of price history.")
    st.stop()
as_of = window.index[-1]
# Calculate on the full history, THEN select chart dates. Short chart ranges must
# not restart moving-average warm-up, and future data must not enter the summary.
prices = prices.loc[:as_of]
averages = {days: price_moving_average(prices, days) for days in (50, 100, 200)}
st.caption(f"Chart period: {window.index[0]:%Y-%m-%d}–{as_of:%Y-%m-%d}. Moving averages use earlier history for warm-up.")
groups = ["My Assets", "All Assets", "Top 5 by MA growth"]
previous_group = st.session_state.get("selected_asset_group", "My Assets")
if previous_group == "Top 5 Performers":
    previous_group = "Top 5 by MA growth"
col1, col2, col3 = st.columns([2, 2, 4])

with col1:
    asset_group = st.selectbox(
        "Asset Groups",
        options=groups,
        index=groups.index(previous_group) if previous_group in groups else 0,
        key="values_asset_group",
    )

with col2:
    ma_days = st.selectbox(
        "Moving-average window",
        options=[50, 100, 200], index=1,
        format_func=lambda days: f"{days} calendar days",
        key="values_ma_days",
    )
with col3:
    scale = st.radio("Comparison scale", ["Euro values", "Normalized (start = 100)"], horizontal=True, key="values_scale")
normalized = scale != "Euro values"
ma_window = averages[ma_days].loc[start:end]
if asset_group == "My Assets":
    assets = [asset for asset in st.session_state.get("selected_assets", []) if asset in prices]
elif asset_group == "All Assets":
    assets = prices.columns.tolist()
else:
    rates = moving_average_growth(averages[ma_days], start, end).dropna()
    rates = rates.sort_index().sort_values(ascending=False, kind="stable").head(5)
    assets = rates.index.tolist()
    st.caption("Top 5 by growth of the selected moving average over the chart period. This measures smoothed price trends, not the Yields page's return ranking. Funds without an average at both boundaries are excluded.")
    if assets:
        st.dataframe(rates.rename("Moving-average growth").to_frame().style.format("{:.2%}"), width="stretch")
plot_values = ma_window[assets].dropna(axis=1, how="all")
unavailable = set(assets).difference(plot_values.columns)
if unavailable:
    st.info("Not enough history for this moving average: " + ", ".join(sorted(unavailable)))
if normalized and not plot_values.empty:
    plot_values = comparison_growth(plot_values) * 100
    if len(plot_values) >= 2:
        st.caption(f"All displayed moving averages start at 100 on {plot_values.index[0]:%Y-%m-%d} and share history through {plot_values.index[-1]:%Y-%m-%d}. This is normalized moving-average growth, not total investment return.")
st.caption("Euro unit-price levels are not comparable measures of investment quality. The normalized view compares relative trends. Calendar-day averages include carried-forward prices on non-valuation days.")

if len(plot_values) >= 2 and len(plot_values.columns):

    fig = go.Figure()

    for asset in plot_values:
        color = COLORS.get(asset, '#000000')  # Default to black if asset not in COLORS
        logger.opt(colors=True).info(
            f"Processing asset: <yellow>{asset}</yellow> with color <cyan>{color}</cyan>"
        )
        
        chart_df = plot_values[asset].dropna().rename("value").rename_axis("time").reset_index()
        if chart_df.empty:
            continue

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
                hovertemplate=f"{asset}<br>%{{x}}<br>" + ("%{y:.2f}" if normalized else "€%{y:.4f}") + "<extra></extra>",
            )
        )
        
        fig.add_annotation(
            x=last_time,
            y=last_value,
            text=f"{last_value:.2f}" if normalized else f"€{last_value:.4f}",
            showarrow=False,
            xanchor="left",
            xshift=5,
            bgcolor=color,
            font=dict(color=contrasting_text_color(color), size=14),
        )
        
        fig.add_annotation(
            x=first_time,
            y=first_value,
            text=f"{first_value:.2f}" if normalized else f"€{first_value:.4f}",
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
            title="Index (start = 100)" if normalized else "Value €",
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

    st.subheader(f"{ma_days}-day Moving Average")
    st.write(f"A trailing {ma_days}-calendar-day average of asset values.")

    st.plotly_chart(
        fig,
        width='stretch',
        config={
            "scrollZoom": True,
            "displayModeBar": True,
        },
    )
else:
    st.info("Select funds with enough shared moving-average history, or choose a shorter average or a later period.")

st.divider()
st.subheader("Single-fund trend: price and moving averages")
preferred = assets[0] if assets else prices.columns[0]
focus = st.selectbox("Fund to inspect", prices.columns.tolist(), index=prices.columns.tolist().index(preferred), key="values_focus_asset")
overlays = st.multiselect("Moving averages to overlay", [50, 100, 200], default=[100, 200], format_func=lambda days: f"{days} days", key="values_focus_averages")
focus_fig = go.Figure()
focus_fig.add_trace(go.Scatter(x=window.index, y=window[focus], name="Actual NAV", mode="lines", line=dict(color=COLORS.get(focus, "#1565c0"), width=2)))
for days in overlays:
    series = averages[days][focus].loc[start:end]
    if series.notna().any():
        focus_fig.add_trace(go.Scatter(x=series.index, y=series, name=f"{days}-day MA", mode="lines", line=dict(dash="dash" if days == 200 else "dot" if days == 100 else "solid")))
    else:
        st.caption(f"Not enough history for the {days}-day average in this period.")
focus_fig.update_traces(hovertemplate="%{x|%Y-%m-%d}<br>€%{y:.4f}<extra>%{fullData.name}</extra>")
focus_fig.update_layout(height=450, hovermode="x unified", yaxis=dict(title="NAV (€)"), dragmode="pan")
st.plotly_chart(focus_fig, width="stretch", config={"scrollZoom": True})

st.subheader(f"Trend summary — all funds as of {as_of:%Y-%m-%d}")
st.caption("Position compares the latest price with its average. Direction compares the average with its value 20 calendar days earlier. Positive distance means price is above the average. Summary values use all history up to this date, independently of the chart's start date.")
summary = price_trend_summary(prices, as_of)
summary.insert(0, "Current weight (%)", summary.index.map(st.session_state.get("asset_percentages", {})).fillna(0))
formats = {column: "{:.4f}" for column in summary if "(€)" in column}
formats.update({column: "{:+.2%}" for column in summary if "Distance" in column or "change" in column})
formats["Current weight (%)"] = "{:.1f}%"
st.dataframe(summary.style.format(formats, na_rep="Insufficient history"), width="stretch")
st.caption("Use this as a trend-confirmation check alongside 3-/6-month returns and drawdowns in Yields. Moving averages lag prices; an above-average price or rising trend alone does not establish future outperformance.")

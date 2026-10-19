"""Streamlit's transparent, multi-month allocation review panel."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analytics import (
    candidate_allocation,
    comparison_growth,
    portfolio_growth,
    review_metrics,
    trailing_fund_metrics,
)


def render_portfolio_review(prices, as_of, percentages):
    metrics = trailing_fund_metrics(prices, as_of)
    end = metrics.attrs["as_of"]
    next_review = end + pd.DateOffset(months=4)
    st.header("Review an allocation for the next four months")
    st.write(
        f"Review date: **{end:%Y-%m-%d}** · Planned next review: **{next_review:%Y-%m-%d}**. "
        "Trailing windows use all available history up to the review date, independently "
        "of the chart's start date."
    )
    method = st.selectbox(
        "Candidate ranking rule",
        ["Combined 3 + 6 months", "3 months", "6 months"],
        key="candidate_ranking_rule",
    )
    positive_only = st.checkbox(
        "Require positive returns over both 3 and 6 months",
        value=True, key="candidate_positive_only",
    )
    st.caption(
        "Combined rule: rank every fund separately by 3- and 6-month return, then average "
        "the two ranks (lower is better). Ties favor higher 6-month, then 3-month returns, "
        "then fund name. Take up to five eligible funds, equally weighted. Drawdowns are "
        "shown for comparison but do not influence this momentum-only rule."
    )
    candidate = candidate_allocation(metrics, method, positive_only)
    current = pd.Series(percentages, dtype=float, name="Current weight (%)")
    screen = metrics.copy()
    screen.attrs = {}
    screen["Current weight (%)"] = current.reindex(screen.index, fill_value=0)
    screen["Candidate weight (%)"] = candidate.reindex(screen.index, fill_value=0)
    screen["Candidate order"] = pd.Series(range(1, len(candidate) + 1), index=candidate.index).reindex(screen.index)
    order_column = "Mean rank" if method == "Combined 3 + 6 months" else f"{method[0]}-month rank"
    order = [order_column, "6-month return", "3-month return"] if method == "Combined 3 + 6 months" else [order_column]
    screen = screen.sort_index().sort_values(
        order, ascending=[True, False, False] if len(order) == 3 else True,
        kind="stable", na_position="last",
    )
    formats = {
        column: "{:.2%}" for column in screen.columns if "return" in column or "drawdown" in column
    }
    formats.update({column: "{:.1f}" for column in screen.columns if "rank" in column.lower()})
    formats.update({"Current weight (%)": "{:.1f}%", "Candidate weight (%)": "{:.1f}%", "Candidate order": "{:.0f}"})
    st.subheader("All funds: returns, persistence, downside and weights")
    st.caption(
        f"3-month window: {end - pd.DateOffset(months=3):%Y-%m-%d}–{end:%Y-%m-%d}; "
        f"6-month window: {end - pd.DateOffset(months=6):%Y-%m-%d}–{end:%Y-%m-%d}. "
        "Previous 3-month return covers the earlier half of the six-month window. "
        "Missing history is shown as —, never as a zero return."
    )
    st.dataframe(screen.style.format(formats, na_rep="—"), width="stretch")

    if candidate.empty:
        st.info("No funds meet this rule with the available history. Your saved allocation has not changed.")
        return
    if len(candidate) < 5:
        st.info(f"Only {len(candidate)} funds qualify. The candidate is equally weighted across those funds.")
    st.subheader("Candidate allocation and changes to consider")
    st.caption(
        "This is a mechanical shortlist for review, not an optimized allocation or a prediction "
        "of the next four months. Equal fund weights do not guarantee diversified exposures. "
        "Compare drawdowns, overlapping exposures and switching costs before choosing a mix."
    )
    changes = pd.concat([current, candidate], axis=1).fillna(0)
    changes = changes[(changes > 0).any(axis=1)]
    changes["Change (percentage points)"] = changes["Candidate weight (%)"] - changes["Current weight (%)"]
    changes["Action"] = changes["Change (percentage points)"].map(
        lambda delta: "Increase / add" if delta > 0.000001 else "Reduce / exit" if delta < -0.000001 else "Keep"
    )
    st.dataframe(changes.style.format({
        "Current weight (%)": "{:.1f}%", "Candidate weight (%)": "{:.1f}%",
        "Change (percentage points)": "{:+.1f}",
    }), width="stretch")

    # Compare identical fixed mixes over the same six-month interval. This remains
    # hindsight: the candidate was selected at the END, not at the start.
    funds = list(dict.fromkeys(current[current > 0].index.tolist() + candidate.index.tolist()))
    missing = set(funds).difference(prices.columns)
    if missing:
        st.info(f"Cannot compare mixes: missing fund history for {', '.join(sorted(missing))}.")
        return
    cutoff = end - pd.DateOffset(months=6)
    available = prices.loc[:end, funds]
    baseline = available.loc[:cutoff]
    if baseline.empty or baseline.iloc[-1].isna().any():
        st.info("Six months of shared history are needed to compare both mixes.")
        return
    growth = comparison_growth(available, baseline.index[-1], end)
    if len(growth) < 2 or growth.index[0] > cutoff or growth.index[-1] != end:
        st.info("Six months of shared history are needed to compare both mixes.")
        return
    try:
        mixes = pd.DataFrame({
            "Current allocation": portfolio_growth(growth, percentages),
            "Candidate allocation": portfolio_growth(growth, candidate.to_dict()),
        })
    except ValueError as exc:
        st.info(str(exc) + " Update your allocation in Settings to compare the mixes.")
        return
    turnover = changes["Change (percentage points)"].abs().sum() / 2
    st.write(f"Switching from the current to the candidate mix would reallocate **{turnover:.1f}%** of the portfolio.")
    st.subheader("Same-mix historical comparison — not a forward test")
    st.caption(
        f"Both mixes start on {growth.index[0]:%Y-%m-%d} and end on {end:%Y-%m-%d}, "
        "with no rebalancing, contributions, withdrawals or switching costs. "
        "The candidate was selected at the end of this history: these returns do not "
        "measure how a switching strategy would have performed out of sample. "
        "Leave the allocation unchanged if the evidence does not justify the change."
    )
    st.dataframe(review_metrics(mixes).style.format("{:.2%}", na_rep="—"), width="stretch")
    fig = go.Figure()
    for name in mixes:
        fig.add_trace(go.Scatter(
            x=mixes.index, y=mixes[name] - 1, name=name, mode="lines",
            hovertemplate="%{x|%Y-%m-%d}<br>%{y:.2%}<extra>%{fullData.name}</extra>",
        ))
    fig.update_layout(height=400, yaxis=dict(title="Return", tickformat=".1%"), hovermode="x unified")
    st.plotly_chart(fig, width="stretch")
    st.download_button(
        "Download fund review (CSV)",
        data=screen.to_csv().encode("utf-8-sig"),
        file_name=f"portfolio_review_{end:%Y-%m-%d}.csv", mime="text/csv",
    )
    st.caption("Candidate weights are a review worksheet. Your saved allocation is changed only in Settings.")

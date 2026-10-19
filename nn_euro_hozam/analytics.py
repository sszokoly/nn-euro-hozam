"""Dated NAV reconstruction and buy-and-hold review calculations."""

import numpy as np
import pandas as pd


def daily_prices(records):
    """Use both interval endpoints; zero-duration fills never override observations.

    Calendar fills are for chart continuity, not additional market observations.
    Conflicting observed prices beyond legacy four-decimal rounding are rejected.
    """
    if records.empty:
        return pd.DataFrame()
    points = []
    for endpoint in ("opening", "closing"):
        point = records[["asset", f"{endpoint}_date", f"{endpoint}_euro_value"]].copy()
        point.columns = ["asset", "date", "price"]
        point["observed"] = records.opening_date.ne(records.closing_date).to_numpy()
        points.append(point)
    points = pd.concat(points, ignore_index=True)
    points["date"] = pd.to_datetime(points.date)
    points["price"] = pd.to_numeric(points.price, errors="raise")
    if points.date.isna().any() or not np.isfinite(points.price).all() or (points.price <= 0).any():
        raise ValueError("NAV dates must be valid and prices finite and positive.")
    observed = points[points.observed]
    spread = observed.groupby(["asset", "date"]).price.agg(["min", "max"])
    conflicts = spread[spread["max"] - spread["min"] > 0.00011]
    if not conflicts.empty:
        raise ValueError(f"Conflicting observed NAVs: {conflicts.index.tolist()[:5]}")
    points = points.sort_values("observed", kind="stable").drop_duplicates(["asset", "date"], keep="last")
    prices = points.pivot(index="date", columns="asset", values="price").sort_index()
    # Fill interior gaps only: unequal coverage must not silently invent history.
    return prices.resample("D").asfreq().ffill(limit_area="inside")


def comparison_growth(prices, start=None, end=None):
    """Rebase a shared, complete comparison interval to one."""
    window = prices.loc[start:end].dropna(how="any")
    if window.empty:
        return window
    return window.div(window.iloc[0])


def portfolio_growth(growth, percentages):
    """Apply allocation at period start, with no subsequent rebalancing."""
    weights = pd.Series(percentages, dtype=float)
    if (not np.isfinite(weights).all() or (weights < 0).any()
            or not np.isclose(weights.sum(), 100)):
        raise ValueError("Allocation percentages must be nonnegative and total 100%.")
    weights = weights[weights > 0]
    missing = weights.index.difference(growth.columns)
    if len(missing):
        raise ValueError(f"Missing portfolio funds: {', '.join(missing)}")
    return growth[weights.index].mul(weights / 100).sum(axis=1, min_count=len(weights))


def review_metrics(growth):
    """Same retrospective metrics for funds and allocation mixes."""
    result = pd.DataFrame(index=growth.columns)
    result["Selected period"] = growth.iloc[-1] / growth.iloc[0] - 1
    for months in (3, 6):
        cutoff = growth.index[-1] - pd.DateOffset(months=months)
        prior = growth.loc[:cutoff]
        result[f"{months}-month return"] = (
            growth.iloc[-1] / prior.iloc[-1] - 1 if not prior.empty else np.nan
        )
    result["Maximum drawdown"] = (growth / growth.cummax() - 1).min()
    result["Current drawdown"] = (growth / growth.cummax() - 1).iloc[-1]
    return result


def trailing_fund_metrics(prices, as_of):
    """Rank funds using only history available on or before the review date.

    Lookbacks are calendar months, independent of the chart's start date.
    A fund missing a cutoff or end valuation is ineligible for that window.
    """
    history = prices.sort_index().loc[:pd.Timestamp(as_of)]
    if history.empty:
        raise ValueError("No prices are available on or before the review date.")
    end = history.index[-1]
    result = pd.DataFrame(index=history.columns)
    for months in (3, 6):
        cutoff = end - pd.DateOffset(months=months)
        prior = history.loc[:cutoff]
        baseline = prior.iloc[-1] if not prior.empty else pd.Series(np.nan, index=history.columns)
        result[f"{months}-month return"] = history.iloc[-1] / baseline - 1
        result[f"{months}-month rank"] = result[f"{months}-month return"].rank(ascending=False, method="min")
        if months == 6:
            window = history.loc[prior.index[-1]:] if not prior.empty else history.iloc[:0]
            drawdown = window / window.cummax() - 1
            result["6-month max drawdown"] = drawdown.min().where(baseline.notna() & history.iloc[-1].notna())
    result["Previous 3-month return"] = (
        (1 + result["6-month return"]) / (1 + result["3-month return"]) - 1
    )
    # Do not silently average just one rank when the other window is missing.
    result["Mean rank"] = (result["3-month rank"] + result["6-month rank"]) / 2
    result["Positive in both windows"] = (
        (result["3-month return"] > 0) & (result["6-month return"] > 0)
    )
    result.index.name = "Fund"
    result.attrs["as_of"] = end
    return result


def candidate_allocation(metrics, method="Combined 3 + 6 months", positive_only=True, count=5):
    """Mechanical equal-weight shortlist, not a forecast or risk optimizer."""
    if count < 1:
        raise ValueError("The shortlist must contain at least one fund.")
    if method not in ("3 months", "6 months", "Combined 3 + 6 months"):
        raise ValueError("Unknown ranking method.")
    eligible = metrics.sort_index()
    if positive_only:
        eligible = eligible[eligible["Positive in both windows"]]
    if method == "Combined 3 + 6 months":
        ordered = eligible.dropna(subset=["Mean rank"]).sort_values(
            ["Mean rank", "6-month return", "3-month return"],
            ascending=[True, False, False], kind="stable",
        )
    else:
        column = f"{method[0]}-month return"
        ordered = eligible.dropna(subset=[column]).sort_values(column, ascending=False, kind="stable")
    funds = ordered.head(count).index
    return pd.Series(100 / len(funds), index=funds, name="Candidate weight (%)") if len(funds) else pd.Series(dtype=float, name="Candidate weight (%)")


def price_moving_average(prices, days):
    """Trailing calendar-day average with a complete daily warm-up window."""
    daily = prices.sort_index().asfreq("D")
    return daily.rolling(f"{days}D", min_periods=days).mean()


def moving_average_growth(averages, start=None, end=None):
    """Rank only funds with an average at BOTH comparison boundaries."""
    window = averages.loc[start:end]
    if len(window) < 2:
        return pd.Series(np.nan, index=averages.columns, dtype=float)
    return window.iloc[-1] / window.iloc[0] - 1


def price_trend_summary(prices, as_of, slope_days=20):
    """Price position and 20-calendar-day MA change, without future prices."""
    history = prices.sort_index().loc[:pd.Timestamp(as_of)]
    if history.empty:
        raise ValueError("No prices are available on or before the trend date.")
    if slope_days < 1:
        raise ValueError("The slope lookback must be positive.")
    end = history.index[-1]
    result = pd.DataFrame({"Latest NAV (€)": history.iloc[-1]})
    for days in (100, 200):
        averages = price_moving_average(history, days)
        latest = averages.iloc[-1]
        prior = averages.loc[:end - pd.Timedelta(days=slope_days)]
        baseline = prior.iloc[-1] if not prior.empty else pd.Series(np.nan, index=history.columns)
        slope = latest / baseline - 1
        distance = history.iloc[-1] / latest - 1
        result[f"{days}d MA (€)"] = latest
        result[f"Distance from {days}d MA"] = distance
        result[f"{days}d MA change ({slope_days}d)"] = slope
        result[f"{days}d position"] = np.select(
            [distance.isna(), np.isclose(distance, 0), distance > 0],
            ["Insufficient history", "At average", "Above"], default="Below",
        )
        result[f"{days}d direction"] = np.select(
            [slope.isna(), np.isclose(slope, 0), slope > 0],
            ["Insufficient history", "Flat", "Rising"], default="Falling",
        )
    result.index.name = "Fund"
    return result

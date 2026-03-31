"""
IBNR (Incurred But Not Reported) Analysis Module.

Uses past complete month data to predict trends:
- Claims count = unique count of Claim_Number (not raw row count)
- Development triangles built from Treatment_Date vs Received_Date lag
- Chain-ladder method for IBNR estimation
- Trend forecasting using complete months only
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from pathlib import Path
from datetime import datetime

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "reports"


def format_naira(x, _=None):
    if abs(x) >= 1_000_000:
        return f"N{x/1_000_000:.1f}M"
    elif abs(x) >= 1_000:
        return f"N{x/1_000:.0f}K"
    return f"N{x:.0f}"


def _get_complete_months(claims, cutoff_date=None):
    """
    Filter to only past complete months (exclude current/incomplete month).
    A complete month is any month strictly before the cutoff month.
    """
    if cutoff_date is None:
        cutoff_date = pd.Timestamp.now()

    # First day of the current month = boundary for "complete"
    current_month_start = cutoff_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    df = claims.dropna(subset=["Treatment_Date"]).copy()
    df = df[df["Treatment_Date"] < current_month_start]
    return df


def _compute_lag_months(treatment_date, received_date):
    """Compute development lag in months between treatment and received dates."""
    return (
        (received_date.dt.year - treatment_date.dt.year) * 12
        + (received_date.dt.month - treatment_date.dt.month)
    ).clip(lower=0)


def build_development_triangle(claims, max_lag=12):
    """
    Build a claims development triangle.
    Rows = incurred month (Treatment_Date month)
    Columns = development lag in months (Treatment -> Received)
    Values = unique claim count at each lag
    """
    df = _get_complete_months(claims)
    df = df.dropna(subset=["Treatment_Date", "Received_Date"])
    df["Incurred_Month"] = df["Treatment_Date"].dt.to_period("M")
    df["Lag_Months"] = _compute_lag_months(df["Treatment_Date"], df["Received_Date"])
    df = df[df["Lag_Months"] <= max_lag]

    # Unique claim count per incurred month per lag
    triangle = (
        df.groupby(["Incurred_Month", "Lag_Months"])["Claim_Number"]
        .nunique()
        .unstack(fill_value=0)
    )

    # Cumulative triangle
    cum_triangle = triangle.cumsum(axis=1)
    return triangle, cum_triangle


def build_amount_triangle(claims, max_lag=12):
    """
    Build a paid amount development triangle.
    Values = total Amount_Paid at each lag.
    """
    df = _get_complete_months(claims)
    df = df.dropna(subset=["Treatment_Date", "Received_Date", "Amount_Paid"])
    df["Incurred_Month"] = df["Treatment_Date"].dt.to_period("M")
    df["Lag_Months"] = _compute_lag_months(df["Treatment_Date"], df["Received_Date"])
    df = df[df["Lag_Months"] <= max_lag]

    triangle = (
        df.groupby(["Incurred_Month", "Lag_Months"])["Amount_Paid"]
        .sum()
        .unstack(fill_value=0)
    )

    cum_triangle = triangle.cumsum(axis=1)
    return triangle, cum_triangle


def chain_ladder_factors(cum_triangle):
    """
    Calculate age-to-age (link) development factors using the chain-ladder method.
    Uses volume-weighted average factors.
    """
    factors = {}
    cols = sorted(cum_triangle.columns)

    for i in range(len(cols) - 1):
        curr_col = cols[i]
        next_col = cols[i + 1]

        # Only use rows that have data in both columns
        mask = (cum_triangle[curr_col] > 0) & (cum_triangle[next_col] > 0)
        if mask.sum() == 0:
            factors[curr_col] = 1.0
            continue

        # Volume-weighted average
        numerator = cum_triangle.loc[mask, next_col].sum()
        denominator = cum_triangle.loc[mask, curr_col].sum()
        factors[curr_col] = numerator / denominator if denominator > 0 else 1.0

    return factors


def estimate_ibnr(cum_triangle, factors):
    """
    Project ultimate claims/amounts using chain-ladder factors.
    Returns DataFrame with current, ultimate, and IBNR columns.
    """
    cols = sorted(cum_triangle.columns)
    results = []

    for idx, row in cum_triangle.iterrows():
        # Find the latest development lag with data
        current_val = 0
        current_lag = 0
        for col in cols:
            if row[col] > 0:
                current_val = row[col]
                current_lag = col

        # Project to ultimate
        ultimate = current_val
        for col in cols:
            if col >= current_lag and col in factors:
                ultimate *= factors[col]

        ibnr = ultimate - current_val
        results.append({
            "Incurred_Month": idx,
            "Current_Reported": current_val,
            "Development_Lag": current_lag,
            "Ultimate_Projected": round(ultimate, 2),
            "IBNR_Estimate": round(max(ibnr, 0), 2),
        })

    return pd.DataFrame(results).set_index("Incurred_Month")


def monthly_trend_analysis(claims):
    """
    Analyze monthly trends using only complete months.
    Claims count = unique Claim_Number count per month.
    """
    df = _get_complete_months(claims)
    df["Month"] = df["Treatment_Date"].dt.to_period("M")

    monthly = df.groupby("Month").agg(
        Unique_Claims=("Claim_Number", "nunique"),
        Total_Paid=("Amount_Paid", "sum"),
        Avg_Paid=("Amount_Paid", "mean"),
        Unique_Members=("Member_ID", "nunique"),
    ).round(2)

    # Month-over-month growth rates
    monthly["Claims_MoM_Pct"] = monthly["Unique_Claims"].pct_change() * 100
    monthly["Paid_MoM_Pct"] = monthly["Total_Paid"].pct_change() * 100

    return monthly


def forecast_next_months(monthly_trend, n_months=3):
    """
    Simple trend forecast for next N months using linear regression on recent data.
    Uses last 6 complete months for the trend line.
    """
    recent = monthly_trend.tail(6)
    if len(recent) < 3:
        return pd.DataFrame()

    x = np.arange(len(recent))
    forecasts = {}

    for col in ["Unique_Claims", "Total_Paid"]:
        y = recent[col].values.astype(float)
        coeffs = np.polyfit(x, y, 1)
        slope, intercept = coeffs

        future_x = np.arange(len(recent), len(recent) + n_months)
        future_y = slope * future_x + intercept

        last_period = recent.index[-1]
        future_periods = [last_period + i + 1 for i in range(n_months)]
        forecasts[col] = pd.Series(future_y.clip(min=0), index=future_periods)

    return pd.DataFrame(forecasts).round(2)


def ibnr_by_organization(claims):
    """Run IBNR estimation separately for each organization."""
    results = {}
    for org in claims["Organization"].unique():
        org_claims = claims[claims["Organization"] == org]
        _, cum_tri = build_development_triangle(org_claims)
        if cum_tri.empty:
            continue
        factors = chain_ladder_factors(cum_tri)
        ibnr = estimate_ibnr(cum_tri, factors)
        ibnr["Organization"] = org
        results[org] = ibnr
    return results


def summary_report(claims):
    """Generate a comprehensive IBNR summary."""
    # Overall development triangle
    inc_tri, cum_tri = build_development_triangle(claims)
    amt_tri, amt_cum_tri = build_amount_triangle(claims)

    # Chain-ladder factors
    count_factors = chain_ladder_factors(cum_tri)
    amount_factors = chain_ladder_factors(amt_cum_tri)

    # IBNR estimates
    count_ibnr = estimate_ibnr(cum_tri, count_factors)
    amount_ibnr = estimate_ibnr(amt_cum_tri, amount_factors)

    # Monthly trends (complete months only)
    trend = monthly_trend_analysis(claims)

    # Forecast
    forecast = forecast_next_months(trend)

    return {
        "incremental_triangle": inc_tri,
        "cumulative_triangle": cum_tri,
        "amount_cumulative_triangle": amt_cum_tri,
        "count_factors": count_factors,
        "amount_factors": amount_factors,
        "count_ibnr": count_ibnr,
        "amount_ibnr": amount_ibnr,
        "monthly_trend": trend,
        "forecast": forecast,
    }


# ── Charts ─────────────────────────────────────────────────────────────

def plot_development_triangle_heatmap(cum_triangle, title="Cumulative Claims Development Triangle"):
    """Heatmap of the development triangle."""
    if cum_triangle.empty:
        return
    # Show last 12 months for readability
    display = cum_triangle.tail(12)
    fig, ax = plt.subplots(figsize=(14, 8))
    sns.heatmap(display.astype(float), annot=True, fmt=".0f", cmap="YlOrRd",
                ax=ax, linewidths=0.5)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_xlabel("Development Lag (Months)")
    ax.set_ylabel("Incurred Month")
    ax.set_yticklabels([str(p) for p in display.index], rotation=0)
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "development_triangle.png", dpi=150)
    plt.close(fig)


def plot_ibnr_estimates(count_ibnr, amount_ibnr):
    """Bar chart of IBNR estimates by incurred month."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

    # Count IBNR
    recent = count_ibnr.tail(12)
    x = [str(p) for p in recent.index]
    ax1.bar(x, recent["Current_Reported"], label="Reported", color="steelblue", alpha=0.8)
    ax1.bar(x, recent["IBNR_Estimate"], bottom=recent["Current_Reported"],
            label="IBNR Estimate", color="coral", alpha=0.8)
    ax1.set_title("Claims Count: Reported vs IBNR Estimate", fontsize=12, fontweight="bold")
    ax1.set_ylabel("Unique Claims")
    ax1.legend()
    ax1.tick_params(axis="x", rotation=45)

    # Amount IBNR
    recent_amt = amount_ibnr.tail(12)
    x2 = [str(p) for p in recent_amt.index]
    ax2.bar(x2, recent_amt["Current_Reported"], label="Reported", color="steelblue", alpha=0.8)
    ax2.bar(x2, recent_amt["IBNR_Estimate"], bottom=recent_amt["Current_Reported"],
            label="IBNR Estimate", color="coral", alpha=0.8)
    ax2.set_title("Amount Paid: Reported vs IBNR Estimate", fontsize=12, fontweight="bold")
    ax2.set_ylabel("Amount (Naira)")
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(format_naira))
    ax2.legend()
    ax2.tick_params(axis="x", rotation=45)

    plt.suptitle("IBNR Analysis (Chain-Ladder Method)", fontsize=14, fontweight="bold")
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "ibnr_estimates.png", dpi=150)
    plt.close(fig)


def plot_monthly_trend_with_forecast(trend, forecast):
    """Monthly trend with forecast overlay."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

    # Claims count trend
    x = [str(p) for p in trend.index]
    ax1.plot(x, trend["Unique_Claims"], color="steelblue", marker="o", linewidth=2, label="Actual")
    if not forecast.empty:
        fx = [str(p) for p in forecast.index]
        # Connect forecast to last actual point
        all_x = x + fx
        all_y = list(trend["Unique_Claims"]) + list(forecast["Unique_Claims"])
        ax1.plot(fx, forecast["Unique_Claims"], color="red", marker="s",
                 linewidth=2, linestyle="--", label="Forecast")
    ax1.set_title("Monthly Unique Claims (Complete Months Only)", fontsize=12, fontweight="bold")
    ax1.set_ylabel("Unique Claim Count")
    ax1.legend()
    for i, label in enumerate(ax1.get_xticklabels()):
        if i % 3 != 0:
            label.set_visible(False)
    ax1.tick_params(axis="x", rotation=45)

    # Amount paid trend
    ax2.plot(x, trend["Total_Paid"], color="green", marker="o", linewidth=2, label="Actual")
    if not forecast.empty:
        ax2.plot(fx, forecast["Total_Paid"], color="red", marker="s",
                 linewidth=2, linestyle="--", label="Forecast")
    ax2.set_title("Monthly Total Paid (Complete Months Only)", fontsize=12, fontweight="bold")
    ax2.set_ylabel("Amount (Naira)")
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(format_naira))
    ax2.legend()
    for i, label in enumerate(ax2.get_xticklabels()):
        if i % 3 != 0:
            label.set_visible(False)
    ax2.tick_params(axis="x", rotation=45)

    plt.suptitle("Claims Trend & Forecast (Based on Complete Months)", fontsize=14, fontweight="bold")
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "trend_forecast.png", dpi=150)
    plt.close(fig)


def plot_chain_ladder_factors(count_factors, amount_factors):
    """Visualize development factors."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    lags = sorted(count_factors.keys())
    vals = [count_factors[l] for l in lags]
    ax1.bar([str(l) for l in lags], vals, color="steelblue")
    ax1.axhline(y=1.0, color="red", linestyle="--", alpha=0.5)
    ax1.set_title("Count Development Factors", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Development Lag (Months)")
    ax1.set_ylabel("Age-to-Age Factor")

    lags2 = sorted(amount_factors.keys())
    vals2 = [amount_factors[l] for l in lags2]
    ax2.bar([str(l) for l in lags2], vals2, color="coral")
    ax2.axhline(y=1.0, color="red", linestyle="--", alpha=0.5)
    ax2.set_title("Amount Development Factors", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Development Lag (Months)")
    ax2.set_ylabel("Age-to-Age Factor")

    plt.suptitle("Chain-Ladder Development Factors", fontsize=14, fontweight="bold")
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "chain_ladder_factors.png", dpi=150)
    plt.close(fig)


def generate_all_charts(report):
    """Generate all IBNR charts."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plot_development_triangle_heatmap(report["cumulative_triangle"])
    plot_ibnr_estimates(report["count_ibnr"], report["amount_ibnr"])
    plot_monthly_trend_with_forecast(report["monthly_trend"], report["forecast"])
    plot_chain_ladder_factors(report["count_factors"], report["amount_factors"])

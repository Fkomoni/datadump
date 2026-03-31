"""
Claims analysis module.
Analyzes insurance claims across organizations: costs, providers, departments,
diagnosis patterns, rejection rates, and trends.
"""

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "reports"


def format_naira(x, _=None):
    if x >= 1_000_000:
        return f"N{x/1_000_000:.1f}M"
    elif x >= 1_000:
        return f"N{x/1_000:.0f}K"
    return f"N{x:.0f}"


def summary_by_organization(claims):
    """High-level claims summary per organization."""
    summary = claims.groupby("Organization").agg(
        Total_Claims=("Claim_Number", "count"),
        Total_Claimed=("Amount_Claimed", "sum"),
        Total_Paid=("Amount_Paid", "sum"),
        Avg_Claim=("Amount_Paid", "mean"),
        Unique_Members=("Member_ID", "nunique"),
        Unique_Providers=("Provider", "nunique"),
    ).round(2)
    summary["Payout_Ratio"] = (summary["Total_Paid"] / summary["Total_Claimed"] * 100).round(1)
    return summary.sort_values("Total_Paid", ascending=False)


def top_providers(claims, n=15):
    """Top providers by total amount paid."""
    return (
        claims.groupby("Provider")
        .agg(
            Total_Paid=("Amount_Paid", "sum"),
            Claim_Count=("Claim_Number", "count"),
            Avg_Paid=("Amount_Paid", "mean"),
            Organizations=("Organization", "nunique"),
        )
        .sort_values("Total_Paid", ascending=False)
        .head(n)
        .round(2)
    )


def department_breakdown(claims):
    """Claims breakdown by department/service category."""
    return (
        claims.groupby("Department")
        .agg(
            Total_Paid=("Amount_Paid", "sum"),
            Claim_Count=("Claim_Number", "count"),
            Avg_Paid=("Amount_Paid", "mean"),
        )
        .sort_values("Total_Paid", ascending=False)
        .round(2)
    )


def rejection_analysis(claims):
    """Analyze claim rejections."""
    status_counts = claims["Claim_Status"].value_counts()
    rejected = claims[claims["Claim_Status"].str.contains("Reject|Denied|Declined", case=False, na=False)]
    if rejected.empty:
        return status_counts, pd.DataFrame()

    rejection_reasons = rejected["Rejection_Reason"].value_counts().head(15)
    return status_counts, rejection_reasons


def monthly_trend(claims):
    """Monthly claims trend."""
    df = claims.dropna(subset=["Treatment_Date"]).copy()
    df["Month"] = df["Treatment_Date"].dt.to_period("M")
    return (
        df.groupby("Month")
        .agg(
            Total_Paid=("Amount_Paid", "sum"),
            Claim_Count=("Claim_Number", "count"),
        )
        .sort_index()
    )


def age_distribution(claims):
    """Claims distribution by age group."""
    df = claims.dropna(subset=["Age"]).copy()
    bins = [0, 5, 12, 18, 30, 45, 60, 100]
    labels = ["0-5", "6-12", "13-18", "19-30", "31-45", "46-60", "60+"]
    df["Age_Group"] = pd.cut(df["Age"], bins=bins, labels=labels, right=True)
    return (
        df.groupby("Age_Group", observed=True)
        .agg(
            Total_Paid=("Amount_Paid", "sum"),
            Claim_Count=("Claim_Number", "count"),
            Avg_Paid=("Amount_Paid", "mean"),
        )
        .round(2)
    )


def top_diagnoses(claims, n=20):
    """Most common diagnoses by frequency and cost."""
    df = claims.dropna(subset=["Diagnosis_Description"])
    return (
        df.groupby("Diagnosis_Description")
        .agg(
            Total_Paid=("Amount_Paid", "sum"),
            Claim_Count=("Claim_Number", "count"),
            Avg_Paid=("Amount_Paid", "mean"),
        )
        .sort_values("Total_Paid", ascending=False)
        .head(n)
        .round(2)
    )


def plot_claims_by_org(claims):
    """Bar chart: total claims paid by organization."""
    fig, ax = plt.subplots(figsize=(10, 6))
    summary = summary_by_organization(claims)
    colors = sns.color_palette("viridis", len(summary))
    bars = ax.bar(summary.index, summary["Total_Paid"], color=colors)
    ax.set_title("Total Claims Paid by Organization", fontsize=14, fontweight="bold")
    ax.set_ylabel("Amount Paid (Naira)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(format_naira))
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height, format_naira(height),
                ha="center", va="bottom", fontsize=9)
    plt.xticks(rotation=15)
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "claims_by_organization.png", dpi=150)
    plt.close(fig)


def plot_department_breakdown(claims):
    """Horizontal bar chart: top departments by cost."""
    fig, ax = plt.subplots(figsize=(10, 7))
    dept = department_breakdown(claims).head(15)
    colors = sns.color_palette("magma", len(dept))
    ax.barh(dept.index[::-1], dept["Total_Paid"][::-1], color=colors)
    ax.set_title("Top 15 Departments by Claims Paid", fontsize=14, fontweight="bold")
    ax.set_xlabel("Amount Paid (Naira)")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(format_naira))
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "department_breakdown.png", dpi=150)
    plt.close(fig)


def plot_monthly_trend(claims):
    """Line chart: monthly claims trend."""
    trend = monthly_trend(claims)
    if trend.empty:
        return
    fig, ax1 = plt.subplots(figsize=(12, 6))
    x = [str(p) for p in trend.index]
    ax1.bar(x, trend["Total_Paid"], alpha=0.4, color="steelblue", label="Amount Paid")
    ax1.set_ylabel("Amount Paid (Naira)", color="steelblue")
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(format_naira))
    ax2 = ax1.twinx()
    ax2.plot(x, trend["Claim_Count"], color="red", marker="o", linewidth=2, label="Claim Count")
    ax2.set_ylabel("Number of Claims", color="red")
    ax1.set_title("Monthly Claims Trend", fontsize=14, fontweight="bold")
    ax1.tick_params(axis="x", rotation=45)
    # Show every 3rd label to avoid crowding
    for i, label in enumerate(ax1.get_xticklabels()):
        if i % 3 != 0:
            label.set_visible(False)
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "monthly_claims_trend.png", dpi=150)
    plt.close(fig)


def plot_age_distribution(claims):
    """Bar chart: claims by age group."""
    age = age_distribution(claims)
    if age.empty:
        return
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    colors = sns.color_palette("coolwarm", len(age))
    ax1.bar(age.index.astype(str), age["Claim_Count"], color=colors)
    ax1.set_title("Claim Count by Age Group", fontsize=12, fontweight="bold")
    ax1.set_ylabel("Number of Claims")
    ax2.bar(age.index.astype(str), age["Avg_Paid"], color=colors)
    ax2.set_title("Average Claim Amount by Age Group", fontsize=12, fontweight="bold")
    ax2.set_ylabel("Average Amount Paid (Naira)")
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(format_naira))
    plt.suptitle("Claims Analysis by Age Group", fontsize=14, fontweight="bold")
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "age_distribution.png", dpi=150)
    plt.close(fig)


def plot_top_diagnoses(claims):
    """Horizontal bar: top diagnoses by cost."""
    diag = top_diagnoses(claims, n=12)
    if diag.empty:
        return
    fig, ax = plt.subplots(figsize=(10, 7))
    colors = sns.color_palette("RdYlGn_r", len(diag))
    ax.barh(diag.index[::-1], diag["Total_Paid"][::-1], color=colors)
    ax.set_title("Top 12 Diagnoses by Total Cost", fontsize=14, fontweight="bold")
    ax.set_xlabel("Amount Paid (Naira)")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(format_naira))
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "top_diagnoses.png", dpi=150)
    plt.close(fig)


def generate_all_charts(claims):
    """Generate all claims charts."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plot_claims_by_org(claims)
    plot_department_breakdown(claims)
    plot_monthly_trend(claims)
    plot_age_distribution(claims)
    plot_top_diagnoses(claims)

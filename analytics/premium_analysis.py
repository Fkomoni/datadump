"""
Premium and enrollment analysis module.
Analyzes member demographics, premium distribution, enrollment status,
and plan breakdowns.
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


def enrollment_summary(premiums, production):
    """Combine premium and production data for enrollment overview."""
    frames = []
    if not premiums.empty:
        frames.append(premiums)
    if not production.empty:
        frames.append(production)
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True, sort=False)
    return combined


def org_enrollment_stats(enrollment):
    """Enrollment statistics by organization."""
    return enrollment.groupby("Organization").agg(
        Total_Members=("Member_ID", "count"),
        Unique_Members=("Member_ID", "nunique"),
        Active_Members=("Status", lambda x: (x == "Active").sum()),
        Total_Premium=("Premium", "sum"),
        Avg_Premium=("Premium", "mean"),
    ).round(2)


def gender_breakdown(enrollment):
    """Gender distribution across organizations."""
    if "Gender" not in enrollment.columns:
        return pd.DataFrame()
    return enrollment.groupby(["Organization", "Gender"]).size().unstack(fill_value=0)


def relationship_breakdown(enrollment):
    """Member vs dependent breakdown."""
    if "Relationship" not in enrollment.columns:
        return pd.DataFrame()
    df = enrollment.copy()
    df["Relationship"] = df["Relationship"].str.strip()
    df["Member_Type"] = df["Relationship"].apply(
        lambda x: "Principal" if "Main" in str(x) or "Principal" in str(x) else "Dependent"
    )
    return df.groupby(["Organization", "Member_Type"]).size().unstack(fill_value=0)


def state_distribution(enrollment, n=15):
    """Top states by member count."""
    if "State" not in enrollment.columns:
        return pd.DataFrame()
    return enrollment["State"].value_counts().head(n)


def plan_distribution(enrollment):
    """Plan type distribution."""
    if "Plan" not in enrollment.columns:
        return pd.DataFrame()
    return enrollment.groupby("Plan").agg(
        Members=("Member_ID", "count"),
        Avg_Premium=("Premium", "mean"),
        Total_Premium=("Premium", "sum"),
    ).sort_values("Members", ascending=False).round(2)


def premium_vs_claims(enrollment, claims):
    """Compare total premiums collected vs claims paid per organization."""
    prem_by_org = enrollment.groupby("Organization")["Premium"].sum()
    claims_by_org = claims.groupby("Organization")["Amount_Paid"].sum()
    comparison = pd.DataFrame({
        "Total_Premium": prem_by_org,
        "Total_Claims_Paid": claims_by_org,
    }).fillna(0)
    comparison["Loss_Ratio"] = (comparison["Total_Claims_Paid"] / comparison["Total_Premium"] * 100).round(1)
    return comparison


def plot_enrollment_by_org(enrollment):
    """Bar chart: enrollment by organization."""
    fig, ax = plt.subplots(figsize=(10, 6))
    stats = org_enrollment_stats(enrollment)
    colors = sns.color_palette("Set2", len(stats))
    bars = ax.bar(stats.index, stats["Total_Members"], color=colors)
    for bar, active in zip(bars, stats["Active_Members"]):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height(),
                f"{int(active)} active", ha="center", va="bottom", fontsize=9)
    ax.set_title("Total Enrollment by Organization", fontsize=14, fontweight="bold")
    ax.set_ylabel("Number of Members")
    plt.xticks(rotation=15)
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "enrollment_by_org.png", dpi=150)
    plt.close(fig)


def plot_gender_distribution(enrollment):
    """Stacked bar chart: gender distribution."""
    gender = gender_breakdown(enrollment)
    if gender.empty:
        return
    fig, ax = plt.subplots(figsize=(10, 6))
    gender.plot(kind="bar", stacked=True, ax=ax, color=sns.color_palette("pastel"))
    ax.set_title("Gender Distribution by Organization", fontsize=14, fontweight="bold")
    ax.set_ylabel("Count")
    ax.legend(title="Gender")
    plt.xticks(rotation=15)
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "gender_distribution.png", dpi=150)
    plt.close(fig)


def plot_state_distribution(enrollment):
    """Horizontal bar: top states."""
    states = state_distribution(enrollment)
    if states.empty:
        return
    fig, ax = plt.subplots(figsize=(10, 7))
    colors = sns.color_palette("ocean", len(states))
    ax.barh(states.index[::-1], states.values[::-1], color=colors)
    ax.set_title("Top 15 States by Member Count", fontsize=14, fontweight="bold")
    ax.set_xlabel("Number of Members")
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "state_distribution.png", dpi=150)
    plt.close(fig)


def plot_loss_ratio(enrollment, claims):
    """Premium vs claims comparison chart."""
    comparison = premium_vs_claims(enrollment, claims)
    if comparison.empty:
        return
    fig, ax = plt.subplots(figsize=(10, 6))
    x = range(len(comparison))
    width = 0.35
    ax.bar([i - width/2 for i in x], comparison["Total_Premium"], width, label="Premium Collected", color="steelblue")
    ax.bar([i + width/2 for i in x], comparison["Total_Claims_Paid"], width, label="Claims Paid", color="coral")
    for i, (_, row) in enumerate(comparison.iterrows()):
        if row["Total_Premium"] > 0:
            ax.text(i, max(row["Total_Premium"], row["Total_Claims_Paid"]),
                    f"LR: {row['Loss_Ratio']}%", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_xticks(list(x))
    ax.set_xticklabels(comparison.index, rotation=15)
    ax.set_title("Premium Collected vs Claims Paid (Loss Ratio)", fontsize=14, fontweight="bold")
    ax.set_ylabel("Amount (Naira)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(format_naira))
    ax.legend()
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "loss_ratio.png", dpi=150)
    plt.close(fig)


def generate_all_charts(enrollment, claims):
    """Generate all premium/enrollment charts."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plot_enrollment_by_org(enrollment)
    plot_gender_distribution(enrollment)
    plot_state_distribution(enrollment)
    plot_loss_ratio(enrollment, claims)

"""
Premium and enrollment analysis module.
Analyzes member demographics, premium distribution, enrollment status,
and plan breakdowns.
"""

import numpy as np
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


def compute_earned_premium(enrollment, as_of=None):
    """
    Calculate earned premium based on the elapsed portion of each policy period.

    Earned Premium = Written Premium * (days elapsed / total policy days)
    Only policies with valid Effective_Date and Expiry_Date are included.
    """
    if as_of is None:
        as_of = pd.Timestamp.now().normalize()
    else:
        as_of = pd.Timestamp(as_of)

    df = enrollment.dropna(subset=["Effective_Date", "Expiry_Date", "Premium"]).copy()
    df = df[df["Premium"] > 0]

    df["Effective_Date"] = pd.to_datetime(df["Effective_Date"], errors="coerce")
    df["Expiry_Date"] = pd.to_datetime(df["Expiry_Date"], errors="coerce")
    df = df.dropna(subset=["Effective_Date", "Expiry_Date"])

    total_days = (df["Expiry_Date"] - df["Effective_Date"]).dt.days
    elapsed_days = (np.minimum(as_of, df["Expiry_Date"]) - df["Effective_Date"]).dt.days
    elapsed_days = elapsed_days.clip(lower=0)

    earning_fraction = (elapsed_days / total_days).clip(upper=1.0)
    df["Earned_Premium"] = df["Premium"] * earning_fraction

    return df


def split_claims_by_status(claims):
    """
    Split claims into Paid, Pipeline, and categorize for MLR.

    - Paid Claims: Claim_Status == 'Paid Claims'
    - Pipeline Claims: Awaiting Payment, Claims for adjudication, In Process
    """
    paid = claims[claims["Claim_Status"] == "Paid Claims"]
    pipeline = claims[claims["Claim_Status"].isin([
        "Awaiting Payment", "Claims for adjudication", "In Process"
    ])]
    return paid, pipeline


def compute_mlr(enrollment, claims, ibnr_by_org=None, as_of=None):
    """
    Medical Loss Ratio per organization.

    MLR = (Paid Claims + Pipeline Claims + IBNR) / Earned Premium

    Args:
        enrollment: Combined enrollment/production DataFrame
        claims: Claims DataFrame
        ibnr_by_org: dict of {org_name: ibnr_df} from ibnr_analysis.ibnr_by_organization()
                     Each df must have an 'IBNR_Estimate' column.
        as_of: Date to compute earned premium as of (default: today)
    """
    # Earned premium by org
    earned_df = compute_earned_premium(enrollment, as_of=as_of)
    earned_by_org = earned_df.groupby("Organization")["Earned_Premium"].sum()
    written_by_org = earned_df.groupby("Organization")["Premium"].sum()

    # Paid and pipeline claims by org
    paid, pipeline = split_claims_by_status(claims)
    paid_by_org = paid.groupby("Organization")["Amount_Paid"].sum()
    pipeline_by_org = pipeline.groupby("Organization")["Amount_Claimed"].sum()

    # IBNR by org
    ibnr_series = {}
    if ibnr_by_org:
        for org, df in ibnr_by_org.items():
            ibnr_series[org] = df["IBNR_Estimate"].sum()
    ibnr_by_org_s = pd.Series(ibnr_series, name="IBNR")

    # Build MLR table
    mlr = pd.DataFrame({
        "Written_Premium": written_by_org,
        "Earned_Premium": earned_by_org,
        "Paid_Claims": paid_by_org,
        "Pipeline_Claims": pipeline_by_org,
        "IBNR": ibnr_by_org_s,
    }).fillna(0)

    mlr["Total_Incurred"] = mlr["Paid_Claims"] + mlr["Pipeline_Claims"] + mlr["IBNR"]
    mlr["MLR"] = (mlr["Total_Incurred"] / mlr["Earned_Premium"] * 100).round(1)
    mlr["MLR"] = mlr["MLR"].replace([np.inf, -np.inf], np.nan)

    return mlr.round(2)


def premium_vs_claims(enrollment, claims, ibnr_by_org=None, as_of=None):
    """
    MLR comparison: (Paid + Pipeline + IBNR) / Earned Premium per organization.
    This replaces the old simple loss ratio calculation.
    """
    return compute_mlr(enrollment, claims, ibnr_by_org=ibnr_by_org, as_of=as_of)


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


def plot_mlr(enrollment, claims, ibnr_by_org=None, as_of=None):
    """Stacked bar chart: Earned Premium vs (Paid + Pipeline + IBNR) with MLR labels."""
    mlr = compute_mlr(enrollment, claims, ibnr_by_org=ibnr_by_org, as_of=as_of)
    if mlr.empty:
        return
    fig, ax = plt.subplots(figsize=(12, 7))
    x = np.arange(len(mlr))
    width = 0.35

    # Earned premium bars
    ax.bar(x - width/2, mlr["Earned_Premium"], width, label="Earned Premium", color="steelblue")

    # Stacked incurred bars: Paid + Pipeline + IBNR
    ax.bar(x + width/2, mlr["Paid_Claims"], width, label="Paid Claims", color="coral")
    ax.bar(x + width/2, mlr["Pipeline_Claims"], width, bottom=mlr["Paid_Claims"],
           label="Pipeline Claims", color="orange")
    ax.bar(x + width/2, mlr["IBNR"], width,
           bottom=mlr["Paid_Claims"] + mlr["Pipeline_Claims"],
           label="IBNR", color="gold")

    # MLR labels
    for i, (_, row) in enumerate(mlr.iterrows()):
        top = max(row["Earned_Premium"], row["Total_Incurred"])
        mlr_val = row["MLR"]
        label = f"MLR: {mlr_val:.1f}%" if pd.notna(mlr_val) else "MLR: N/A"
        ax.text(i, top * 1.02, label, ha="center", va="bottom", fontsize=10, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(mlr.index, rotation=15)
    ax.set_title("Medical Loss Ratio: (Paid + Pipeline + IBNR) / Earned Premium",
                 fontsize=14, fontweight="bold")
    ax.set_ylabel("Amount (Naira)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(format_naira))
    ax.legend(loc="upper right")
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "mlr.png", dpi=150)
    plt.close(fig)


def generate_all_charts(enrollment, claims, ibnr_by_org=None, as_of=None):
    """Generate all premium/enrollment charts."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plot_enrollment_by_org(enrollment)
    plot_gender_distribution(enrollment)
    plot_state_distribution(enrollment)
    plot_mlr(enrollment, claims, ibnr_by_org=ibnr_by_org, as_of=as_of)

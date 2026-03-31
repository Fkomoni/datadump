"""
Hospital network analysis module.
Analyzes provider network coverage by geography, specialty, and category.
"""

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "reports"


def network_summary(hospitals):
    """Overall hospital network summary."""
    return hospitals.groupby("Organization").agg(
        Total_Providers=("Provider_Name", "count"),
        Unique_Providers=("Provider_Name", "nunique"),
        States_Covered=("State", "nunique"),
        Zones_Covered=("Zone", "nunique"),
        Specialties=("Specialty", "nunique"),
    )


def coverage_by_zone(hospitals):
    """Provider count by geographic zone."""
    return hospitals.groupby("Zone").agg(
        Providers=("Provider_Name", "nunique"),
        States=("State", "nunique"),
    ).sort_values("Providers", ascending=False)


def coverage_by_state(hospitals, n=20):
    """Top states by number of providers."""
    return hospitals.groupby("State").agg(
        Providers=("Provider_Name", "nunique"),
        Towns=("Town", "nunique"),
    ).sort_values("Providers", ascending=False).head(n)


def specialty_breakdown(hospitals):
    """Provider distribution by specialty."""
    if "Specialty" not in hospitals.columns:
        return pd.DataFrame()
    return hospitals["Specialty"].value_counts()


def category_breakdown(hospitals):
    """Provider distribution by category (A, B, C, D)."""
    if "Category" not in hospitals.columns:
        return pd.DataFrame()
    return hospitals.groupby(["Organization", "Category"]).size().unstack(fill_value=0)


def coverage_gaps(hospitals):
    """Identify states with fewer than 5 providers."""
    state_counts = hospitals.groupby("State")["Provider_Name"].nunique()
    return state_counts[state_counts < 5].sort_values()


def plot_zone_coverage(hospitals):
    """Bar chart: providers by zone."""
    zone = coverage_by_zone(hospitals)
    if zone.empty:
        return
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = sns.color_palette("Set2", len(zone))
    bars = ax.bar(zone.index, zone["Providers"], color=colors)
    for bar, states in zip(bars, zone["States"]):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height(),
                f"{states} states", ha="center", va="bottom", fontsize=9)
    ax.set_title("Hospital Network Coverage by Zone", fontsize=14, fontweight="bold")
    ax.set_ylabel("Number of Providers")
    plt.xticks(rotation=15)
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "zone_coverage.png", dpi=150)
    plt.close(fig)


def plot_state_coverage(hospitals):
    """Horizontal bar: top states."""
    states = coverage_by_state(hospitals)
    if states.empty:
        return
    fig, ax = plt.subplots(figsize=(10, 8))
    colors = sns.color_palette("flare", len(states))
    ax.barh(states.index[::-1], states["Providers"][::-1], color=colors)
    ax.set_title("Top 20 States by Provider Count", fontsize=14, fontweight="bold")
    ax.set_xlabel("Number of Providers")
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "state_coverage.png", dpi=150)
    plt.close(fig)


def plot_specialty_pie(hospitals):
    """Pie chart: specialty distribution."""
    spec = specialty_breakdown(hospitals)
    if spec.empty:
        return
    # Group small categories
    threshold = spec.sum() * 0.02
    major = spec[spec >= threshold]
    other = spec[spec < threshold].sum()
    if other > 0:
        major["Other"] = other

    fig, ax = plt.subplots(figsize=(10, 8))
    colors = sns.color_palette("husl", len(major))
    ax.pie(major.values, labels=major.index, autopct="%1.1f%%", colors=colors, startangle=90)
    ax.set_title("Hospital Network by Specialty", fontsize=14, fontweight="bold")
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "specialty_distribution.png", dpi=150)
    plt.close(fig)


def generate_all_charts(hospitals):
    """Generate all hospital network charts."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plot_zone_coverage(hospitals)
    plot_state_coverage(hospitals)
    plot_specialty_pie(hospitals)

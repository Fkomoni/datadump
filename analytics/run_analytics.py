#!/usr/bin/env python3
"""
Main analytics runner.
Loads all data, performs analysis, generates charts, and outputs a summary report.

Usage:
    python analytics/run_analytics.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from pathlib import Path
from analytics.data_loader import (
    load_claims, load_premiums, load_production, load_hospitals, load_benefits,
)
from analytics import claims_analysis, premium_analysis, hospital_analysis, ibnr_analysis

REPORT_DIR = Path(__file__).resolve().parent.parent / "reports"


def section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def print_table(df, max_rows=20):
    if isinstance(df, pd.Series):
        df = df.to_frame()
    with pd.option_context("display.max_rows", max_rows, "display.max_columns", 20,
                           "display.width", 120, "display.float_format", "{:,.2f}".format):
        print(df)


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Load Data ──────────────────────────────────────────────────────
    section("LOADING DATA")

    print("Loading claims data...")
    claims = load_claims()
    print(f"  -> {len(claims):,} claim records loaded")

    print("Loading premium data...")
    premiums = load_premiums()
    print(f"  -> {len(premiums):,} premium records loaded")

    print("Loading production/enrollment data...")
    production = load_production()
    print(f"  -> {len(production):,} production records loaded")

    print("Loading hospital network data...")
    hospitals = load_hospitals()
    print(f"  -> {len(hospitals):,} hospital records loaded")

    print("Loading benefit data...")
    benefits = load_benefits()
    print(f"  -> {len(benefits)} organization benefit files loaded")

    enrollment = premium_analysis.enrollment_summary(premiums, production)
    print(f"\n  Total enrollment records: {len(enrollment):,}")

    # ── Claims Analysis ────────────────────────────────────────────────
    section("CLAIMS ANALYSIS")

    print(">> Claims Summary by Organization")
    print_table(claims_analysis.summary_by_organization(claims))

    print("\n>> Top 15 Providers by Total Paid")
    print_table(claims_analysis.top_providers(claims))

    print("\n>> Department Breakdown (Top 15)")
    print_table(claims_analysis.department_breakdown(claims).head(15))

    print("\n>> Claims by Age Group")
    print_table(claims_analysis.age_distribution(claims))

    print("\n>> Top 20 Diagnoses by Cost")
    print_table(claims_analysis.top_diagnoses(claims))

    status_counts, rejection_reasons = claims_analysis.rejection_analysis(claims)
    print("\n>> Claim Status Distribution")
    print_table(status_counts)
    if not rejection_reasons.empty:
        print("\n>> Top Rejection Reasons")
        print_table(rejection_reasons)

    print("\n>> Monthly Claims Trend (last 12 months)")
    trend = claims_analysis.monthly_trend(claims)
    if not trend.empty:
        print_table(trend.tail(12))

    # ── Premium & Enrollment Analysis ──────────────────────────────────
    section("PREMIUM & ENROLLMENT ANALYSIS")

    if not enrollment.empty:
        print(">> Enrollment by Organization")
        print_table(premium_analysis.org_enrollment_stats(enrollment))

        print("\n>> Gender Distribution")
        print_table(premium_analysis.gender_breakdown(enrollment))

        print("\n>> Member vs Dependent Breakdown")
        print_table(premium_analysis.relationship_breakdown(enrollment))

        print("\n>> Top 15 States by Enrollment")
        print_table(premium_analysis.state_distribution(enrollment))

        print("\n>> Plan Distribution")
        print_table(premium_analysis.plan_distribution(enrollment).head(10))

        print("\n>> Premium vs Claims (Loss Ratio)")
        print_table(premium_analysis.premium_vs_claims(enrollment, claims))
    else:
        print("No enrollment data available.")

    # ── Hospital Network Analysis ──────────────────────────────────────
    section("HOSPITAL NETWORK ANALYSIS")

    if not hospitals.empty:
        print(">> Network Summary by Organization")
        print_table(hospital_analysis.network_summary(hospitals))

        print("\n>> Coverage by Zone")
        print_table(hospital_analysis.coverage_by_zone(hospitals))

        print("\n>> Top 20 States by Providers")
        print_table(hospital_analysis.coverage_by_state(hospitals))

        print("\n>> Specialty Breakdown")
        print_table(hospital_analysis.specialty_breakdown(hospitals).head(15))

        print("\n>> Category Distribution by Organization")
        print_table(hospital_analysis.category_breakdown(hospitals))

        gaps = hospital_analysis.coverage_gaps(hospitals)
        if not gaps.empty:
            print(f"\n>> Coverage Gaps ({len(gaps)} states with fewer than 5 providers)")
            print_table(gaps)
    else:
        print("No hospital network data available.")

    # ── IBNR Analysis ──────────────────────────────────────────────────
    section("IBNR ANALYSIS (Incurred But Not Reported)")

    print("Running IBNR estimation using complete months, unique claim IDs...")
    ibnr_report = ibnr_analysis.summary_report(claims)

    print("\n>> Chain-Ladder Development Factors (Claims Count)")
    for lag, factor in sorted(ibnr_report["count_factors"].items()):
        print(f"   Lag {lag} -> {lag+1}: {factor:.4f}")

    print("\n>> Chain-Ladder Development Factors (Amount Paid)")
    for lag, factor in sorted(ibnr_report["amount_factors"].items()):
        print(f"   Lag {lag} -> {lag+1}: {factor:.4f}")

    print("\n>> IBNR Estimates by Incurred Month (Claims Count, last 12)")
    print_table(ibnr_report["count_ibnr"].tail(12))

    print("\n>> IBNR Estimates by Incurred Month (Amount Paid, last 12)")
    print_table(ibnr_report["amount_ibnr"].tail(12))

    total_count_ibnr = ibnr_report["count_ibnr"]["IBNR_Estimate"].sum()
    total_amount_ibnr = ibnr_report["amount_ibnr"]["IBNR_Estimate"].sum()
    print(f"\n>> Total IBNR Reserve Estimate:")
    print(f"   Claims count IBNR: {total_count_ibnr:,.0f} additional claims expected")
    print(f"   Amount IBNR: N{total_amount_ibnr:,.2f}")

    print("\n>> Monthly Trend (Complete Months, Unique Claims, last 12)")
    print_table(ibnr_report["monthly_trend"].tail(12))

    if not ibnr_report["forecast"].empty:
        print("\n>> Forecast (Next 3 Months)")
        print_table(ibnr_report["forecast"])

    print("\n>> IBNR by Organization")
    org_ibnr = ibnr_analysis.ibnr_by_organization(claims)
    for org, df in org_ibnr.items():
        org_total = df["IBNR_Estimate"].sum()
        print(f"   {org}: {org_total:,.0f} additional claims estimated as IBNR")

    # ── Generate Charts ────────────────────────────────────────────────
    section("GENERATING CHARTS")

    print("Generating claims charts...")
    claims_analysis.generate_all_charts(claims)

    if not enrollment.empty:
        print("Generating enrollment charts...")
        premium_analysis.generate_all_charts(enrollment, claims)

    if not hospitals.empty:
        print("Generating hospital network charts...")
        hospital_analysis.generate_all_charts(hospitals)

    print("Generating IBNR charts...")
    ibnr_analysis.generate_all_charts(ibnr_report)

    print(f"\nAll charts saved to: {REPORT_DIR}/")

    # ── Export Summary to Excel ────────────────────────────────────────
    section("EXPORTING SUMMARY REPORT")

    output_file = REPORT_DIR / "analytics_summary.xlsx"
    with pd.ExcelWriter(output_file, engine="xlsxwriter") as writer:
        claims_analysis.summary_by_organization(claims).to_excel(writer, sheet_name="Claims by Org")
        claims_analysis.top_providers(claims).to_excel(writer, sheet_name="Top Providers")
        claims_analysis.department_breakdown(claims).head(20).to_excel(writer, sheet_name="Departments")
        claims_analysis.age_distribution(claims).to_excel(writer, sheet_name="Age Groups")
        claims_analysis.top_diagnoses(claims).to_excel(writer, sheet_name="Top Diagnoses")

        if not enrollment.empty:
            premium_analysis.org_enrollment_stats(enrollment).to_excel(writer, sheet_name="Enrollment Stats")
            premium_analysis.plan_distribution(enrollment).to_excel(writer, sheet_name="Plan Distribution")
            premium_analysis.premium_vs_claims(enrollment, claims).to_excel(writer, sheet_name="Loss Ratio")

        if not hospitals.empty:
            hospital_analysis.network_summary(hospitals).to_excel(writer, sheet_name="Hospital Network")
            hospital_analysis.coverage_by_zone(hospitals).to_excel(writer, sheet_name="Zone Coverage")
            hospital_analysis.coverage_by_state(hospitals).to_excel(writer, sheet_name="State Coverage")

        # IBNR sheets
        ibnr_report["count_ibnr"].to_excel(writer, sheet_name="IBNR Claims Count")
        ibnr_report["amount_ibnr"].to_excel(writer, sheet_name="IBNR Amount")
        ibnr_report["monthly_trend"].to_excel(writer, sheet_name="Monthly Trend")
        if not ibnr_report["forecast"].empty:
            ibnr_report["forecast"].to_excel(writer, sheet_name="Forecast")

    print(f"Summary report exported to: {output_file}")

    # ── Key Insights ───────────────────────────────────────────────────
    section("KEY INSIGHTS")

    total_claims_paid = claims["Amount_Paid"].sum()
    total_claims_count = len(claims)
    avg_claim = claims["Amount_Paid"].mean()

    print(f"1. Total claims processed: {total_claims_count:,}")
    print(f"2. Total amount paid: N{total_claims_paid:,.2f}")
    print(f"3. Average claim amount: N{avg_claim:,.2f}")

    if not enrollment.empty:
        total_enrolled = len(enrollment)
        active = enrollment[enrollment.get("Status", pd.Series()) == "Active"].shape[0]
        total_premium = enrollment["Premium"].sum()
        loss_ratio = (total_claims_paid / total_premium * 100) if total_premium > 0 else 0
        print(f"4. Total enrolled members: {total_enrolled:,} ({active:,} active)")
        print(f"5. Total premium collected: N{total_premium:,.2f}")
        print(f"6. Overall loss ratio: {loss_ratio:.1f}%")

    if not hospitals.empty:
        print(f"7. Hospital network: {hospitals['Provider_Name'].nunique():,} unique providers")
        print(f"8. Geographic coverage: {hospitals['State'].nunique()} states, {hospitals['Zone'].nunique()} zones")

    top_dept = claims_analysis.department_breakdown(claims).head(1)
    if not top_dept.empty:
        print(f"9. Highest-cost department: {top_dept.index[0]} (N{top_dept['Total_Paid'].iloc[0]:,.2f})")

    top_org = claims_analysis.summary_by_organization(claims).head(1)
    if not top_org.empty:
        print(f"10. Largest claims org: {top_org.index[0]} (N{top_org['Total_Paid'].iloc[0]:,.2f})")

    print(f"\n{'='*70}")
    print("  ANALYTICS COMPLETE")
    print(f"  Reports: {REPORT_DIR}/")
    print(f"  Charts: {len(list(REPORT_DIR.glob('*.png')))} PNG files generated")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()

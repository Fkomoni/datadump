#!/usr/bin/env python3
"""Generate branded PENCOM HTML analytics report."""

import pandas as pd
import numpy as np
from pathlib import Path
from analytics.data_loader import load_claims, load_premiums, load_production, load_hospitals
from analytics import claims_analysis, premium_analysis, ibnr_analysis


def fmt(x):
    """Format number as Naira."""
    if abs(x) >= 1_000_000_000:
        return f"&#8358;{x/1_000_000_000:,.2f}B"
    if abs(x) >= 1_000_000:
        return f"&#8358;{x/1_000_000:,.2f}M"
    if abs(x) >= 1_000:
        return f"&#8358;{x/1_000:,.0f}K"
    return f"&#8358;{x:,.0f}"


def fmt_full(x):
    """Full Naira format."""
    return f"&#8358;{x:,.2f}"


def pct(x):
    return f"{x:.1f}%"


def month_label(period):
    """Convert period to full month name, e.g. 'July 2025'."""
    ts = period.to_timestamp()
    return ts.strftime("%B %Y")


def generate_report():
    # Load data
    claims = load_claims()
    premiums = load_premiums()
    production = load_production()
    hospitals = load_hospitals()
    enrollment = premium_analysis.enrollment_summary(premiums, production)

    pc = claims[claims["Organization"] == "PENCOM"]
    pc_enroll = enrollment[enrollment["Organization"] == "PENCOM"]
    pc_hospitals = hospitals[hospitals["Organization"] == "PENCOM"]

    # IBNR
    org_ibnr = ibnr_analysis.ibnr_by_organization(claims)
    _, amt_cum = ibnr_analysis.build_amount_triangle(pc)
    amt_factors = ibnr_analysis.chain_ladder_factors(amt_cum)
    amt_ibnr = ibnr_analysis.estimate_ibnr(amt_cum, amt_factors)
    ibnr_total = amt_ibnr["IBNR_Estimate"].sum()

    # Claims by status
    paid_claims = pc[pc["Claim_Status"] == "Paid Claims"]
    pipeline_claims = pc[pc["Claim_Status"].isin(
        ["Awaiting Payment", "Claims for adjudication", "In Process"]
    )]
    paid_total = paid_claims["Amount_Paid"].sum()
    pipeline_total = pipeline_claims["Amount_Claimed"].sum()
    total_incurred = paid_total + pipeline_total + ibnr_total

    # Earned premium
    earned_df = premium_analysis.compute_earned_premium(pc_enroll)
    earned_total = earned_df["Earned_Premium"].sum()
    written_total = earned_df["Premium"].sum()

    # MLR
    mlr_pct = (total_incurred / earned_total * 100) if earned_total > 0 else 0

    # COR = MLR + Admin (15%) + NHIA (2%)
    admin_pct = 15.0
    nhia_pct = 2.0
    admin_amount = earned_total * admin_pct / 100
    nhia_amount = earned_total * nhia_pct / 100
    cor_pct = mlr_pct + admin_pct + nhia_pct

    # Unique counts
    unique_claims = pc["Claim_Number"].nunique()
    unique_members = pc["Member_ID"].nunique()
    paid_unique_claims = paid_claims["Claim_Number"].nunique()
    paid_unique_members = paid_claims["Member_ID"].nunique()
    avg_per_member = paid_total / paid_unique_members if paid_unique_members > 0 else 0
    avg_per_visit = paid_total / paid_unique_claims if paid_unique_claims > 0 else 0

    # Top 20 providers
    top_prov = pc.groupby("Provider").agg(
        Total_Paid=("Amount_Paid", "sum"),
        Unique_Claims=("Claim_Number", "nunique"),
        Unique_Members=("Member_ID", "nunique"),
    ).sort_values("Total_Paid", ascending=False).head(20)
    top_prov["Pct_of_Total"] = (top_prov["Total_Paid"] / paid_total * 100).round(1)
    top_prov["Avg_Per_Visit"] = (top_prov["Total_Paid"] / top_prov["Unique_Claims"]).round(2)
    top_prov["Avg_Per_Member"] = (top_prov["Total_Paid"] / top_prov["Unique_Members"]).round(2)

    # Department breakdown
    dept = pc.groupby("Department").agg(
        Total_Paid=("Amount_Paid", "sum"),
        Unique_Claims=("Claim_Number", "nunique"),
        Unique_Members=("Member_ID", "nunique"),
    ).sort_values("Total_Paid", ascending=False)
    dept["Pct_of_Total"] = (dept["Total_Paid"] / paid_total * 100).round(1)
    dept["Avg_Per_Visit"] = (dept["Total_Paid"] / dept["Unique_Claims"]).round(2)

    # Age distribution
    df_age = pc.dropna(subset=["Age"]).copy()
    bins = [0, 5, 12, 18, 30, 45, 60, 100]
    labels = ["0-5", "6-12", "13-18", "19-30", "31-45", "46-60", "60+"]
    df_age["Age_Group"] = pd.cut(df_age["Age"], bins=bins, labels=labels, right=True)
    age_dist = df_age.groupby("Age_Group", observed=True).agg(
        Total_Paid=("Amount_Paid", "sum"),
        Unique_Claims=("Claim_Number", "nunique"),
        Unique_Members=("Member_ID", "nunique"),
    ).round(2)
    age_dist["Avg_Per_Visit"] = (age_dist["Total_Paid"] / age_dist["Unique_Claims"]).round(2)
    age_dist["Avg_Per_Member"] = (age_dist["Total_Paid"] / age_dist["Unique_Members"]).round(2)

    # Monthly trend
    df_m = pc.dropna(subset=["Treatment_Date"]).copy()
    df_m["Month"] = df_m["Treatment_Date"].dt.to_period("M")
    monthly = df_m.groupby("Month").agg(
        Unique_Claims=("Claim_Number", "nunique"),
        Total_Paid=("Amount_Paid", "sum"),
        Unique_Members=("Member_ID", "nunique"),
    ).sort_index()
    monthly["Avg_Per_Member"] = (monthly["Total_Paid"] / monthly["Unique_Members"]).round(2)
    monthly["Avg_Per_Visit"] = (monthly["Total_Paid"] / monthly["Unique_Claims"]).round(2)

    # Top diagnoses
    diag = pc.dropna(subset=["Diagnosis_Description"]).groupby("Diagnosis_Description").agg(
        Total_Paid=("Amount_Paid", "sum"),
        Unique_Claims=("Claim_Number", "nunique"),
    ).sort_values("Total_Paid", ascending=False).head(20)
    diag["Avg_Per_Visit"] = (diag["Total_Paid"] / diag["Unique_Claims"]).round(2)

    # Enrollment
    plan_dist = premium_analysis.plan_distribution(pc_enroll) if not pc_enroll.empty else pd.DataFrame()

    # Claim status
    status = pc["Claim_Status"].value_counts()

    # ── Build provider rows ──
    prov_rows = ""
    for i, (name, row) in enumerate(top_prov.iterrows(), 1):
        name_clean = str(name).strip().title()
        prov_rows += f"""<tr>
            <td>{i}</td>
            <td>{name_clean}</td>
            <td class="num">{fmt_full(row['Total_Paid'])}</td>
            <td class="num">{pct(row['Pct_of_Total'])}</td>
            <td class="num">{row['Unique_Claims']:,}</td>
            <td class="num">{row['Unique_Members']:,}</td>
            <td class="num">{fmt_full(row['Avg_Per_Visit'])}</td>
            <td class="num">{fmt_full(row['Avg_Per_Member'])}</td>
        </tr>"""

    # ── Build department rows ──
    dept_rows = ""
    for i, (name, row) in enumerate(dept.head(15).iterrows(), 1):
        dept_rows += f"""<tr>
            <td>{i}</td>
            <td>{name}</td>
            <td class="num">{fmt_full(row['Total_Paid'])}</td>
            <td class="num">{pct(row['Pct_of_Total'])}</td>
            <td class="num">{row['Unique_Claims']:,}</td>
            <td class="num">{fmt_full(row['Avg_Per_Visit'])}</td>
        </tr>"""

    # ── Build age rows ──
    age_rows = ""
    for grp, row in age_dist.iterrows():
        age_rows += f"""<tr>
            <td>{grp}</td>
            <td class="num">{fmt_full(row['Total_Paid'])}</td>
            <td class="num">{row['Unique_Claims']:,}</td>
            <td class="num">{row['Unique_Members']:,}</td>
            <td class="num">{fmt_full(row['Avg_Per_Visit'])}</td>
            <td class="num">{fmt_full(row['Avg_Per_Member'])}</td>
        </tr>"""

    # ── Build monthly rows ──
    monthly_rows = ""
    for period, row in monthly.iterrows():
        monthly_rows += f"""<tr>
            <td>{month_label(period)}</td>
            <td class="num">{row['Unique_Claims']:,}</td>
            <td class="num">{row['Unique_Members']:,}</td>
            <td class="num">{fmt_full(row['Total_Paid'])}</td>
            <td class="num">{fmt_full(row['Avg_Per_Member'])}</td>
            <td class="num">{fmt_full(row['Avg_Per_Visit'])}</td>
        </tr>"""

    # ── Build diagnosis rows ──
    diag_rows = ""
    for i, (name, row) in enumerate(diag.iterrows(), 1):
        diag_rows += f"""<tr>
            <td>{i}</td>
            <td>{name}</td>
            <td class="num">{fmt_full(row['Total_Paid'])}</td>
            <td class="num">{row['Unique_Claims']:,}</td>
            <td class="num">{fmt_full(row['Avg_Per_Visit'])}</td>
        </tr>"""

    # ── Build IBNR rows ──
    ibnr_rows = ""
    for period, row in amt_ibnr.iterrows():
        ibnr_rows += f"""<tr>
            <td>{month_label(period)}</td>
            <td class="num">{fmt_full(row['Current_Reported'])}</td>
            <td class="num">{row['Development_Lag']}</td>
            <td class="num">{fmt_full(row['Ultimate_Projected'])}</td>
            <td class="num highlight">{fmt_full(row['IBNR_Estimate'])}</td>
        </tr>"""

    # ── Plan rows ──
    plan_rows = ""
    if not plan_dist.empty:
        for name, row in plan_dist.iterrows():
            plan_rows += f"""<tr>
                <td>{name}</td>
                <td class="num">{int(row['Members']):,}</td>
                <td class="num">{fmt_full(row['Avg_Premium'])}</td>
                <td class="num">{fmt_full(row['Total_Premium'])}</td>
            </tr>"""

    # ── Status rows ──
    status_rows = ""
    for s, count in status.items():
        status_rows += f"<tr><td>{s}</td><td class='num'>{count:,}</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PENCOM Analytics Report</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

  :root {{
    --navy: #1A1A2E;
    --crimson: #C8102E;
    --coral: #E87722;
    --cream: #FAF7F2;
    --light-blue: #E8F4FD;
    --soft-pink: #FDF0ED;
    --light-grey: #F4F4F6;
    --medium-grey: #E8E8EC;
    --text-dark: #1A1A2E;
    --text-muted: #6B7280;
    --white: #FFFFFF;
  }}

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    font-family: 'Inter', 'Leadway Book', 'Segoe UI', sans-serif;
    background: var(--cream);
    color: var(--text-dark);
    line-height: 1.6;
    font-size: 14px;
  }}

  .container {{
    max-width: 1140px;
    margin: 0 auto;
    padding: 40px 20px;
  }}

  /* Header */
  .header {{
    background: var(--navy);
    color: var(--white);
    padding: 50px 40px;
    border-radius: 16px;
    margin-bottom: 30px;
    position: relative;
    overflow: hidden;
  }}
  .header::after {{
    content: '';
    position: absolute;
    top: 0; right: 0;
    width: 300px; height: 100%;
    background: linear-gradient(135deg, transparent 40%, rgba(200,16,46,0.15) 100%);
  }}
  .header h1 {{
    font-family: 'Inter', 'Leadway Bold', sans-serif;
    font-weight: 800;
    font-size: 32px;
    letter-spacing: -0.5px;
    margin-bottom: 6px;
  }}
  .header .subtitle {{
    font-weight: 400;
    font-size: 15px;
    opacity: 0.75;
  }}
  .header .org-label {{
    display: inline-block;
    background: var(--crimson);
    color: white;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 16px;
  }}

  /* Section */
  .section {{
    background: var(--white);
    border-radius: 14px;
    padding: 32px;
    margin-bottom: 24px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }}
  .section h2 {{
    font-family: 'Inter', 'Leadway Bold', sans-serif;
    font-weight: 700;
    font-size: 20px;
    color: var(--navy);
    margin-bottom: 20px;
    padding-bottom: 10px;
    border-bottom: 2px solid var(--medium-grey);
  }}
  .section h2 span.accent {{
    color: var(--crimson);
  }}

  /* KPI Grid */
  .kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 10px;
  }}
  .kpi {{
    background: var(--white);
    border: 1px solid var(--medium-grey);
    border-radius: 12px;
    padding: 22px 18px;
    text-align: center;
    transition: transform 0.15s;
  }}
  .kpi:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.06); }}
  .kpi .label {{
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: var(--text-muted);
    margin-bottom: 8px;
  }}
  .kpi .value {{
    font-family: 'Inter', 'Leadway Heavy', sans-serif;
    font-weight: 800;
    font-size: 22px;
    color: var(--navy);
  }}
  .kpi.highlight {{ border-color: var(--crimson); border-width: 2px; }}
  .kpi.highlight .value {{ color: var(--crimson); }}
  .kpi.coral .value {{ color: var(--coral); }}
  .kpi.coral {{ border-color: var(--coral); border-width: 2px; }}

  /* MLR / COR Card */
  .mlr-card {{
    background: var(--navy);
    color: var(--white);
    border-radius: 14px;
    padding: 32px;
    margin-bottom: 24px;
  }}
  .mlr-card h2 {{
    color: var(--white);
    border-bottom-color: rgba(255,255,255,0.15);
    font-weight: 700;
    font-size: 20px;
    margin-bottom: 6px;
    padding-bottom: 0;
    border: none;
  }}
  .mlr-card .formula {{
    font-size: 13px;
    opacity: 0.6;
    margin-bottom: 24px;
    font-style: italic;
  }}
  .mlr-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
  }}
  .mlr-table {{
    width: 100%;
    border-collapse: collapse;
  }}
  .mlr-table td {{
    padding: 10px 12px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    font-size: 13px;
  }}
  .mlr-table td:last-child {{ text-align: right; font-weight: 600; }}
  .mlr-table tr.total td {{
    border-top: 2px solid var(--crimson);
    font-weight: 800;
    font-size: 15px;
    padding-top: 14px;
  }}
  .mlr-table tr.total td:last-child {{ color: var(--coral); }}
  .cor-result {{
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    background: rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 30px;
  }}
  .cor-result .big-number {{
    font-family: 'Inter', 'Leadway Heavy', sans-serif;
    font-size: 56px;
    font-weight: 900;
    color: var(--coral);
    line-height: 1;
  }}
  .cor-result .big-label {{
    font-size: 14px;
    opacity: 0.7;
    margin-top: 8px;
  }}
  .cor-breakdown {{
    margin-top: 20px;
    display: flex;
    gap: 16px;
    justify-content: center;
    flex-wrap: wrap;
  }}
  .cor-chip {{
    background: rgba(255,255,255,0.08);
    border-radius: 8px;
    padding: 10px 16px;
    text-align: center;
    min-width: 100px;
  }}
  .cor-chip .chip-val {{ font-weight: 800; font-size: 18px; }}
  .cor-chip .chip-lbl {{ font-size: 10px; opacity: 0.6; text-transform: uppercase; letter-spacing: 0.5px; }}

  /* Tables */
  .data-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }}
  .data-table thead th {{
    background: var(--navy);
    color: var(--white);
    padding: 12px 10px;
    text-align: left;
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  .data-table thead th.num {{ text-align: right; }}
  .data-table tbody td {{
    padding: 10px;
    border-bottom: 1px solid var(--light-grey);
  }}
  .data-table tbody td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .data-table tbody td.highlight {{ color: var(--crimson); font-weight: 700; }}
  .data-table tbody tr:hover {{ background: var(--light-blue); }}
  .data-table tbody tr:nth-child(even) {{ background: var(--light-grey); }}
  .data-table tbody tr:nth-child(even):hover {{ background: var(--light-blue); }}

  /* Footer */
  .footer {{
    text-align: center;
    color: var(--text-muted);
    font-size: 11px;
    margin-top: 20px;
    padding: 20px;
  }}

  @media print {{
    body {{ background: white; }}
    .section {{ box-shadow: none; break-inside: avoid; }}
    .kpi:hover {{ transform: none; }}
  }}
</style>
</head>
<body>
<div class="container">

  <!-- HEADER -->
  <div class="header">
    <div class="org-label">National Pension Commission</div>
    <h1>PENCOM Analytics Report</h1>
    <div class="subtitle">Claims, Premium &amp; IBNR Analysis &nbsp;|&nbsp; {pd.Timestamp.now().strftime('%d %B %Y')}</div>
  </div>

  <!-- KPI OVERVIEW -->
  <div class="section">
    <h2>Executive <span class="accent">Overview</span></h2>
    <div class="kpi-grid">
      <div class="kpi highlight">
        <div class="label">Total Incurred</div>
        <div class="value">{fmt(total_incurred)}</div>
      </div>
      <div class="kpi">
        <div class="label">Paid Claims</div>
        <div class="value">{fmt(paid_total)}</div>
      </div>
      <div class="kpi">
        <div class="label">Pipeline Claims</div>
        <div class="value">{fmt(pipeline_total)}</div>
      </div>
      <div class="kpi coral">
        <div class="label">IBNR Reserve</div>
        <div class="value">{fmt(ibnr_total)}</div>
      </div>
      <div class="kpi">
        <div class="label">Earned Premium</div>
        <div class="value">{fmt(earned_total)}</div>
      </div>
      <div class="kpi">
        <div class="label">Written Premium</div>
        <div class="value">{fmt(written_total)}</div>
      </div>
      <div class="kpi">
        <div class="label">Unique Members</div>
        <div class="value">{unique_members:,}</div>
      </div>
      <div class="kpi">
        <div class="label">Unique Claims</div>
        <div class="value">{unique_claims:,}</div>
      </div>
      <div class="kpi">
        <div class="label">Avg Paid Per Member</div>
        <div class="value">{fmt(avg_per_member)}</div>
      </div>
      <div class="kpi">
        <div class="label">Avg Paid Per Visit</div>
        <div class="value">{fmt(avg_per_visit)}</div>
      </div>
    </div>
  </div>

  <!-- MLR & COR -->
  <div class="mlr-card">
    <h2>Medical Loss Ratio &amp; Combined Operating Ratio</h2>
    <div class="formula">MLR = (Paid Claims + Pipeline Claims + IBNR) / Earned Premium &nbsp;&nbsp;|&nbsp;&nbsp; COR = MLR + Admin + NHIA</div>

    <div class="mlr-grid">
      <div>
        <table class="mlr-table">
          <tr><td>Paid Claims</td><td>{fmt_full(paid_total)}</td></tr>
          <tr><td>Pipeline Claims</td><td>{fmt_full(pipeline_total)}</td></tr>
          <tr><td>IBNR</td><td>{fmt_full(ibnr_total)}</td></tr>
          <tr class="total"><td>Total Incurred</td><td>{fmt_full(total_incurred)}</td></tr>
          <tr><td style="padding-top:16px;">Earned Premium</td><td style="padding-top:16px;">{fmt_full(earned_total)}</td></tr>
          <tr><td>Written Premium</td><td>{fmt_full(written_total)}</td></tr>
          <tr class="total"><td>MLR</td><td>{pct(mlr_pct)}</td></tr>
          <tr><td style="padding-top:16px;">Admin Expense (15%)</td><td style="padding-top:16px;">{fmt_full(admin_amount)}</td></tr>
          <tr><td>NHIA Levy (2%)</td><td>{fmt_full(nhia_amount)}</td></tr>
          <tr class="total"><td>Combined Operating Ratio</td><td>{pct(cor_pct)}</td></tr>
        </table>
      </div>
      <div class="cor-result">
        <div class="big-number">{pct(cor_pct)}</div>
        <div class="big-label">Combined Operating Ratio</div>
        <div class="cor-breakdown">
          <div class="cor-chip">
            <div class="chip-val">{pct(mlr_pct)}</div>
            <div class="chip-lbl">MLR</div>
          </div>
          <div class="cor-chip">
            <div class="chip-val">{pct(admin_pct)}</div>
            <div class="chip-lbl">Admin</div>
          </div>
          <div class="cor-chip">
            <div class="chip-val">{pct(nhia_pct)}</div>
            <div class="chip-lbl">NHIA</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- IBNR -->
  <div class="section">
    <h2>IBNR <span class="accent">Estimate</span> by Incurred Month</h2>
    <table class="data-table">
      <thead>
        <tr>
          <th>Incurred Month</th>
          <th class="num">Current Reported</th>
          <th class="num">Dev. Lag</th>
          <th class="num">Ultimate Projected</th>
          <th class="num">IBNR Estimate</th>
        </tr>
      </thead>
      <tbody>
        {ibnr_rows}
        <tr style="background:var(--soft-pink);font-weight:700;">
          <td>Total</td>
          <td class="num">{fmt_full(amt_ibnr['Current_Reported'].sum())}</td>
          <td></td>
          <td class="num">{fmt_full(amt_ibnr['Ultimate_Projected'].sum())}</td>
          <td class="num highlight">{fmt_full(ibnr_total)}</td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- TOP 20 PROVIDERS -->
  <div class="section">
    <h2>Top 20 Paid <span class="accent">Providers</span></h2>
    <table class="data-table">
      <thead>
        <tr>
          <th>#</th>
          <th>Provider</th>
          <th class="num">Total Paid</th>
          <th class="num">% of Total</th>
          <th class="num">Unique Claims</th>
          <th class="num">Unique Members</th>
          <th class="num">Avg Per Visit</th>
          <th class="num">Avg Per Member</th>
        </tr>
      </thead>
      <tbody>{prov_rows}</tbody>
    </table>
  </div>

  <!-- DEPARTMENT BREAKDOWN -->
  <div class="section">
    <h2>Department <span class="accent">Breakdown</span></h2>
    <table class="data-table">
      <thead>
        <tr>
          <th>#</th>
          <th>Department</th>
          <th class="num">Total Paid</th>
          <th class="num">% of Total</th>
          <th class="num">Unique Claims</th>
          <th class="num">Avg Per Visit</th>
        </tr>
      </thead>
      <tbody>{dept_rows}</tbody>
    </table>
  </div>

  <!-- AGE DISTRIBUTION -->
  <div class="section">
    <h2>Claims by <span class="accent">Age Group</span></h2>
    <table class="data-table">
      <thead>
        <tr>
          <th>Age Group</th>
          <th class="num">Total Paid</th>
          <th class="num">Unique Claims</th>
          <th class="num">Unique Members</th>
          <th class="num">Avg Per Visit</th>
          <th class="num">Avg Per Member</th>
        </tr>
      </thead>
      <tbody>{age_rows}</tbody>
    </table>
  </div>

  <!-- MONTHLY TREND -->
  <div class="section">
    <h2>Monthly Claims <span class="accent">Trend</span></h2>
    <table class="data-table">
      <thead>
        <tr>
          <th>Month</th>
          <th class="num">Unique Claims</th>
          <th class="num">Unique Members</th>
          <th class="num">Total Paid</th>
          <th class="num">Avg Per Member</th>
          <th class="num">Avg Per Visit</th>
        </tr>
      </thead>
      <tbody>{monthly_rows}</tbody>
    </table>
  </div>

  <!-- TOP DIAGNOSES -->
  <div class="section">
    <h2>Top 20 <span class="accent">Diagnoses</span> by Cost</h2>
    <table class="data-table">
      <thead>
        <tr>
          <th>#</th>
          <th>Diagnosis</th>
          <th class="num">Total Paid</th>
          <th class="num">Unique Claims</th>
          <th class="num">Avg Per Visit</th>
        </tr>
      </thead>
      <tbody>{diag_rows}</tbody>
    </table>
  </div>

  <!-- PLAN DISTRIBUTION -->
  <div class="section">
    <h2>Enrollment by <span class="accent">Plan</span></h2>
    <table class="data-table">
      <thead>
        <tr>
          <th>Plan</th>
          <th class="num">Members</th>
          <th class="num">Avg Premium</th>
          <th class="num">Total Premium</th>
        </tr>
      </thead>
      <tbody>{plan_rows}</tbody>
    </table>
  </div>

  <!-- CLAIM STATUS -->
  <div class="section">
    <h2>Claim <span class="accent">Status</span> Distribution</h2>
    <table class="data-table">
      <thead><tr><th>Status</th><th class="num">Count</th></tr></thead>
      <tbody>{status_rows}</tbody>
    </table>
  </div>

  <div class="footer">
    PENCOM Analytics Report &nbsp;|&nbsp; Leadway Health Insurance &nbsp;|&nbsp; Generated {pd.Timestamp.now().strftime('%d %B %Y')}
  </div>

</div>
</body>
</html>"""

    Path("reports/PENCOM_Analytics_Report.html").write_text(html)
    print("Report saved to: reports/PENCOM_Analytics_Report.html")


if __name__ == "__main__":
    generate_report()

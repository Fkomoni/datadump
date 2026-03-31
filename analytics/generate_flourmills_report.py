#!/usr/bin/env python3
"""Generate branded Flour Mills HTML analytics report with subsidiary comparison."""

import pandas as pd
import numpy as np
from pathlib import Path
from analytics.data_loader import load_claims, load_premiums, load_production, load_hospitals
from analytics import claims_analysis, premium_analysis, ibnr_analysis


def fmt(x):
    if abs(x) >= 1_000_000_000:
        return f"&#8358;{x/1_000_000_000:,.2f}B"
    if abs(x) >= 1_000_000:
        return f"&#8358;{x/1_000_000:,.2f}M"
    if abs(x) >= 1_000:
        return f"&#8358;{x/1_000:,.0f}K"
    return f"&#8358;{x:,.0f}"


def fmt_full(x):
    return f"&#8358;{x:,.2f}"


def pct(x):
    return f"{x:.1f}%"


def month_label(period):
    return period.to_timestamp().strftime("%B %Y")


def short_name(name):
    """Shorten subsidiary names for display."""
    mapping = {
        "FLOUR MILLS OF NIGERIA PLC": "FMN Plc (HQ)",
        "FLOUR MILLS  – BAGCO LAGOS": "Bagco Lagos",
        "FLOUR MILLS  – BAGCO KANO": "Bagco Kano",
        "FLOUR MILLS  – GOLDEN PASTA": "Golden Pasta",
        "GOLDEN PASTA AGBARA": "Golden Pasta Agbara",
        "NORTHERN NIGERIA FLOUR MILLS PLC": "NNFM Plc",
        "FLOUR MILLS - PREMIUM EDIBLE OILS LIMITED PEOPLE": "Premium Edible Oils",
        "SUNTI GOLDEN SUGAR": "Sunti Golden Sugar",
        "FLOUR MILLS PLC - PREMIUM CASSAVA PRODUCTS LIMITED": "Premium Cassava Products",
        "NNFM CONTRACT STAFF": "NNFM Contract Staff",
    }
    return mapping.get(name.strip(), name.strip().title())


def generate_report():
    # Load data
    claims = load_claims()
    premiums = load_premiums()
    production = load_production()
    hospitals = load_hospitals()
    enrollment = premium_analysis.enrollment_summary(premiums, production)

    fm = claims[claims["Organization"] == "Flour Mills"]
    fm_enroll = enrollment[enrollment["Organization"] == "Flour Mills"]
    fm_hospitals = hospitals[hospitals["Organization"] == "Flour Mills"]

    # ── IBNR ──
    org_ibnr = ibnr_analysis.ibnr_by_organization(claims)
    _, amt_cum = ibnr_analysis.build_amount_triangle(fm)
    amt_factors = ibnr_analysis.chain_ladder_factors(amt_cum)
    amt_ibnr_raw = ibnr_analysis.estimate_ibnr(amt_cum, amt_factors)

    # Only reserve IBNR from December 2025 onwards, with ₦95M ultimate floor
    ibnr_start = pd.Period("2025-12", "M")
    ultimate_floor = 95_000_000
    amt_ibnr = amt_ibnr_raw.copy()
    for idx in amt_ibnr.index:
        if idx < ibnr_start:
            amt_ibnr.at[idx, "IBNR_Estimate"] = 0.0
            amt_ibnr.at[idx, "Ultimate_Projected"] = amt_ibnr.at[idx, "Current_Reported"]
        else:
            current = amt_ibnr.at[idx, "Current_Reported"]
            raw_ultimate = amt_ibnr.at[idx, "Ultimate_Projected"]
            adjusted_ultimate = max(raw_ultimate, ultimate_floor)
            amt_ibnr.at[idx, "Ultimate_Projected"] = round(adjusted_ultimate, 2)
            amt_ibnr.at[idx, "IBNR_Estimate"] = round(max(adjusted_ultimate - current, 0), 2)

    # Filter display to Dec 2025 onwards
    amt_ibnr_display = amt_ibnr[amt_ibnr.index >= ibnr_start]
    ibnr_total = amt_ibnr["IBNR_Estimate"].sum()

    # Update org_ibnr dict so MLR uses the adjusted IBNR for Flour Mills
    org_ibnr["Flour Mills"] = amt_ibnr

    # ── Claims by status ──
    paid_claims = fm[fm["Claim_Status"] == "Paid Claims"]
    pipeline_claims = fm[fm["Claim_Status"].isin(
        ["Awaiting Payment", "Claims for adjudication", "In Process"]
    )]
    paid_total = paid_claims["Amount_Paid"].sum()
    pipeline_total = pipeline_claims["Amount_Claimed"].sum()
    total_incurred = paid_total + pipeline_total + ibnr_total

    # ── Earned premium ──
    earned_df = premium_analysis.compute_earned_premium(fm_enroll)
    earned_total = earned_df["Earned_Premium"].sum()
    written_total = earned_df["Premium"].sum()

    # ── MLR & COR ──
    mlr_pct = (total_incurred / earned_total * 100) if earned_total > 0 else 0
    admin_pct = 15.0
    nhia_pct = 2.0
    admin_amount = earned_total * admin_pct / 100
    nhia_amount = earned_total * nhia_pct / 100
    cor_pct = mlr_pct + admin_pct + nhia_pct

    # ── Unique counts ──
    unique_claims = fm["Claim_Number"].nunique()
    unique_members = fm["Member_ID"].nunique()
    paid_unique_claims = paid_claims["Claim_Number"].nunique()
    paid_unique_members = paid_claims["Member_ID"].nunique()
    avg_per_member = paid_total / paid_unique_members if paid_unique_members > 0 else 0
    avg_per_visit = paid_total / paid_unique_claims if paid_unique_claims > 0 else 0

    # ════════════════════════════════════════════════════════════════════
    # SUBSIDIARY COMPARISON
    # ════════════════════════════════════════════════════════════════════

    # Claims by subsidiary
    sub_claims = fm.groupby("Group_Code").agg(
        Total_Paid=("Amount_Paid", "sum"),
        Total_Claimed=("Amount_Claimed", "sum"),
        Unique_Claims=("Claim_Number", "nunique"),
        Unique_Members=("Member_ID", "nunique"),
        Unique_Providers=("Provider", "nunique"),
    ).sort_values("Total_Paid", ascending=False)
    sub_claims["Avg_Per_Member"] = (sub_claims["Total_Paid"] / sub_claims["Unique_Members"]).round(2)
    sub_claims["Avg_Per_Visit"] = (sub_claims["Total_Paid"] / sub_claims["Unique_Claims"]).round(2)
    sub_claims["Pct_of_Total"] = (sub_claims["Total_Paid"] / paid_total * 100).round(1)

    # Earned premium by subsidiary
    if "Client_Name" in earned_df.columns:
        sub_earned = earned_df.groupby("Client_Name").agg(
            Written_Premium=("Premium", "sum"),
            Earned_Premium=("Earned_Premium", "sum"),
            Members=("Member_ID", "count"),
        )
    else:
        sub_earned = pd.DataFrame()

    # Merge for subsidiary MLR
    sub_comparison_rows = ""
    for i, (sub_name, row) in enumerate(sub_claims.iterrows(), 1):
        sname = short_name(sub_name)
        s_paid = fm[(fm["Group_Code"] == sub_name) & (fm["Claim_Status"] == "Paid Claims")]["Amount_Paid"].sum()
        s_pipeline = fm[(fm["Group_Code"] == sub_name) & (fm["Claim_Status"].isin(
            ["Awaiting Payment", "Claims for adjudication", "In Process"]
        ))]["Amount_Claimed"].sum()

        # Earned premium for this subsidiary
        s_earned = 0
        s_written = 0
        if not sub_earned.empty and sub_name in sub_earned.index:
            s_earned = sub_earned.loc[sub_name, "Earned_Premium"]
            s_written = sub_earned.loc[sub_name, "Written_Premium"]

        s_incurred = s_paid + s_pipeline
        s_mlr = (s_incurred / s_earned * 100) if s_earned > 0 else 0
        s_cor = s_mlr + admin_pct + nhia_pct if s_earned > 0 else 0

        mlr_class = "danger" if s_mlr > 100 else ("warning" if s_mlr > 85 else "good")

        sub_comparison_rows += f"""<tr>
            <td>{i}</td>
            <td><strong>{sname}</strong></td>
            <td class="num">{row['Unique_Members']:,}</td>
            <td class="num">{row['Unique_Claims']:,}</td>
            <td class="num">{fmt_full(s_earned)}</td>
            <td class="num">{fmt_full(s_incurred)}</td>
            <td class="num">{fmt_full(row['Avg_Per_Member'])}</td>
            <td class="num">{fmt_full(row['Avg_Per_Visit'])}</td>
            <td class="num {mlr_class}">{pct(s_mlr) if s_earned > 0 else 'N/A'}</td>
            <td class="num {mlr_class}">{pct(s_cor) if s_earned > 0 else 'N/A'}</td>
        </tr>"""

    # ── Loss Ratio by Plan ──
    earned_by_plan = earned_df.groupby("Plan").agg(
        Written_Premium=("Premium", "sum"),
        Earned_Premium=("Earned_Premium", "sum"),
        Members=("Member_ID", "count"),
    )

    # Map claims Scheme to Plan — only the 3 core plans
    valid_plans = ["PLUS - Flour Mills", "PRO - Flour Mills", "MAX- Flour Mills"]
    plan_paid = fm[(fm["Claim_Status"] == "Paid Claims") & (fm["Scheme"].isin(valid_plans))].groupby("Scheme").agg(
        Paid_Claims=("Amount_Paid", "sum"),
        Unique_Claims=("Claim_Number", "nunique"),
        Unique_Members=("Member_ID", "nunique"),
    )
    plan_pipeline = fm[fm["Claim_Status"].isin(
        ["Awaiting Payment", "Claims for adjudication", "In Process"]
    ) & (fm["Scheme"].isin(valid_plans))].groupby("Scheme").agg(
        Pipeline_Claims=("Amount_Claimed", "sum"),
    )

    plan_lr = earned_by_plan.join(plan_paid, how="outer").join(plan_pipeline, how="outer").fillna(0)
    plan_lr = plan_lr[plan_lr.index.isin(valid_plans)]
    plan_lr["Total_Incurred"] = plan_lr["Paid_Claims"] + plan_lr["Pipeline_Claims"]
    plan_lr["MLR"] = np.where(
        plan_lr["Earned_Premium"] > 0,
        (plan_lr["Total_Incurred"] / plan_lr["Earned_Premium"] * 100),
        0
    )
    plan_lr["COR"] = plan_lr["MLR"] + admin_pct + nhia_pct
    plan_lr["Avg_Per_Member"] = np.where(
        plan_lr["Unique_Members"] > 0,
        plan_lr["Paid_Claims"] / plan_lr["Unique_Members"],
        0
    )
    plan_lr["Avg_Per_Visit"] = np.where(
        plan_lr["Unique_Claims"] > 0,
        plan_lr["Paid_Claims"] / plan_lr["Unique_Claims"],
        0
    )
    plan_lr = plan_lr.sort_values("Paid_Claims", ascending=False)

    plan_lr_rows = ""
    for i, (plan_name, row) in enumerate(plan_lr.iterrows(), 1):
        p_mlr = row["MLR"]
        p_cor = row["COR"]
        mlr_cls = "danger" if p_mlr > 100 else ("warning" if p_mlr > 85 else "good")
        has_earned = row["Earned_Premium"] > 0
        plan_lr_rows += f"""<tr>
            <td>{i}</td>
            <td><strong>{plan_name}</strong></td>
            <td class="num">{int(row['Members']):,}</td>
            <td class="num">{int(row['Unique_Members']):,}</td>
            <td class="num">{int(row['Unique_Claims']):,}</td>
            <td class="num">{fmt_full(row['Earned_Premium'])}</td>
            <td class="num">{fmt_full(row['Paid_Claims'])}</td>
            <td class="num">{fmt_full(row['Pipeline_Claims'])}</td>
            <td class="num">{fmt_full(row['Total_Incurred'])}</td>
            <td class="num">{fmt_full(row['Avg_Per_Member'])}</td>
            <td class="num">{fmt_full(row['Avg_Per_Visit'])}</td>
            <td class="num {mlr_cls}">{pct(p_mlr) if has_earned else 'N/A'}</td>
            <td class="num {mlr_cls}">{pct(p_cor) if has_earned else 'N/A'}</td>
        </tr>"""

    # ── Top 20 providers ──
    top_prov = fm.groupby("Provider").agg(
        Total_Paid=("Amount_Paid", "sum"),
        Unique_Claims=("Claim_Number", "nunique"),
        Unique_Members=("Member_ID", "nunique"),
    ).sort_values("Total_Paid", ascending=False).head(20)
    top_prov["Pct_of_Total"] = (top_prov["Total_Paid"] / paid_total * 100).round(1)
    top_prov["Avg_Per_Visit"] = (top_prov["Total_Paid"] / top_prov["Unique_Claims"]).round(2)
    top_prov["Avg_Per_Member"] = (top_prov["Total_Paid"] / top_prov["Unique_Members"]).round(2)

    prov_rows = ""
    for i, (name, row) in enumerate(top_prov.iterrows(), 1):
        prov_rows += f"""<tr>
            <td>{i}</td>
            <td>{str(name).strip().title()}</td>
            <td class="num">{fmt_full(row['Total_Paid'])}</td>
            <td class="num">{pct(row['Pct_of_Total'])}</td>
            <td class="num">{row['Unique_Claims']:,}</td>
            <td class="num">{row['Unique_Members']:,}</td>
            <td class="num">{fmt_full(row['Avg_Per_Visit'])}</td>
            <td class="num">{fmt_full(row['Avg_Per_Member'])}</td>
        </tr>"""

    # ── Department breakdown ──
    dept = fm.groupby("Department").agg(
        Total_Paid=("Amount_Paid", "sum"),
        Unique_Claims=("Claim_Number", "nunique"),
        Unique_Members=("Member_ID", "nunique"),
    ).sort_values("Total_Paid", ascending=False)
    dept["Pct_of_Total"] = (dept["Total_Paid"] / paid_total * 100).round(1)
    dept["Avg_Per_Visit"] = (dept["Total_Paid"] / dept["Unique_Claims"]).round(2)

    dept_rows = ""
    for i, (name, row) in enumerate(dept.head(15).iterrows(), 1):
        dept_rows += f"""<tr>
            <td>{i}</td><td>{name}</td>
            <td class="num">{fmt_full(row['Total_Paid'])}</td>
            <td class="num">{pct(row['Pct_of_Total'])}</td>
            <td class="num">{row['Unique_Claims']:,}</td>
            <td class="num">{fmt_full(row['Avg_Per_Visit'])}</td>
        </tr>"""

    # ── Age distribution ──
    df_age = fm.dropna(subset=["Age"]).copy()
    bins = [0, 5, 12, 18, 30, 45, 60, 100]
    labels = ["0-5", "6-12", "13-18", "19-30", "31-45", "46-60", "60+"]
    df_age["Age_Group"] = pd.cut(df_age["Age"], bins=bins, labels=labels, right=True)
    age_dist = df_age.groupby("Age_Group", observed=True).agg(
        Total_Paid=("Amount_Paid", "sum"),
        Unique_Claims=("Claim_Number", "nunique"),
        Unique_Members=("Member_ID", "nunique"),
    )
    age_dist["Avg_Per_Visit"] = (age_dist["Total_Paid"] / age_dist["Unique_Claims"]).round(2)
    age_dist["Avg_Per_Member"] = (age_dist["Total_Paid"] / age_dist["Unique_Members"]).round(2)

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

    # ── Monthly trend ──
    df_m = fm.dropna(subset=["Treatment_Date"]).copy()
    df_m["Month"] = df_m["Treatment_Date"].dt.to_period("M")
    monthly = df_m.groupby("Month").agg(
        Unique_Claims=("Claim_Number", "nunique"),
        Total_Paid=("Amount_Paid", "sum"),
        Unique_Members=("Member_ID", "nunique"),
    ).sort_index()
    monthly["Avg_Per_Member"] = (monthly["Total_Paid"] / monthly["Unique_Members"]).round(2)
    monthly["Avg_Per_Visit"] = (monthly["Total_Paid"] / monthly["Unique_Claims"]).round(2)

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

    # ── Top diagnoses ──
    diag = fm.dropna(subset=["Diagnosis_Description"]).groupby("Diagnosis_Description").agg(
        Total_Paid=("Amount_Paid", "sum"),
        Unique_Claims=("Claim_Number", "nunique"),
    ).sort_values("Total_Paid", ascending=False).head(20)
    diag["Avg_Per_Visit"] = (diag["Total_Paid"] / diag["Unique_Claims"]).round(2)

    diag_rows = ""
    for i, (name, row) in enumerate(diag.iterrows(), 1):
        diag_rows += f"""<tr>
            <td>{i}</td><td>{name}</td>
            <td class="num">{fmt_full(row['Total_Paid'])}</td>
            <td class="num">{row['Unique_Claims']:,}</td>
            <td class="num">{fmt_full(row['Avg_Per_Visit'])}</td>
        </tr>"""

    # ── IBNR rows (Dec 2025 onwards only) ──
    ibnr_rows = ""
    for period, row in amt_ibnr_display.iterrows():
        ibnr_rows += f"""<tr>
            <td>{month_label(period)}</td>
            <td class="num">{fmt_full(row['Current_Reported'])}</td>
            <td class="num">{row['Development_Lag']}</td>
            <td class="num">{fmt_full(row['Ultimate_Projected'])}</td>
            <td class="num highlight">{fmt_full(row['IBNR_Estimate'])}</td>
        </tr>"""

    # ── Plan rows ──
    plan_dist = premium_analysis.plan_distribution(fm_enroll)
    plan_rows = ""
    for name, row in plan_dist.iterrows():
        plan_rows += f"""<tr>
            <td>{name}</td>
            <td class="num">{int(row['Members']):,}</td>
            <td class="num">{fmt_full(row['Avg_Premium'])}</td>
            <td class="num">{fmt_full(row['Total_Premium'])}</td>
        </tr>"""

    # ── Status rows (unique claim IDs, not claim lines) ──
    status = fm.groupby("Claim_Status")["Claim_Number"].nunique().sort_values(ascending=False)
    status_rows = ""
    for s, count in status.items():
        status_rows += f"<tr><td>{s}</td><td class='num'>{count:,}</td></tr>"

    # ── Subsidiary dept heatmap: top 5 depts x all subs ──
    top5_depts = dept.head(5).index.tolist()
    sub_dept_rows = ""
    for dept_name in top5_depts:
        sub_dept_rows += f"<tr><td><strong>{dept_name}</strong></td>"
        for sub_name, _ in sub_claims.iterrows():
            sub_dept = fm[(fm["Group_Code"] == sub_name) & (fm["Department"] == dept_name)]
            val = sub_dept["Amount_Paid"].sum()
            sub_dept_rows += f'<td class="num">{fmt(val) if val > 0 else "—"}</td>'
        sub_dept_rows += "</tr>"

    sub_headers = "".join(f"<th class='num'>{short_name(n)}</th>" for n in sub_claims.index)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Flour Mills Group Analytics Report</title>
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
    font-family: 'Inter', 'Leadway Book', sans-serif;
    background: var(--cream);
    color: var(--text-dark);
    line-height: 1.6;
    font-size: 14px;
  }}

  .container {{ max-width: 1200px; margin: 0 auto; padding: 40px 20px; }}

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
    font-weight: 800; font-size: 32px; letter-spacing: -0.5px; margin-bottom: 6px;
  }}
  .header .subtitle {{ font-weight: 400; font-size: 15px; opacity: 0.75; }}
  .header .org-label {{
    display: inline-block; background: var(--crimson); color: white;
    padding: 4px 14px; border-radius: 20px; font-size: 11px; font-weight: 700;
    letter-spacing: 1px; text-transform: uppercase; margin-bottom: 16px;
  }}
  .header .sub-count {{
    display: inline-block; background: var(--coral); color: white;
    padding: 4px 14px; border-radius: 20px; font-size: 11px; font-weight: 700;
    letter-spacing: 1px; margin-left: 8px;
  }}

  .section {{
    background: var(--white); border-radius: 14px; padding: 32px;
    margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }}
  .section h2 {{
    font-family: 'Inter', 'Leadway Bold', sans-serif;
    font-weight: 700; font-size: 20px; color: var(--navy);
    margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid var(--medium-grey);
  }}
  .section h2 span.accent {{ color: var(--crimson); }}

  .kpi-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px; margin-bottom: 10px;
  }}
  .kpi {{
    background: var(--white); border: 1px solid var(--medium-grey);
    border-radius: 12px; padding: 22px 18px; text-align: center;
    transition: transform 0.15s;
  }}
  .kpi:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.06); }}
  .kpi .label {{
    font-size: 11px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.8px; color: var(--text-muted); margin-bottom: 8px;
  }}
  .kpi .value {{
    font-family: 'Inter', 'Leadway Heavy', sans-serif;
    font-weight: 800; font-size: 22px; color: var(--navy);
  }}
  .kpi.highlight {{ border-color: var(--crimson); border-width: 2px; }}
  .kpi.highlight .value {{ color: var(--crimson); }}
  .kpi.coral {{ border-color: var(--coral); border-width: 2px; }}
  .kpi.coral .value {{ color: var(--coral); }}

  .mlr-card {{
    background: var(--navy); color: var(--white);
    border-radius: 14px; padding: 32px; margin-bottom: 24px;
  }}
  .mlr-card h2 {{
    color: var(--white); border: none; font-weight: 700;
    font-size: 20px; margin-bottom: 6px; padding-bottom: 0;
  }}
  .mlr-card .formula {{
    font-size: 13px; opacity: 0.6; margin-bottom: 24px; font-style: italic;
  }}
  .mlr-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
  .mlr-table {{ width: 100%; border-collapse: collapse; }}
  .mlr-table td {{
    padding: 10px 12px; border-bottom: 1px solid rgba(255,255,255,0.08); font-size: 13px;
  }}
  .mlr-table td:last-child {{ text-align: right; font-weight: 600; }}
  .mlr-table tr.total td {{
    border-top: 2px solid var(--crimson); font-weight: 800; font-size: 15px; padding-top: 14px;
  }}
  .mlr-table tr.total td:last-child {{ color: var(--coral); }}
  .cor-result {{
    display: flex; align-items: center; justify-content: center; flex-direction: column;
    background: rgba(255,255,255,0.06); border-radius: 12px; padding: 30px;
  }}
  .cor-result .big-number {{
    font-family: 'Inter', 'Leadway Heavy', sans-serif;
    font-size: 56px; font-weight: 900; color: var(--coral); line-height: 1;
  }}
  .cor-result .big-label {{ font-size: 14px; opacity: 0.7; margin-top: 8px; }}
  .cor-breakdown {{
    margin-top: 20px; display: flex; gap: 16px; justify-content: center; flex-wrap: wrap;
  }}
  .cor-chip {{
    background: rgba(255,255,255,0.08); border-radius: 8px;
    padding: 10px 16px; text-align: center; min-width: 100px;
  }}
  .cor-chip .chip-val {{ font-weight: 800; font-size: 18px; }}
  .cor-chip .chip-lbl {{ font-size: 10px; opacity: 0.6; text-transform: uppercase; letter-spacing: 0.5px; }}

  .data-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  .data-table thead th {{
    background: var(--navy); color: var(--white); padding: 12px 10px; text-align: left;
    font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;
  }}
  .data-table thead th.num {{ text-align: right; }}
  .data-table tbody td {{ padding: 10px; border-bottom: 1px solid var(--light-grey); }}
  .data-table tbody td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .data-table tbody td.highlight {{ color: var(--crimson); font-weight: 700; }}
  .data-table tbody tr:hover {{ background: var(--light-blue); }}
  .data-table tbody tr:nth-child(even) {{ background: var(--light-grey); }}
  .data-table tbody tr:nth-child(even):hover {{ background: var(--light-blue); }}

  .data-table tbody td.good {{ color: #16a34a; font-weight: 700; }}
  .data-table tbody td.warning {{ color: var(--coral); font-weight: 700; }}
  .data-table tbody td.danger {{ color: var(--crimson); font-weight: 700; }}

  .scroll-x {{ overflow-x: auto; }}

  .footer {{
    text-align: center; color: var(--text-muted); font-size: 11px;
    margin-top: 20px; padding: 20px;
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

  <div class="header">
    <div>
      <span class="org-label">Flour Mills of Nigeria Group</span>
      <span class="sub-count">9 Subsidiaries</span>
    </div>
    <h1>Flour Mills Group Analytics Report</h1>
    <div class="subtitle">Claims, Premium, IBNR &amp; Subsidiary Comparison &nbsp;|&nbsp; {pd.Timestamp.now().strftime('%d %B %Y')}</div>
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
    <div class="formula">MLR = (Paid Claims + Pipeline Claims + IBNR) / Earned Premium &nbsp;&nbsp;|&nbsp;&nbsp; COR = MLR + Admin (15%) + NHIA (2%)</div>
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

  <!-- SUBSIDIARY COMPARISON -->
  <div class="section">
    <h2>Subsidiary <span class="accent">Comparison</span></h2>
    <p style="color:var(--text-muted);font-size:13px;margin-bottom:16px;">
      MLR colour coding: <span style="color:#16a34a;font-weight:700;">Green &lt; 85%</span> &nbsp;
      <span style="color:var(--coral);font-weight:700;">Orange 85-100%</span> &nbsp;
      <span style="color:var(--crimson);font-weight:700;">Red &gt; 100%</span>
    </p>
    <div class="scroll-x">
    <table class="data-table">
      <thead>
        <tr>
          <th>#</th>
          <th>Subsidiary</th>
          <th class="num">Members</th>
          <th class="num">Unique Claims</th>
          <th class="num">Earned Premium</th>
          <th class="num">Total Claims</th>
          <th class="num">Avg/Member</th>
          <th class="num">Avg/Visit</th>
          <th class="num">LR</th>
          <th class="num">COR</th>
        </tr>
      </thead>
      <tbody>{sub_comparison_rows}</tbody>
    </table>
    </div>
  </div>

  <!-- SUBSIDIARY x DEPARTMENT HEATMAP -->
  <div class="section">
    <h2>Top 5 Departments by <span class="accent">Subsidiary</span></h2>
    <div class="scroll-x">
    <table class="data-table">
      <thead><tr><th>Department</th>{sub_headers}</tr></thead>
      <tbody>{sub_dept_rows}</tbody>
    </table>
    </div>
  </div>

  <!-- LOSS RATIO BY PLAN -->
  <div class="section">
    <h2>Loss Ratio by <span class="accent">Plan</span></h2>
    <p style="color:var(--text-muted);font-size:13px;margin-bottom:16px;">
      MLR colour coding: <span style="color:#16a34a;font-weight:700;">Green &lt; 85%</span> &nbsp;
      <span style="color:var(--coral);font-weight:700;">Orange 85-100%</span> &nbsp;
      <span style="color:var(--crimson);font-weight:700;">Red &gt; 100%</span>
    </p>
    <div class="scroll-x">
    <table class="data-table">
      <thead>
        <tr>
          <th>#</th>
          <th>Plan</th>
          <th class="num">Enrolled</th>
          <th class="num">Claimants</th>
          <th class="num">Unique Claims</th>
          <th class="num">Earned Premium</th>
          <th class="num">Paid Claims</th>
          <th class="num">Pipeline</th>
          <th class="num">Total Incurred</th>
          <th class="num">Avg/Member</th>
          <th class="num">Avg/Visit</th>
          <th class="num">MLR</th>
          <th class="num">COR</th>
        </tr>
      </thead>
      <tbody>{plan_lr_rows}</tbody>
    </table>
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
          <td class="num">{fmt_full(amt_ibnr_display['Current_Reported'].sum())}</td>
          <td></td>
          <td class="num">{fmt_full(amt_ibnr_display['Ultimate_Projected'].sum())}</td>
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
          <th>#</th><th>Provider</th>
          <th class="num">Total Paid</th><th class="num">% of Total</th>
          <th class="num">Unique Claims</th><th class="num">Unique Members</th>
          <th class="num">Avg Per Visit</th><th class="num">Avg Per Member</th>
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
          <th>#</th><th>Department</th>
          <th class="num">Total Paid</th><th class="num">% of Total</th>
          <th class="num">Unique Claims</th><th class="num">Avg Per Visit</th>
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
          <th class="num">Total Paid</th><th class="num">Unique Claims</th>
          <th class="num">Unique Members</th><th class="num">Avg Per Visit</th>
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
          <th>Month</th><th class="num">Unique Claims</th>
          <th class="num">Unique Members</th><th class="num">Total Paid</th>
          <th class="num">Avg Per Member</th><th class="num">Avg Per Visit</th>
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
        <tr><th>#</th><th>Diagnosis</th>
          <th class="num">Total Paid</th><th class="num">Unique Claims</th>
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
      <thead><tr><th>Plan</th><th class="num">Members</th><th class="num">Avg Premium</th><th class="num">Total Premium</th></tr></thead>
      <tbody>{plan_rows}</tbody>
    </table>
  </div>

  <!-- CLAIM STATUS -->
  <div class="section">
    <h2>Claim <span class="accent">Status</span> Distribution</h2>
    <p style="color:var(--text-muted);font-size:12px;margin-bottom:12px;">Counted by unique claim ID, not claim lines</p>
    <table class="data-table">
      <thead><tr><th>Status</th><th class="num">Unique Claims</th></tr></thead>
      <tbody>{status_rows}</tbody>
    </table>
  </div>

  <div class="footer">
    Flour Mills Group Analytics Report &nbsp;|&nbsp; Leadway Health Insurance &nbsp;|&nbsp; Generated {pd.Timestamp.now().strftime('%d %B %Y')}
  </div>

</div>
</body>
</html>"""

    Path("reports/FlourMills_Analytics_Report.html").write_text(html)
    print("Report saved to: reports/FlourMills_Analytics_Report.html")


if __name__ == "__main__":
    generate_report()

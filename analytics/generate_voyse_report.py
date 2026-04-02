#!/usr/bin/env python3
"""Generate branded Voyse Technologies HTML analytics report."""

import pandas as pd
import numpy as np
import base64
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "reports"


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


def classify_drug(desc):
    if pd.isna(desc):
        return "Unresolved"
    d = str(desc).upper()
    if any(x in d for x in ["ARTEMETH","ARTHEMETER","COARTEM","LONART","ARTESUNATE","MALARI","EMAL","LUMARTEM","PALUTHER","QUININE","CHLOROQUINE","FANSIDAR","AMATEM","P ALAXIN","ARTEETHER"]):
        return "Antimalarials"
    if any(x in d for x in ["CEFTRIAXONE","AUGMENTIN","AMOXICILLIN","AMOXICILIN","AMOXYCILLIN","AMOXYL","AMOXIL","AMOVIN","AMOXICLAV","AMOKSICLAV","AZITHROMYCIN","CIPROFLOXACIN","CIPROTAB","METRONIDAZOLE","FLAGYL","CEFUROXIME","ROCEPHIN","ERYTHROMYCIN","DOXYCYCLINE","GENTAMICIN","GENTAMYCIN","CLOXACILLIN","AMPICILLIN","LEVOFLOXACIN","ZINNAT","CEFIXIME","AMPICLOX","SEPTRIN","CEFTAZIDIME","CLARITHROMYCIN","MEROPENEM","MERONEM","CILOXAN","VANCOMYCIN","AMIKACIN","CEFPODOXIME"]):
        return "Antibiotics"
    if any(x in d for x in ["PARACETAMOL","PARASAM","DICLOFENAC","IBUPROFEN","TRAMADOL","PIROXICAM","KETOPROFEN","FELDENE","CELEBREX","VOLTAREN","ARTHROTEC","COCODAMOL","PENTAZOCINE","MORPHINE","NEUROGESIC","ORPHENADRINE","NORFLEX","SIRDALUD","PREGABALIN","LYRICA"]):
        return "Analgesics / Pain Relief"
    if any(x in d for x in ["OMEPRAZOLE","GAVISCON","GASCOL","BUSCOPAN","RANITIDINE","LOPERAMIDE","LANSOPRAZOLE","PANTOPRAZOLE","GESTID","ESOMEPRAZOLE","RABEPRAZOLE","FLORANORM","ORS","ORAL REHYDRA","ONDASENTRON","ONDANSETRON","LACTULOSE","METOCLOPRAMIDE"]):
        return "Gastrointestinal"
    if any(x in d for x in ["EYE DROP","ALOMIDE","TEARS NATURALE","EFEMOLINE","LATANOPROST","NEPAFENAC","XALATAN","COSOPT","BRIMONIDINE","AZOPT","HYPROMELLOSE","OPHTHALMIC"]):
        return "Eye Care"
    if any(x in d for x in ["LORATIDINE","LORATADINE","CETIRIZINE","PIRITON","CHLORPHENIRAMINE","FEXOFENADINE","PROMETHAZINE"]):
        return "Antihistamines"
    if any(x in d for x in ["COUGH","MENTHODEX","ASCOREX","RHINATHIOL","BENYLIN","SALBUTAMOL","VENTOLIN","INHALER","AMINOPHYLLINE","BROMHEXINE","STREPSIL"]):
        return "Respiratory"
    if any(x in d for x in ["VITAMIN","FOLIC ACID","FERROUS","IRON","CALCIMAX","CALCIUM","ZINC","MULTIVIT","PREGNACARE","RANFERON","B COMPLEX","ABIDEC"]):
        return "Vitamins & Supplements"
    if any(x in d for x in ["NORMAL SALINE","DEXTROSE","RINGER","INFUSION","DRIP","IV FLUID","DARROWS","HARTMANN"]):
        return "IV Fluids & Infusions"
    if any(x in d for x in ["AMLODIPINE","LISINOPRIL","ATENOLOL","LOSARTAN","NIFEDIPINE","RAMIPRIL","VALSARTAN","TELMISARTAN","ENALAPRIL","ASPIRIN","CLOPIDOGREL","ATORVASTATIN","SIMVASTATIN","ROSUVASTATIN","ALDOMET","INDAPAMIDE","TRANEXAMIC","FRUSEMIDE","FUROSEMIDE"]):
        return "Cardiovascular"
    if any(x in d for x in ["METFORMIN","GLIMEPIRIDE","INSULIN","GLUCOPHAGE","GLICLAZIDE","DAONIL","GLIPTUS"]):
        return "Antidiabetics"
    if any(x in d for x in ["DEXAMETHASONE","HYDROCORTISONE","HYDROCORTIZONE","METHYLPREDNISOLONE","PREDNISOLONE"]):
        return "Steroids"
    if any(x in d for x in ["FLUCONAZOLE","DIFLUCAN","KLOVINAL"]):
        return "Antifungals"
    if any(x in d for x in ["CAFFEINE","OXYGEN","BROMAZEPAM"]):
        return "Specialised / ICU"
    if len(d.strip()) < 15 and any(c.isdigit() for c in d) and " " not in d.strip():
        return "Unresolved"
    return "Other Medications"


def generate_report():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Load Data ──
    claims = pd.read_excel(BASE_DIR / "Voyse claims.xlsx")
    claims.columns = claims.columns.str.strip()
    claims["Amt Claimed"] = pd.to_numeric(claims["Amt Claimed"].astype(str).str.replace(",", ""), errors="coerce")
    claims["Amt Paid"] = pd.to_numeric(claims["Amt Paid"].astype(str).str.replace(",", ""), errors="coerce")
    claims["Treatment Date"] = pd.to_datetime(claims["Treatment Date"], errors="coerce")
    claims["Received On"] = pd.to_datetime(claims["Received On"], errors="coerce")
    claims["CURRENTAGE"] = pd.to_numeric(claims["CURRENTAGE"], errors="coerce")

    prod = pd.read_excel(BASE_DIR / "Voyse production.xlsx")
    prod["Individual Premium Fees"] = pd.to_numeric(prod["Individual Premium Fees"].astype(str).str.replace(",", ""), errors="coerce")
    prod["Member Effectivedate"] = pd.to_datetime(prod["Member Effectivedate"], errors="coerce")
    prod["Client Expiry Date"] = pd.to_datetime(prod["Client Expiry Date"], errors="coerce")

    # Tariff lookup
    tariff_lookup = pd.read_excel(BASE_DIR / "master tariff upload.xlsx", usecols=["LEADWAY CODE", "LEADWAY DESCRIPTION"])
    tariff_lookup = tariff_lookup.dropna(subset=["LEADWAY CODE", "LEADWAY DESCRIPTION"])
    tariff_lookup["LEADWAY CODE"] = tariff_lookup["LEADWAY CODE"].astype(str).str.strip()
    tariff_lookup["LEADWAY DESCRIPTION"] = tariff_lookup["LEADWAY DESCRIPTION"].astype(str).str.strip()
    tariff_lookup = tariff_lookup.drop_duplicates(subset="LEADWAY CODE", keep="first")
    tariff_map = dict(zip(tariff_lookup["LEADWAY CODE"], tariff_lookup["LEADWAY DESCRIPTION"]))

    # Logo as base64
    logo_path = BASE_DIR / "leadway health logo 20266.jpg"
    logo_b64 = ""
    if logo_path.exists():
        logo_b64 = base64.b64encode(logo_path.read_bytes()).decode()

    # ── Key Metrics ──
    unique_claims = claims["Claim NUmber"].nunique()
    unique_members = claims["Member Ship No"].nunique()
    total_enrolled = len(prod)
    principals = prod[prod["Member Relationship"].str.strip() == "Main member"]
    num_principals = len(principals)

    paid_claims = claims[claims["Claim Status"] == "Paid Claims"]
    pipeline_claims = claims[claims["Claim Status"].isin(["Awaiting Payment", "Claims for adjudication", "In Process"])]
    paid_total = paid_claims["Amt Paid"].sum()
    pipeline_total = pipeline_claims["Amt Claimed"].sum()

    # Earned Premium
    as_of = pd.Timestamp.now().normalize()
    ep = prod.dropna(subset=["Member Effectivedate", "Client Expiry Date", "Individual Premium Fees"]).copy()
    ep = ep[ep["Individual Premium Fees"] > 0]
    total_days = (ep["Client Expiry Date"] - ep["Member Effectivedate"]).dt.days
    elapsed = (np.minimum(as_of, ep["Client Expiry Date"]) - ep["Member Effectivedate"]).dt.days.clip(lower=0)
    frac = (elapsed / total_days).clip(upper=1.0)
    ep["Earned"] = ep["Individual Premium Fees"] * frac
    earned_total = ep["Earned"].sum()
    written_total = ep["Individual Premium Fees"].sum()

    # IBNR (simple chain-ladder)
    df_ibnr = claims.dropna(subset=["Treatment Date", "Received On"]).copy()
    df_ibnr["Incurred_Month"] = df_ibnr["Treatment Date"].dt.to_period("M")
    df_ibnr["Lag"] = ((df_ibnr["Received On"].dt.year - df_ibnr["Treatment Date"].dt.year) * 12 + (df_ibnr["Received On"].dt.month - df_ibnr["Treatment Date"].dt.month)).clip(lower=0)
    df_ibnr = df_ibnr[df_ibnr["Lag"] <= 6]
    inc_tri = df_ibnr.groupby(["Incurred_Month", "Lag"])["Amt Paid"].sum().unstack(fill_value=np.nan)
    for lag in range(7):
        if lag not in inc_tri.columns:
            inc_tri[lag] = np.nan
    inc_tri = inc_tri[sorted(inc_tri.columns)]
    val_date = pd.Timestamp.now()
    for idx in inc_tri.index:
        max_lag = max(0, (val_date.to_period("M").year - idx.year) * 12 + (val_date.to_period("M").month - idx.month))
        for lag in inc_tri.columns:
            if lag <= max_lag:
                if pd.isna(inc_tri.at[idx, lag]):
                    inc_tri.at[idx, lag] = 0
            else:
                inc_tri.at[idx, lag] = np.nan
    cum_tri = inc_tri.cumsum(axis=1)
    # Chain-ladder factors
    cols = sorted(cum_tri.columns)
    factors = {}
    for i in range(len(cols) - 1):
        c, n = cols[i], cols[i + 1]
        mask = cum_tri[c].notna() & cum_tri[n].notna() & (cum_tri[c] > 0)
        if mask.sum() > 0:
            factors[c] = cum_tri.loc[mask, n].sum() / cum_tri.loc[mask, c].sum()
        else:
            factors[c] = 1.0
    # Project ultimate with 5M floor
    ibnr_results = []
    for idx, row in cum_tri.iterrows():
        current = 0
        current_lag = 0
        for col in cols:
            if pd.notna(row[col]):
                current = row[col]
                current_lag = col
        ultimate = current
        for col in cols:
            if col >= current_lag and col in factors:
                ultimate *= factors[col]
        ultimate = max(ultimate, 5_000_000)
        ibnr_est = max(ultimate - current, 0)
        ibnr_results.append({"Month": idx, "Current": current, "Lag": current_lag, "Ultimate": round(ultimate, 2), "IBNR": round(ibnr_est, 2)})
    ibnr_df = pd.DataFrame(ibnr_results).set_index("Month")
    ibnr_total = ibnr_df["IBNR"].sum()
    total_incurred = paid_total + pipeline_total + ibnr_total

    # MLR & COR
    mlr_pct = (total_incurred / earned_total * 100) if earned_total > 0 else 0
    admin_pct = 15.0
    nhia_pct = 2.0
    admin_amount = earned_total * admin_pct / 100
    nhia_amount = earned_total * nhia_pct / 100
    cor_pct = mlr_pct + admin_pct + nhia_pct

    avg_per_member = paid_total / unique_members if unique_members > 0 else 0
    avg_per_visit = paid_total / unique_claims if unique_claims > 0 else 0
    written_per_member = written_total / total_enrolled if total_enrolled > 0 else 0
    earned_per_member = earned_total / unique_members if unique_members > 0 else 0
    cost_per_member = total_incurred / unique_members if unique_members > 0 else 0
    required_prem = cost_per_member / 0.70 if cost_per_member > 0 else 0
    price_gap = required_prem - written_per_member

    # ── Monthly Trend ──
    claims["Month"] = claims["Treatment Date"].dt.to_period("M")
    monthly = claims.dropna(subset=["Treatment Date"]).groupby("Month").agg(
        Unique_Claims=("Claim NUmber", "nunique"),
        Total_Paid=("Amt Paid", "sum"),
        Unique_Members=("Member Ship No", "nunique"),
    ).sort_index()
    monthly["Avg_Per_Member"] = (monthly["Total_Paid"] / monthly["Unique_Members"]).round(2)
    monthly["Visits_Per_Member"] = (monthly["Unique_Claims"] / monthly["Unique_Members"]).round(1)

    monthly_rows = ""
    for period, row in monthly.iterrows():
        monthly_rows += f"""<tr>
            <td>{month_label(period)}</td>
            <td class="num">{row['Unique_Claims']:,}</td>
            <td class="num">{row['Unique_Members']:,}</td>
            <td class="num">{fmt_full(row['Total_Paid'])}</td>
            <td class="num">{fmt_full(row['Avg_Per_Member'])}</td>
            <td class="num">{row['Visits_Per_Member']}</td>
        </tr>"""

    # ── Early High Claimers ──
    prod_dates = prod.set_index("L")["Member Effectivedate"].to_dict()
    member_first_claim = claims.groupby("Member Ship No")["Treatment Date"].min()
    member_total_paid = claims.groupby("Member Ship No")["Amt Paid"].sum()
    member_names = claims.groupby("Member Ship No")["Principal Member"].first()
    prod_premium = prod.set_index("L")["Individual Premium Fees"].to_dict()

    early_rows = ""
    early_count = 0
    for mid, first_claim in member_first_claim.items():
        eff = prod_dates.get(mid)
        if pd.notna(eff) and pd.notna(first_claim):
            days = (pd.Timestamp(first_claim) - pd.Timestamp(eff)).days
            total = member_total_paid.get(mid, 0)
            prem = prod_premium.get(mid, 0)
            if days <= 30 and total > 200000:
                early_count += 1
                ratio = total / prem if prem > 0 else 0
                cls = "danger" if ratio > 5 else ("warning" if ratio > 2 else "")
                name = member_names.get(mid, "")
                early_rows += f"""<tr>
                    <td>{mid}</td>
                    <td>{name}</td>
                    <td class="num">{str(eff)[:10]}</td>
                    <td class="num">{str(first_claim)[:10]}</td>
                    <td class="num">{days}d</td>
                    <td class="num">{fmt_full(total)}</td>
                    <td class="num">{fmt_full(prem)}</td>
                    <td class="num {cls}">{ratio:.1f}x</td>
                </tr>"""

    # ── Top Spending Families ──
    family_rows = ""
    fam = claims.groupby("Principal Member").agg(
        Paid=("Amt Paid", "sum"),
        Members=("Member Ship No", "nunique"),
        Claims=("Claim NUmber", "nunique"),
    ).sort_values("Paid", ascending=False).head(10)
    for name, row in fam.iterrows():
        # Get family premium
        fam_ids = claims[claims["Principal Member"] == name]["Member Ship No"].unique()
        fam_prem = sum(prod_premium.get(mid, 0) for mid in fam_ids)
        fam_lr = row["Paid"] / fam_prem * 100 if fam_prem > 0 else 0
        lr_cls = "danger" if fam_lr > 100 else ("warning" if fam_lr > 70 else "good")
        family_rows += f"""<tr>
            <td>{str(name).strip().title()}</td>
            <td class="num">{row['Members']:,}</td>
            <td class="num">{row['Claims']:,}</td>
            <td class="num">{fmt_full(row['Paid'])}</td>
            <td class="num">{fmt_full(fam_prem)}</td>
            <td class="num {lr_cls}">{pct(fam_lr)}</td>
        </tr>"""

    # ── Claims by Relationship ──
    member_rel = prod.set_index("L")["Member Relationship"].str.strip().to_dict()
    claims["Relationship"] = claims["Member Ship No"].map(member_rel)
    rel = claims.groupby("Relationship").agg(
        Paid=("Amt Paid", "sum"),
        Members=("Member Ship No", "nunique"),
        Claims=("Claim NUmber", "nunique"),
    ).sort_values("Paid", ascending=False)
    rel["Avg_Per_Member"] = (rel["Paid"] / rel["Members"]).round(2)
    rel_rows = ""
    for r_name, row in rel.iterrows():
        rel_rows += f"""<tr>
            <td>{r_name}</td>
            <td class="num">{fmt_full(row['Paid'])}</td>
            <td class="num">{row['Members']:,}</td>
            <td class="num">{row['Claims']:,}</td>
            <td class="num">{fmt_full(row['Avg_Per_Member'])}</td>
        </tr>"""

    # ── Top Providers ──
    top_prov = claims.groupby("Provider").agg(
        Paid=("Amt Paid", "sum"),
        Claims=("Claim NUmber", "nunique"),
        Members=("Member Ship No", "nunique"),
    ).sort_values("Paid", ascending=False).head(10)
    top_prov["Pct"] = (top_prov["Paid"] / paid_total * 100).round(1)
    top_prov["VPM"] = (top_prov["Claims"] / top_prov["Members"]).round(1)
    top_prov["APV"] = (top_prov["Paid"] / top_prov["Claims"]).round(2)
    prov_rows = ""
    for i, (name, row) in enumerate(top_prov.iterrows(), 1):
        prov_rows += f"""<tr>
            <td>{i}</td>
            <td>{str(name).strip().title()}</td>
            <td class="num">{fmt_full(row['Paid'])}</td>
            <td class="num">{pct(row['Pct'])}</td>
            <td class="num">{row['Members']:,}</td>
            <td class="num">{row['VPM']}</td>
            <td class="num">{fmt_full(row['APV'])}</td>
        </tr>"""

    # ── Department Breakdown ──
    dept = claims.groupby("DEPARTMENT").agg(
        Paid=("Amt Paid", "sum"),
        Claims=("Claim NUmber", "nunique"),
    ).sort_values("Paid", ascending=False)
    dept["Pct"] = (dept["Paid"] / paid_total * 100).round(1)
    dept_rows = ""
    for i, (name, row) in enumerate(dept.head(15).iterrows(), 1):
        dept_rows += f"""<tr>
            <td>{i}</td>
            <td>{name}</td>
            <td class="num">{fmt_full(row['Paid'])}</td>
            <td class="num">{pct(row['Pct'])}</td>
            <td class="num">{row['Claims']:,}</td>
        </tr>"""

    # ── Medication by Class ──
    med = claims[claims["DEPARTMENT"].str.contains("Medication|Chronic Medication|VITAMIN", case=False, na=False)].copy()
    def resolve_desc(desc):
        if pd.isna(desc): return desc
        d = str(desc).strip()
        if len(d) < 15 and any(c.isdigit() for c in d) and " " not in d:
            return tariff_map.get(d, d)
        return d
    med["Drug_Name"] = med["Description"].apply(resolve_desc)
    med["Drug_Class"] = med["Drug_Name"].apply(classify_drug)

    drug_summary = med.groupby("Drug_Class").agg(
        Paid=("Amt Paid", "sum"),
        Claims=("Claim NUmber", "nunique"),
    ).sort_values("Paid", ascending=False)
    total_med = drug_summary["Paid"].sum()
    drug_summary["Pct"] = (drug_summary["Paid"] / total_med * 100).round(1)
    drug_summary["APV"] = (drug_summary["Paid"] / drug_summary["Claims"]).round(2)

    drug_rows = ""
    for i, (cls, row) in enumerate(drug_summary.iterrows(), 1):
        drug_rows += f"""<tr style="background:var(--light-blue);">
            <td>{i}</td>
            <td><strong>{cls}</strong></td>
            <td class="num" style="font-weight:700;">{fmt_full(row['Paid'])}</td>
            <td class="num" style="font-weight:700;">{pct(row['Pct'])}</td>
            <td class="num" style="font-weight:700;">{row['Claims']:,}</td>
            <td class="num" style="font-weight:700;">{fmt_full(row['APV'])}</td>
        </tr>"""
        if cls != "Unresolved":
            top_drugs = med[med["Drug_Class"] == cls].groupby("Drug_Name").agg(
                Paid=("Amt Paid", "sum"), Claims=("Claim NUmber", "nunique"),
            ).sort_values("Paid", ascending=False).head(5)
            for dname, drow in top_drugs.iterrows():
                d_avg = drow["Paid"] / drow["Claims"] if drow["Claims"] > 0 else 0
                drug_rows += f"""<tr>
                    <td></td>
                    <td style="padding-left:28px;color:var(--text-muted);font-size:12px;">{str(dname).strip().title()}</td>
                    <td class="num" style="font-size:12px;">{fmt_full(drow['Paid'])}</td>
                    <td class="num" style="font-size:12px;">{pct(drow['Paid']/total_med*100)}</td>
                    <td class="num" style="font-size:12px;">{drow['Claims']:,}</td>
                    <td class="num" style="font-size:12px;">{fmt_full(d_avg)}</td>
                </tr>"""

    # ── Claim Status ──
    status = claims.groupby("Claim Status")["Claim NUmber"].nunique().sort_values(ascending=False)
    status_rows = ""
    for s, count in status.items():
        status_rows += f"<tr><td>{s}</td><td class='num'>{count:,}</td></tr>"

    # ── IBNR rows ──
    ibnr_rows = ""
    for period, row in ibnr_df.iterrows():
        ibnr_rows += f"""<tr>
            <td>{month_label(period)}</td>
            <td class="num">{fmt_full(row['Current'])}</td>
            <td class="num">{row['Lag']}</td>
            <td class="num">{fmt_full(row['Ultimate'])}</td>
            <td class="num highlight">{fmt_full(row['IBNR'])}</td>
        </tr>"""

    mlr_cls = "danger" if mlr_pct > 100 else ("warning" if mlr_pct > 85 else "good")
    cor_cls = "danger" if cor_pct > 100 else ("warning" if cor_pct > 85 else "good")

    # ── BUILD HTML ──
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Voyse Technologies — Claims & Performance Review</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
  :root {{
    --navy: #1A1A2E; --crimson: #C8102E; --coral: #E87722;
    --cream: #FAF7F2; --light-blue: #E8F4FD; --soft-pink: #FDF0ED;
    --light-grey: #F4F4F6; --medium-grey: #E8E8EC;
    --text-dark: #1A1A2E; --text-muted: #6B7280; --white: #FFFFFF;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Inter', sans-serif; background: var(--cream); color: var(--text-dark); line-height: 1.6; font-size: 14px; }}
  .container {{ max-width: 1140px; margin: 0 auto; padding: 40px 20px; }}
  .header {{ background: var(--navy); color: var(--white); padding: 40px; border-radius: 16px; margin-bottom: 30px; display: flex; align-items: center; gap: 24px; }}
  .header img {{ height: 60px; }}
  .header h1 {{ font-weight: 800; font-size: 28px; letter-spacing: -0.5px; }}
  .header .subtitle {{ font-size: 14px; opacity: 0.7; }}
  .section {{ background: var(--white); border-radius: 14px; padding: 32px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }}
  .section h2 {{ font-weight: 700; font-size: 20px; color: var(--navy); margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid var(--medium-grey); }}
  .section h2 span.accent {{ color: var(--crimson); }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 10px; }}
  .kpi {{ background: var(--white); border: 1px solid var(--medium-grey); border-radius: 12px; padding: 22px 18px; text-align: center; }}
  .kpi:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.06); }}
  .kpi .label {{ font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px; color: var(--text-muted); margin-bottom: 8px; }}
  .kpi .value {{ font-weight: 800; font-size: 22px; color: var(--navy); }}
  .kpi.highlight {{ border-color: var(--crimson); border-width: 2px; }}
  .kpi.highlight .value {{ color: var(--crimson); }}
  .kpi.coral {{ border-color: var(--coral); border-width: 2px; }}
  .kpi.coral .value {{ color: var(--coral); }}
  .mlr-card {{ background: var(--navy); color: var(--white); border-radius: 14px; padding: 32px; margin-bottom: 24px; }}
  .mlr-card h2 {{ color: var(--white); border: none; margin-bottom: 6px; padding-bottom: 0; }}
  .mlr-card .formula {{ font-size: 13px; opacity: 0.6; margin-bottom: 24px; font-style: italic; }}
  .mlr-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
  .mlr-table {{ width: 100%; border-collapse: collapse; }}
  .mlr-table td {{ padding: 10px 12px; border-bottom: 1px solid rgba(255,255,255,0.08); font-size: 13px; }}
  .mlr-table td:last-child {{ text-align: right; font-weight: 600; }}
  .mlr-table tr.total td {{ border-top: 2px solid var(--crimson); font-weight: 800; font-size: 15px; padding-top: 14px; }}
  .mlr-table tr.total td:last-child {{ color: var(--coral); }}
  .cor-result {{ display: flex; align-items: center; justify-content: center; flex-direction: column; background: rgba(255,255,255,0.06); border-radius: 12px; padding: 30px; }}
  .cor-result .big-number {{ font-size: 56px; font-weight: 900; color: var(--coral); line-height: 1; }}
  .cor-result .big-label {{ font-size: 14px; opacity: 0.7; margin-top: 8px; }}
  .cor-breakdown {{ margin-top: 20px; display: flex; gap: 16px; justify-content: center; flex-wrap: wrap; }}
  .cor-chip {{ background: rgba(255,255,255,0.08); border-radius: 8px; padding: 10px 16px; text-align: center; min-width: 100px; }}
  .cor-chip .chip-val {{ font-weight: 800; font-size: 18px; }}
  .cor-chip .chip-lbl {{ font-size: 10px; opacity: 0.6; text-transform: uppercase; letter-spacing: 0.5px; }}
  .data-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  .data-table thead th {{ background: var(--navy); color: var(--white); padding: 12px 10px; text-align: left; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }}
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
  .footer {{ text-align: center; color: var(--text-muted); font-size: 11px; margin-top: 20px; padding: 20px; }}
  @media print {{ body {{ background: white; }} .section {{ box-shadow: none; break-inside: avoid; }} }}
</style>
</head>
<body>
<div class="container">

  <div class="header">
    {'<img src="data:image/jpeg;base64,' + logo_b64 + '" alt="Leadway Health">' if logo_b64 else ''}
    <div>
      <h1>Voyse Technologies</h1>
      <div class="subtitle">Claims &amp; Performance Review &nbsp;|&nbsp; {pd.Timestamp.now().strftime('%d %B %Y')}</div>
    </div>
  </div>

  <div class="section">
    <h2>Executive <span class="accent">Overview</span></h2>
    <div class="kpi-grid">
      <div class="kpi highlight"><div class="label">Total Incurred</div><div class="value">{fmt(total_incurred)}</div></div>
      <div class="kpi"><div class="label">Paid Claims</div><div class="value">{fmt(paid_total)}</div></div>
      <div class="kpi"><div class="label">Pipeline Claims</div><div class="value">{fmt(pipeline_total)}</div></div>
      <div class="kpi coral"><div class="label">IBNR Reserve</div><div class="value">{fmt(ibnr_total)}</div></div>
      <div class="kpi"><div class="label">Earned Premium</div><div class="value">{fmt(earned_total)}</div></div>
      <div class="kpi"><div class="label">Written Premium</div><div class="value">{fmt(written_total)}</div></div>
      <div class="kpi highlight"><div class="label">MLR</div><div class="value">{pct(mlr_pct)}</div></div>
      <div class="kpi highlight"><div class="label">COR</div><div class="value">{pct(cor_pct)}</div></div>
      <div class="kpi"><div class="label">Enrolled Members</div><div class="value">{total_enrolled:,}</div></div>
      <div class="kpi"><div class="label">Unique Claimants</div><div class="value">{unique_members:,}</div></div>
      <div class="kpi"><div class="label">Avg Paid / Member</div><div class="value">{fmt(avg_per_member)}</div></div>
      <div class="kpi"><div class="label">Avg Paid / Visit</div><div class="value">{fmt(avg_per_visit)}</div></div>
    </div>
  </div>

  <div class="mlr-card">
    <h2>Medical Loss Ratio &amp; Combined Operating Ratio</h2>
    <div class="formula">MLR = (Paid Claims + Pipeline Claims + IBNR) / Earned Premium &nbsp;|&nbsp; COR = MLR + Admin (15%) + NHIA (2%)</div>
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
          <tr><td style="padding-top:16px;">Admin (15%)</td><td style="padding-top:16px;">{fmt_full(admin_amount)}</td></tr>
          <tr><td>NHIA Levy (2%)</td><td>{fmt_full(nhia_amount)}</td></tr>
          <tr class="total"><td>Combined Operating Ratio</td><td>{pct(cor_pct)}</td></tr>
        </table>
      </div>
      <div class="cor-result">
        <div class="big-number">{pct(cor_pct)}</div>
        <div class="big-label">Combined Operating Ratio</div>
        <div class="cor-breakdown">
          <div class="cor-chip"><div class="chip-val">{pct(mlr_pct)}</div><div class="chip-lbl">MLR</div></div>
          <div class="cor-chip"><div class="chip-val">{pct(admin_pct)}</div><div class="chip-lbl">Admin</div></div>
          <div class="cor-chip"><div class="chip-val">{pct(nhia_pct)}</div><div class="chip-lbl">NHIA</div></div>
        </div>
      </div>
    </div>
  </div>

  <div class="section">
    <h2>Monthly Claims <span class="accent">Trend</span></h2>
    <table class="data-table"><thead><tr>
      <th>Month</th><th class="num">Unique Claims</th><th class="num">Members</th><th class="num">Total Paid</th><th class="num">Avg/Member</th><th class="num">Visits/Member</th>
    </tr></thead><tbody>{monthly_rows}</tbody></table>
  </div>

  <div class="section" style="border-left:4px solid var(--crimson);">
    <h2>Early High <span class="accent">Claimers</span></h2>
    <p style="color:var(--text-muted);font-size:12px;margin-bottom:16px;">Members who spent over &#8358;200K within 30 days of enrolment ({early_count} flagged)</p>
    <div class="scroll-x"><table class="data-table"><thead><tr>
      <th>Member ID</th><th>Principal</th><th class="num">Join Date</th><th class="num">First Claim</th><th class="num">Days</th><th class="num">Total Spent</th><th class="num">Premium</th><th class="num">Spend/Premium</th>
    </tr></thead><tbody>{early_rows}</tbody></table></div>
  </div>

  <div class="section">
    <h2>Top Spending <span class="accent">Families</span></h2>
    <table class="data-table"><thead><tr>
      <th>Family</th><th class="num">Members</th><th class="num">Claims</th><th class="num">Total Paid</th><th class="num">Family Premium</th><th class="num">Family LR</th>
    </tr></thead><tbody>{family_rows}</tbody></table>
  </div>

  <div class="section">
    <h2>Claims by <span class="accent">Relationship</span></h2>
    <table class="data-table"><thead><tr>
      <th>Relationship</th><th class="num">Total Paid</th><th class="num">Members</th><th class="num">Claims</th><th class="num">Avg/Member</th>
    </tr></thead><tbody>{rel_rows}</tbody></table>
  </div>

  <div class="section">
    <h2>Top 10 <span class="accent">Providers</span></h2>
    <table class="data-table"><thead><tr>
      <th>#</th><th>Provider</th><th class="num">Total Paid</th><th class="num">% of Total</th><th class="num">Members</th><th class="num">Visits/Member</th><th class="num">Avg/Visit</th>
    </tr></thead><tbody>{prov_rows}</tbody></table>
  </div>

  <div class="section">
    <h2>Department <span class="accent">Breakdown</span></h2>
    <table class="data-table"><thead><tr>
      <th>#</th><th>Department</th><th class="num">Total Paid</th><th class="num">%</th><th class="num">Unique Claims</th>
    </tr></thead><tbody>{dept_rows}</tbody></table>
  </div>

  <div class="section">
    <h2>Medication by <span class="accent">Therapeutic Class</span></h2>
    <table class="data-table"><thead><tr>
      <th>#</th><th>Drug Class</th><th class="num">Total Paid</th><th class="num">% of Med</th><th class="num">Claims</th><th class="num">Avg/Claim</th>
    </tr></thead><tbody>{drug_rows}</tbody></table>
  </div>

  <div class="section">
    <h2>IBNR <span class="accent">Estimate</span></h2>
    <table class="data-table"><thead><tr>
      <th>Month</th><th class="num">Current Reported</th><th class="num">Dev. Lag</th><th class="num">Ultimate</th><th class="num">IBNR</th>
    </tr></thead><tbody>{ibnr_rows}
      <tr style="background:var(--soft-pink);font-weight:700;">
        <td>Total</td><td class="num">{fmt_full(ibnr_df['Current'].sum())}</td><td></td>
        <td class="num">{fmt_full(ibnr_df['Ultimate'].sum())}</td><td class="num highlight">{fmt_full(ibnr_total)}</td>
      </tr>
    </tbody></table>
  </div>

  <div class="section">
    <h2>Claim <span class="accent">Status</span></h2>
    <p style="color:var(--text-muted);font-size:12px;margin-bottom:12px;">Unique claim IDs</p>
    <table class="data-table"><thead><tr><th>Status</th><th class="num">Unique Claims</th></tr></thead>
    <tbody>{status_rows}</tbody></table>
  </div>

  <div class="section" style="border-left:4px solid var(--crimson);">
    <h2>What Went <span class="accent">Wrong</span></h2>
    <table class="data-table"><thead><tr><th>Finding</th><th>Impact</th></tr></thead>
    <tbody>
      <tr><td>Neonatal ICU case (25219085/2) — premature baby requiring incubator, CPAP, neonatologist, Meronem antibiotics</td><td class="num danger">&#8358;6.7M cost against &#8358;300K premium (22.3x). Single case = 30% of all claims paid.</td></tr>
      <tr><td>Caesarean myomectomy + post-operative admission (25219086/1) at Reddington Hospital</td><td class="num danger">&#8358;3.8M cost against &#8358;299K premium (12.6x)</td></tr>
      <tr><td>Two families (Samuel Tunde, Aririguzo Clinton) consumed &#8358;10.6M — 48% of total paid claims against &#8358;1.5M combined premium</td><td class="num danger">Combined family LR of 707%</td></tr>
      <tr><td>87% of members claimed within 30 days of enrolment — consistent with adverse selection or pre-existing conditions</td><td class="num warning">Waiting period was not enforced or not sufficient</td></tr>
      <tr><td>Sons averaged &#8358;669K per member — 2.6x the average premium of &#8358;261K. Driven by neonatal case.</td><td class="num warning">Dependant risk not adequately priced</td></tr>
      <tr><td>Outreach Signature Women &amp; Children Hospital: &#8358;5.7M from just 2 members (4 claims)</td><td class="num warning">Single provider = 26% of total spend. Provider tariff compliance needs review.</td></tr>
      <tr><td>PROMAX plan offers unlimited outpatient + inpatient + maternity for only &#8358;300K per head</td><td class="num danger">Benefit structure does not match premium level</td></tr>
    </tbody></table>
  </div>

  <div class="section">
    <h2>Is the Plan Adequately <span class="accent">Priced?</span></h2>
    <table class="data-table"><thead><tr><th>Metric</th><th class="num">Amount</th></tr></thead>
    <tbody>
      <tr><td>Written Premium per Member</td><td class="num">{fmt_full(written_per_member)}</td></tr>
      <tr><td>Earned Premium per Member</td><td class="num">{fmt_full(earned_per_member)}</td></tr>
      <tr><td>Actual Cost per Member (Total Incurred / Members)</td><td class="num danger">{fmt_full(cost_per_member)}</td></tr>
      <tr><td>Required Premium at 70% Target MLR</td><td class="num">{fmt_full(required_prem)}</td></tr>
      <tr style="background:var(--soft-pink);">
        <td style="font-weight:700;">Price Gap (Required - Written)</td>
        <td class="num danger" style="font-weight:700;">{fmt_full(price_gap)}</td>
      </tr>
      <tr><td>Principals covering dependants</td><td class="num">{num_principals} principals covering {total_enrolled} lives (avg family size {total_enrolled/num_principals:.1f})</td></tr>
    </tbody></table>
  </div>

  <div class="section" style="border-left:4px solid var(--crimson);">
    <h2>Key <span class="accent">Recommendations</span></h2>
    <table class="data-table"><thead><tr><th>Area</th><th>Finding</th><th>Action Required</th></tr></thead>
    <tbody>
      <tr><td><strong>Waiting Period</strong></td><td>87% of members claimed within 30 days; neonatal case claimed on day 1 (treatment date before effective date)</td><td>Enforce 30-day general waiting period and 12-month maternity/surgical waiting period for new enrolments</td></tr>
      <tr><td><strong>Premium Adequacy</strong></td><td>Current premium of &#8358;261K per head against actual cost of {fmt_full(cost_per_member)}</td><td>Increase premium to minimum {fmt_full(required_prem)} per head to achieve 70% target MLR</td></tr>
      <tr><td><strong>Catastrophic Claims</strong></td><td>Two cases (&#8358;10.5M) represent 48% of total spend</td><td>Introduce per-claim and per-family annual caps. Consider reinsurance for claims above &#8358;2M</td></tr>
      <tr><td><strong>Provider Management</strong></td><td>Outreach Signature Hospital: &#8358;5.7M from 2 members</td><td>Conduct tariff audit. Pre-authorisation mandatory for all admissions and procedures above &#8358;500K</td></tr>
      <tr><td><strong>Benefit Restructuring</strong></td><td>Unlimited PROMAX benefits unsustainable at this premium level</td><td>Introduce sub-limits on maternity (&#8358;2M cap), neonatal (&#8358;3M cap), and surgical benefits</td></tr>
      <tr><td><strong>Underwriting</strong></td><td>No evidence of medical screening at enrolment</td><td>Require pre-enrolment medical questionnaire and exclude pre-existing conditions for first 12 months</td></tr>
    </tbody></table>
  </div>

  <div class="footer">
    Voyse Technologies — Claims &amp; Performance Review &nbsp;|&nbsp; Leadway Health Insurance &nbsp;|&nbsp; {pd.Timestamp.now().strftime('%d %B %Y')}
  </div>

</div>
</body>
</html>"""

    Path("reports/Voyse_Analytics_Report.html").write_text(html)
    print("Report saved to: reports/Voyse_Analytics_Report.html")


if __name__ == "__main__":
    generate_report()

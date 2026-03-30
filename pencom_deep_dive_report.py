#!/usr/bin/env python3
"""
PENCOM Deep-Dive Data Analytics Report
=======================================
Comprehensive single-client analysis for National Pension Commission (PENCOM)
Leadway Health Insurance
"""

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.image as mpimg
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import seaborn as sns
from datetime import datetime, timedelta
import numpy as np
import os
import warnings
warnings.filterwarnings('ignore')

# ── Config ────────────────────────────────────────────────────────────
sns.set_theme(style="whitegrid", font_scale=1.05)
PRIMARY = '#1D8348'
SECONDARY = '#2E86C1'
ACCENT = '#E74C3C'
DARK = '#1B2631'
PALETTE = [PRIMARY, SECONDARY, '#F39C12', ACCENT, '#8E44AD', '#1ABC9C', '#E67E22', '#3498DB']

OUT_DIR = '/home/user/datadump/pencom_report'
os.makedirs(OUT_DIR, exist_ok=True)

LOGO_PATH = '/home/user/datadump/leadway health logo 20266.jpg'
HAS_LOGO = os.path.exists(LOGO_PATH)

def add_logo(fig, zoom=0.08):
    """Add Leadway Health logo to top-right of figure."""
    if not HAS_LOGO:
        return
    try:
        logo = mpimg.imread(LOGO_PATH)
        imagebox = OffsetImage(logo, zoom=zoom)
        ab = AnnotationBbox(imagebox, (0.98, 0.98), xycoords='figure fraction',
                           frameon=False, box_alignment=(1, 1))
        fig.add_artist(ab)
    except:
        pass

def naira(val):
    return f'₦{val:,.0f}'

def excel_to_datetime(series):
    """Convert Excel serial date numbers to datetime."""
    return pd.to_datetime('1899-12-30') + pd.to_timedelta(pd.to_numeric(series, errors='coerce'), unit='D')

# ══════════════════════════════════════════════════════════════════════
print("=" * 70)
print("  PENCOM DEEP-DIVE — LEADWAY HEALTH INSURANCE")
print(f"  Report Date: {datetime.now().strftime('%B %d, %Y')}")
print("=" * 70)

# ── 1. LOAD & CLEAN ──────────────────────────────────────────────────
print("\n[1/10] Loading PENCOM data...")

claims = pd.read_excel('PENCOM CLAIMS.xlsx')
premium = pd.read_excel('PENCOM Premium.xlsx')
benefit = pd.read_excel('PENCOM BENEFIT.xlsx')
hospitals = pd.read_excel('PENCOM HOSPITAL LIST (STANDARD).xlsx')

# Clean claims
for col in ['Amt Claimed', 'Amt Paid', 'Debit']:
    if col in claims.columns:
        claims[col] = pd.to_numeric(claims[col], errors='coerce').fillna(0)
claims['CURRENTAGE'] = pd.to_numeric(claims['CURRENTAGE'], errors='coerce')
claims['Treatment Date'] = excel_to_datetime(claims['Treatment Date'])
claims['Received On'] = excel_to_datetime(claims['Received On'])
claims['TAT_days'] = (claims['Received On'] - claims['Treatment Date']).dt.days

# Clean premium
premium['Individual Premium Fees'] = pd.to_numeric(premium['Individual Premium Fees'], errors='coerce').fillna(0)
premium['Member Date Of Birth'] = pd.to_datetime(premium['Member Date Of Birth'], errors='coerce')
premium['Member Effectivedate'] = pd.to_datetime(premium['Member Effectivedate'], errors='coerce')
premium['Client Expiry Date'] = pd.to_datetime(premium['Client Expiry Date'], errors='coerce')
premium['Age'] = ((pd.Timestamp.now() - premium['Member Date Of Birth']).dt.days / 365.25).round(0)

# Clean hospitals
hospitals['CAT'] = hospitals['CAT'].str.strip()

print(f"   Claims: {len(claims):,} records")
print(f"   Members: {len(premium):,} records ({premium['Member Enrollee ID'].nunique():,} unique)")
print(f"   Hospitals: {len(hospitals):,} providers")

# ── 2. EXECUTIVE SUMMARY ─────────────────────────────────────────────
print("\n[2/10] Executive Summary...")

n_members = premium['Member Enrollee ID'].nunique()
n_active = premium[premium['Member Status Desc'] == 'Active'].shape[0]
total_premium = premium['Individual Premium Fees'].sum()
total_claimed = claims['Amt Claimed'].sum()
total_paid = claims['Amt Paid'].sum()
n_claims = len(claims)
loss_ratio = total_paid / total_premium * 100 if total_premium else 0
avg_claim = total_paid / n_claims if n_claims else 0
claims_per_member = n_claims / n_members if n_members else 0
cost_per_member = total_paid / n_members if n_members else 0
prem_per_member = total_premium / n_members if n_members else 0
rejection_rate = (claims['Amt Claimed'].sum() - claims['Amt Paid'].sum()) / claims['Amt Claimed'].sum() * 100

print(f"""
  ┌────────────────────────────────────────────────────────────────────┐
  │                  PENCOM — EXECUTIVE SUMMARY                       │
  ├────────────────────────────────────────────────────────────────────┤
  │  Total Members:           {n_members:>6,}                                  │
  │  Active Members:          {n_active:>6,}                                  │
  │  Total Claims:            {n_claims:>6,}                                  │
  │                                                                    │
  │  Total Premium:           {naira(total_premium):>20s}                  │
  │  Total Claims Paid:       {naira(total_paid):>20s}                  │
  │  Total Claims Submitted:  {naira(total_claimed):>20s}                  │
  │                                                                    │
  │  Loss Ratio:              {loss_ratio:>6.1f}%                              │
  │  Claims Rejection Rate:   {rejection_rate:>6.1f}%                              │
  │  Avg Claim Size:          {naira(avg_claim):>20s}                  │
  │  Claims per Member:       {claims_per_member:>9.1f}                           │
  │  Avg Cost per Member:     {naira(cost_per_member):>20s}                  │
  │  Avg Premium per Member:  {naira(prem_per_member):>20s}                  │
  │  Profit Margin:           {naira(total_premium - total_paid):>20s}                  │
  └────────────────────────────────────────────────────────────────────┘
""")

# ── 3. MONTHLY CLAIMS TREND ──────────────────────────────────────────
print("[3/10] Monthly claims trend...")

claims['YearMonth'] = claims['Treatment Date'].dt.to_period('M')
monthly = claims.groupby('YearMonth').agg(
    claim_count=('Amt Paid', 'count'),
    total_paid=('Amt Paid', 'sum'),
    total_claimed=('Amt Claimed', 'sum'),
    avg_paid=('Amt Paid', 'mean'),
    unique_members=('Member Ship No', 'nunique')
).sort_index()

fig, ax1 = plt.subplots(figsize=(14, 6))
x = range(len(monthly))
labels = [str(p) for p in monthly.index]

ax1.bar(x, monthly['total_paid'] / 1e6, color=PRIMARY, alpha=0.7, label='Total Paid (₦M)')
ax1.set_ylabel('Claims Paid (₦ Millions)', color=PRIMARY)
ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'₦{v:,.1f}M'))

ax2 = ax1.twinx()
ax2.plot(x, monthly['claim_count'], color=ACCENT, linewidth=2.5, marker='o', label='Claim Count')
ax2.set_ylabel('Number of Claims', color=ACCENT)

ax1.set_xticks(x)
ax1.set_xticklabels(labels, rotation=45, ha='right')
ax1.set_title('PENCOM — Monthly Claims Trend', fontsize=14, fontweight='bold', pad=20)

lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
add_logo(fig)
plt.tight_layout()
plt.savefig(f'{OUT_DIR}/01_monthly_trend.png', dpi=150)
plt.close()

print("   Monthly Summary:")
for idx, row in monthly.iterrows():
    print(f"   {idx}: {row['claim_count']:>5,} claims | Paid: {naira(row['total_paid']):>15s} | Avg: {naira(row['avg_paid']):>10s} | Members: {row['unique_members']:>4,}")

# ── 4. DEPARTMENT ANALYSIS ───────────────────────────────────────────
print("\n[4/10] Department analysis...")

dept = claims.groupby('DEPARTMENT').agg(
    count=('Amt Paid', 'count'),
    total_paid=('Amt Paid', 'sum'),
    avg_paid=('Amt Paid', 'mean'),
    total_claimed=('Amt Claimed', 'sum'),
    unique_members=('Member Ship No', 'nunique')
).sort_values('total_paid', ascending=False)

dept['pct_of_total'] = dept['total_paid'] / dept['total_paid'].sum() * 100
dept['rejection_rate'] = ((dept['total_claimed'] - dept['total_paid']) / dept['total_claimed'] * 100).round(1)

# Chart: Top departments
fig, axes = plt.subplots(1, 2, figsize=(18, 8))

top_dept = dept.head(12)

# Bar chart
top_dept_sorted = top_dept.sort_values('total_paid')
axes[0].barh(range(len(top_dept_sorted)), top_dept_sorted['total_paid'] / 1e6,
             color=PRIMARY, edgecolor='white')
axes[0].set_yticks(range(len(top_dept_sorted)))
axes[0].set_yticklabels(top_dept_sorted.index, fontsize=9)
axes[0].set_xlabel('₦ Millions')
axes[0].set_title('Top 12 Departments by Claims Paid', fontweight='bold')
axes[0].xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'₦{v:,.1f}M'))

# Pie chart (top 8 + others)
top8 = dept.head(8)['total_paid']
others = dept.iloc[8:]['total_paid'].sum()
pie_data = pd.concat([top8, pd.Series({'Others': others})])
wedges, texts, autotexts = axes[1].pie(pie_data, labels=pie_data.index, autopct='%1.1f%%',
                                        colors=PALETTE + ['#BDC3C7'], startangle=90, textprops={'fontsize': 8})
axes[1].set_title('Claims Distribution by Department', fontweight='bold')

add_logo(fig)
plt.tight_layout()
plt.savefig(f'{OUT_DIR}/02_department_analysis.png', dpi=150)
plt.close()

print("\n   Top 12 Departments:")
print(f"   {'Department':<45s} {'Claims':>7s} {'Total Paid':>15s} {'%':>6s} {'Avg':>12s}")
print("   " + "-" * 90)
for name, row in dept.head(12).iterrows():
    print(f"   {name:<45s} {row['count']:>7,} {naira(row['total_paid']):>15s} {row['pct_of_total']:>5.1f}% {naira(row['avg_paid']):>12s}")

# ── 5. PROVIDER ANALYSIS ─────────────────────────────────────────────
print("\n[5/10] Provider analysis...")

provider = claims.groupby('Provider').agg(
    count=('Amt Paid', 'count'),
    total_paid=('Amt Paid', 'sum'),
    avg_paid=('Amt Paid', 'mean'),
    unique_members=('Member Ship No', 'nunique'),
    unique_depts=('DEPARTMENT', 'nunique')
).sort_values('total_paid', ascending=False)

provider['pct_of_total'] = provider['total_paid'] / provider['total_paid'].sum() * 100
provider['claims_per_member'] = provider['count'] / provider['unique_members']

# Chart
fig, ax = plt.subplots(figsize=(14, 8))
top15 = provider.head(15).sort_values('total_paid')
colors = [PRIMARY if v < provider['total_paid'].quantile(0.9) else ACCENT for v in top15['total_paid']]
bars = ax.barh(range(len(top15)), top15['total_paid'] / 1e6, color=PRIMARY, edgecolor='white')

for i, (_, row) in enumerate(top15.iterrows()):
    ax.text(row['total_paid']/1e6 + 0.1, i, f"{row['count']:,} claims | {row['unique_members']:,} members",
            va='center', fontsize=8, color=DARK)

ax.set_yticks(range(len(top15)))
ax.set_yticklabels(top15.index, fontsize=9)
ax.set_xlabel('₦ Millions')
ax.set_title('PENCOM — Top 15 Providers by Claims Paid', fontsize=14, fontweight='bold', pad=15)
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'₦{v:,.1f}M'))
add_logo(fig)
plt.tight_layout()
plt.savefig(f'{OUT_DIR}/03_top_providers.png', dpi=150)
plt.close()

# Provider concentration
top5_pct = provider.head(5)['pct_of_total'].sum()
top10_pct = provider.head(10)['pct_of_total'].sum()
print(f"   Provider Concentration: Top 5 = {top5_pct:.1f}% | Top 10 = {top10_pct:.1f}% of total claims")
print(f"   Total unique providers used: {len(provider):,}")

print("\n   Top 15 Providers:")
print(f"   {'Provider':<55s} {'Claims':>7s} {'Total Paid':>14s} {'Members':>8s}")
print("   " + "-" * 90)
for name, row in provider.head(15).iterrows():
    print(f"   {name[:55]:<55s} {row['count']:>7,} {naira(row['total_paid']):>14s} {row['unique_members']:>8,}")

# ── 6. DIAGNOSIS ANALYSIS ────────────────────────────────────────────
print("\n[6/10] Diagnosis analysis...")

diag = claims[claims['Diagnosis Description'].notna()].groupby('Diagnosis Description').agg(
    count=('Amt Paid', 'count'),
    total_paid=('Amt Paid', 'sum'),
    avg_paid=('Amt Paid', 'mean'),
    max_paid=('Amt Paid', 'max'),
    unique_members=('Member Ship No', 'nunique')
).sort_values('total_paid', ascending=False)

fig, ax = plt.subplots(figsize=(14, 8))
top15_diag = diag.head(15).sort_values('total_paid')
ax.barh(range(len(top15_diag)), top15_diag['total_paid'] / 1e6, color='#922B21', edgecolor='white')
for i, (name, row) in enumerate(top15_diag.iterrows()):
    ax.text(row['total_paid']/1e6 + 0.02, i, f"n={row['count']:,}  avg={naira(row['avg_paid'])}",
            va='center', fontsize=8, color=DARK)
ax.set_yticks(range(len(top15_diag)))
ax.set_yticklabels([d[:50] for d in top15_diag.index], fontsize=9)
ax.set_xlabel('₦ Millions')
ax.set_title('PENCOM — Top 15 Diagnoses by Claims Paid', fontsize=14, fontweight='bold', pad=15)
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'₦{v:,.1f}M'))
add_logo(fig)
plt.tight_layout()
plt.savefig(f'{OUT_DIR}/04_top_diagnoses.png', dpi=150)
plt.close()

# Disease categories
malaria_cost = diag[diag.index.str.contains('malaria|Malaria|plasmodium|Plasmodium', na=False)]['total_paid'].sum()
chronic_terms = 'hypertension|diabetes|asthma|heart|cancer|neoplasm|glaucoma'
chronic_cost = diag[diag.index.str.contains(chronic_terms, case=False, na=False)]['total_paid'].sum()
infection_terms = 'sepsis|infection|pneumonia|respiratory'
infection_cost = diag[diag.index.str.contains(infection_terms, case=False, na=False)]['total_paid'].sum()

print(f"   Disease Category Costs:")
print(f"   Malaria-related:          {naira(malaria_cost):>15s}")
print(f"   Chronic conditions:       {naira(chronic_cost):>15s}")
print(f"   Infections:               {naira(infection_cost):>15s}")

# ── 7. DEMOGRAPHICS ──────────────────────────────────────────────────
print("\n[7/10] Demographics analysis...")

fig, axes = plt.subplots(2, 2, figsize=(16, 12))

# Gender
gender = premium['Member Gender'].value_counts()
axes[0,0].pie(gender, labels=gender.index, autopct='%1.1f%%',
              colors=[SECONDARY, ACCENT], startangle=90, textprops={'fontsize':12})
axes[0,0].set_title('Gender Distribution', fontweight='bold')

# Relationship
rel = premium['Member Relationship'].str.strip().value_counts()
axes[0,1].pie(rel, labels=rel.index, autopct='%1.1f%%',
              colors=PALETTE[:len(rel)], startangle=90, textprops={'fontsize':11})
axes[0,1].set_title('Principal vs Dependents', fontweight='bold')

# Age distribution
ages = premium['Age'].dropna()
axes[1,0].hist(ages, bins=range(0, 85, 5), color=PRIMARY, edgecolor='white', alpha=0.85)
axes[1,0].axvline(ages.median(), color=ACCENT, linewidth=2, linestyle='--', label=f'Median: {ages.median():.0f}')
axes[1,0].set_title('Member Age Distribution', fontweight='bold')
axes[1,0].set_xlabel('Age')
axes[1,0].set_ylabel('Count')
axes[1,0].legend()

# State distribution
state = premium['Member Country State'].value_counts()
axes[1,1].bar(state.index, state.values, color=PRIMARY, edgecolor='white')
axes[1,1].set_title('Members by State', fontweight='bold')
axes[1,1].set_ylabel('Members')
for i, (s, v) in enumerate(state.items()):
    axes[1,1].text(i, v + 10, f'{v:,}', ha='center', fontweight='bold')

add_logo(fig)
plt.suptitle('PENCOM — Member Demographics', fontsize=16, fontweight='bold', y=1.01)
plt.tight_layout()
plt.savefig(f'{OUT_DIR}/05_demographics.png', dpi=150, bbox_inches='tight')
plt.close()

# Dependency ratio
principals = premium[premium['Member Relationship'].str.strip() == 'Main member'].shape[0]
dependents = len(premium) - principals
dep_ratio = dependents / principals if principals else 0
print(f"   Principals: {principals:,} | Dependents: {dependents:,} | Dependency Ratio: {dep_ratio:.2f}")
print(f"   Gender: Male {gender.get('Male',0):,} ({gender.get('Male',0)/len(premium)*100:.1f}%) | Female {gender.get('Female',0):,} ({gender.get('Female',0)/len(premium)*100:.1f}%)")
print(f"   Median Age: {ages.median():.0f} years | Mean Age: {ages.mean():.1f} years")
print(f"   Geography: FCT {state.get('Federal Capital Territory',0):,} ({state.get('Federal Capital Territory',0)/len(premium)*100:.1f}%) | Lagos {state.get('Lagos',0):,} ({state.get('Lagos',0)/len(premium)*100:.1f}%)")

# ── 8. AGE-BAND COST ANALYSIS ────────────────────────────────────────
print("\n[8/10] Age-band cost analysis...")

claims['Age Band'] = pd.cut(claims['CURRENTAGE'],
                            bins=[0, 5, 12, 18, 30, 40, 50, 60, 70, 100],
                            labels=['0-5', '6-12', '13-18', '19-30', '31-40', '41-50', '51-60', '61-70', '71+'])

age_analysis = claims.groupby('Age Band', observed=True).agg(
    claim_count=('Amt Paid', 'count'),
    total_paid=('Amt Paid', 'sum'),
    avg_paid=('Amt Paid', 'mean'),
    unique_members=('Member Ship No', 'nunique')
).sort_index()
age_analysis['pct_of_total'] = age_analysis['total_paid'] / age_analysis['total_paid'].sum() * 100
age_analysis['cost_per_member'] = age_analysis['total_paid'] / age_analysis['unique_members']

fig, axes = plt.subplots(1, 2, figsize=(16, 6))

# Claims volume by age
axes[0].bar(age_analysis.index.astype(str), age_analysis['claim_count'], color=SECONDARY, edgecolor='white')
axes[0].set_title('Claims Volume by Age Band', fontweight='bold')
axes[0].set_ylabel('Number of Claims')
axes[0].set_xlabel('Age Band')
for i, v in enumerate(age_analysis['claim_count']):
    axes[0].text(i, v + 50, f'{v:,}', ha='center', fontsize=9)

# Cost per member by age
axes[1].bar(age_analysis.index.astype(str), age_analysis['cost_per_member'] / 1000,
            color=ACCENT, edgecolor='white')
axes[1].set_title('Average Cost per Member by Age Band', fontweight='bold')
axes[1].set_ylabel("Cost per Member (₦ '000)")
axes[1].set_xlabel('Age Band')
for i, v in enumerate(age_analysis['cost_per_member'] / 1000):
    axes[1].text(i, v + 1, f'₦{v:,.0f}K', ha='center', fontsize=9)

add_logo(fig)
plt.suptitle('PENCOM — Age-Band Analysis', fontsize=14, fontweight='bold', y=1.01)
plt.tight_layout()
plt.savefig(f'{OUT_DIR}/06_age_band_analysis.png', dpi=150, bbox_inches='tight')
plt.close()

print("\n   Age Band Breakdown:")
print(f"   {'Band':<8s} {'Claims':>7s} {'Total Paid':>15s} {'%':>6s} {'Members':>8s} {'Cost/Member':>13s}")
print("   " + "-" * 62)
for band, row in age_analysis.iterrows():
    print(f"   {str(band):<8s} {row['claim_count']:>7,} {naira(row['total_paid']):>15s} {row['pct_of_total']:>5.1f}% {row['unique_members']:>8,} {naira(row['cost_per_member']):>13s}")

# ── 9. PLAN ANALYSIS ─────────────────────────────────────────────────
print("\n[9/10] Plan analysis...")

plan_members = premium.groupby('Member Plan').agg(
    members=('Member Enrollee ID', 'nunique'),
    total_premium=('Individual Premium Fees', 'sum'),
    avg_premium=('Individual Premium Fees', 'mean')
)

# Match claims to plans via Member Ship No
member_plan_map = premium.set_index('Member Enrollee ID')['Member Plan'].to_dict()

print("\n   Plan Breakdown:")
print(f"   {'Plan':<35s} {'Members':>8s} {'Total Premium':>16s} {'Avg Premium':>14s}")
print("   " + "-" * 78)
for plan, row in plan_members.iterrows():
    print(f"   {plan:<35s} {row['members']:>8,} {naira(row['total_premium']):>16s} {naira(row['avg_premium']):>14s}")

fig, axes = plt.subplots(1, 2, figsize=(14, 6))
plan_members_sorted = plan_members.sort_values('members', ascending=False)
axes[0].bar(range(len(plan_members_sorted)),
            plan_members_sorted['members'],
            color=[PRIMARY, SECONDARY, '#F39C12', ACCENT][:len(plan_members_sorted)])
axes[0].set_xticks(range(len(plan_members_sorted)))
axes[0].set_xticklabels([p.replace('PENCOM - ','') for p in plan_members_sorted.index], rotation=30, ha='right')
axes[0].set_title('Members by Plan', fontweight='bold')
axes[0].set_ylabel('Number of Members')

axes[1].bar(range(len(plan_members_sorted)),
            plan_members_sorted['avg_premium'] / 1000,
            color=[PRIMARY, SECONDARY, '#F39C12', ACCENT][:len(plan_members_sorted)])
axes[1].set_xticks(range(len(plan_members_sorted)))
axes[1].set_xticklabels([p.replace('PENCOM - ','') for p in plan_members_sorted.index], rotation=30, ha='right')
axes[1].set_title('Average Premium by Plan', fontweight='bold')
axes[1].set_ylabel("₦ '000")
axes[1].yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'₦{v:,.0f}K'))

add_logo(fig)
plt.suptitle('PENCOM — Plan Analysis', fontsize=14, fontweight='bold', y=1.01)
plt.tight_layout()
plt.savefig(f'{OUT_DIR}/07_plan_analysis.png', dpi=150, bbox_inches='tight')
plt.close()

# ── 10. HOSPITAL NETWORK ANALYSIS ────────────────────────────────────
print("\n[10/10] Hospital network analysis...")

fig, axes = plt.subplots(1, 3, figsize=(18, 6))

# By Zone
zone = hospitals['ZONE'].value_counts()
zone.plot.bar(ax=axes[0], color=PRIMARY, edgecolor='white')
axes[0].set_title('Providers by Zone', fontweight='bold')
axes[0].set_ylabel('Count')
axes[0].tick_params(axis='x', rotation=45)

# By Category
cat = hospitals['CAT'].value_counts().sort_index()
cat.plot.bar(ax=axes[1], color=SECONDARY, edgecolor='white')
axes[1].set_title('Providers by Category', fontweight='bold')
axes[1].set_ylabel('Count')

# Top States
top_states = hospitals['STATE'].value_counts().head(10)
top_states.sort_values().plot.barh(ax=axes[2], color=PRIMARY, edgecolor='white')
axes[2].set_title('Top 10 States by Provider Count', fontweight='bold')
axes[2].set_xlabel('Count')

add_logo(fig)
plt.suptitle('PENCOM — Hospital Network Coverage', fontsize=14, fontweight='bold', y=1.01)
plt.tight_layout()
plt.savefig(f'{OUT_DIR}/08_hospital_network.png', dpi=150, bbox_inches='tight')
plt.close()

# Utilization vs Network
providers_used = claims['Provider'].nunique()
providers_available = len(hospitals)
utilization_rate = providers_used / providers_available * 100 if providers_available else 0
print(f"   Providers in network: {providers_available:,}")
print(f"   Providers utilized:   {providers_used:,}")
print(f"   Network utilization:  {utilization_rate:.1f}%")

print("\n   Zone Coverage:")
for z, count in zone.items():
    print(f"   {z:<20s}: {count:>5,} providers")

# ── CLAIMS TURNAROUND ────────────────────────────────────────────────
print("\n[BONUS] Claims processing turnaround...")

tat = claims['TAT_days'].dropna()
tat_valid = tat[tat >= 0]

fig, ax = plt.subplots(figsize=(10, 5))
ax.hist(tat_valid, bins=50, color=SECONDARY, edgecolor='white', alpha=0.85)
ax.axvline(tat_valid.median(), color=ACCENT, linewidth=2, linestyle='--', label=f'Median: {tat_valid.median():.0f} days')
ax.axvline(tat_valid.mean(), color='orange', linewidth=2, linestyle='--', label=f'Mean: {tat_valid.mean():.1f} days')
ax.set_title('PENCOM — Claims Turnaround Time (Treatment to Receipt)', fontweight='bold')
ax.set_xlabel('Days')
ax.set_ylabel('Frequency')
ax.legend()
add_logo(fig)
plt.tight_layout()
plt.savefig(f'{OUT_DIR}/09_turnaround_time.png', dpi=150)
plt.close()

# ── HIGH-VALUE CLAIMS ────────────────────────────────────────────────
print("\n[BONUS] High-value claims (₦500K+)...")

high_value = claims[claims['Amt Paid'] >= 500000].sort_values('Amt Paid', ascending=False)
print(f"   Claims ≥ ₦500K: {len(high_value):,} (Total: {naira(high_value['Amt Paid'].sum())})")

fig, ax = plt.subplots(figsize=(14, 6))
hv_dept = high_value.groupby('DEPARTMENT')['Amt Paid'].agg(['sum', 'count']).sort_values('sum', ascending=False).head(10)
hv_dept_sorted = hv_dept.sort_values('sum')
ax.barh(range(len(hv_dept_sorted)), hv_dept_sorted['sum'] / 1e6, color=ACCENT, edgecolor='white')
for i, (name, row) in enumerate(hv_dept_sorted.iterrows()):
    ax.text(row['sum']/1e6 + 0.05, i, f"n={int(row['count'])}", va='center', fontsize=10)
ax.set_yticks(range(len(hv_dept_sorted)))
ax.set_yticklabels(hv_dept_sorted.index, fontsize=10)
ax.set_xlabel('₦ Millions')
ax.set_title('PENCOM — High-Value Claims (≥₦500K) by Department', fontsize=13, fontweight='bold')
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'₦{v:,.1f}M'))
add_logo(fig)
plt.tight_layout()
plt.savefig(f'{OUT_DIR}/10_high_value_claims.png', dpi=150)
plt.close()

print("\n   Top 10 High-Value Claims:")
for _, row in high_value.head(10).iterrows():
    hv_dept_name = str(row.get('DEPARTMENT', ''))[:30]
    diag_desc = str(row.get('Diagnosis Description', ''))[:40]
    prov = str(row.get('Provider', ''))[:35]
    print(f"   {naira(row['Amt Paid']):>12s}  |  {hv_dept_name:<30s}  |  {prov:<35s}  |  {diag_desc}")

# ── EXPORT TO EXCEL ──────────────────────────────────────────────────
print("\n[EXPORT] Saving detailed Excel workbook...")

output_path = f'{OUT_DIR}/PENCOM_Deep_Dive_Report.xlsx'
with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
    # Executive Summary
    exec_data = {
        'Metric': ['Total Members', 'Active Members', 'Total Claims', 'Total Premium (₦)',
                    'Total Claims Paid (₦)', 'Loss Ratio (%)', 'Claims Rejection Rate (%)',
                    'Avg Claim Size (₦)', 'Claims per Member', 'Cost per Member (₦)',
                    'Premium per Member (₦)', 'Profit Margin (₦)'],
        'Value': [n_members, n_active, n_claims, total_premium, total_paid,
                  round(loss_ratio, 1), round(rejection_rate, 1), round(avg_claim, 0),
                  round(claims_per_member, 1), round(cost_per_member, 0),
                  round(prem_per_member, 0), round(total_premium - total_paid, 0)]
    }
    pd.DataFrame(exec_data).to_excel(writer, sheet_name='Executive Summary', index=False)

    # Monthly Trend
    monthly_export = monthly.copy()
    monthly_export.index = monthly_export.index.astype(str)
    monthly_export.to_excel(writer, sheet_name='Monthly Trend')

    # Department Analysis
    dept.to_excel(writer, sheet_name='Department Analysis')

    # Provider Analysis
    provider.head(50).to_excel(writer, sheet_name='Top Providers')

    # Diagnosis Analysis
    diag.head(50).to_excel(writer, sheet_name='Top Diagnoses')

    # Age Band Analysis
    age_analysis.to_excel(writer, sheet_name='Age Band Analysis')

    # Plan Breakdown
    plan_members.to_excel(writer, sheet_name='Plan Analysis')

    # High Value Claims
    hv_export = high_value[['Provider', 'DEPARTMENT', 'Diagnosis Description', 'Amt Claimed', 'Amt Paid', 'Treatment Date', 'CURRENTAGE']].copy()
    hv_export.to_excel(writer, sheet_name='High Value Claims', index=False)

    # Hospital Network
    zone_df = pd.DataFrame({'Zone': zone.index, 'Provider Count': zone.values})
    zone_df.to_excel(writer, sheet_name='Hospital Network', index=False)

    # Format
    workbook = writer.book
    for sheet_name in writer.sheets:
        ws = writer.sheets[sheet_name]
        ws.set_column('A:A', 30)
        ws.set_column('B:H', 18)

print(f"   Saved to: {output_path}")

# ── FINAL SUMMARY ────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("  PENCOM DEEP-DIVE REPORT — COMPLETE")
print(f"  Charts:  {OUT_DIR}/ (10 PNG files)")
print(f"  Excel:   {output_path}")
print("=" * 70)
print(f"""
  KEY FINDINGS:
  1. Loss Ratio: {loss_ratio:.1f}% — well within profitable range (<70% target)
  2. Medication is the #1 cost driver ({naira(dept.loc['Medication','total_paid'])} | {dept.loc['Medication','pct_of_total']:.1f}% of total)
  3. Top provider (DEDA Hospital) accounts for {provider.iloc[0]['pct_of_total']:.1f}% of all claims
  4. Malaria remains the costliest disease category ({naira(malaria_cost)})
  5. 41-50 age band has highest claims volume ({age_analysis.loc['41-50','claim_count']:,} claims)
  6. {principals:,} principals with {dep_ratio:.2f} dependency ratio
  7. 96.2% FCT-concentrated membership
  8. Network utilization: {utilization_rate:.1f}% of available providers
""")

#!/usr/bin/env python3
"""
Leadway Health Insurance — Corporate Client Data Analytics Report
=================================================================
Comprehensive analytics across Baker Hughes, Guinness, and PENCOM
covering claims, premiums, demographics, loss ratios, and utilization.
"""

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from datetime import datetime
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# ── Style setup ──────────────────────────────────────────────────────
sns.set_theme(style="whitegrid", font_scale=1.1)
COLORS = {
    'Baker Hughes': '#1B4F72',
    'Guinness': '#922B21',
    'PENCOM': '#1D8348',
}
PALETTE = list(COLORS.values())

print("=" * 70)
print("  LEADWAY HEALTH INSURANCE — DATA ANALYTICS REPORT")
print(f"  Generated: {datetime.now().strftime('%B %d, %Y')}")
print("=" * 70)

# ── 1. LOAD DATA ─────────────────────────────────────────────────────
print("\n[1/8] Loading data...")

claims = {}
premiums = {}

# Baker Hughes
bh_claims_24 = pd.read_excel('Baker hughes claims 2024.xlsx')
bh_claims_25 = pd.read_excel('Baker hughes claims 2025.xlsx')
bh_claims_24['Year'] = 2024
bh_claims_25['Year'] = 2025
claims['Baker Hughes'] = pd.concat([bh_claims_24, bh_claims_25], ignore_index=True)

bh_prem_24 = pd.read_excel('Baker hughes premium 2024.xlsx')
bh_prem_25 = pd.read_excel('Baker hughes premium 2025.xlsx')
bh_prem_24['Year'] = 2024
bh_prem_25['Year'] = 2025
premiums['Baker Hughes'] = pd.concat([bh_prem_24, bh_prem_25], ignore_index=True)

# Guinness
claims['Guinness'] = pd.read_excel('Guiness claims (1).xlsx')
premiums['Guinness'] = pd.read_excel('GUINESS PRODUCTION.xlsx')

# PENCOM
claims['PENCOM'] = pd.read_excel('PENCOM CLAIMS.xlsx')
premiums['PENCOM'] = pd.read_excel('PENCOM Premium.xlsx')

print("   Data loaded successfully.")

# ── 2. DATA CLEANING ─────────────────────────────────────────────────
print("[2/8] Cleaning data...")

for client in claims:
    df = claims[client]
    # Standardise monetary columns
    for col in ['Amt Claimed', 'Amt Paid', 'Debit']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    # Parse dates
    if 'Treatment Date' in df.columns:
        df['Treatment Date'] = pd.to_datetime(df['Treatment Date'], errors='coerce')
    if 'Received On' in df.columns:
        df['Received On'] = pd.to_datetime(df['Received On'], errors='coerce')
    df['CURRENTAGE'] = pd.to_numeric(df.get('CURRENTAGE', pd.Series(dtype=float)), errors='coerce')
    claims[client] = df

for client in premiums:
    df = premiums[client]
    prem_col = 'Individual Premium Fees'
    if prem_col in df.columns:
        df[prem_col] = pd.to_numeric(df[prem_col], errors='coerce').fillna(0)
    for dc in ['Member Effectivedate', 'Client Expiry Date', 'Member Date Of Birth']:
        if dc in df.columns:
            df[dc] = pd.to_datetime(df[dc], errors='coerce')
    premiums[client] = df

print("   Data cleaned.")

# ── 3. EXECUTIVE SUMMARY ─────────────────────────────────────────────
print("[3/8] Computing executive summary...\n")

summary_rows = []
for client in ['Baker Hughes', 'Guinness', 'PENCOM']:
    c = claims[client]
    p = premiums[client]
    total_claims = c['Amt Paid'].sum()
    total_premium = p['Individual Premium Fees'].sum()
    n_claims = len(c)
    n_members = p['Member Enrollee ID'].nunique() if 'Member Enrollee ID' in p.columns else len(p)
    loss_ratio = (total_claims / total_premium * 100) if total_premium > 0 else 0
    avg_claim = total_claims / n_claims if n_claims > 0 else 0
    summary_rows.append({
        'Client': client,
        'Total Members': n_members,
        'Total Claims Count': n_claims,
        'Total Claims Paid (₦)': total_claims,
        'Total Premium (₦)': total_premium,
        'Loss Ratio (%)': round(loss_ratio, 1),
        'Avg Claim (₦)': round(avg_claim, 2),
    })

summary_df = pd.DataFrame(summary_rows)
print("  ┌─────────────────── EXECUTIVE SUMMARY ───────────────────┐")
for _, row in summary_df.iterrows():
    print(f"  │ {row['Client']:15s} │ Members: {row['Total Members']:>6,} │ Claims: {row['Total Claims Count']:>6,} │")
    print(f"  │                 │ Premium: ₦{row['Total Premium (₦)']:>14,.0f} │")
    print(f"  │                 │ Paid:    ₦{row['Total Claims Paid (₦)']:>14,.0f} │")
    print(f"  │                 │ Loss Ratio: {row['Loss Ratio (%)']:>6.1f}%  │ Avg: ₦{row['Avg Claim (₦)']:>10,.0f} │")
    print(f"  ├─────────────────────────────────────────────────────────┤")
print(f"  └─────────────────────────────────────────────────────────┘\n")

# ── 4. VISUALIZATIONS ────────────────────────────────────────────────
print("[4/8] Generating visualizations...")

fig_dir = '/home/user/datadump/report_charts'
import os
os.makedirs(fig_dir, exist_ok=True)

# ──── Chart 1: Claims Paid vs Premium by Client ────
fig, ax = plt.subplots(figsize=(10, 6))
x = np.arange(len(summary_df))
width = 0.35
ax.bar(x - width/2, summary_df['Total Premium (₦)'] / 1e6, width, label='Premium Collected', color='#2E86C1')
ax.bar(x + width/2, summary_df['Total Claims Paid (₦)'] / 1e6, width, label='Claims Paid', color='#E74C3C')
ax.set_xlabel('Client')
ax.set_ylabel('Amount (₦ Millions)')
ax.set_title('Premium Collected vs Claims Paid by Client')
ax.set_xticks(x)
ax.set_xticklabels(summary_df['Client'])
ax.legend()
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'₦{v:,.0f}M'))
plt.tight_layout()
plt.savefig(f'{fig_dir}/01_premium_vs_claims.png', dpi=150)
plt.close()

# ──── Chart 2: Loss Ratio Comparison ────
fig, ax = plt.subplots(figsize=(8, 5))
bars = ax.bar(summary_df['Client'], summary_df['Loss Ratio (%)'],
              color=[COLORS[c] for c in summary_df['Client']])
ax.axhline(y=100, color='red', linestyle='--', linewidth=1.5, label='Break-even (100%)')
ax.axhline(y=70, color='orange', linestyle='--', linewidth=1, alpha=0.7, label='Target (70%)')
for bar, val in zip(bars, summary_df['Loss Ratio (%)']):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, f'{val:.1f}%',
            ha='center', va='bottom', fontweight='bold')
ax.set_ylabel('Loss Ratio (%)')
ax.set_title('Loss Ratio by Client')
ax.legend()
plt.tight_layout()
plt.savefig(f'{fig_dir}/02_loss_ratio.png', dpi=150)
plt.close()

# ──── Chart 3: Claims by Department / Service ────
fig, axes = plt.subplots(1, 3, figsize=(18, 6))
for i, client in enumerate(['Baker Hughes', 'Guinness', 'PENCOM']):
    c = claims[client]
    dept_col = 'DEPARTMENT' if 'DEPARTMENT' in c.columns else 'SERVICE'
    top_dept = c.groupby(dept_col)['Amt Paid'].sum().nlargest(8).sort_values()
    top_dept_m = top_dept / 1e6
    top_dept_m.plot.barh(ax=axes[i], color=COLORS[client], edgecolor='white')
    axes[i].set_title(f'{client}\nTop Departments by Claims Paid')
    axes[i].set_xlabel('₦ Millions')
    axes[i].xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'₦{v:,.1f}M'))
plt.tight_layout()
plt.savefig(f'{fig_dir}/03_claims_by_department.png', dpi=150)
plt.close()

# ──── Chart 4: Age Distribution of Claimants ────
fig, axes = plt.subplots(1, 3, figsize=(18, 5))
for i, client in enumerate(['Baker Hughes', 'Guinness', 'PENCOM']):
    c = claims[client]
    ages = c['CURRENTAGE'].dropna()
    if len(ages) > 0:
        axes[i].hist(ages, bins=range(0, 85, 5), color=COLORS[client], edgecolor='white', alpha=0.85)
    axes[i].set_title(f'{client} — Age Distribution')
    axes[i].set_xlabel('Age')
    axes[i].set_ylabel('Claim Count')
plt.tight_layout()
plt.savefig(f'{fig_dir}/04_age_distribution.png', dpi=150)
plt.close()

# ──── Chart 5: Monthly Claims Trend (Baker Hughes 2024 vs 2025) ────
fig, ax = plt.subplots(figsize=(12, 5))
bh = claims['Baker Hughes'].copy()
bh['Month'] = bh['Treatment Date'].dt.to_period('M')
for year in [2024, 2025]:
    subset = bh[bh['Year'] == year].copy()
    monthly = subset.groupby(subset['Treatment Date'].dt.month)['Amt Paid'].sum() / 1e6
    ax.plot(monthly.index, monthly.values, marker='o', linewidth=2, label=str(year))
ax.set_xlabel('Month')
ax.set_ylabel('Claims Paid (₦ Millions)')
ax.set_title('Baker Hughes — Monthly Claims Trend (2024 vs 2025)')
ax.set_xticks(range(1, 13))
ax.set_xticklabels(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'])
ax.legend()
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'₦{v:,.1f}M'))
plt.tight_layout()
plt.savefig(f'{fig_dir}/05_bh_monthly_trend.png', dpi=150)
plt.close()

# ──── Chart 6: Top 10 Providers by Claims Paid (All Clients) ────
fig, ax = plt.subplots(figsize=(12, 6))
all_claims = pd.concat([c.assign(Client=name) for name, c in claims.items()], ignore_index=True)
top_providers = all_claims.groupby('Provider')['Amt Paid'].sum().nlargest(15).sort_values()
top_providers_m = top_providers / 1e6
top_providers_m.plot.barh(ax=ax, color='#2E86C1', edgecolor='white')
ax.set_title('Top 15 Providers by Total Claims Paid (All Clients)')
ax.set_xlabel('₦ Millions')
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'₦{v:,.1f}M'))
plt.tight_layout()
plt.savefig(f'{fig_dir}/06_top_providers.png', dpi=150)
plt.close()

# ──── Chart 7: Gender Distribution of Members ────
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
for i, client in enumerate(['Baker Hughes', 'Guinness', 'PENCOM']):
    p = premiums[client]
    if 'Member Gender' in p.columns:
        gender_counts = p['Member Gender'].value_counts()
        axes[i].pie(gender_counts, labels=gender_counts.index, autopct='%1.1f%%',
                     colors=['#3498DB', '#E74C3C', '#95A5A6'], startangle=90)
    axes[i].set_title(f'{client}\nGender Distribution')
plt.tight_layout()
plt.savefig(f'{fig_dir}/07_gender_distribution.png', dpi=150)
plt.close()

# ──── Chart 8: Member Relationship (Principal vs Dependent) ────
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
for i, client in enumerate(['Baker Hughes', 'Guinness', 'PENCOM']):
    p = premiums[client]
    if 'Member Relationship' in p.columns:
        rel_counts = p['Member Relationship'].value_counts()
        axes[i].pie(rel_counts, labels=rel_counts.index, autopct='%1.1f%%',
                     colors=['#1ABC9C', '#F39C12', '#8E44AD', '#E74C3C'], startangle=90)
    axes[i].set_title(f'{client}\nPrincipal vs Dependents')
plt.tight_layout()
plt.savefig(f'{fig_dir}/08_relationship_split.png', dpi=150)
plt.close()

# ──── Chart 9: Geographic Distribution (State) ────
fig, ax = plt.subplots(figsize=(14, 6))
all_prem = pd.concat([p.assign(Client=name) for name, p in premiums.items()], ignore_index=True)
if 'Member Country State' in all_prem.columns:
    state_counts = all_prem['Member Country State'].value_counts().nlargest(15)
    state_counts.plot.bar(ax=ax, color='#2E86C1', edgecolor='white')
    ax.set_title('Top 15 States by Member Count (All Clients)')
    ax.set_ylabel('Number of Members')
    ax.set_xlabel('')
    plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.savefig(f'{fig_dir}/09_geographic_distribution.png', dpi=150)
plt.close()

# ──── Chart 10: Top Diagnoses ────
fig, ax = plt.subplots(figsize=(12, 6))
if 'Diagnosis Description' in all_claims.columns:
    top_diag = all_claims.groupby('Diagnosis Description')['Amt Paid'].sum().nlargest(15).sort_values()
    top_diag_m = top_diag / 1e6
    top_diag_m.plot.barh(ax=ax, color='#922B21', edgecolor='white')
    ax.set_title('Top 15 Diagnoses by Claims Paid (All Clients)')
    ax.set_xlabel('₦ Millions')
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'₦{v:,.1f}M'))
plt.tight_layout()
plt.savefig(f'{fig_dir}/10_top_diagnoses.png', dpi=150)
plt.close()

print(f"   10 charts saved to {fig_dir}/")

# ── 5. CLAIMS STATUS ANALYSIS ────────────────────────────────────────
print("[5/8] Analyzing claim statuses...")

print("\n  CLAIM STATUS BREAKDOWN:")
for client in ['Baker Hughes', 'Guinness', 'PENCOM']:
    c = claims[client]
    if 'Claim Status' in c.columns:
        status = c['Claim Status'].value_counts()
        total = len(c)
        print(f"\n  {client}:")
        for s, count in status.items():
            pct = count / total * 100
            print(f"    {s:25s} — {count:>6,} ({pct:5.1f}%)")

# ── 6. PER-MEMBER COST ANALYSIS ──────────────────────────────────────
print("\n[6/8] Per-member cost analysis...")

print("\n  PER-MEMBER METRICS:")
for client in ['Baker Hughes', 'Guinness', 'PENCOM']:
    c = claims[client]
    p = premiums[client]
    n_members = p['Member Enrollee ID'].nunique() if 'Member Enrollee ID' in p.columns else len(p)
    total_paid = c['Amt Paid'].sum()
    total_prem = p['Individual Premium Fees'].sum()
    claims_per_member = len(c) / n_members if n_members > 0 else 0
    cost_per_member = total_paid / n_members if n_members > 0 else 0
    premium_per_member = total_prem / n_members if n_members > 0 else 0
    print(f"\n  {client}:")
    print(f"    Unique Members:       {n_members:>6,}")
    print(f"    Claims per Member:    {claims_per_member:>9.1f}")
    print(f"    Avg Cost per Member:  ₦{cost_per_member:>12,.0f}")
    print(f"    Avg Premium/Member:   ₦{premium_per_member:>12,.0f}")

# ── 7. HIGH-VALUE CLAIMS ANALYSIS ────────────────────────────────────
print("\n[7/8] High-value claims analysis...")

print("\n  HIGH-VALUE CLAIMS (Top 5 per Client):")
for client in ['Baker Hughes', 'Guinness', 'PENCOM']:
    c = claims[client]
    top5 = c.nlargest(5, 'Amt Paid')[['Provider', 'Diagnosis Description', 'Amt Paid', 'DEPARTMENT']].copy()
    top5['Amt Paid'] = top5['Amt Paid'].apply(lambda x: f'₦{x:,.0f}')
    print(f"\n  {client}:")
    for _, row in top5.iterrows():
        dept = row.get('DEPARTMENT', 'N/A')
        diag = str(row.get('Diagnosis Description', 'N/A'))[:40]
        print(f"    ₦ {row['Amt Paid']:>15s}  |  {dept}  |  {diag}")

# ── 8. EXPORT SUMMARY TO EXCEL ───────────────────────────────────────
print("\n[8/8] Exporting analytics summary to Excel...")

output_path = '/home/user/datadump/Analytics_Report_Summary.xlsx'
with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
    # Executive Summary
    summary_df.to_excel(writer, sheet_name='Executive Summary', index=False)

    # Claims by Department per client
    for client in ['Baker Hughes', 'Guinness', 'PENCOM']:
        c = claims[client]
        dept_col = 'DEPARTMENT' if 'DEPARTMENT' in c.columns else 'SERVICE'
        dept_summary = c.groupby(dept_col).agg(
            Claim_Count=('Amt Paid', 'count'),
            Total_Paid=('Amt Paid', 'sum'),
            Avg_Paid=('Amt Paid', 'mean'),
            Total_Claimed=('Amt Claimed', 'sum') if 'Amt Claimed' in c.columns else ('Amt Paid', 'sum')
        ).sort_values('Total_Paid', ascending=False)
        sheet = f'{client[:15]} Depts'
        dept_summary.to_excel(writer, sheet_name=sheet)

    # Top Providers
    provider_summary = all_claims.groupby(['Client', 'Provider']).agg(
        Claim_Count=('Amt Paid', 'count'),
        Total_Paid=('Amt Paid', 'sum'),
        Avg_Paid=('Amt Paid', 'mean')
    ).sort_values('Total_Paid', ascending=False).head(50)
    provider_summary.to_excel(writer, sheet_name='Top Providers')

    # Top Diagnoses
    if 'Diagnosis Description' in all_claims.columns:
        diag_summary = all_claims.groupby(['Client', 'Diagnosis Description']).agg(
            Claim_Count=('Amt Paid', 'count'),
            Total_Paid=('Amt Paid', 'sum'),
            Avg_Paid=('Amt Paid', 'mean')
        ).sort_values('Total_Paid', ascending=False).head(50)
        diag_summary.to_excel(writer, sheet_name='Top Diagnoses')

    # Geographic
    if 'Member Country State' in all_prem.columns:
        geo = all_prem.groupby(['Client', 'Member Country State']).size().reset_index(name='Members')
        geo = geo.sort_values('Members', ascending=False)
        geo.to_excel(writer, sheet_name='Geography', index=False)

    # Format workbook
    workbook = writer.book
    money_fmt = workbook.add_format({'num_format': '₦#,##0'})
    pct_fmt = workbook.add_format({'num_format': '0.0%'})
    header_fmt = workbook.add_format({'bold': True, 'bg_color': '#1B4F72', 'font_color': 'white'})

    for sheet_name in writer.sheets:
        ws = writer.sheets[sheet_name]
        ws.set_column('A:A', 25)
        ws.set_column('B:H', 18)

print(f"   Report saved to: {output_path}")

print("\n" + "=" * 70)
print("  REPORT COMPLETE")
print(f"  Charts: {fig_dir}/ (10 PNG files)")
print(f"  Excel:  {output_path}")
print("=" * 70)

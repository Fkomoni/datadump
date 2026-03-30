#!/usr/bin/env python3
"""
Quick Report Generator for Leadway Health Insurance Data
Usage:
    python3 generate_report.py                          # All clients
    python3 generate_report.py --client "Baker Hughes"  # Single client
    python3 generate_report.py --type claims             # Claims only
    python3 generate_report.py --type premium            # Premium only
"""
import pandas as pd
import argparse
import os
import warnings
warnings.filterwarnings('ignore')

CSV_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'csv_data')

CLIENTS = {
    'Baker Hughes': {
        'claims': ['Baker hughes claims 2024.csv', 'Baker hughes claims 2025.csv'],
        'premium': ['Baker hughes premium 2024.csv', 'Baker hughes premium 2025.csv'],
        'hospitals': 'Baker hughes HOSPITAL LIST (STANDARD).csv',
        'benefit': 'BAKER HUGHES BENEFIT.csv',
    },
    'Guinness': {
        'claims': ['Guiness claims (1).csv'],
        'premium': ['GUINESS PRODUCTION.csv'],
        'hospitals': 'GUINESS HOSPITAL LIST (STANDARD).csv',
        'benefit': 'Guiness benefit.csv',
    },
    'PENCOM': {
        'claims': ['PENCOM CLAIMS.csv'],
        'premium': ['PENCOM Premium.csv'],
        'hospitals': 'PENCOM HOSPITAL LIST (STANDARD).csv',
        'benefit': 'PENCOM BENEFIT.csv',
    },
}


def load_csv(filename):
    path = os.path.join(CSV_DIR, filename)
    if os.path.exists(path):
        return pd.read_csv(path)
    return pd.DataFrame()


def fmt(amount):
    """Format NGN amounts."""
    if pd.isna(amount):
        return 'N/A'
    return f"NGN {amount:,.2f}"


def claims_report(client_name, files):
    frames = [load_csv(f) for f in files]
    df = pd.concat(frames, ignore_index=True)
    if df.empty:
        return

    print(f"\n{'='*60}")
    print(f"  CLAIMS REPORT: {client_name}")
    print(f"{'='*60}")
    print(f"  Total claims:          {len(df):,}")

    if 'Amt Claimed' in df.columns:
        print(f"  Total amount claimed:  {fmt(df['Amt Claimed'].sum())}")
    if 'Amt Paid' in df.columns:
        print(f"  Total amount paid:     {fmt(df['Amt Paid'].sum())}")
        print(f"  Average claim paid:    {fmt(df['Amt Paid'].mean())}")

    if 'Claim Status' in df.columns:
        print(f"\n  Claims by Status:")
        status = df['Claim Status'].value_counts()
        for s, c in status.items():
            print(f"    {s:<25} {c:>8,}  ({c/len(df)*100:.1f}%)")

    if 'DEPARTMENT' in df.columns:
        print(f"\n  Top 10 Departments:")
        dept = df['DEPARTMENT'].value_counts().head(10)
        for d, c in dept.items():
            print(f"    {str(d):<30} {c:>8,}")

    if 'Provider' in df.columns:
        print(f"\n  Top 10 Providers by Claims:")
        prov = df['Provider'].value_counts().head(10)
        for p, c in prov.items():
            print(f"    {str(p)[:40]:<42} {c:>6,}")

    if 'Amt Paid' in df.columns and 'Provider' in df.columns:
        print(f"\n  Top 10 Providers by Amount Paid:")
        prov_amt = df.groupby('Provider')['Amt Paid'].sum().sort_values(ascending=False).head(10)
        for p, a in prov_amt.items():
            print(f"    {str(p)[:40]:<42} {fmt(a)}")

    if 'Diagnosis Description' in df.columns:
        print(f"\n  Top 10 Diagnoses:")
        diag = df['Diagnosis Description'].value_counts().head(10)
        for d, c in diag.items():
            print(f"    {str(d)[:50]:<52} {c:>6,}")

    # Loss ratio hint
    if 'Amt Claimed' in df.columns and 'Amt Paid' in df.columns:
        claimed = df['Amt Claimed'].sum()
        paid = df['Amt Paid'].sum()
        if claimed > 0:
            print(f"\n  Payment ratio (paid/claimed): {paid/claimed*100:.1f}%")


def premium_report(client_name, files):
    frames = [load_csv(f) for f in files]
    df = pd.concat(frames, ignore_index=True)
    if df.empty:
        return

    print(f"\n{'='*60}")
    print(f"  PREMIUM/ENROLLMENT REPORT: {client_name}")
    print(f"{'='*60}")
    print(f"  Total enrollees:       {len(df):,}")

    premium_col = 'Individual Premium Fees'
    if premium_col in df.columns:
        print(f"  Total premium:         {fmt(df[premium_col].sum())}")
        print(f"  Average premium:       {fmt(df[premium_col].mean())}")
        print(f"  Median premium:        {fmt(df[premium_col].median())}")

    if 'Member Gender' in df.columns:
        print(f"\n  Gender Distribution:")
        gender = df['Member Gender'].value_counts()
        for g, c in gender.items():
            print(f"    {g:<20} {c:>6,}  ({c/len(df)*100:.1f}%)")

    if 'Member Relationship' in df.columns:
        print(f"\n  Relationship Type:")
        rel = df['Member Relationship'].value_counts()
        for r, c in rel.items():
            print(f"    {str(r):<20} {c:>6,}  ({c/len(df)*100:.1f}%)")

    if 'Member Country State' in df.columns:
        print(f"\n  Top 10 States:")
        state = df['Member Country State'].value_counts().head(10)
        for s, c in state.items():
            print(f"    {str(s):<25} {c:>6,}")

    plan_col = None
    for col in ['Member Plan', 'Product Scheme Type']:
        if col in df.columns:
            plan_col = col
            break
    if plan_col:
        print(f"\n  Plans:")
        plans = df[plan_col].value_counts()
        for p, c in plans.items():
            print(f"    {str(p):<30} {c:>6,}")


def loss_ratio_summary(clients_to_run):
    """Cross-client loss ratio comparison."""
    print(f"\n{'='*60}")
    print(f"  LOSS RATIO SUMMARY (All Clients)")
    print(f"{'='*60}")
    print(f"  {'Client':<20} {'Premium':>18} {'Claims Paid':>18} {'Loss Ratio':>12}")
    print(f"  {'-'*20} {'-'*18} {'-'*18} {'-'*12}")

    for name, files in clients_to_run.items():
        # Total premium
        premium_frames = [load_csv(f) for f in files.get('premium', [])]
        prem_df = pd.concat(premium_frames, ignore_index=True) if premium_frames else pd.DataFrame()
        total_premium = prem_df['Individual Premium Fees'].sum() if 'Individual Premium Fees' in prem_df.columns else 0

        # Total claims paid
        claims_frames = [load_csv(f) for f in files.get('claims', [])]
        claims_df = pd.concat(claims_frames, ignore_index=True) if claims_frames else pd.DataFrame()
        total_paid = claims_df['Amt Paid'].sum() if 'Amt Paid' in claims_df.columns else 0

        ratio = (total_paid / total_premium * 100) if total_premium > 0 else 0
        print(f"  {name:<20} {fmt(total_premium):>18} {fmt(total_paid):>18} {ratio:>10.1f}%")


def main():
    parser = argparse.ArgumentParser(description='Generate health insurance analytics report')
    parser.add_argument('--client', type=str, help='Client name (Baker Hughes, Guinness, PENCOM)')
    parser.add_argument('--type', type=str, choices=['claims', 'premium', 'all'], default='all',
                        help='Report type')
    args = parser.parse_args()

    if args.client:
        matched = {k: v for k, v in CLIENTS.items() if args.client.lower() in k.lower()}
        if not matched:
            print(f"Client '{args.client}' not found. Available: {', '.join(CLIENTS.keys())}")
            return
        clients_to_run = matched
    else:
        clients_to_run = CLIENTS

    print("\n" + "#" * 60)
    print("#  LEADWAY HEALTH - INSURANCE ANALYTICS REPORT")
    print("#" + "#" * 59)

    for name, files in clients_to_run.items():
        if args.type in ('claims', 'all'):
            claims_report(name, files.get('claims', []))
        if args.type in ('premium', 'all'):
            premium_report(name, files.get('premium', []))

    if args.type in ('all',) and len(clients_to_run) > 1:
        loss_ratio_summary(clients_to_run)

    print(f"\n{'='*60}")
    print("  Report complete.")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()

"""
Data Preprocessing Script - Converts Excel files to CSV and generates analytics-ready summaries.
Solves timeout issues by creating fast-loading intermediate files.
"""
import pandas as pd
import os
import warnings
warnings.filterwarnings('ignore')

DATA_DIR = "/home/user/datadump"
OUTPUT_DIR = os.path.join(DATA_DIR, "processed")
SUMMARY_DIR = os.path.join(DATA_DIR, "summaries")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(SUMMARY_DIR, exist_ok=True)

# ── Client file mappings ──────────────────────────────────────────────
CLIENTS = {
    "baker_hughes": {
        "claims": ["Baker hughes claims 2024.xlsx", "Baker hughes claims 2025.xlsx"],
        "premium": ["Baker hughes premium 2024.xlsx", "Baker hughes premium 2025.xlsx"],
        "benefit": ["BAKER HUGHES BENEFIT.xlsx"],
        "hospital_list": ["Baker hughes HOSPITAL LIST (STANDARD).xlsx"],
    },
    "flour_mills": {
        "claims": [
            "FLOUR MILLS CLAIMS BATCH 1.xlsx",
            "FLOUR MILLS CLAIMS BATCH 2.xlsx",
            "FLOUR MILLS CLIAMS BATCH 3.xlsx",
            "flour mills batch 4.xlsx",
        ],
        "production": ["FFLOUR MILLS PRODUCTION.xlsx"],
        "benefit": ["FLOUR MILLS UPDATED BENEFIT.xlsx"],
        "hospital_list": ["FLOURMILLS HOSPITAL LIST (STANDARD).xlsx"],
    },
    "guinness": {
        "claims": ["Guiness claims (1).xlsx"],
        "production": ["GUINESS PRODUCTION.xlsx"],
        "benefit": ["Guiness benefit.xlsx"],
        "hospital_list": ["GUINESS HOSPITAL LIST (STANDARD).xlsx"],
    },
    "pencom": {
        "claims": ["PENCOM CLAIMS.xlsx"],
        "premium": ["PENCOM Premium.xlsx"],
        "benefit": ["PENCOM BENEFIT.xlsx"],
        "hospital_list": ["PENCOM HOSPITAL LIST (STANDARD).xlsx"],
    },
}


def load_excel(filepath):
    """Load first sheet of an Excel file."""
    xl = pd.ExcelFile(filepath)
    df = pd.read_excel(xl, sheet_name=0)
    xl.close()
    return df


def convert_to_csv(client_name, data_type, files):
    """Convert Excel files to CSV, concatenating multiple files."""
    dfs = []
    for f in files:
        path = os.path.join(DATA_DIR, f)
        if not os.path.exists(path):
            print(f"  WARNING: {f} not found, skipping")
            continue
        print(f"  Loading {f}...")
        df = load_excel(path)
        df["_source_file"] = f
        dfs.append(df)

    if not dfs:
        return None

    combined = pd.concat(dfs, ignore_index=True, sort=False)
    out_path = os.path.join(OUTPUT_DIR, f"{client_name}_{data_type}.csv")
    combined.to_csv(out_path, index=False)
    print(f"  -> Saved {out_path} ({len(combined):,} rows)")
    return combined


def generate_claims_summary(client_name, claims_df):
    """Generate analytics summaries from claims data."""
    if claims_df is None or claims_df.empty:
        return

    # Normalize column names for consistency
    claims_df.columns = claims_df.columns.str.strip()

    # Find amount/cost columns
    amount_cols = [c for c in claims_df.columns if any(
        kw in c.lower() for kw in ['amount', 'cost', 'paid', 'bill', 'charge', 'approved']
    )]

    # Convert amount columns to numeric
    for col in amount_cols:
        claims_df[col] = pd.to_numeric(claims_df[col], errors='coerce')

    summary = {
        "total_claims": len(claims_df),
        "unique_members": claims_df.get("Member Ship No", claims_df.get("Member Ship No", pd.Series())).nunique(),
    }

    # Per-amount-column stats
    for col in amount_cols:
        summary[f"{col}_total"] = claims_df[col].sum()
        summary[f"{col}_mean"] = claims_df[col].mean()
        summary[f"{col}_median"] = claims_df[col].median()

    # Save summary stats
    summary_df = pd.DataFrame([summary])
    summary_df.to_csv(os.path.join(SUMMARY_DIR, f"{client_name}_claims_overview.csv"), index=False)

    # Claims by service type (if column exists)
    service_col = None
    for col_name in ["SERVICE", "Service", "service", "DEPARTMENT"]:
        if col_name in claims_df.columns:
            service_col = col_name
            break

    if service_col:
        by_service = claims_df.groupby(service_col).agg(
            claim_count=("Claim NUmber", "count"),
            **{f"{ac}_total": (ac, "sum") for ac in amount_cols if ac in claims_df.columns}
        ).reset_index().sort_values("claim_count", ascending=False)
        by_service.to_csv(os.path.join(SUMMARY_DIR, f"{client_name}_claims_by_service.csv"), index=False)
        print(f"  -> Saved claims_by_service ({len(by_service)} service types)")

    # Claims by provider (if column exists)
    provider_col = None
    for col_name in ["Provider", "PROVIDER", "provider", "Provider Name"]:
        if col_name in claims_df.columns:
            provider_col = col_name
            break

    if provider_col:
        by_provider = claims_df.groupby(provider_col).agg(
            claim_count=("Claim NUmber", "count"),
            **{f"{ac}_total": (ac, "sum") for ac in amount_cols if ac in claims_df.columns}
        ).reset_index().sort_values("claim_count", ascending=False)
        by_provider.to_csv(os.path.join(SUMMARY_DIR, f"{client_name}_claims_by_provider.csv"), index=False)
        print(f"  -> Saved claims_by_provider ({len(by_provider)} providers)")

    # Claims by scheme/plan
    scheme_col = None
    for col_name in ["SCHEME", "Scheme", "Member Plan"]:
        if col_name in claims_df.columns:
            scheme_col = col_name
            break

    if scheme_col:
        by_scheme = claims_df.groupby(scheme_col).agg(
            claim_count=("Claim NUmber", "count"),
            **{f"{ac}_total": (ac, "sum") for ac in amount_cols if ac in claims_df.columns}
        ).reset_index().sort_values("claim_count", ascending=False)
        by_scheme.to_csv(os.path.join(SUMMARY_DIR, f"{client_name}_claims_by_scheme.csv"), index=False)
        print(f"  -> Saved claims_by_scheme")

    # Monthly trend (if date column exists)
    date_col = None
    for col_name in claims_df.columns:
        if any(kw in col_name.lower() for kw in ['date', 'treatment']):
            date_col = col_name
            break

    if date_col:
        claims_df["_parsed_date"] = pd.to_datetime(claims_df[date_col], errors="coerce")
        claims_df["_month"] = claims_df["_parsed_date"].dt.to_period("M")
        monthly = claims_df.dropna(subset=["_month"]).groupby("_month").agg(
            claim_count=("Claim NUmber", "count"),
            **{f"{ac}_total": (ac, "sum") for ac in amount_cols if ac in claims_df.columns}
        ).reset_index()
        monthly["_month"] = monthly["_month"].astype(str)
        monthly.to_csv(os.path.join(SUMMARY_DIR, f"{client_name}_claims_monthly.csv"), index=False)
        print(f"  -> Saved claims_monthly ({len(monthly)} months)")

    print(f"  -> Saved claims_overview")


def generate_production_summary(client_name, prod_df):
    """Generate member/enrollment summaries."""
    if prod_df is None or prod_df.empty:
        return

    prod_df.columns = prod_df.columns.str.strip()

    # Normalize column names
    col_map = {}
    for c in prod_df.columns:
        cl = c.lower().replace(" ", "_")
        if "plan" in cl:
            col_map[c] = "plan"
        elif "relationship" in cl:
            col_map[c] = "relationship"
        elif "gender" in cl:
            col_map[c] = "gender"
        elif "state" in cl:
            col_map[c] = "state"

    for orig, new in col_map.items():
        if new not in prod_df.columns:
            prod_df[new] = prod_df[orig]

    summaries = {}
    for group_col in ["plan", "relationship", "gender", "state"]:
        if group_col in prod_df.columns:
            summaries[group_col] = prod_df[group_col].value_counts().reset_index()
            summaries[group_col].columns = [group_col, "count"]

    for key, df in summaries.items():
        df.to_csv(os.path.join(SUMMARY_DIR, f"{client_name}_members_by_{key}.csv"), index=False)
        print(f"  -> Saved members_by_{key}")


# ── Main processing ──────────────────────────────────────────────────
if __name__ == "__main__":
    # Also convert shared files
    print("=" * 60)
    print("Converting provider list...")
    provider_path = os.path.join(DATA_DIR, "2025 LH Provider List standard leadway hospital list.xlsx")
    if os.path.exists(provider_path):
        xl = pd.ExcelFile(provider_path)
        for sheet in xl.sheet_names:
            if sheet.startswith("_"):
                continue
            df = pd.read_excel(xl, sheet_name=sheet)
            safe_name = sheet.lower().replace(" ", "_").replace("-", "_")
            df.to_csv(os.path.join(OUTPUT_DIR, f"provider_list_{safe_name}.csv"), index=False)
            print(f"  -> {sheet}: {len(df):,} rows")
        xl.close()

    print("\nConverting standard benefit...")
    benefit_path = os.path.join(DATA_DIR, "2026 STANDARD BENEFIT LWH.xlsx")
    if os.path.exists(benefit_path):
        xl = pd.ExcelFile(benefit_path)
        for sheet in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=sheet)
            safe_name = sheet.lower().replace(" ", "_").replace("-", "_")
            df.to_csv(os.path.join(OUTPUT_DIR, f"standard_benefit_{safe_name}.csv"), index=False)
            print(f"  -> {sheet}: {len(df):,} rows")
        xl.close()

    for client, file_groups in CLIENTS.items():
        print(f"\n{'=' * 60}")
        print(f"Processing {client.upper().replace('_', ' ')}...")
        print("=" * 60)

        claims_df = None
        for data_type, files in file_groups.items():
            df = convert_to_csv(client, data_type, files)
            if data_type == "claims":
                claims_df = df
            elif data_type in ("premium", "production"):
                generate_production_summary(client, df)

        generate_claims_summary(client, claims_df)

    print(f"\n{'=' * 60}")
    print("DONE! All files processed.")
    print(f"  CSV files: {OUTPUT_DIR}/")
    print(f"  Summaries: {SUMMARY_DIR}/")
    print("=" * 60)

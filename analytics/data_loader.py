"""
Data loader module for health insurance analytics.
Loads and standardizes claims, premium, benefit, hospital, and production data
across all organizations (Baker Hughes, Flour Mills, Guinness, PENCOM).
"""

import os
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _read_excel(filename, **kwargs):
    filepath = BASE_DIR / filename
    if not filepath.exists():
        return pd.DataFrame()
    return pd.read_excel(filepath, **kwargs)


def load_claims():
    """Load and combine claims data from all organizations."""
    claims_files = {
        "Baker Hughes": [
            ("Baker hughes claims 2024.xlsx", "Sheet1"),
            ("Baker hughes claims 2025.xlsx", "Sheet1"),
        ],
        "Flour Mills": [
            ("FLOUR MILLS CLAIMS BATCH 1.xlsx", None),
            ("FLOUR MILLS CLAIMS BATCH 2.xlsx", None),
            ("FLOUR MILLS CLIAMS BATCH 3.xlsx", None),
            ("flour mills batch 4.xlsx", None),
        ],
        "Guinness": [
            ("Guiness claims (1).xlsx", "Sheet1"),
        ],
        "PENCOM": [
            ("PENCOM CLAIMS.xlsx", "Sheet1"),
        ],
    }

    frames = []
    for org, files in claims_files.items():
        for filename, sheet in files:
            try:
                df = _read_excel(filename, sheet_name=sheet if sheet else 0)
                if df.empty:
                    continue
                df.columns = df.columns.str.strip()
                df["Organization"] = org
                df["Source_File"] = filename
                frames.append(df)
            except Exception as e:
                print(f"Warning: Could not load {filename}: {e}")

    if not frames:
        return pd.DataFrame()

    # Standardize column names across organizations
    all_claims = pd.concat(frames, ignore_index=True, sort=False)

    # Standardize key columns
    col_map = {
        "Claim NUmber": "Claim_Number",
        "Batch Number": "Batch_Number",
        "First Name": "First_Name",
        "Surname": "Surname",
        "GROUPCODE": "Group_Code",
        "Member Ship No": "Member_ID",
        "SCHEME": "Scheme",
        "SERVICE": "Service_Type",
        "DEPARTMENT": "Department",
        "Provider": "Provider",
        "Debit": "Debit_Type",
        "CURRENTAGE": "Age",
        "Treatment Date": "Treatment_Date",
        "Amt Claimed": "Amount_Claimed",
        "Amt Paid": "Amount_Paid",
        "Principal Member": "Principal_Member",
        "Received On": "Received_Date",
        "Claim Status": "Claim_Status",
        "Otherdiagnosis": "Diagnosis_Codes",
        "Description": "Description",
        "Diagnosis Description": "Diagnosis_Description",
        "Units Paid": "Units_Paid",
        "Rejection Reason": "Rejection_Reason",
        "Procedure Code": "Procedure_Code",
    }
    all_claims.rename(columns=col_map, inplace=True)

    # Parse numeric columns
    for col in ["Amount_Claimed", "Amount_Paid", "Age", "Units_Paid"]:
        if col in all_claims.columns:
            all_claims[col] = pd.to_numeric(all_claims[col], errors="coerce")

    # Parse date columns
    for col in ["Treatment_Date", "Received_Date"]:
        if col in all_claims.columns:
            all_claims[col] = pd.to_datetime(all_claims[col], errors="coerce")

    return all_claims


def load_premiums():
    """Load and combine premium/enrollment data from all organizations."""
    premium_files = {
        "Baker Hughes": [
            ("Baker hughes premium 2024.xlsx", "Sheet1"),
            ("Baker hughes premium 2025.xlsx", "rptProductionData"),
        ],
        "PENCOM": [
            ("PENCOM Premium.xlsx", "rptProductionData"),
        ],
    }

    frames = []
    for org, files in premium_files.items():
        for filename, sheet in files:
            try:
                df = _read_excel(filename, sheet_name=sheet)
                if df.empty:
                    continue
                df.columns = df.columns.str.strip()
                df["Organization"] = org
                frames.append(df)
            except Exception as e:
                print(f"Warning: Could not load {filename}: {e}")

    if not frames:
        return pd.DataFrame()

    all_premiums = pd.concat(frames, ignore_index=True, sort=False)

    col_map = {
        "Member Enrollee ID": "Member_ID",
        "Member Plan": "Plan",
        "Member Date Of Birth": "Date_of_Birth",
        "Member Relationship": "Relationship",
        "Member Gender": "Gender",
        "Member Country State": "State",
        "Member Effectivedate": "Effective_Date",
        "Client Expiry Date": "Expiry_Date",
        "Member Status Desc": "Status",
        "Individual Premium Fees": "Premium",
        "Member Customer Name": "Member_Name",
        "Product Scheme Type": "Scheme_Type",
    }
    all_premiums.rename(columns=col_map, inplace=True)

    if "Premium" in all_premiums.columns:
        all_premiums["Premium"] = pd.to_numeric(all_premiums["Premium"], errors="coerce")

    for col in ["Date_of_Birth", "Effective_Date", "Expiry_Date"]:
        if col in all_premiums.columns:
            all_premiums[col] = pd.to_datetime(all_premiums[col], errors="coerce")

    return all_premiums


def load_production():
    """Load production/enrollment data (Flour Mills, Guinness)."""
    prod_files = {
        "Flour Mills": ("FFLOUR MILLS PRODUCTION.xlsx", "Sheet1"),
        "Guinness": ("GUINESS PRODUCTION.xlsx", "rptProductionData"),
    }

    frames = []
    for org, (filename, sheet) in prod_files.items():
        try:
            df = _read_excel(filename, sheet_name=sheet)
            if df.empty:
                continue
            df.columns = df.columns.str.strip()
            df["Organization"] = org
            frames.append(df)
        except Exception as e:
            print(f"Warning: Could not load {filename}: {e}")

    if not frames:
        return pd.DataFrame()

    all_prod = pd.concat(frames, ignore_index=True, sort=False)

    col_map = {
        "Member_EnrolleeID": "Member_ID",
        "Member Enrollee ID": "Member_ID",
        "Client_ClientName": "Client_Name",
        "Member Customer Name": "Member_Name",
        "Member_Plan": "Plan",
        "Member Plan": "Plan",
        "Product_SchemeType": "Scheme_Type",
        "Product Scheme Type": "Scheme_Type",
        "Member_DateOfBirth": "Date_of_Birth",
        "Member Date Of Birth": "Date_of_Birth",
        "Member_Relationship": "Relationship",
        "Member Relationship": "Relationship",
        "Member_Gender": "Gender",
        "Member Gender": "Gender",
        "Member_CountryState": "State",
        "Member Country State": "State",
        "Member_Effectivedate": "Effective_Date",
        "Member Effectivedate": "Effective_Date",
        "Client_ExpiryDate": "Expiry_Date",
        "Client Expiry Date": "Expiry_Date",
        "MemberStatus_Desc": "Status",
        "Member Status Desc": "Status",
        "IndividualPremiumFees": "Premium",
        "Individual Premium Fees": "Premium",
    }
    all_prod.rename(columns=col_map, inplace=True)

    # Drop duplicate columns (keep first occurrence)
    all_prod = all_prod.loc[:, ~all_prod.columns.duplicated()]

    if "Premium" in all_prod.columns:
        all_prod["Premium"] = pd.to_numeric(all_prod["Premium"].astype(str), errors="coerce")

    return all_prod


def load_hospitals():
    """Load and combine hospital network data."""
    hospital_files = {
        "Baker Hughes": "Baker hughes HOSPITAL LIST (STANDARD).xlsx",
        "Flour Mills": "FLOURMILLS HOSPITAL LIST (STANDARD).xlsx",
        "Guinness": "GUINESS HOSPITAL LIST (STANDARD).xlsx",
        "PENCOM": "PENCOM HOSPITAL LIST (STANDARD).xlsx",
    }

    frames = []
    for org, filename in hospital_files.items():
        try:
            df = _read_excel(filename, sheet_name=0)
            if df.empty:
                continue
            df.columns = df.columns.str.strip()
            df["Organization"] = org
            frames.append(df)
        except Exception as e:
            print(f"Warning: Could not load {filename}: {e}")

    if not frames:
        return pd.DataFrame()

    all_hospitals = pd.concat(frames, ignore_index=True, sort=False)

    col_map = {
        "CODE": "Provider_Code",
        "ZONE": "Zone",
        "STATE": "State",
        "TOWN": "Town",
        "PROVIDER": "Provider_Name",
        "ADDRESS": "Address",
        "CAT": "Category",
        "PLAN": "Plan",
        "SPECIALTY": "Specialty",
    }
    all_hospitals.rename(columns=col_map, inplace=True)

    return all_hospitals


def load_benefits():
    """Load benefit information for all organizations."""
    benefit_files = {
        "Baker Hughes": "BAKER HUGHES BENEFIT.xlsx",
        "Flour Mills": "FLOUR MILLS UPDATED BENEFIT.xlsx",
        "Guinness": "Guiness benefit.xlsx",
        "PENCOM": "PENCOM BENEFIT.xlsx",
    }

    results = {}
    for org, filename in benefit_files.items():
        try:
            df = _read_excel(filename, sheet_name=0)
            if not df.empty:
                df.columns = df.columns.str.strip()
                results[org] = df
        except Exception as e:
            print(f"Warning: Could not load {filename}: {e}")

    return results

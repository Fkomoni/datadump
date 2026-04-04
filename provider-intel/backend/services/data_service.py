"""Shared data operations — session management and column mapping."""

import pickle
from pathlib import Path
from difflib import SequenceMatcher
import pandas as pd
import numpy as np

SESSIONS_DIR = Path(__file__).parent.parent / "sessions"

# ── Canonical column schema with known aliases from Leadway exports ──
COLUMN_SCHEMA = {
    "claims_paid":       ["amt paid", "claims paid", "paid", "amount paid", "amount_paid"],
    "amt_claimed":       ["amt claimed", "amount claimed", "amountclaimed"],
    "claim_no":          ["claim number", "claim no", "claim_number", "claimno"],
    "claim_line_no":     ["claim line no", "claim line number", "line no"],
    "enrolee_id":        ["membershipno", "enrolee id", "member id", "enrollee id", "member_id", "member enrollee id", "member ship no"],
    "encounter_date":    ["treatment date", "encounter date", "visit date", "treatment_date", "date of service"],
    "provider_name":     ["provider", "provider name", "hospital", "facility"],
    "group_name":        ["group name", "group", "group_code", "client", "organization"],
    "scheme":            ["scheme", "scheme name"],
    "plan_category":     ["plan category", "plan", "plan tier", "plan_category"],
    "benefit":           ["benefit", "benefit type", "benefit category"],
    "service_type":      ["service type", "service_type", "department", "claim type"],
    "tariff_descr":      ["tariff descr", "tariff description", "tariff_descr", "service description"],
    "tariff_code":       ["tarif code", "tariff code", "tariff_code"],
    "description":       ["description", "drug description", "item description"],
    "diagnosis":         ["diagnosis", "diagnosis code", "diag"],
    "diag_descr":        ["diag descr", "diagnosis description", "diagnosis_description"],
    "claim_status":      ["claim status", "claim_status", "status"],
    "relationship":      ["relationship type", "relationship", "member type"],
    "member_sex":        ["member gender", "member sex", "sex", "gender"],
    "member_age":        ["member age", "age", "currentage"],
    "member_name":       ["member", "member name"],
    "first_name":        ["first name", "firstname"],
    "surname":           ["surname", "last name", "lastname"],
    "provider_location": ["prov location", "provider location", "state", "provider state", "location"],
    "discipline":        ["discipline", "speciality", "specialty"],
    "dob":               ["dob", "date of birth", "birth date", "birthdate"],
}

# Service types that should normalise to "Outpatient"
OPD_ALIASES = {"outpatient", "opd", "out-patient", "out patient", "mtn pha"}
IPD_ALIASES = {"inpatient", "ipd", "in-patient", "in patient"}

# Claim statuses to exclude from spend calculations
EXCLUDED_STATUSES = {"abandoned", "rejected", "declined"}

# Diagnostic service keywords
DIAGNOSTIC_KEYWORDS = [
    "test", "lab", "scan", "x-ray", "xray", "x ray", "uss", "culture",
    "ecg", "urinalysis", "fbc", "blood count", "esr", "crp", "lipid",
    "sugar", "electrolyte", "urea", "creatinine", "liver function",
    "thyroid", "hba1c", "psa", "hiv", "hepatitis", "widal",
    "malaria parasite", "microscopy", "ultrasound", "mri", "ct scan",
]

# Consumable keywords
CONSUMABLE_KEYWORDS = [
    "syringe", "glove", "catheter", "dressing", "cannula", "set",
    "consumable", "consumables", "cotton", "gauze", "bandage",
    "plaster", "swab", "needle", "infusion set",
]


def fuzzy_match(col_name: str, candidates: list[str], threshold: float = 0.6) -> str | None:
    col_lower = col_name.lower().strip()
    # Check substring containment first (most reliable)
    for candidate in candidates:
        if candidate in col_lower or col_lower in candidate:
            return candidate
    # Fuzzy ratio
    best_score = 0
    best_match = None
    for candidate in candidates:
        score = SequenceMatcher(None, col_lower, candidate).ratio()
        if score > best_score:
            best_score = score
            best_match = candidate
    return best_match if best_score >= threshold else None


def auto_map_columns(df: pd.DataFrame) -> dict:
    """Auto-detect column mapping from uploaded dataframe to canonical schema."""
    # Clean column names: strip whitespace and newlines
    df.columns = [c.replace("\n", " ").replace("\r", " ").strip() for c in df.columns]

    mapping = {}
    confidence = {}
    used_cols = set()

    for canonical, aliases in COLUMN_SCHEMA.items():
        matched = False
        for col in df.columns:
            if col in used_cols:
                continue
            col_lower = col.lower().strip()
            if col_lower in aliases:
                mapping[canonical] = col
                confidence[canonical] = "high"
                used_cols.add(col)
                matched = True
                break
        if not matched:
            for col in df.columns:
                if col in used_cols:
                    continue
                result = fuzzy_match(col, aliases, threshold=0.65)
                if result:
                    mapping[canonical] = col
                    confidence[canonical] = "low"
                    used_cols.add(col)
                    matched = True
                    break
        if not matched:
            mapping[canonical] = None
            confidence[canonical] = "missing"

    return {"mapping": mapping, "confidence": confidence}


def parse_and_clean(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """Rename columns to canonical names and parse types."""
    # Clean column names first
    df.columns = [c.replace("\n", " ").replace("\r", " ").strip() for c in df.columns]

    # Build rename dict
    rename = {actual: canonical for canonical, actual in col_map.items() if actual is not None}
    df = df.rename(columns=rename)

    # Parse monetary columns
    for col in ["claims_paid", "amt_claimed"]:
        if col in df.columns:
            df[col] = (
                df[col].astype(str)
                .str.replace("₦", "", regex=False)
                .str.replace(",", "", regex=False)
                .str.replace("nan", "", regex=False)
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Build effective_spend: use claims_paid, fall back to amt_claimed for non-paid non-abandoned
    if "claims_paid" in df.columns:
        df["effective_spend"] = df["claims_paid"]
        if "amt_claimed" in df.columns and "claim_status" in df.columns:
            non_paid = df["claims_paid"].fillna(0) == 0
            not_excluded = ~df["claim_status"].str.lower().str.strip().isin(EXCLUDED_STATUSES)
            df.loc[non_paid & not_excluded, "effective_spend"] = df.loc[non_paid & not_excluded, "amt_claimed"]
        elif "amt_claimed" in df.columns:
            non_paid = df["claims_paid"].fillna(0) == 0
            df.loc[non_paid, "effective_spend"] = df.loc[non_paid, "amt_claimed"]
    elif "amt_claimed" in df.columns:
        df["effective_spend"] = df["amt_claimed"]
    else:
        df["effective_spend"] = 0

    # Parse dates — handle "02/01/2026 12:00:00 am" format, Excel serials, etc.
    for col in ["encounter_date", "dob"]:
        if col in df.columns:
            raw = df[col].copy()
            # Skip if already datetime
            if pd.api.types.is_datetime64_any_dtype(raw):
                continue
            # Filter out corrupted values like ############
            raw = raw.astype(str).str.strip()
            raw = raw.replace({"############": pd.NA, "nan": pd.NA, "None": pd.NA, "NaT": pd.NA})

            # Try Excel serial numbers
            numeric = pd.to_numeric(raw, errors="coerce")
            excel_like = numeric.notna() & (numeric > 30000) & (numeric < 60000)
            if excel_like.sum() > numeric.notna().sum() * 0.3 and numeric.notna().sum() > 0:
                df[col] = pd.NaT
                df.loc[excel_like, col] = pd.to_datetime("1899-12-30") + pd.to_timedelta(numeric[excel_like], unit="D")
            else:
                # Try standard parsing with dayfirst
                df[col] = pd.to_datetime(raw, errors="coerce", dayfirst=True)

    # Normalise service type
    if "service_type" in df.columns:
        df["service_type"] = df["service_type"].astype(str).str.strip()
        st_lower = df["service_type"].str.lower()
        df.loc[st_lower.isin(OPD_ALIASES), "service_type"] = "Outpatient"
        df.loc[st_lower.isin(IPD_ALIASES), "service_type"] = "Inpatient"

    # Parse age
    if "member_age" in df.columns:
        df["member_age"] = pd.to_numeric(df["member_age"], errors="coerce")

    # Family ID from enrolee_id (first 8 chars)
    if "enrolee_id" in df.columns:
        df["family_id"] = df["enrolee_id"].astype(str).str[:8]

    return df


def save_session(session_id: str, df: pd.DataFrame, metadata: dict):
    path = SESSIONS_DIR / f"{session_id}.pkl"
    data = {"df": df, "meta": metadata}
    with open(path, "wb") as f:
        pickle.dump(data, f)


def load_session(session_id: str) -> tuple[pd.DataFrame, dict]:
    path = SESSIONS_DIR / f"{session_id}.pkl"
    if not path.exists():
        raise FileNotFoundError(f"Session {session_id} not found")
    with open(path, "rb") as f:
        data = pickle.load(f)
    return data["df"], data["meta"]


def apply_filters(df: pd.DataFrame, provider: str = None, date_from: str = None,
                  date_to: str = None, plan: str = None, scheme: str = None) -> pd.DataFrame:
    """Apply common filters to a session dataframe."""
    if provider and "provider_name" in df.columns:
        df = df[df["provider_name"] == provider]
    if date_from and "encounter_date" in df.columns:
        df = df[df["encounter_date"] >= pd.to_datetime(date_from, dayfirst=True)]
    if date_to and "encounter_date" in df.columns:
        df = df[df["encounter_date"] <= pd.to_datetime(date_to, dayfirst=True)]
    if plan and "plan_category" in df.columns:
        df = df[df["plan_category"].str.contains(plan, case=False, na=False)]
    if scheme and "scheme" in df.columns:
        df = df[df["scheme"] == scheme]
    return df


def month_label(period) -> str:
    """Format a pandas Period as 'Jan 2025'."""
    return period.to_timestamp().strftime("%b %Y")


def is_diagnostic(descr: str) -> bool:
    """Check if a tariff description is a diagnostic service."""
    if not descr:
        return False
    d = str(descr).lower()
    return any(kw in d for kw in DIAGNOSTIC_KEYWORDS)


def is_consumable(descr: str) -> bool:
    """Check if a tariff description is a consumable."""
    if not descr:
        return False
    d = str(descr).lower()
    return any(kw in d for kw in CONSUMABLE_KEYWORDS)

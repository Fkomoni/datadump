"""Shared data operations — session management and column mapping."""

import pickle
import uuid
from pathlib import Path
from difflib import SequenceMatcher
import pandas as pd
import numpy as np

SESSIONS_DIR = Path(__file__).parent.parent / "sessions"

# ── Canonical column schema ──
COLUMN_SCHEMA = {
    "claims_paid":      ["claims paid", "paid", "amount paid", "amt paid", "amount_paid"],
    "claim_no":         ["claim no", "claim number", "claim_number", "claimno"],
    "enrolee_id":       ["enrolee id", "member id", "enrollee id", "member_id", "membershipno", "member enrollee id", "member ship no"],
    "encounter_date":   ["encounter date", "treatment date", "visit date", "treatment_date", "date of service"],
    "provider_name":    ["provider name", "provider", "hospital", "facility"],
    "group_name":       ["group", "group name", "group_code", "client", "organization"],
    "scheme":           ["scheme", "scheme name"],
    "plan_category":    ["plan category", "plan", "plan tier", "plan_category"],
    "benefit":          ["benefit", "benefit type", "benefit category"],
    "service_type":     ["service type", "service_type", "department", "claim type"],
    "tariff_descr":     ["tariff descr", "tariff description", "tariff_descr", "service description"],
    "description":      ["description", "drug description", "item description"],
    "diagnosis":        ["diagnosis", "diagnosis description", "diagnosis_description", "diag"],
    "relationship":     ["relationship", "member type", "relationship type"],
    "member_sex":       ["member sex", "sex", "gender"],
    "dob":              ["dob", "date of birth", "birth date", "birthdate"],
    "provider_location": ["provider location", "state", "provider state", "location"],
}


def fuzzy_match(col_name: str, candidates: list[str], threshold: float = 0.6) -> str | None:
    """Fuzzy match a column name to a list of canonical candidates."""
    col_lower = col_name.lower().strip()
    best_score = 0
    best_match = None
    for candidate in candidates:
        score = SequenceMatcher(None, col_lower, candidate).ratio()
        if score > best_score:
            best_score = score
            best_match = candidate
    # Also check substring containment
    for candidate in candidates:
        if candidate in col_lower or col_lower in candidate:
            return candidate
    return best_match if best_score >= threshold else None


def auto_map_columns(df: pd.DataFrame) -> dict:
    """Auto-detect column mapping from uploaded dataframe to canonical schema."""
    mapping = {}      # canonical_name -> actual_column_name
    confidence = {}   # canonical_name -> "high" | "low"

    for canonical, aliases in COLUMN_SCHEMA.items():
        matched = False
        for col in df.columns:
            col_lower = col.lower().strip()
            # Exact or alias match
            if col_lower in aliases:
                mapping[canonical] = col
                confidence[canonical] = "high"
                matched = True
                break
        if not matched:
            # Fuzzy match
            for col in df.columns:
                result = fuzzy_match(col, aliases, threshold=0.65)
                if result:
                    mapping[canonical] = col
                    confidence[canonical] = "low"
                    matched = True
                    break
        if not matched:
            mapping[canonical] = None
            confidence[canonical] = "missing"

    return {"mapping": mapping, "confidence": confidence}


def parse_and_clean(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """Rename columns to canonical names and parse types."""
    # Build rename dict (only mapped columns)
    rename = {actual: canonical for canonical, actual in col_map.items() if actual is not None}
    df = df.rename(columns=rename)

    # Parse monetary
    if "claims_paid" in df.columns:
        df["claims_paid"] = (
            df["claims_paid"].astype(str)
            .str.replace("₦", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.strip()
        )
        df["claims_paid"] = pd.to_numeric(df["claims_paid"], errors="coerce")

    # Parse dates
    for col in ["encounter_date", "dob"]:
        if col in df.columns:
            raw = df[col].copy()
            # Try Excel serial numbers first
            numeric = pd.to_numeric(raw, errors="coerce")
            excel_like = numeric.notna() & (numeric > 30000) & (numeric < 60000)
            if excel_like.sum() > numeric.notna().sum() * 0.5 and numeric.notna().sum() > 0:
                df[col] = pd.NaT
                df.loc[excel_like, col] = pd.to_datetime("1899-12-30") + pd.to_timedelta(numeric[excel_like], unit="D")
            else:
                df[col] = pd.to_datetime(raw, errors="coerce", dayfirst=True)

    return df


def save_session(session_id: str, df: pd.DataFrame, metadata: dict):
    """Save dataframe and metadata to a pickle session file."""
    path = SESSIONS_DIR / f"{session_id}.pkl"
    data = {"df": df, "meta": metadata}
    with open(path, "wb") as f:
        pickle.dump(data, f)


def load_session(session_id: str) -> tuple[pd.DataFrame, dict]:
    """Load a session's dataframe and metadata."""
    path = SESSIONS_DIR / f"{session_id}.pkl"
    if not path.exists():
        raise FileNotFoundError(f"Session {session_id} not found")
    with open(path, "rb") as f:
        data = pickle.load(f)
    return data["df"], data["meta"]


def apply_filters(df: pd.DataFrame, provider: str = None, date_from: str = None,
                  date_to: str = None, plan: str = None) -> pd.DataFrame:
    """Apply common filters to a session dataframe."""
    if provider and "provider_name" in df.columns:
        df = df[df["provider_name"].str.contains(provider, case=False, na=False)]
    if date_from and "encounter_date" in df.columns:
        df = df[df["encounter_date"] >= pd.to_datetime(date_from)]
    if date_to and "encounter_date" in df.columns:
        df = df[df["encounter_date"] <= pd.to_datetime(date_to)]
    if plan and "plan_category" in df.columns:
        df = df[df["plan_category"].str.contains(plan, case=False, na=False)]
    return df

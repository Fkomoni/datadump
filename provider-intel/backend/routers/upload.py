"""File upload and schema detection endpoint."""

import uuid
import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException
from services.data_service import auto_map_columns, parse_and_clean, save_session

router = APIRouter(tags=["upload"])


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a claims file (.xlsx or .csv), auto-detect columns, store session."""
    if not file.filename:
        raise HTTPException(400, "No file provided")

    ext = file.filename.lower().rsplit(".", 1)[-1]
    if ext not in ("xlsx", "xls", "csv"):
        raise HTTPException(400, "Only .xlsx, .xls, or .csv files are supported")

    content = await file.read()

    # Parse file
    try:
        if ext == "csv":
            import io
            df = pd.read_csv(io.BytesIO(content))
        else:
            import io
            df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(400, f"Failed to parse file: {str(e)}")

    df.columns = df.columns.str.strip()

    # Auto-detect column mapping
    result = auto_map_columns(df)
    col_map = result["mapping"]
    confidence = result["confidence"]

    # Parse and clean using the mapping
    df = parse_and_clean(df, col_map)

    # Compute session metadata
    session_id = str(uuid.uuid4())[:12]
    row_count = len(df)

    date_range = None
    if "encounter_date" in df.columns:
        valid_dates = df["encounter_date"].dropna()
        if len(valid_dates) > 0:
            date_range = {
                "from": valid_dates.min().strftime("%b %Y"),
                "to": valid_dates.max().strftime("%b %Y"),
            }

    unique_providers = []
    if "provider_name" in df.columns:
        unique_providers = sorted(df["provider_name"].dropna().unique().tolist()[:200])

    unique_members = 0
    if "enrolee_id" in df.columns:
        unique_members = int(df["enrolee_id"].nunique())

    total_spend = 0
    if "claims_paid" in df.columns:
        total_spend = float(df["claims_paid"].sum())

    metadata = {
        "filename": file.filename,
        "row_count": row_count,
        "date_range": date_range,
        "unique_providers_count": len(unique_providers),
        "unique_members": unique_members,
        "total_spend": total_spend,
        "column_mapping": col_map,
        "column_confidence": confidence,
    }

    save_session(session_id, df, metadata)

    return {
        "session_id": session_id,
        "filename": file.filename,
        "row_count": row_count,
        "date_range": date_range,
        "unique_providers": unique_providers[:50],
        "unique_providers_count": len(unique_providers),
        "unique_members": unique_members,
        "total_spend": total_spend,
        "detected_columns": col_map,
        "column_confidence": confidence,
    }

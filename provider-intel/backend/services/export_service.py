"""Export utilities — Excel, Word, PDF generation."""

import io
import pandas as pd


def dataframe_to_excel(df: pd.DataFrame, sheet_name: str = "Data") -> io.BytesIO:
    """Convert a dataframe to an Excel file in memory."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    buf.seek(0)
    return buf

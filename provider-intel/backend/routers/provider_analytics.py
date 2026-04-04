"""Provider Analytics — Module 1: Deep analytics on a single provider."""

import io
import pandas as pd
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse

from services.data_service import (
    load_session, apply_filters, month_label,
    is_diagnostic, is_consumable, EXCLUDED_STATUSES,
)

router = APIRouter(tags=["provider-analytics"])


def _load_and_filter(session_id, provider=None, date_from=None, date_to=None, plan=None):
    try:
        df, meta = load_session(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")
    if "claim_status" in df.columns:
        df = df[~df["claim_status"].str.lower().str.strip().isin(EXCLUDED_STATUSES)]
    return apply_filters(df, provider=provider, date_from=date_from, date_to=date_to, plan=plan)


def _agg_members(df):
    return ("enrolee_id", "nunique") if "enrolee_id" in df.columns else ("effective_spend", "count")


def _agg_visits(df):
    return ("claim_no", "nunique") if "claim_no" in df.columns else ("effective_spend", "count")


# ── 1A. OVERVIEW ──
@router.get("/provider/overview")
def overview(session_id: str = Query(...), provider_name: str = Query(None),
             date_from: str = Query(None), date_to: str = Query(None), plan_category: str = Query(None)):
    df = _load_and_filter(session_id, provider_name, date_from, date_to, plan_category)
    if df.empty:
        return {"monthly": [], "cumulative_unique_members": 0, "summary": {}}

    monthly = []
    if "encounter_date" in df.columns:
        d = df.dropna(subset=["encounter_date"]).copy()
        d["month"] = d["encounter_date"].dt.to_period("M")
        g = d.groupby("month").agg(amount_paid=("effective_spend", "sum"),
                                    unique_members=_agg_members(d), unique_visits=_agg_visits(d)).sort_index()
        for p, r in g.iterrows():
            monthly.append({"month": month_label(p), "amount_paid": round(float(r["amount_paid"])),
                            "unique_members": int(r["unique_members"]), "unique_visits": int(r["unique_visits"])})

    cum = int(df["enrolee_id"].nunique()) if "enrolee_id" in df.columns else 0
    visits = int(df["claim_no"].nunique()) if "claim_no" in df.columns else len(df)
    total = float(df["effective_spend"].sum())
    return {"monthly": monthly, "cumulative_unique_members": cum,
            "summary": {"total_spend": round(total), "total_claims": visits,
                        "total_members": cum, "avg_per_visit": round(total / max(visits, 1))}}


# ── 1B. GROUPS ──
@router.get("/provider/groups")
def groups(session_id: str = Query(...), provider_name: str = Query(None),
           date_from: str = Query(None), date_to: str = Query(None), plan_category: str = Query(None)):
    df = _load_and_filter(session_id, provider_name, date_from, date_to, plan_category)
    if "group_name" not in df.columns:
        return {"data": []}
    g = df.groupby("group_name").agg(amount_paid=("effective_spend", "sum"),
                                      unique_members=_agg_members(df), unique_visits=_agg_visits(df)
                                      ).sort_values("amount_paid", ascending=False).reset_index()
    return {"data": [{"group": r["group_name"], "amount_paid": round(float(r["amount_paid"])),
                       "unique_members": int(r["unique_members"]), "unique_visits": int(r["unique_visits"])}
                      for _, r in g.iterrows()]}


# ── 1C. SCHEMES ──
@router.get("/provider/schemes")
def schemes(session_id: str = Query(...), provider_name: str = Query(None),
            date_from: str = Query(None), date_to: str = Query(None), plan_category: str = Query(None)):
    df = _load_and_filter(session_id, provider_name, date_from, date_to, plan_category)
    if "scheme" not in df.columns:
        return {"data": []}
    g = df.groupby("scheme").agg(amount_paid=("effective_spend", "sum"),
                                  unique_members=_agg_members(df), unique_visits=_agg_visits(df)
                                  ).sort_values("amount_paid", ascending=False).reset_index()
    return {"data": [{"scheme": r["scheme"], "amount_paid": round(float(r["amount_paid"])),
                       "unique_members": int(r["unique_members"]), "unique_visits": int(r["unique_visits"])}
                      for _, r in g.iterrows()]}


# ── 1D. TOP 30 TARIFF LINES ──
@router.get("/provider/top-lines")
def top_lines(session_id: str = Query(...), provider_name: str = Query(None),
              date_from: str = Query(None), date_to: str = Query(None), plan_category: str = Query(None)):
    df = _load_and_filter(session_id, provider_name, date_from, date_to, plan_category)
    if "tariff_descr" not in df.columns:
        return {"data": []}
    g = df.groupby("tariff_descr").agg(amount_paid=("effective_spend", "sum"),
                                        unique_members=_agg_members(df), times_utilized=_agg_visits(df)
                                        ).sort_values("amount_paid", ascending=False).head(30).reset_index()
    g["avg_paid"] = (g["amount_paid"] / g["times_utilized"].clip(lower=1)).round(0)
    return {"data": [{"rank": i+1, "service": r["tariff_descr"], "amount_paid": round(float(r["amount_paid"])),
                       "unique_members": int(r["unique_members"]), "times_utilized": int(r["times_utilized"]),
                       "avg_paid_per_line": round(float(r["avg_paid"]))}
                      for i, (_, r) in enumerate(g.iterrows())]}


# ── 1E. CHRONIC MEDICATION ──
@router.get("/provider/chronic")
def chronic(session_id: str = Query(...), provider_name: str = Query(None),
            date_from: str = Query(None), date_to: str = Query(None), plan_category: str = Query(None)):
    df = _load_and_filter(session_id, provider_name, date_from, date_to, plan_category)
    if "benefit" not in df.columns:
        return {"total_chronic_spend": 0, "unique_members_on_chronic": 0, "data": []}
    ch = df[df["benefit"].str.contains("chronic", case=False, na=False)]
    if ch.empty:
        return {"total_chronic_spend": 0, "unique_members_on_chronic": 0, "data": []}
    drug_col = "tariff_descr" if "tariff_descr" in ch.columns else ("description" if "description" in ch.columns else None)
    result = {"total_chronic_spend": round(float(ch["effective_spend"].sum())),
              "unique_members_on_chronic": int(ch["enrolee_id"].nunique()) if "enrolee_id" in ch.columns else 0, "data": []}
    if drug_col:
        g = ch.groupby(drug_col).agg(total_spend=("effective_spend", "sum"),
                                      unique_members=_agg_members(ch), times_dispensed=_agg_visits(ch)
                                      ).sort_values("total_spend", ascending=False).reset_index()
        result["data"] = [{"drug": r[drug_col], "total_spend": round(float(r["total_spend"])),
                            "unique_members": int(r["unique_members"]), "times_dispensed": int(r["times_dispensed"])}
                           for _, r in g.iterrows()]
    return result


# ── 1F. SIMULATION ──
@router.get("/provider/simulate")
def simulate(session_id: str = Query(...), provider_name: str = Query(None),
             date_from: str = Query(None), date_to: str = Query(None),
             plan_category: str = Query(None), discount_pct: float = Query(20, ge=0, le=100)):
    df = _load_and_filter(session_id, provider_name, date_from, date_to, plan_category)
    if "tariff_descr" not in df.columns:
        return {"original_top30_total": 0, "simulated_top30_total": 0, "estimated_saving": 0, "data": []}
    g = df.groupby("tariff_descr")["effective_spend"].sum().sort_values(ascending=False).head(30)
    orig = float(g.sum())
    factor = 1 - discount_pct / 100
    return {"original_top30_total": round(orig), "simulated_top30_total": round(orig * factor),
            "estimated_saving": round(orig * discount_pct / 100), "discount_pct": discount_pct,
            "data": [{"service": s, "original_spend": round(float(a)),
                       "simulated_spend": round(float(a) * factor), "saving": round(float(a) * discount_pct / 100)}
                      for s, a in g.items()]}


# ── 1G. HIGH COST CASE REVIEW ──
@router.get("/provider/high-cost-cases")
def high_cost_cases(session_id: str = Query(...), provider_name: str = Query(None),
                    date_from: str = Query(None), date_to: str = Query(None), plan_category: str = Query(None)):
    df = _load_and_filter(session_id, provider_name, date_from, date_to, plan_category)
    # Filter OPD
    if "service_type" in df.columns:
        opd = df[df["service_type"].str.lower().str.strip().isin(["outpatient", "opd", "out-patient"])]
    else:
        opd = df
    if opd.empty or "claim_no" not in opd.columns:
        return {"cases": [], "ai_narrative": None}

    agg_dict = {"total_paid": ("effective_spend", "sum")}
    if "enrolee_id" in opd.columns:
        agg_dict["enrolee_id"] = ("enrolee_id", "first")
    if "encounter_date" in opd.columns:
        agg_dict["encounter_date"] = ("encounter_date", "first")
    if "diag_descr" in opd.columns:
        agg_dict["diagnosis"] = ("diag_descr", lambda x: "; ".join(x.dropna().unique()[:3]))
    elif "diagnosis" in opd.columns:
        agg_dict["diagnosis"] = ("diagnosis", lambda x: "; ".join(x.dropna().unique()[:3]))
    if "tariff_descr" in opd.columns:
        agg_dict["services"] = ("tariff_descr", lambda x: ", ".join(x.dropna().unique()[:10]))

    cs = opd.groupby("claim_no").agg(**agg_dict).sort_values("total_paid", ascending=False).head(30)

    cases = []
    for cn, row in cs.iterrows():
        d = row.get("encounter_date", "")
        cases.append({
            "claim_no": str(cn),
            "enrolee_id": str(row.get("enrolee_id", "")),
            "encounter_date": d.strftime("%d %b %Y") if hasattr(d, "strftime") else "",
            "diagnosis": str(row.get("diagnosis", "")),
            "services": str(row.get("services", "")),
            "total_paid": round(float(row["total_paid"])),
        })

    ai_narrative = None
    try:
        from services.claude_service import ask_claude
        prov = provider_name or "the provider"
        csv = "Claim No,Enrolee ID,Date,Diagnosis,Services,Total Paid\n"
        for c in cases:
            csv += f'{c["claim_no"]},{c["enrolee_id"]},{c["encounter_date"]},"{c["diagnosis"]}","{c["services"]}",{c["total_paid"]}\n'
        ai_narrative = ask_claude(
            system=f"You are a Nigerian HMO utilization management analyst reviewing outpatient claims for {prov}. Be specific, cite claim numbers.",
            user=f"Review these high-cost outpatient visits. Flag cases where:\n(a) cost is disproportionate to the diagnosis,\n(b) multiple premium services in a single OPD visit,\n(c) excessive visit frequency by a single member.\nFor each flag: state enrolee ID, visit date, what was billed, concern, severity (HIGH/MEDIUM/LOW).\n\nData:\n{csv}",
            max_tokens=3000)
    except Exception:
        pass

    return {"cases": cases, "ai_narrative": ai_narrative}


# ── 1H. BUNDLING & CONSUMABLE PATTERNS ──
@router.get("/provider/bundling-flags")
def bundling_flags(session_id: str = Query(...), provider_name: str = Query(None),
                   date_from: str = Query(None), date_to: str = Query(None), plan_category: str = Query(None)):
    df = _load_and_filter(session_id, provider_name, date_from, date_to, plan_category)
    if "claim_no" not in df.columns or "tariff_descr" not in df.columns:
        return {"flags": [], "total_flagged": 0, "ai_narrative": None}

    flagged = []
    for cn, grp in df.groupby("claim_no"):
        svcs = grp["tariff_descr"].dropna().tolist()
        total = float(grp["effective_spend"].sum())
        eid = str(grp["enrolee_id"].iloc[0]) if "enrolee_id" in grp.columns else ""
        d = grp["encounter_date"].iloc[0] if "encounter_date" in grp.columns else ""
        ds = d.strftime("%d %b %Y") if hasattr(d, "strftime") else ""

        diag_count = sum(1 for s in svcs if is_diagnostic(s))
        has_cons = any(is_consumable(s) for s in svcs)
        has_proc = any(not is_diagnostic(s) and not is_consumable(s) and s.upper() not in ("GP CONSULTATION", "GP REVIEW CONSULTATION") for s in svcs)

        flags = []
        if diag_count >= 3:
            flags.append(("Excessive Diagnostics", f"{diag_count} diagnostic services in one visit"))
        if has_cons and has_proc:
            cons = [s for s in svcs if is_consumable(s)]
            flags.append(("Consumable Unbundling", f"Consumables ({', '.join(cons[:3])}) billed alongside procedures"))

        for ft, fr in flags:
            flagged.append({"claim_no": str(cn), "enrolee_id": eid, "date": ds,
                            "services": ", ".join(svcs[:10]), "total_paid": round(total),
                            "flag_type": ft, "flag_reason": fr})

    flagged.sort(key=lambda x: x["total_paid"], reverse=True)

    ai_narrative = None
    try:
        from services.claude_service import ask_claude
        if flagged:
            csv = "Claim No,Enrolee ID,Date,Services,Total Paid,Flag Type,Reason\n"
            for f in flagged[:20]:
                csv += f'{f["claim_no"]},{f["enrolee_id"]},{f["date"]},"{f["services"]}",{f["total_paid"]},{f["flag_type"]},"{f["flag_reason"]}"\n'
            ai_narrative = ask_claude(
                system="You are a Nigerian HMO fraud, waste and abuse analyst reviewing flagged claims. Be specific.",
                user=f"Review these flagged claims for bundling or consumable abuse. Explain what is unusual, expected billing, severity (HIGH/MEDIUM/LOW). Summarise overall patterns.\n\nData:\n{csv}",
                max_tokens=2500)
    except Exception:
        pass

    return {"flags": flagged, "total_flagged": len(flagged), "ai_narrative": ai_narrative}


# ── 1I. PROVIDER VISIT SUMMARY (client-wide) ──
@router.get("/client/provider-summary")
def provider_summary(session_id: str = Query(...), date_from: str = Query(None),
                     date_to: str = Query(None), plan_category: str = Query(None)):
    df = _load_and_filter(session_id, provider=None, date_from=date_from, date_to=date_to, plan=plan_category)
    if "claim_status" in df.columns:
        df = df[~df["claim_status"].str.lower().str.strip().isin(EXCLUDED_STATUSES)]
    if "provider_name" not in df.columns:
        return {"total_providers": 0, "data": []}
    g = df.groupby("provider_name").agg(amount_paid=("effective_spend", "sum"),
                                         unique_members=_agg_members(df), unique_visits=_agg_visits(df)
                                         ).sort_values("amount_paid", ascending=False).reset_index()
    return {"total_providers": len(g),
            "data": [{"provider": r["provider_name"], "amount_paid": round(float(r["amount_paid"])),
                       "unique_members": int(r["unique_members"]), "unique_visits": int(r["unique_visits"])}
                      for _, r in g.iterrows()]}


# ── 1J. ENROLLEE-LEVEL ──
@router.get("/client/enrollees")
def enrollees(session_id: str = Query(...), provider_name: str = Query(None),
              date_from: str = Query(None), date_to: str = Query(None), plan_category: str = Query(None)):
    df = _load_and_filter(session_id, provider_name, date_from, date_to, plan_category)
    if "enrolee_id" not in df.columns:
        return {"data": [], "flagged_multi_provider": []}
    if "claim_status" in df.columns:
        df = df[~df["claim_status"].str.lower().str.strip().isin(EXCLUDED_STATUSES)]

    agg = {"total_paid": ("effective_spend", "sum"), "num_visits": _agg_visits(df)}
    if "provider_name" in df.columns:
        agg["hospitals"] = ("provider_name", lambda x: list(x.dropna().unique()))
    g = df.groupby("enrolee_id").agg(**agg).sort_values("total_paid", ascending=False).reset_index()

    data, flagged = [], []
    for _, r in g.iterrows():
        hosps = r.get("hospitals", []) if isinstance(r.get("hospitals"), list) else []
        e = {"enrolee_id": r["enrolee_id"], "family_id": str(r["enrolee_id"])[:8],
             "total_paid": round(float(r["total_paid"])), "hospitals_visited": ", ".join(hosps[:5]),
             "num_hospitals": len(hosps), "num_visits": int(r["num_visits"]),
             "multi_provider_flag": len(hosps) > 5}
        data.append(e)
        if len(hosps) > 5:
            flagged.append(e)
    return {"data": data, "flagged_multi_provider": flagged}


# ── 1K. EXPORT ALL ──
@router.post("/provider/export-all")
def export_all(session_id: str = Query(...), provider_name: str = Query(None),
               date_from: str = Query(None), date_to: str = Query(None), plan_category: str = Query(None)):
    df = _load_and_filter(session_id, provider_name, date_from, date_to, plan_category)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        if "encounter_date" in df.columns:
            d = df.dropna(subset=["encounter_date"]).copy()
            d["Month"] = d["encounter_date"].dt.to_period("M").apply(month_label)
            ov = d.groupby("Month").agg(Amount_Paid=("effective_spend", "sum"), Members=_agg_members(d), Visits=_agg_visits(d)).reset_index()
            ov.to_excel(w, sheet_name="Overview", index=False)
        if "group_name" in df.columns:
            df.groupby("group_name").agg(Amount_Paid=("effective_spend", "sum"), Members=_agg_members(df), Visits=_agg_visits(df)).sort_values("Amount_Paid", ascending=False).reset_index().to_excel(w, sheet_name="Groups", index=False)
        if "scheme" in df.columns:
            df.groupby("scheme").agg(Amount_Paid=("effective_spend", "sum"), Members=_agg_members(df), Visits=_agg_visits(df)).sort_values("Amount_Paid", ascending=False).reset_index().to_excel(w, sheet_name="Schemes", index=False)
        if "tariff_descr" in df.columns:
            t = df.groupby("tariff_descr").agg(Amount_Paid=("effective_spend", "sum"), Members=_agg_members(df), Utilized=_agg_visits(df)).sort_values("Amount_Paid", ascending=False).head(30).reset_index()
            t["Avg_Per_Line"] = (t["Amount_Paid"] / t["Utilized"].clip(lower=1)).round(0)
            t.to_excel(w, sheet_name="Top30Lines", index=False)
        if "benefit" in df.columns:
            ch = df[df["benefit"].str.contains("chronic", case=False, na=False)]
            if not ch.empty and "tariff_descr" in ch.columns:
                ch.groupby("tariff_descr").agg(Spend=("effective_spend", "sum"), Members=_agg_members(ch), Dispensed=_agg_visits(ch)).sort_values("Spend", ascending=False).reset_index().to_excel(w, sheet_name="Chronic", index=False)
        if "enrolee_id" in df.columns:
            df.groupby("enrolee_id").agg(Total_Paid=("effective_spend", "sum"), Visits=_agg_visits(df)).sort_values("Total_Paid", ascending=False).reset_index().to_excel(w, sheet_name="EnrolleeAnalysis", index=False)
    buf.seek(0)
    fn = f"{(provider_name or 'All').replace(' ', '_')[:30]}_Analytics_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename={fn}"})

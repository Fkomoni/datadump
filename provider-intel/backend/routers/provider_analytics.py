"""Provider Analytics — Module 1: Deep analytics on a single provider."""

import io
import json
import pandas as pd
from fastapi import APIRouter, Query, HTTPException, Body
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


# ═══════════════════════════════════════════════
# 1A. OVERVIEW — enhanced with trends, OPD/IPD split, per-member cost
# ═══════════════════════════════════════════════
@router.get("/provider/overview")
def overview(session_id: str = Query(...), provider_name: str = Query(None),
             date_from: str = Query(None), date_to: str = Query(None), plan_category: str = Query(None)):
    df = _load_and_filter(session_id, provider_name, date_from, date_to, plan_category)
    if df.empty:
        return {"monthly": [], "cumulative_unique_members": 0, "summary": {}, "service_split": []}

    monthly = []
    if "encounter_date" in df.columns:
        d = df.dropna(subset=["encounter_date"]).copy()
        d["month"] = d["encounter_date"].dt.to_period("M")
        g = d.groupby("month").agg(amount_paid=("effective_spend", "sum"),
                                    unique_members=_agg_members(d), unique_visits=_agg_visits(d)).sort_index()
        prev_spend = None
        for p, r in g.iterrows():
            spend = round(float(r["amount_paid"]))
            members = int(r["unique_members"])
            visits = int(r["unique_visits"])
            mom_change = round((spend - prev_spend) / prev_spend * 100, 1) if prev_spend and prev_spend > 0 else None
            monthly.append({
                "month": month_label(p), "amount_paid": spend,
                "unique_members": members, "unique_visits": visits,
                "avg_per_member": round(spend / max(members, 1)),
                "avg_per_visit": round(spend / max(visits, 1)),
                "mom_change": mom_change,
            })
            prev_spend = spend

    cum = int(df["enrolee_id"].nunique()) if "enrolee_id" in df.columns else 0
    visits = int(df["claim_no"].nunique()) if "claim_no" in df.columns else len(df)
    total = float(df["effective_spend"].sum())

    # OPD vs IPD split
    service_split = []
    if "service_type" in df.columns:
        for st, grp in df.groupby("service_type"):
            service_split.append({
                "service_type": st,
                "amount_paid": round(float(grp["effective_spend"].sum())),
                "pct": round(float(grp["effective_spend"].sum()) / max(total, 1) * 100, 1),
                "visits": int(grp["claim_no"].nunique()) if "claim_no" in grp.columns else len(grp),
            })
        service_split.sort(key=lambda x: x["amount_paid"], reverse=True)

    return {"monthly": monthly, "cumulative_unique_members": cum,
            "summary": {"total_spend": round(total), "total_claims": visits,
                        "total_members": cum, "avg_per_visit": round(total / max(visits, 1)),
                        "avg_per_member": round(total / max(cum, 1))},
            "service_split": service_split}


# ═══════════════════════════════════════════════
# 1B. GROUPS — enhanced with per-member cost
# ═══════════════════════════════════════════════
@router.get("/provider/groups")
def groups(session_id: str = Query(...), provider_name: str = Query(None),
           date_from: str = Query(None), date_to: str = Query(None), plan_category: str = Query(None)):
    df = _load_and_filter(session_id, provider_name, date_from, date_to, plan_category)
    if "group_name" not in df.columns:
        return {"data": []}
    g = df.groupby("group_name").agg(amount_paid=("effective_spend", "sum"),
                                      unique_members=_agg_members(df), unique_visits=_agg_visits(df)
                                      ).sort_values("amount_paid", ascending=False).reset_index()
    total = float(g["amount_paid"].sum())
    return {"data": [{"group": r["group_name"], "amount_paid": round(float(r["amount_paid"])),
                       "unique_members": int(r["unique_members"]), "unique_visits": int(r["unique_visits"]),
                       "per_member_cost": round(float(r["amount_paid"]) / max(int(r["unique_members"]), 1)),
                       "pct_of_total": round(float(r["amount_paid"]) / max(total, 1) * 100, 1)}
                      for _, r in g.iterrows()]}


# ═══════════════════════════════════════════════
# 1C. SCHEMES
# ═══════════════════════════════════════════════
@router.get("/provider/schemes")
def schemes(session_id: str = Query(...), provider_name: str = Query(None),
            date_from: str = Query(None), date_to: str = Query(None), plan_category: str = Query(None)):
    df = _load_and_filter(session_id, provider_name, date_from, date_to, plan_category)
    if "scheme" not in df.columns:
        return {"data": []}
    g = df.groupby("scheme").agg(amount_paid=("effective_spend", "sum"),
                                  unique_members=_agg_members(df), unique_visits=_agg_visits(df)
                                  ).sort_values("amount_paid", ascending=False).reset_index()
    total = float(g["amount_paid"].sum())
    return {"data": [{"scheme": r["scheme"], "amount_paid": round(float(r["amount_paid"])),
                       "unique_members": int(r["unique_members"]), "unique_visits": int(r["unique_visits"]),
                       "per_member_cost": round(float(r["amount_paid"]) / max(int(r["unique_members"]), 1)),
                       "pct_of_total": round(float(r["amount_paid"]) / max(total, 1) * 100, 1)}
                      for _, r in g.iterrows()]}


# ═══════════════════════════════════════════════
# 1D. TOP 30 TARIFF LINES — enhanced with % of total + cumulative %
# ═══════════════════════════════════════════════
@router.get("/provider/top-lines")
def top_lines(session_id: str = Query(...), provider_name: str = Query(None),
              date_from: str = Query(None), date_to: str = Query(None), plan_category: str = Query(None)):
    df = _load_and_filter(session_id, provider_name, date_from, date_to, plan_category)
    if "tariff_descr" not in df.columns:
        return {"data": [], "total_all_lines": 0}
    total_all = float(df["effective_spend"].sum())
    g = df.groupby("tariff_descr").agg(amount_paid=("effective_spend", "sum"),
                                        unique_members=_agg_members(df), times_utilized=_agg_visits(df)
                                        ).sort_values("amount_paid", ascending=False).head(30).reset_index()
    g["avg_paid"] = (g["amount_paid"] / g["times_utilized"].clip(lower=1)).round(0)
    cum_pct = 0
    rows = []
    for i, (_, r) in enumerate(g.iterrows()):
        pct = round(float(r["amount_paid"]) / max(total_all, 1) * 100, 1)
        cum_pct += pct
        rows.append({"rank": i+1, "service": r["tariff_descr"], "amount_paid": round(float(r["amount_paid"])),
                       "unique_members": int(r["unique_members"]), "times_utilized": int(r["times_utilized"]),
                       "avg_paid_per_line": round(float(r["avg_paid"])),
                       "pct_of_total": pct, "cumulative_pct": round(cum_pct, 1)})
    return {"data": rows, "total_all_lines": round(total_all)}


# ═══════════════════════════════════════════════
# 1E. CHRONIC MEDICATION
# ═══════════════════════════════════════════════
@router.get("/provider/chronic")
def chronic(session_id: str = Query(...), provider_name: str = Query(None),
            date_from: str = Query(None), date_to: str = Query(None), plan_category: str = Query(None)):
    df = _load_and_filter(session_id, provider_name, date_from, date_to, plan_category)
    if "benefit" not in df.columns:
        return {"total_chronic_spend": 0, "unique_members_on_chronic": 0, "pct_of_total_spend": 0, "data": []}
    ch = df[df["benefit"].str.contains("chronic", case=False, na=False)]
    total_all = float(df["effective_spend"].sum())
    if ch.empty:
        return {"total_chronic_spend": 0, "unique_members_on_chronic": 0, "pct_of_total_spend": 0, "data": []}
    chronic_spend = float(ch["effective_spend"].sum())
    drug_col = "tariff_descr" if "tariff_descr" in ch.columns else ("description" if "description" in ch.columns else None)
    result = {"total_chronic_spend": round(chronic_spend),
              "unique_members_on_chronic": int(ch["enrolee_id"].nunique()) if "enrolee_id" in ch.columns else 0,
              "pct_of_total_spend": round(chronic_spend / max(total_all, 1) * 100, 1), "data": []}
    if drug_col:
        g = ch.groupby(drug_col).agg(total_spend=("effective_spend", "sum"),
                                      unique_members=_agg_members(ch), times_dispensed=_agg_visits(ch)
                                      ).sort_values("total_spend", ascending=False).reset_index()
        result["data"] = [{"drug": r[drug_col], "total_spend": round(float(r["total_spend"])),
                            "unique_members": int(r["unique_members"]), "times_dispensed": int(r["times_dispensed"]),
                            "avg_per_dispense": round(float(r["total_spend"]) / max(int(r["times_dispensed"]), 1))}
                           for _, r in g.iterrows()]
    return result


# ═══════════════════════════════════════════════
# 1F. SIMULATION — enhanced with per-service selective discounting
# ═══════════════════════════════════════════════
@router.get("/provider/simulate")
def simulate(session_id: str = Query(...), provider_name: str = Query(None),
             date_from: str = Query(None), date_to: str = Query(None),
             plan_category: str = Query(None), discount_pct: float = Query(20, ge=0, le=100),
             selected_services: str = Query(None)):
    """If selected_services is provided (comma-separated), discount only those. Otherwise discount all top 30."""
    df = _load_and_filter(session_id, provider_name, date_from, date_to, plan_category)
    if "tariff_descr" not in df.columns:
        return {"original_top30_total": 0, "simulated_top30_total": 0, "estimated_saving": 0, "data": []}
    g = df.groupby("tariff_descr")["effective_spend"].sum().sort_values(ascending=False).head(30)
    selected = set(s.strip() for s in selected_services.split(",")) if selected_services else None
    factor = 1 - discount_pct / 100
    orig_total = 0
    sim_total = 0
    rows = []
    for svc, amt in g.items():
        a = float(amt)
        apply_discount = selected is None or svc in selected
        sim = a * factor if apply_discount else a
        rows.append({"service": svc, "original_spend": round(a), "simulated_spend": round(sim),
                      "saving": round(a - sim), "discounted": apply_discount})
        orig_total += a
        sim_total += sim
    return {"original_top30_total": round(orig_total), "simulated_top30_total": round(sim_total),
            "estimated_saving": round(orig_total - sim_total), "discount_pct": discount_pct, "data": rows}


# ═══════════════════════════════════════════════
# 1G. HIGH COST CASES — enhanced with member visit history
# ═══════════════════════════════════════════════
@router.get("/provider/high-cost-cases")
def high_cost_cases(session_id: str = Query(...), provider_name: str = Query(None),
                    date_from: str = Query(None), date_to: str = Query(None), plan_category: str = Query(None)):
    df = _load_and_filter(session_id, provider_name, date_from, date_to, plan_category)
    if "service_type" in df.columns:
        opd = df[df["service_type"].str.lower().str.strip().isin(["outpatient", "opd", "out-patient"])]
    else:
        opd = df
    if opd.empty or "claim_no" not in opd.columns:
        return {"cases": [], "ai_narrative": None}

    # Member-level totals for context
    member_totals = {}
    if "enrolee_id" in df.columns:
        mt = df.groupby("enrolee_id").agg(total_spend=("effective_spend", "sum"), total_visits=_agg_visits(df))
        member_totals = {eid: {"total_spend": round(float(r["total_spend"])), "total_visits": int(r["total_visits"])}
                         for eid, r in mt.iterrows()}

    agg_dict = {"total_paid": ("effective_spend", "sum")}
    if "enrolee_id" in opd.columns: agg_dict["enrolee_id"] = ("enrolee_id", "first")
    if "encounter_date" in opd.columns: agg_dict["encounter_date"] = ("encounter_date", "first")
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
        eid = str(row.get("enrolee_id", ""))
        mt = member_totals.get(eid, {})
        cases.append({
            "claim_no": str(cn), "enrolee_id": eid,
            "encounter_date": d.strftime("%d %b %Y") if hasattr(d, "strftime") else "",
            "diagnosis": str(row.get("diagnosis", "")),
            "services": str(row.get("services", "")),
            "total_paid": round(float(row["total_paid"])),
            "member_total_spend": mt.get("total_spend", 0),
            "member_total_visits": mt.get("total_visits", 0),
        })

    ai_narrative = None
    try:
        from services.claude_service import ask_claude
        prov = provider_name or "the provider"
        csv = "Claim No,Enrolee ID,Date,Diagnosis,Services,Total Paid,Member Total Spend,Member Total Visits\n"
        for c in cases:
            csv += f'{c["claim_no"]},{c["enrolee_id"]},{c["encounter_date"]},"{c["diagnosis"]}","{c["services"]}",{c["total_paid"]},{c["member_total_spend"]},{c["member_total_visits"]}\n'
        ai_narrative = ask_claude(
            system=f"You are a Nigerian HMO utilization management analyst reviewing outpatient claims for {prov}. Be specific, cite claim numbers.",
            user=f"Review these high-cost outpatient visits. Flag cases where:\n(a) cost is disproportionate to the diagnosis,\n(b) multiple premium services in a single OPD visit,\n(c) a single member has excessive visit frequency (check Member Total Visits and Member Total Spend columns).\nFor each flag: state enrolee ID, visit date, what was billed, concern, severity (HIGH/MEDIUM/LOW).\n\nData:\n{csv}",
            max_tokens=3000)
    except Exception:
        pass

    return {"cases": cases, "ai_narrative": ai_narrative}


# ═══════════════════════════════════════════════
# 1H. BUNDLING & CONSUMABLE PATTERNS
# ═══════════════════════════════════════════════
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
        has_proc = any(not is_diagnostic(s) and not is_consumable(s)
                       and s.upper() not in ("GP CONSULTATION", "GP REVIEW CONSULTATION") for s in svcs)

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


# ═══════════════════════════════════════════════
# 1I. PROVIDER VISIT SUMMARY (client-wide)
# ═══════════════════════════════════════════════
@router.get("/client/provider-summary")
def provider_summary(session_id: str = Query(...), date_from: str = Query(None),
                     date_to: str = Query(None), plan_category: str = Query(None)):
    df = _load_and_filter(session_id, provider=None, date_from=date_from, date_to=date_to, plan=plan_category)
    if "claim_status" in df.columns:
        df = df[~df["claim_status"].str.lower().str.strip().isin(EXCLUDED_STATUSES)]
    if "provider_name" not in df.columns:
        return {"total_providers": 0, "data": []}
    total_all = float(df["effective_spend"].sum())
    g = df.groupby("provider_name").agg(amount_paid=("effective_spend", "sum"),
                                         unique_members=_agg_members(df), unique_visits=_agg_visits(df)
                                         ).sort_values("amount_paid", ascending=False).reset_index()
    return {"total_providers": len(g),
            "data": [{"provider": r["provider_name"], "amount_paid": round(float(r["amount_paid"])),
                       "unique_members": int(r["unique_members"]), "unique_visits": int(r["unique_visits"]),
                       "per_member_cost": round(float(r["amount_paid"]) / max(int(r["unique_members"]), 1)),
                       "pct_of_total": round(float(r["amount_paid"]) / max(total_all, 1) * 100, 1)}
                      for _, r in g.iterrows()]}


# ═══════════════════════════════════════════════
# 1J. ENROLLEE-LEVEL — enhanced with top spender flag + family subtotals
# ═══════════════════════════════════════════════
@router.get("/client/enrollees")
def enrollees(session_id: str = Query(...), provider_name: str = Query(None),
              date_from: str = Query(None), date_to: str = Query(None), plan_category: str = Query(None)):
    df = _load_and_filter(session_id, provider_name, date_from, date_to, plan_category)
    if "enrolee_id" not in df.columns:
        return {"data": [], "families": [], "flagged_multi_provider": [], "top_spenders": []}
    if "claim_status" in df.columns:
        df = df[~df["claim_status"].str.lower().str.strip().isin(EXCLUDED_STATUSES)]

    agg = {"total_paid": ("effective_spend", "sum"), "num_visits": _agg_visits(df)}
    if "provider_name" in df.columns:
        agg["hospitals"] = ("provider_name", lambda x: list(x.dropna().unique()))
    g = df.groupby("enrolee_id").agg(**agg).sort_values("total_paid", ascending=False).reset_index()

    data, flagged, top_spenders = [], [], []
    for idx, r in g.iterrows():
        hosps = r.get("hospitals", []) if isinstance(r.get("hospitals"), list) else []
        e = {"enrolee_id": r["enrolee_id"], "family_id": str(r["enrolee_id"])[:8],
             "total_paid": round(float(r["total_paid"])), "hospitals_visited": ", ".join(hosps[:5]),
             "num_hospitals": len(hosps), "num_visits": int(r["num_visits"]),
             "multi_provider_flag": len(hosps) > 5, "top_spender": idx < 10}
        data.append(e)
        if len(hosps) > 5: flagged.append(e)
        if idx < 10: top_spenders.append(e)

    # Family-level subtotals
    families = []
    family_groups = {}
    for e in data:
        fid = e["family_id"]
        if fid not in family_groups: family_groups[fid] = {"family_id": fid, "members": [], "total_paid": 0, "total_visits": 0}
        family_groups[fid]["members"].append(e["enrolee_id"])
        family_groups[fid]["total_paid"] += e["total_paid"]
        family_groups[fid]["total_visits"] += e["num_visits"]
    for fid, fg in sorted(family_groups.items(), key=lambda x: x[1]["total_paid"], reverse=True):
        if len(fg["members"]) > 1:
            families.append({"family_id": fid, "member_count": len(fg["members"]),
                              "total_paid": fg["total_paid"], "total_visits": fg["total_visits"]})

    return {"data": data, "families": families[:50], "flagged_multi_provider": flagged, "top_spenders": top_spenders}


# ═══════════════════════════════════════════════
# 1L. DIAGNOSIS PATTERN ANALYSIS (NEW)
# ═══════════════════════════════════════════════
VAGUE_DIAGNOSIS_KEYWORDS = ["unspecified", "nos", "other", "unknown", "not otherwise specified", "not specified"]

@router.get("/provider/diagnosis-patterns")
def diagnosis_patterns(session_id: str = Query(...), provider_name: str = Query(None),
                       date_from: str = Query(None), date_to: str = Query(None), plan_category: str = Query(None)):
    df = _load_and_filter(session_id, provider_name, date_from, date_to, plan_category)
    diag_col = "diag_descr" if "diag_descr" in df.columns else ("diagnosis" if "diagnosis" in df.columns else None)
    if not diag_col:
        return {"data": [], "vague_diagnoses": [], "total_vague_spend": 0}

    total_all = float(df["effective_spend"].sum())
    g = df.groupby(diag_col).agg(amount_paid=("effective_spend", "sum"),
                                  unique_members=_agg_members(df), unique_visits=_agg_visits(df)
                                  ).sort_values("amount_paid", ascending=False).reset_index()

    rows = []
    vague = []
    for _, r in g.head(30).iterrows():
        diag = str(r[diag_col])
        is_vague = any(kw in diag.lower() for kw in VAGUE_DIAGNOSIS_KEYWORDS)
        entry = {"diagnosis": diag, "amount_paid": round(float(r["amount_paid"])),
                  "unique_members": int(r["unique_members"]), "unique_visits": int(r["unique_visits"]),
                  "pct_of_total": round(float(r["amount_paid"]) / max(total_all, 1) * 100, 1),
                  "vague_flag": is_vague}
        rows.append(entry)
        if is_vague: vague.append(entry)

    # All vague diagnoses (not just top 30)
    all_vague_mask = g[diag_col].str.lower().apply(lambda d: any(kw in d for kw in VAGUE_DIAGNOSIS_KEYWORDS))
    total_vague_spend = round(float(g.loc[all_vague_mask, "amount_paid"].sum())) if all_vague_mask.any() else 0

    return {"data": rows, "vague_diagnoses": vague, "total_vague_spend": total_vague_spend,
            "pct_vague": round(total_vague_spend / max(total_all, 1) * 100, 1)}


# ═══════════════════════════════════════════════
# 1M. VISIT FREQUENCY ANALYSIS (NEW)
# ═══════════════════════════════════════════════
@router.get("/provider/visit-frequency")
def visit_frequency(session_id: str = Query(...), provider_name: str = Query(None),
                    date_from: str = Query(None), date_to: str = Query(None), plan_category: str = Query(None)):
    df = _load_and_filter(session_id, provider_name, date_from, date_to, plan_category)
    if "enrolee_id" not in df.columns or "encounter_date" not in df.columns or "claim_no" not in df.columns:
        return {"high_frequency_members": [], "day_of_week": [], "monthly_frequency": []}

    d = df.dropna(subset=["encounter_date"]).copy()
    d["year_month"] = d["encounter_date"].dt.to_period("M")
    d["dow"] = d["encounter_date"].dt.day_name()

    # Members with 4+ visits in a single month to same provider
    prov_col = "provider_name" if "provider_name" in d.columns else None
    group_cols = ["enrolee_id", "year_month"]
    if prov_col: group_cols.append(prov_col)
    freq = d.groupby(group_cols)["claim_no"].nunique().reset_index(name="visit_count")
    high_freq = freq[freq["visit_count"] >= 4].sort_values("visit_count", ascending=False)

    hf_rows = []
    for _, r in high_freq.head(30).iterrows():
        entry = {"enrolee_id": r["enrolee_id"], "month": month_label(r["year_month"]),
                  "visit_count": int(r["visit_count"])}
        if prov_col: entry["provider"] = r[prov_col]
        hf_rows.append(entry)

    # Day of week distribution
    dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow_counts = d.groupby("dow")["claim_no"].nunique().reindex(dow_order, fill_value=0)
    dow_data = [{"day": day, "visits": int(count)} for day, count in dow_counts.items()]

    return {"high_frequency_members": hf_rows, "day_of_week": dow_data}


# ═══════════════════════════════════════════════
# 1K. EXPORT — enhanced with section selection
# ═══════════════════════════════════════════════
@router.post("/provider/export-all")
def export_all(session_id: str = Query(...), provider_name: str = Query(None),
               date_from: str = Query(None), date_to: str = Query(None), plan_category: str = Query(None),
               sections: str = Query(None)):
    """sections = comma-separated sheet names to include. If None, include all."""
    df = _load_and_filter(session_id, provider_name, date_from, date_to, plan_category)
    include = set(s.strip().lower() for s in sections.split(",")) if sections else None

    def should_include(name):
        return include is None or name.lower() in include

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        if should_include("overview") and "encounter_date" in df.columns:
            d = df.dropna(subset=["encounter_date"]).copy()
            d["Month"] = d["encounter_date"].dt.to_period("M").apply(month_label)
            g = d.groupby("Month").agg(Amount_Paid=("effective_spend", "sum"), Members=_agg_members(d), Visits=_agg_visits(d)).reset_index()
            g["Avg_Per_Member"] = (g["Amount_Paid"] / g["Members"].clip(lower=1)).round(0)
            g.to_excel(w, sheet_name="Overview", index=False)

        if should_include("groups") and "group_name" in df.columns:
            g = df.groupby("group_name").agg(Amount_Paid=("effective_spend", "sum"), Members=_agg_members(df), Visits=_agg_visits(df)).sort_values("Amount_Paid", ascending=False).reset_index()
            g["Per_Member_Cost"] = (g["Amount_Paid"] / g["Members"].clip(lower=1)).round(0)
            g.to_excel(w, sheet_name="Groups", index=False)

        if should_include("schemes") and "scheme" in df.columns:
            g = df.groupby("scheme").agg(Amount_Paid=("effective_spend", "sum"), Members=_agg_members(df), Visits=_agg_visits(df)).sort_values("Amount_Paid", ascending=False).reset_index()
            g["Per_Member_Cost"] = (g["Amount_Paid"] / g["Members"].clip(lower=1)).round(0)
            g.to_excel(w, sheet_name="Schemes", index=False)

        if should_include("top30lines") and "tariff_descr" in df.columns:
            total_all = float(df["effective_spend"].sum())
            t = df.groupby("tariff_descr").agg(Amount_Paid=("effective_spend", "sum"), Members=_agg_members(df), Utilized=_agg_visits(df)).sort_values("Amount_Paid", ascending=False).head(30).reset_index()
            t["Avg_Per_Line"] = (t["Amount_Paid"] / t["Utilized"].clip(lower=1)).round(0)
            t["Pct_of_Total"] = (t["Amount_Paid"] / max(total_all, 1) * 100).round(1)
            t.to_excel(w, sheet_name="Top30Lines", index=False)

        if should_include("chronic") and "benefit" in df.columns:
            ch = df[df["benefit"].str.contains("chronic", case=False, na=False)]
            if not ch.empty and "tariff_descr" in ch.columns:
                ch.groupby("tariff_descr").agg(Spend=("effective_spend", "sum"), Members=_agg_members(ch), Dispensed=_agg_visits(ch)).sort_values("Spend", ascending=False).reset_index().to_excel(w, sheet_name="Chronic", index=False)

        if should_include("diagnosis") and ("diag_descr" in df.columns or "diagnosis" in df.columns):
            dc = "diag_descr" if "diag_descr" in df.columns else "diagnosis"
            g = df.groupby(dc).agg(Amount_Paid=("effective_spend", "sum"), Members=_agg_members(df), Visits=_agg_visits(df)).sort_values("Amount_Paid", ascending=False).head(30).reset_index()
            g.to_excel(w, sheet_name="Diagnosis", index=False)

        if should_include("enrollees") and "enrolee_id" in df.columns:
            g = df.groupby("enrolee_id").agg(Total_Paid=("effective_spend", "sum"), Visits=_agg_visits(df)).sort_values("Total_Paid", ascending=False).reset_index()
            g["Family_ID"] = g["enrolee_id"].str[:8]
            g.to_excel(w, sheet_name="EnrolleeAnalysis", index=False)

        if should_include("visitfrequency") and "encounter_date" in df.columns and "enrolee_id" in df.columns:
            d = df.dropna(subset=["encounter_date"]).copy()
            d["Month"] = d["encounter_date"].dt.to_period("M").apply(month_label)
            freq = d.groupby(["enrolee_id", "Month"])["claim_no"].nunique().reset_index(name="Visit_Count")
            freq[freq["Visit_Count"] >= 4].sort_values("Visit_Count", ascending=False).to_excel(w, sheet_name="VisitFrequency", index=False)

    buf.seek(0)
    fn = f"{(provider_name or 'All').replace(' ', '_')[:30]}_Analytics_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename={fn}"})

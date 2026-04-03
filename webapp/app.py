#!/usr/bin/env python3
"""Leadway Health Analytics Web App — Upload CSV, get instant report."""

import os
import sys
import uuid
import base64
import json
from pathlib import Path
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = Path(__file__).parent / "uploads"
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB
app.secret_key = os.environ.get("SECRET_KEY", "leadway-health-analytics-2026")

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"
LOGO_PATH = BASE_DIR / "leadway health logo 20266.jpg"
USERS_FILE = Path(__file__).parent / "users.json"


def load_users():
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text())
    # Default admin user — change password on first login
    default = {
        "admin@leadwayhealth.com": {
            "password": generate_password_hash("admin123"),
            "name": "Admin",
            "role": "admin"
        }
    }
    USERS_FILE.write_text(json.dumps(default, indent=2))
    return default


def save_users(users):
    USERS_FILE.write_text(json.dumps(users, indent=2))


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        users = load_users()
        user = users.get(session["user"], {})
        if user.get("role") != "admin":
            flash("Admin access required.")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated


def get_logo_b64():
    if LOGO_PATH.exists():
        return base64.b64encode(LOGO_PATH.read_bytes()).decode()
    return ""


@app.route("/login", methods=["GET", "POST"])
def login():
    logo = get_logo_b64()
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        users = load_users()
        user = users.get(email)
        if user and check_password_hash(user["password"], password):
            session["user"] = email
            session["name"] = user.get("name", email.split("@")[0])
            return redirect(url_for("index"))
        flash("Invalid email or password.")
    return render_template("login.html", logo=logo)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/manage-users", methods=["GET", "POST"])
@admin_required
def manage_users():
    logo = get_logo_b64()
    users = load_users()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            email = request.form.get("email", "").strip().lower()
            name = request.form.get("name", "").strip()
            password = request.form.get("password", "")
            role = request.form.get("role", "user")
            if email and password:
                users[email] = {
                    "password": generate_password_hash(password),
                    "name": name or email.split("@")[0],
                    "role": role
                }
                save_users(users)
                flash(f"User {email} added.")
        elif action == "remove":
            email = request.form.get("email", "").strip().lower()
            if email in users and email != session["user"]:
                del users[email]
                save_users(users)
                flash(f"User {email} removed.")
    user_list = [{"email": e, "name": u["name"], "role": u["role"]} for e, u in users.items()]
    return render_template("manage_users.html", logo=logo, users=user_list)


@app.route("/")
@login_required
def index():
    logo = get_logo_b64()
    user_name = session.get("name", "")
    users = load_users()
    is_admin = users.get(session.get("user", ""), {}).get("role") == "admin"
    # List existing reports
    reports = sorted(REPORTS_DIR.glob("*.html"), key=lambda f: f.stat().st_mtime, reverse=True) if REPORTS_DIR.exists() else []
    report_list = [{"name": r.stem.replace("_", " "), "file": r.name} for r in reports]
    return render_template("index.html", logo=logo, reports=report_list, user_name=user_name, is_admin=is_admin)


@app.route("/upload", methods=["POST"])
@login_required
def upload():
    # Get form data
    brokered = request.form.get("brokered", "no")
    broker_fee = float(request.form.get("broker_fee", 0)) if brokered == "yes" else 0
    additional_reqs = request.form.get("additional_reqs", "").strip()

    if brokered == "yes":
        admin_pct = 12.0
    else:
        admin_pct = 15.0
    nhia_pct = 2.0

    # Handle file uploads
    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        return redirect(url_for("index"))

    # Save uploaded files
    session_id = str(uuid.uuid4())[:8]
    upload_dir = app.config["UPLOAD_FOLDER"] / session_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved_files = {}
    for f in files:
        if f.filename:
            fname = f.filename.lower()
            fpath = upload_dir / f.filename
            f.save(fpath)
            if "claim" in fname:
                saved_files["claims"] = fpath
            elif "production" in fname or "premium" in fname:
                saved_files["production"] = fpath
            elif "benefit" in fname:
                saved_files["benefit"] = fpath
            elif "hospital" in fname:
                saved_files["hospital"] = fpath
            else:
                saved_files[f.filename] = fpath

    if "claims" not in saved_files:
        return "No claims file found. Please upload a file with 'claims' in the name.", 400

    # Generate report
    try:
        report_path = generate_report_from_files(
            saved_files, admin_pct, nhia_pct, broker_fee, additional_reqs, session_id
        )
        return redirect(url_for("view_report", filename=report_path.name))
    except Exception as e:
        import traceback
        return f"<pre>Error generating report:\n{traceback.format_exc()}</pre>", 500


def generate_report_from_files(files, admin_pct, nhia_pct, broker_fee, additional_reqs, session_id):
    """Generate an HTML analytics report from uploaded files."""
    import pandas as pd
    import numpy as np

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Load claims
    claims_path = files["claims"]
    if str(claims_path).endswith(".csv"):
        claims = pd.read_csv(claims_path)
    else:
        claims = pd.read_excel(claims_path)

    claims.columns = claims.columns.str.strip()

    # Standardize column names
    col_map = {}
    for col in claims.columns:
        cl = col.lower().strip()
        if "claim" in cl and ("num" in cl or "no" in cl):
            col_map[col] = "Claim_Number"
        elif cl in ("amt paid", "amount paid", "amountpaid"):
            col_map[col] = "Amount_Paid"
        elif cl in ("amt claimed", "amount claimed", "amountclaimed"):
            col_map[col] = "Amount_Claimed"
        elif "treatment" in cl and "date" in cl:
            col_map[col] = "Treatment_Date"
        elif cl in ("received on", "receivedon", "received_on"):
            col_map[col] = "Received_Date"
        elif "claim" in cl and "status" in cl:
            col_map[col] = "Claim_Status"
        elif cl in ("member ship no", "membershipno", "member_id", "enrollee id", "member enrollee id"):
            col_map[col] = "Member_ID"
        elif cl in ("department",):
            col_map[col] = "Department"
        elif cl in ("provider",):
            col_map[col] = "Provider"
        elif cl in ("principal member", "principalmember"):
            col_map[col] = "Principal_Member"
        elif cl in ("description",):
            col_map[col] = "Description"
        elif cl in ("scheme",):
            col_map[col] = "Scheme"
        elif cl in ("groupcode", "group code", "group_code"):
            col_map[col] = "Group_Code"
        elif cl in ("currentage", "age"):
            col_map[col] = "Age"
        elif "diagnosis" in cl and "desc" in cl:
            col_map[col] = "Diagnosis_Description"

    claims.rename(columns=col_map, inplace=True)

    # Parse numerics
    for col in ["Amount_Paid", "Amount_Claimed", "Age"]:
        if col in claims.columns:
            claims[col] = pd.to_numeric(claims[col].astype(str).str.replace(",", ""), errors="coerce")

    # Parse dates
    for col in ["Treatment_Date", "Received_Date"]:
        if col in claims.columns:
            claims[col] = pd.to_datetime(claims[col], errors="coerce")

    # Load production if available
    prod = None
    if "production" in files:
        prod_path = files["production"]
        if str(prod_path).endswith(".csv"):
            prod = pd.read_csv(prod_path)
        else:
            prod = pd.read_excel(prod_path)
        prod.columns = prod.columns.str.strip()

        # Standardize prod columns
        prod_col_map = {}
        for col in prod.columns:
            cl = col.lower().strip()
            if cl in ("l", "member enrollee id", "member_enrolleeid", "memberenrolleeid"):
                prod_col_map[col] = "Member_ID"
            elif "premium" in cl and ("fee" in cl or "individual" in cl):
                prod_col_map[col] = "Premium"
            elif "effective" in cl:
                prod_col_map[col] = "Effective_Date"
            elif "expiry" in cl or "expir" in cl:
                prod_col_map[col] = "Expiry_Date"
            elif "status" in cl and "desc" in cl:
                prod_col_map[col] = "Status"
            elif "relationship" in cl:
                prod_col_map[col] = "Relationship"
            elif "gender" in cl:
                prod_col_map[col] = "Gender"
            elif "plan" in cl:
                prod_col_map[col] = "Plan"
            elif "customer" in cl or "client" in cl and "name" in cl:
                prod_col_map[col] = "Client_Name"
        prod.rename(columns=prod_col_map, inplace=True)

        if "Premium" in prod.columns:
            prod["Premium"] = pd.to_numeric(prod["Premium"].astype(str).str.replace(",", ""), errors="coerce")
        for col in ["Effective_Date", "Expiry_Date"]:
            if col in prod.columns:
                prod[col] = pd.to_datetime(prod[col], errors="coerce")

    # Detect client name
    client_name = "Client"
    if "Group_Code" in claims.columns:
        client_name = claims["Group_Code"].mode().iloc[0] if not claims["Group_Code"].mode().empty else "Client"
    elif prod is not None and "Client_Name" in prod.columns:
        client_name = prod["Client_Name"].mode().iloc[0] if not prod["Client_Name"].mode().empty else "Client"

    # ── Metrics ──
    unique_claims = int(claims["Claim_Number"].nunique()) if "Claim_Number" in claims.columns else len(claims)
    unique_members = int(claims["Member_ID"].nunique()) if "Member_ID" in claims.columns else 0
    total_enrolled = len(prod) if prod is not None else unique_members

    paid = claims[claims["Claim_Status"] == "Paid Claims"] if "Claim_Status" in claims.columns else claims
    pipeline = claims[claims["Claim_Status"].isin(["Awaiting Payment", "Claims for adjudication", "In Process"])] if "Claim_Status" in claims.columns else pd.DataFrame()
    paid_total = float(paid["Amount_Paid"].sum()) if "Amount_Paid" in paid.columns else 0
    pipeline_total = float(pipeline["Amount_Claimed"].sum()) if "Amount_Claimed" in pipeline.columns and not pipeline.empty else 0

    # Earned premium
    earned_total = 0
    written_total = 0
    if prod is not None and "Premium" in prod.columns and "Effective_Date" in prod.columns and "Expiry_Date" in prod.columns:
        as_of = pd.Timestamp.now().normalize()
        ep = prod.dropna(subset=["Effective_Date", "Expiry_Date", "Premium"]).copy()
        ep = ep[ep["Premium"] > 0]
        total_days = (ep["Expiry_Date"] - ep["Effective_Date"]).dt.days
        elapsed = (np.minimum(as_of, ep["Expiry_Date"]) - ep["Effective_Date"]).dt.days.clip(lower=0)
        frac = (elapsed / total_days).clip(upper=1.0)
        ep["Earned"] = ep["Premium"] * frac
        earned_total = float(ep["Earned"].sum())
        written_total = float(ep["Premium"].sum())

    # Simple IBNR
    ibnr_total = 0
    if "Treatment_Date" in claims.columns and "Received_Date" in claims.columns:
        df_i = claims.dropna(subset=["Treatment_Date", "Received_Date"]).copy()
        monthly_paid = df_i.groupby(df_i["Treatment_Date"].dt.to_period("M"))["Amount_Paid"].sum()
        if len(monthly_paid) > 2:
            avg_monthly = monthly_paid.iloc[:-1].median()
            ibnr_total = float(max(avg_monthly * 0.3, 0))

    total_incurred = float(paid_total + pipeline_total + ibnr_total)
    mlr_pct = (total_incurred / earned_total * 100) if earned_total > 0 else 0
    cor_pct = mlr_pct + admin_pct + nhia_pct
    admin_amount = earned_total * admin_pct / 100
    nhia_amount = earned_total * nhia_pct / 100

    avg_per_member = paid_total / unique_members if unique_members > 0 else 0
    avg_per_visit = paid_total / unique_claims if unique_claims > 0 else 0

    # ── Helper functions ──
    def to_initials(name):
        if not name or str(name).strip() == "":
            return ""
        parts = str(name).strip().split()
        return " ".join(p[0] + "." for p in parts if p)

    def fmt(x):
        if abs(x) >= 1_000_000:
            return f"&#8358;{x/1_000_000:,.2f}M"
        if abs(x) >= 1_000:
            return f"&#8358;{x/1_000:,.0f}K"
        return f"&#8358;{x:,.0f}"

    def fmt_full(x):
        return f"&#8358;{x:,.2f}"

    def pct(x):
        return f"{x:.1f}%"

    def month_label(period):
        return period.to_timestamp().strftime("%B %Y")

    mlr_cls = "danger" if mlr_pct > 100 else ("warning" if mlr_pct > 85 else "good")

    # ── Monthly Trend ──
    monthly_rows = ""
    if "Treatment_Date" in claims.columns:
        claims["Month"] = claims["Treatment_Date"].dt.to_period("M")
        monthly = claims.dropna(subset=["Treatment_Date"]).groupby("Month").agg(
            Claims=("Claim_Number", "nunique") if "Claim_Number" in claims.columns else ("Amount_Paid", "count"),
            Paid=("Amount_Paid", "sum"),
            Members=("Member_ID", "nunique") if "Member_ID" in claims.columns else ("Amount_Paid", "count"),
        ).sort_index()
        for period, row in monthly.iterrows():
            m_claims = row["Claims"]
            m_members = row["Members"]
            m_paid = row["Paid"]
            m_avg = m_paid / m_members if m_members > 0 else 0
            m_visits = m_claims / m_members if m_members > 0 else 0
            monthly_rows += f'<tr><td>{month_label(period)}</td><td class="num">{m_claims:,}</td><td class="num">{m_members:,}</td><td class="num">{fmt_full(m_paid)}</td><td class="num">{fmt_full(m_avg)}</td><td class="num">{m_visits:.1f}</td></tr>'

    # ── Top Providers ──
    prov_rows = ""
    if "Provider" in claims.columns:
        top_prov = claims.groupby("Provider").agg(Paid=("Amount_Paid", "sum"), Claims=("Claim_Number", "nunique") if "Claim_Number" in claims.columns else ("Amount_Paid", "count")).sort_values("Paid", ascending=False).head(10)
        top_prov["Pct"] = (top_prov["Paid"] / paid_total * 100).round(1)
        for i, (name, row) in enumerate(top_prov.iterrows(), 1):
            prov_rows += f'<tr><td>{i}</td><td>{str(name).strip().title()}</td><td class="num">{fmt_full(row["Paid"])}</td><td class="num">{pct(row["Pct"])}</td><td class="num">{row["Claims"]:,}</td></tr>'

    # ── Department Breakdown ──
    dept_rows = ""
    if "Department" in claims.columns:
        dept = claims.groupby("Department").agg(Paid=("Amount_Paid", "sum"), Claims=("Claim_Number", "nunique") if "Claim_Number" in claims.columns else ("Amount_Paid", "count")).sort_values("Paid", ascending=False)
        dept["Pct"] = (dept["Paid"] / paid_total * 100).round(1)
        for i, (name, row) in enumerate(dept.head(15).iterrows(), 1):
            dept_rows += f'<tr><td>{i}</td><td>{name}</td><td class="num">{fmt_full(row["Paid"])}</td><td class="num">{pct(row["Pct"])}</td><td class="num">{row["Claims"]:,}</td></tr>'

    # ── Disease Category (Diagnosis Bands) ──
    disease_cat_rows = ""
    if "Diagnosis_Description" in claims.columns:
        disease_categories = {
            "Malaria": ["malaria", "plasmodium"],
            "Respiratory Infections": ["respiratory", "pneumonia", "bronchitis", "asthma", "cough", "influenza", "flu", "pharyngitis", "sinusitis", "tonsillitis", "rhinitis", "laryngitis", "upper respiratory", "lower respiratory", "urt", "lrt", "urti", "lrti", "nasal"],
            "Cardiovascular & Hypertension": ["hypertension", "hypertensive", "cardiac", "heart", "cardiovascular", "angina", "stroke", "cerebrovascular", "ischaemic", "ischemic", "coronary", "arrhythmia", "blood pressure"],
            "Diabetes & Metabolic": ["diabet", "glucose", "metabolic", "thyroid", "cholesterol", "lipid", "obesity", "gout", "hyperglycaemia", "hypoglycaemia"],
            "Gastrointestinal": ["gastro", "gastritis", "ulcer", "diarrh", "dyspepsia", "colitis", "intestin", "abdominal", "stomach", "bowel", "hepatitis", "liver", "gerd", "reflux", "constipation", "appendic", "hernia", "pancreat", "gallstone", "peptic"],
            "Musculoskeletal": ["arthritis", "osteo", "muscul", "joint", "back pain", "spine", "spinal", "fracture", "rheumat", "ortho", "lumbar", "cervical", "spondyl", "musculo"],
            "Eye & Ophthalmology": ["eye", "ophthalm", "visual", "cataract", "glaucoma", "conjunctiv", "retina", "myopia", "optical", "vision"],
            "Dental & Oral": ["dental", "tooth", "teeth", "oral", "gingiv", "caries", "periodon", "dentition"],
            "Obstetric & Maternity": ["pregnan", "matern", "obstetric", "antenatal", "postnatal", "delivery", "caesarean", "c-section", "labour", "labor", "gestation", "neonatal", "perinatal"],
            "Surgery & Procedures": ["surgery", "surgical", "operation", "procedure", "excision", "repair", "implant", "biopsy", "laparoscop", "endoscop"],
            "Dermatology & Skin": ["skin", "dermat", "eczema", "rash", "wound", "abscess", "cellulitis", "fungal", "urticaria", "psoriasis", "acne"],
            "Genitourinary": ["urinary", "kidney", "renal", "bladder", "urin", "prostat", "uti", "nephri", "genital", "pelvic"],
            "Infections & Parasitic": ["typhoid", "infection", "sepsis", "hiv", "tuberculosis", "measles", "chicken pox", "viral", "bacterial", "fever", "parasit"],
            "Oncology": ["cancer", "tumour", "tumor", "malignan", "carcinoma", "oncolog", "leukaemia", "leukemia", "lymphoma", "neoplasm"],
            "Mental Health & Neurology": ["mental", "depression", "anxiety", "psychi", "epilep", "seizure", "migraine", "headache", "neuro", "insomnia", "bipolar"],
            "ENT": ["ear", "nose", "throat", "otitis", "hearing", "vertigo", "adenoid"],
        }

        def classify_diagnosis(desc):
            if not desc or str(desc).strip() == "":
                return "Other / Unclassified"
            desc_lower = str(desc).lower()
            for category, keywords in disease_categories.items():
                for kw in keywords:
                    if kw in desc_lower:
                        return category
            return "Other / Unclassified"

        claims["Disease_Category"] = claims["Diagnosis_Description"].apply(classify_diagnosis)
        disease_agg = claims.groupby("Disease_Category").agg(
            Paid=("Amount_Paid", "sum"),
            Claims=("Claim_Number", "nunique") if "Claim_Number" in claims.columns else ("Amount_Paid", "count"),
        ).sort_values("Paid", ascending=False)
        disease_agg["Pct"] = (disease_agg["Paid"] / paid_total * 100).round(1)
        for i, (cat, row) in enumerate(disease_agg.head(10).iterrows(), 1):
            disease_cat_rows += f'<tr><td>{i}</td><td>{cat}</td><td class="num">{fmt_full(row["Paid"])}</td><td class="num">{pct(row["Pct"])}</td><td class="num">{row["Claims"]:,}</td></tr>'

    # ── MLR by Age Group ──
    age_mlr_rows = ""
    if "Age" in claims.columns and earned_total > 0:
        age_bins = [0, 5, 18, 30, 40, 50, 60, 70, 120]
        age_labels = ["0-5", "6-18", "19-30", "31-40", "41-50", "51-60", "61-70", "71+"]
        claims["Age_Group"] = pd.cut(claims["Age"].dropna(), bins=age_bins, labels=age_labels, right=True)
        age_agg = claims.dropna(subset=["Age_Group"]).groupby("Age_Group", observed=True).agg(
            Paid=("Amount_Paid", "sum"),
            Claims=("Claim_Number", "nunique") if "Claim_Number" in claims.columns else ("Amount_Paid", "count"),
            Members=("Member_ID", "nunique") if "Member_ID" in claims.columns else ("Amount_Paid", "count"),
        )
        # Distribute earned premium proportionally by member count for age-group MLR
        total_age_members = age_agg["Members"].sum()
        for grp, row in age_agg.iterrows():
            if row["Members"] == 0:
                continue
            grp_earned = earned_total * (row["Members"] / total_age_members) if total_age_members > 0 else 0
            grp_mlr = (row["Paid"] / grp_earned * 100) if grp_earned > 0 else 0
            grp_avg = row["Paid"] / row["Members"] if row["Members"] > 0 else 0
            mlr_class = "danger" if grp_mlr > 100 else ("warning" if grp_mlr > 85 else "good")
            age_mlr_rows += f'<tr><td>{grp}</td><td class="num">{row["Members"]:,}</td><td class="num">{row["Claims"]:,}</td><td class="num">{fmt_full(row["Paid"])}</td><td class="num">{fmt_full(grp_earned)}</td><td class="num {mlr_class}">{pct(grp_mlr)}</td><td class="num">{fmt_full(grp_avg)}</td></tr>'

    # ── Early High Claimers ──
    early_claimers_rows = ""
    early_claimers_count = 0
    if prod is not None and "Effective_Date" in prod.columns and "Member_ID" in prod.columns and "Member_ID" in claims.columns:
        # Build member join dates and premium from production data
        member_join = prod.dropna(subset=["Effective_Date", "Member_ID"]).groupby("Member_ID").agg(
            Join_Date=("Effective_Date", "min"),
            Premium=("Premium", "sum") if "Premium" in prod.columns else ("Effective_Date", "count"),
        )
        # Get first claim date and total spent per member
        member_claims = claims.dropna(subset=["Treatment_Date"]).groupby("Member_ID").agg(
            First_Claim=("Treatment_Date", "min"),
            Total_Spent=("Amount_Paid", "sum"),
        )
        # Merge
        ehc = member_join.join(member_claims, how="inner")
        ehc["Days"] = (ehc["First_Claim"] - ehc["Join_Date"]).dt.days
        # Filter: spent over 200K within 30 days of enrolment
        ehc_flagged = ehc[(ehc["Days"].abs() <= 30) & (ehc["Total_Spent"] > 200_000)].sort_values("Total_Spent", ascending=False)
        early_claimers_count = len(ehc_flagged)

        # Get principal member name for initials
        principal_map = {}
        if "Principal_Member" in claims.columns:
            principal_map = claims.dropna(subset=["Member_ID", "Principal_Member"]).drop_duplicates("Member_ID").set_index("Member_ID")["Principal_Member"].to_dict()

        for mid, row in ehc_flagged.head(20).iterrows():
            full_name = str(principal_map.get(mid, "")).strip()
            initials = to_initials(full_name) if full_name else ""
            join_dt = row["Join_Date"].strftime("%Y-%m-%d") if pd.notna(row["Join_Date"]) else ""
            first_dt = row["First_Claim"].strftime("%Y-%m-%d") if pd.notna(row["First_Claim"]) else ""
            days_val = int(row["Days"])
            days_str = f"{days_val}d"
            premium_val = row["Premium"] if "Premium" in prod.columns and pd.notna(row["Premium"]) and row["Premium"] > 0 else 0
            spend_ratio = row["Total_Spent"] / premium_val if premium_val > 0 else 0
            ratio_cls = "danger" if spend_ratio > 5 else ("warning" if spend_ratio > 2 else "")
            ratio_str = f"{spend_ratio:.1f}x" if premium_val > 0 else "N/A"
            early_claimers_rows += f'<tr><td>{mid}</td><td>{initials}</td><td class="num">{join_dt}</td><td class="num">{first_dt}</td><td class="num">{days_str}</td><td class="num">{fmt_full(row["Total_Spent"])}</td><td class="num">{fmt_full(premium_val) if premium_val > 0 else "—"}</td><td class="num {ratio_cls}">{ratio_str}</td></tr>'

    # ── What Went Wrong (MLR > 90%) ──
    what_went_wrong_html = ""
    if mlr_pct > 90 and earned_total > 0:
        issues = []
        # Identify top cost-driving disease categories
        if "Diagnosis_Description" in claims.columns and "Disease_Category" in claims.columns:
            top_cats = claims.groupby("Disease_Category")["Amount_Paid"].sum().sort_values(ascending=False).head(3)
            top_cat_names = ", ".join(top_cats.index.tolist())
            top_cat_pct = (top_cats.sum() / paid_total * 100)
            issues.append(f"The top 3 disease categories (<strong>{top_cat_names}</strong>) account for <strong>{top_cat_pct:.0f}%</strong> of total paid claims, indicating heavy cost concentration.")
        # High-cost providers
        if "Provider" in claims.columns:
            top3_prov = claims.groupby("Provider")["Amount_Paid"].sum().sort_values(ascending=False).head(3)
            top3_prov_pct = (top3_prov.sum() / paid_total * 100)
            issues.append(f"The top 3 providers consume <strong>{top3_prov_pct:.0f}%</strong> of paid claims. Provider concentration risk is elevated.")
        # High utilisation per member
        if unique_members > 0:
            freq = unique_claims / unique_members
            issues.append(f"Average claims frequency is <strong>{freq:.1f} visits per member</strong>. {'This is high and suggests over-utilisation.' if freq > 3 else 'Monitor for upward trends.'}")
        # Pipeline pressure
        if pipeline_total > 0 and earned_total > 0:
            pipeline_pct = pipeline_total / earned_total * 100
            if pipeline_pct > 10:
                issues.append(f"Outstanding pipeline claims represent <strong>{pipeline_pct:.1f}%</strong> of earned premium — a significant liability exposure.")
        # IBNR warning
        if ibnr_total > 0 and earned_total > 0:
            ibnr_pct_ep = ibnr_total / earned_total * 100
            if ibnr_pct_ep > 5:
                issues.append(f"IBNR reserve estimate is <strong>{ibnr_pct_ep:.1f}%</strong> of earned premium, indicating delayed claims reporting.")

        if issues:
            items = "".join(f"<li>{i}</li>" for i in issues)
            what_went_wrong_html = f'''<div class="alert-card warning-card">
    <h2>&#9888; What Went <span class="accent">Wrong</span></h2>
    <p class="alert-subtitle">MLR is at <strong>{pct(mlr_pct)}</strong> — claims are consuming a disproportionate share of premium income.</p>
    <ul class="insight-list">{items}</ul></div>'''

    # ── Is the Plan Adequately Priced? (MLR > 100%) ──
    pricing_html = ""
    if mlr_pct > 100 and earned_total > 0:
        shortfall = total_incurred - earned_total
        required_premium = total_incurred / 0.85  # target 85% MLR
        premium_increase_pct = ((required_premium - earned_total) / earned_total * 100) if earned_total > 0 else 0
        per_member_deficit = shortfall / total_enrolled if total_enrolled > 0 else 0

        pricing_points = []
        pricing_points.append(f"Total incurred claims (<strong>{fmt_full(total_incurred)}</strong>) exceed earned premium (<strong>{fmt_full(earned_total)}</strong>) by <strong>{fmt_full(shortfall)}</strong>.")
        pricing_points.append(f"To achieve a target MLR of 85%, the required annual premium would be approximately <strong>{fmt_full(required_premium)}</strong> — a <strong>{premium_increase_pct:.0f}%</strong> increase.")
        if per_member_deficit > 0:
            pricing_points.append(f"The per-member deficit is <strong>{fmt_full(per_member_deficit)}</strong>, which must be recovered through premium adjustment or benefit redesign.")
        pricing_points.append("The current premium structure is <strong>not sustainable</strong>. Without corrective action, the plan will continue to operate at a loss.")

        items = "".join(f"<li>{i}</li>" for i in pricing_points)
        pricing_html = f'''<div class="alert-card danger-card">
    <h2>&#128200; Is the Plan <span class="accent">Adequately Priced?</span></h2>
    <p class="alert-subtitle">MLR exceeds 100% — the plan is paying out more in claims than it earns in premium.</p>
    <ul class="insight-list">{items}</ul></div>'''

    # ── Key Recommendations ──
    recommendations = []
    if mlr_pct > 100:
        recommendations.append("Initiate an immediate premium review. Current pricing does not cover incurred claims and the plan is operating at a loss.")
    elif mlr_pct > 90:
        recommendations.append("Conduct a premium adequacy assessment at the next renewal cycle. The MLR is approaching unsustainable levels.")
    if "Provider" in claims.columns:
        recommendations.append("Negotiate provider tariff agreements and expand the preferred provider network to control unit costs.")
    if "Disease_Category" in claims.columns:
        top_cat = claims.groupby("Disease_Category")["Amount_Paid"].sum().idxmax()
        recommendations.append(f"Implement targeted wellness and disease management programmes for <strong>{top_cat}</strong>, the highest cost disease category.")
    if unique_members > 0 and unique_claims / unique_members > 3:
        recommendations.append("Introduce utilisation management controls such as pre-authorisation for high-cost procedures and specialist referrals.")
    if pipeline_total > 0 and earned_total > 0 and (pipeline_total / earned_total * 100) > 10:
        recommendations.append("Accelerate claims adjudication to reduce pipeline backlog and improve reserve forecasting accuracy.")
    if ibnr_total > 0:
        recommendations.append("Strengthen claims reporting timelines with providers to reduce IBNR exposure and improve loss estimation.")
    recommendations.append("Review benefit design — consider co-payments, sub-limits, or exclusions on high-frequency, low-severity claims to reduce overall utilisation.")
    recommendations.append("Schedule quarterly claims experience reviews to monitor trends and enable early intervention.")

    reco_items = "".join(f"<li>{r}</li>" for r in recommendations)
    recommendations_html = f'''<div class="alert-card reco-card">
    <h2>&#128161; Key <span class="accent">Recommendations</span></h2>
    <ol class="insight-list numbered">{reco_items}</ol></div>'''

    logo = get_logo_b64()
    clean_name = str(client_name).strip().replace(" ", "_")[:30]

    # ── Additional info ──
    fee_note = ""
    if broker_fee > 0:
        fee_note = f"<tr><td>Broker Fee</td><td>{broker_fee}%</td></tr>"
    addl_note = f'<p style="color:var(--text-muted);font-size:12px;margin-top:8px;">{additional_reqs}</p>' if additional_reqs else ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{client_name} — Analytics Report</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
  :root {{ --navy: #1A1A2E; --crimson: #C8102E; --coral: #E87722; --cream: #FAF7F2; --light-blue: #E8F4FD; --light-grey: #F4F4F6; --medium-grey: #E8E8EC; --text-dark: #1A1A2E; --text-muted: #6B7280; --white: #FFFFFF; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Inter', sans-serif; background: var(--cream); color: var(--text-dark); line-height: 1.6; font-size: 14px; }}
  .container {{ max-width: 1140px; margin: 0 auto; padding: 40px 20px; }}
  .header {{ background: var(--navy); color: var(--white); padding: 40px; border-radius: 16px; margin-bottom: 30px; display: flex; align-items: center; gap: 24px; }}
  .header img {{ height: 60px; }}
  .header h1 {{ font-weight: 800; font-size: 28px; }}
  .header .subtitle {{ font-size: 14px; opacity: 0.7; }}
  .section {{ background: var(--white); border-radius: 14px; padding: 32px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }}
  .section h2 {{ font-weight: 700; font-size: 20px; color: var(--navy); margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid var(--medium-grey); }}
  .section h2 span.accent {{ color: var(--crimson); }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }}
  .kpi {{ background: var(--white); border: 1px solid var(--medium-grey); border-radius: 12px; padding: 22px 18px; text-align: center; }}
  .kpi .label {{ font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px; color: var(--text-muted); margin-bottom: 8px; }}
  .kpi .value {{ font-weight: 800; font-size: 22px; color: var(--navy); }}
  .kpi.highlight {{ border-color: var(--crimson); border-width: 2px; }}
  .kpi.highlight .value {{ color: var(--crimson); }}
  .data-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  .data-table thead th {{ background: var(--navy); color: var(--white); padding: 12px 10px; text-align: left; font-weight: 600; font-size: 11px; text-transform: uppercase; }}
  .data-table thead th.num {{ text-align: right; }}
  .data-table tbody td {{ padding: 10px; border-bottom: 1px solid var(--light-grey); }}
  .data-table tbody td.num {{ text-align: right; }}
  .data-table tbody tr:hover {{ background: var(--light-blue); }}
  .data-table tbody tr:nth-child(even) {{ background: var(--light-grey); }}
  .data-table tbody td.good {{ color: #16a34a; font-weight: 700; }}
  .data-table tbody td.warning {{ color: var(--coral); font-weight: 700; }}
  .data-table tbody td.danger {{ color: var(--crimson); font-weight: 700; }}
  .mlr-card {{ background: var(--navy); color: var(--white); border-radius: 14px; padding: 32px; margin-bottom: 24px; }}
  .mlr-card h2 {{ color: var(--white); border: none; }}
  .mlr-table {{ width: 100%; border-collapse: collapse; }}
  .mlr-table td {{ padding: 10px 12px; border-bottom: 1px solid rgba(255,255,255,0.08); font-size: 13px; }}
  .mlr-table td:last-child {{ text-align: right; font-weight: 600; }}
  .mlr-table tr.total td {{ border-top: 2px solid var(--crimson); font-weight: 800; font-size: 15px; }}
  .mlr-table tr.total td:last-child {{ color: var(--coral); }}
  .footer {{ text-align: center; color: var(--text-muted); font-size: 11px; margin-top: 20px; padding: 20px; }}
  .dl-btn {{ display: inline-flex; align-items: center; gap: 6px; padding: 10px 20px; background: var(--crimson); color: var(--white); border: none; border-radius: 8px; font-family: inherit; font-size: 13px; font-weight: 700; text-decoration: none; cursor: pointer; transition: background 0.2s; margin-left: auto; }}
  .dl-btn:hover {{ background: #a00d24; }}
  .dl-btn svg {{ width: 16px; height: 16px; }}
  .alert-card {{ border-radius: 14px; padding: 32px; margin-bottom: 24px; }}
  .alert-card h2 {{ font-weight: 700; font-size: 20px; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 2px solid rgba(0,0,0,0.08); }}
  .alert-card h2 span.accent {{ color: var(--crimson); }}
  .alert-subtitle {{ font-size: 14px; color: var(--text-muted); margin-bottom: 16px; font-weight: 500; }}
  .alert-subtitle strong {{ color: var(--text-dark); }}
  .insight-list {{ margin: 0; padding-left: 20px; }}
  .insight-list li {{ padding: 8px 0; font-size: 13px; line-height: 1.7; border-bottom: 1px solid rgba(0,0,0,0.04); }}
  .insight-list li:last-child {{ border: none; }}
  .insight-list li strong {{ color: var(--navy); }}
  .warning-card {{ background: #FFF7ED; border: 2px solid var(--coral); box-shadow: 0 2px 8px rgba(232,119,34,0.1); }}
  .warning-card h2 {{ color: var(--coral); }}
  .danger-card {{ background: #FEF2F2; border: 2px solid var(--crimson); box-shadow: 0 2px 8px rgba(200,16,46,0.1); }}
  .danger-card h2 {{ color: var(--crimson); }}
  .reco-card {{ background: #F0FDF4; border: 2px solid #16a34a; box-shadow: 0 2px 8px rgba(22,163,74,0.1); }}
  .reco-card h2 {{ color: #16a34a; }}
  .reco-card h2 span.accent {{ color: #15803d; }}
  .insight-list.numbered {{ list-style-type: decimal; }}
  @media print {{ .dl-btn {{ display: none; }} }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    {'<img src="data:image/jpeg;base64,' + logo + '" alt="Leadway Health">' if logo else ''}
    <div><h1>{client_name}</h1><div class="subtitle">Analytics Report &nbsp;|&nbsp; {pd.Timestamp.now().strftime('%d %B %Y')}</div></div>
    <button class="dl-btn" onclick="downloadReport()" style="margin-left:auto;"><svg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='currentColor' stroke-width='2'><path stroke-linecap='round' stroke-linejoin='round' d='M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5m0 0l5-5m-5 5V3'/></svg>Download</button>
  </div>
  {addl_note}
  <div class="section">
    <h2>Executive <span class="accent">Overview</span></h2>
    <div class="kpi-grid">
      <div class="kpi highlight"><div class="label">Total Incurred</div><div class="value">{fmt(total_incurred)}</div></div>
      <div class="kpi"><div class="label">Paid Claims</div><div class="value">{fmt(paid_total)}</div></div>
      <div class="kpi"><div class="label">Pipeline</div><div class="value">{fmt(pipeline_total)}</div></div>
      <div class="kpi"><div class="label">Earned Premium</div><div class="value">{fmt(earned_total)}</div></div>
      <div class="kpi"><div class="label">Written Premium</div><div class="value">{fmt(written_total)}</div></div>
      <div class="kpi highlight"><div class="label">MLR</div><div class="value">{pct(mlr_pct)}</div></div>
      <div class="kpi highlight"><div class="label">COR</div><div class="value">{pct(cor_pct)}</div></div>
      <div class="kpi"><div class="label">Members</div><div class="value">{unique_members:,}</div></div>
      <div class="kpi"><div class="label">Unique Claims</div><div class="value">{unique_claims:,}</div></div>
      <div class="kpi"><div class="label">Avg/Member</div><div class="value">{fmt(avg_per_member)}</div></div>
    </div>
  </div>
  <div class="mlr-card">
    <h2>MLR &amp; COR</h2>
    <table class="mlr-table">
      <tr><td>Paid Claims</td><td>{fmt_full(paid_total)}</td></tr>
      <tr><td>Pipeline Claims</td><td>{fmt_full(pipeline_total)}</td></tr>
      <tr><td>IBNR</td><td>{fmt_full(ibnr_total)}</td></tr>
      <tr class="total"><td>Total Incurred</td><td>{fmt_full(total_incurred)}</td></tr>
      <tr><td style="padding-top:16px;">Earned Premium</td><td style="padding-top:16px;">{fmt_full(earned_total)}</td></tr>
      <tr class="total"><td>MLR</td><td>{pct(mlr_pct)}</td></tr>
      <tr><td style="padding-top:16px;">Admin ({admin_pct}%)</td><td style="padding-top:16px;">{fmt_full(admin_amount)}</td></tr>
      <tr><td>NHIA (2%)</td><td>{fmt_full(nhia_amount)}</td></tr>
      {fee_note}
      <tr class="total"><td>COR</td><td>{pct(cor_pct)}</td></tr>
    </table>
  </div>
  <div class="section"><h2>Monthly Claims <span class="accent">Trend</span></h2>
    <table class="data-table"><thead><tr><th>Month</th><th class="num">Unique Claims</th><th class="num">Members</th><th class="num">Total Paid</th><th class="num">Avg/Member</th><th class="num">Visits/Member</th></tr></thead>
    <tbody>{monthly_rows}</tbody></table></div>
  <div class="section"><h2>Top <span class="accent">Providers</span></h2>
    <table class="data-table"><thead><tr><th>#</th><th>Provider</th><th class="num">Total Paid</th><th class="num">%</th><th class="num">Claims</th></tr></thead>
    <tbody>{prov_rows}</tbody></table></div>
  <div class="section"><h2>Department <span class="accent">Breakdown</span></h2>
    <table class="data-table"><thead><tr><th>#</th><th>Department</th><th class="num">Total Paid</th><th class="num">%</th><th class="num">Claims</th></tr></thead>
    <tbody>{dept_rows}</tbody></table></div>
  {"" if not disease_cat_rows else '<div class="section"><h2>Top 10 <span class="accent">Disease Categories</span></h2><table class="data-table"><thead><tr><th>#</th><th>Disease Category</th><th class="num">Total Paid</th><th class="num">%</th><th class="num">Claims</th></tr></thead><tbody>' + disease_cat_rows + '</tbody></table></div>'}
  {"" if not age_mlr_rows else '<div class="section"><h2>MLR by <span class="accent">Age Group</span></h2><table class="data-table"><thead><tr><th>Age Group</th><th class="num">Members</th><th class="num">Claims</th><th class="num">Total Paid</th><th class="num">Earned Premium</th><th class="num">MLR</th><th class="num">Avg/Member</th></tr></thead><tbody>' + age_mlr_rows + '</tbody></table></div>'}
  {"" if not early_claimers_rows else '<div class="section"><h2>Early High <span class="accent">Claimers</span></h2><p style="color:var(--text-muted);font-size:13px;margin-bottom:16px;">Members who spent over &#8358;200K within 30 days of enrolment (' + str(early_claimers_count) + ' flagged)</p><table class="data-table"><thead><tr><th>Member ID</th><th>Principal</th><th class="num">Join Date</th><th class="num">First Claim</th><th class="num">Days</th><th class="num">Total Spent</th><th class="num">Premium</th><th class="num">Spend/Premium</th></tr></thead><tbody>' + early_claimers_rows + '</tbody></table></div>'}
  {what_went_wrong_html}
  {pricing_html}
  {recommendations_html}
  <div class="footer">Generated by Leadway Health Analytics &nbsp;|&nbsp; {pd.Timestamp.now().strftime('%d %B %Y')}</div>
</div>
<script>
function downloadReport() {{
  var el = document.createElement('a');
  el.setAttribute('href', 'data:text/html;charset=utf-8,' + encodeURIComponent(document.documentElement.outerHTML));
  el.setAttribute('download', '{clean_name}_Report.html');
  el.style.display = 'none';
  document.body.appendChild(el);
  el.click();
  document.body.removeChild(el);
}}
</script>
</body></html>"""

    # Save report
    report_path = REPORTS_DIR / f"{clean_name}_Report_{session_id}.html"
    report_path.write_text(html)
    return report_path


@app.route("/report/<filename>")
@login_required
def view_report(filename):
    return send_file(REPORTS_DIR / filename)


@app.route("/download/<filename>")
@login_required
def download_report(filename):
    return send_file(REPORTS_DIR / filename, as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

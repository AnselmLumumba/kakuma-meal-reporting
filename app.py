import hmac
import io
import os
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

# set_page_config must be the first Streamlit command in the script.
st.set_page_config(page_title="Kakuma MEAL Reporting System", page_icon="📊", layout="wide")


def check_password():
    """Simple shared-password gate. The password is stored in Streamlit Secrets as APP_PASSWORD."""
    def password_entered():
        if hmac.compare_digest(st.session_state["password"], st.secrets["APP_PASSWORD"]):
            st.session_state["authenticated"] = True
            del st.session_state["password"]
        else:
            st.session_state["authenticated"] = False

    if st.session_state.get("authenticated"):
        return True

    st.title("Kakuma MEAL Reporting")
    st.text_input("Password", type="password", on_change=password_entered, key="password")
    if st.session_state.get("authenticated") is False:
        st.error("Incorrect password")
    return False


if not check_password():
    st.stop()

CENTRES = ["DBK", "DB1", "DB2", "DB3", "DB4", "Kalobeyei"]
REQUIRED_COLUMNS = ["date", "centre", "participant_id", "gender", "population_group", "course", "enrolled", "completed", "employed"]
OPTIONAL_COLUMNS = ["project", "age", "employment_date", "employer", "activity", "indicator", "target", "achieved", "notes"]
ALL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

st.title("Kakuma NGO / MEAL Reporting System")
st.caption("Beneficiary statistics • Training and employment tracking • Monthly and quarterly reporting")

with st.sidebar:
    st.header("Data source")
    source = st.radio("Choose how to load data", ["Google Sheets URL", "Upload Excel/CSV", "Use sample data"], index=0)
    st.markdown("---")
    st.markdown("**Google Sheets setup**")
    st.caption("For a quick connection, set the sheet to ‘Anyone with the link — Viewer’ and paste its URL. For confidential data, use a private sheet with the optional service-account setup in README.md.")

@st.cache_data(ttl=300, show_spinner=False)
def read_sheet_csv(url: str) -> pd.DataFrame:
    import re
    # Convert common Google Sheets URLs to a CSV export URL.
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    if not m:
        raise ValueError("That does not look like a Google Sheets URL.")
    sheet_id = m.group(1)
    gid_match = re.search(r"[?#&]gid=(\d+)", url)
    gid = gid_match.group(1) if gid_match else "0"
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    try:
        return pd.read_csv(csv_url)
    except Exception as public_error:
        # Optional private-sheet access for deployments configured with Streamlit secrets.
        try:
            service_account_info = dict(st.secrets["gcp_service_account"])
            import gspread
            client = gspread.service_account_from_dict(service_account_info)
            spreadsheet = client.open_by_key(sheet_id)
            worksheet = next((ws for ws in spreadsheet.worksheets() if str(ws.id) == str(gid)), spreadsheet.sheet1)
            values = worksheet.get_all_records()
            if not values:
                raise ValueError("The selected worksheet is empty or has no header row.")
            return pd.DataFrame(values)
        except Exception as private_error:
            raise ValueError(
                "Could not read this Google Sheet. For the quick setup, allow 'Anyone with the link' Viewer access. "
                "For a private sheet, configure Streamlit secrets with a service account and share the sheet with its email. "
                f"Public-link error: {public_error}; private access error: {private_error}"
            ) from private_error

def sample_data() -> pd.DataFrame:
    rows = [
        ["2026-01-12","DBK","DBK-001","Female","Refugee","Digital Skills",1,1,1,"Digital Livelihoods",22,"2026-03-02","Online gig work","Training","Learners trained",100,85,"Sample record"],
        ["2026-01-18","DB1","DB1-002","Male","Refugee","Electrical Installation",1,1,0,"TVET",24,"","","Training","Learners trained",80,72,"Sample record"],
        ["2026-02-05","DB2","DB2-003","Female","Host","Business Skills",1,1,1,"Livelihoods",27,"2026-03-20","Small business","Business coaching","Graduates employed/self-employed",40,18,"Sample record"],
        ["2026-02-22","DB3","DB3-004","Female","Refugee","ICT",1,0,0,"Digital Livelihoods",19,"","","Training","Learners trained",90,65,"Sample record"],
        ["2026-03-10","DB4","DB4-005","Male","Host","Fashion and Design",1,1,0,"TVET",21,"","","Training","Learners trained",70,51,"Sample record"],
        ["2026-04-14","Kalobeyei","KAL-006","Female","Refugee","Digital Skills",1,1,1,"Digital Livelihoods",23,"2026-05-02","Freelancing","Apprenticeship","Learners employed",50,32,"Sample record"],
        ["2026-05-09","DBK","DBK-007","Male","Refugee","Agriculture",1,1,0,"Livelihoods",29,"","","Training","Learners trained",60,43,"Sample record"],
        ["2026-06-17","DB1","DB1-008","Female","Host","Secretarial",1,1,1,"TVET",20,"2026-07-01","Office assistant","Placement","Graduates employed",30,17,"Sample record"],
        ["2026-07-03","DB2","DB2-009","Female","Refugee","ICT",1,1,0,"Digital Livelihoods",18,"","","Training","Learners trained",100,88,"Sample record"],
        ["2026-08-21","DB3","DB3-010","Male","Refugee","Business Skills",1,0,0,"Livelihoods",26,"","","Training","Learners trained",75,49,"Sample record"],
        ["2026-09-06","DB4","DB4-011","Female","Host","Fashion and Design",1,1,1,"TVET",25,"2026-09-20","Tailoring business","Enterprise support","Graduates employed/self-employed",35,24,"Sample record"],
        ["2026-09-19","Kalobeyei","KAL-012","Male","Refugee","Digital Skills",1,1,1,"Digital Livelihoods",22,"2026-10-01","Remote work","Job linkage","Learners employed",45,38,"Sample record"],
    ]
    cols = ["date","centre","participant_id","gender","population_group","course","enrolled","completed","employed","project","age","employment_date","employer","activity","indicator","target","achieved","notes"]
    return pd.DataFrame(rows, columns=cols)

raw = None
try:
    if source == "Google Sheets URL":
        sheet_url = st.sidebar.text_input("Google Sheets URL", placeholder="https://docs.google.com/spreadsheets/d/...")
        if sheet_url.strip():
            with st.spinner("Loading Google Sheet…"):
                raw = read_sheet_csv(sheet_url.strip())
            st.sidebar.success("Google Sheet loaded")
        else:
            st.info("Paste a Google Sheets URL in the sidebar, or choose another data source to preview the system.")
            raw = sample_data()
            st.warning("Showing sample data until you connect your sheet. Sample records are fictional.")
    elif source == "Upload Excel/CSV":
        upload = st.sidebar.file_uploader("Upload an Excel or CSV file", type=["csv", "xlsx", "xls"])
        if upload:
            raw = pd.read_csv(upload) if upload.name.lower().endswith(".csv") else pd.read_excel(upload)
        else:
            st.info("Upload an Excel or CSV file in the sidebar. You can use sample data to preview the system.")
            raw = sample_data()
    else:
        raw = sample_data()
        st.warning("You are viewing fictional sample data. Replace it with your real records before reporting.")
except Exception as e:
    st.error(f"Could not load the data source: {e}")
    st.info("Check that the sheet is accessible and that the first row contains column headers. See README.md for details.")
    raw = sample_data()

if raw is not None:
    raw.columns = [str(c).strip().lower().replace(" ", "_") for c in raw.columns]
    aliases = {"participantid":"participant_id", "beneficiary_id":"participant_id", "centre_name":"centre", "training_centre":"centre", "sex":"gender", "community":"population_group", "training_completed":"completed", "employment_status":"employed", "enrolment":"enrolled"}
    raw = raw.rename(columns={c: aliases[c] for c in raw.columns if c in aliases})
    missing = [c for c in REQUIRED_COLUMNS if c not in raw.columns]
    if missing:
        st.error("Your data is missing required columns: " + ", ".join(missing))
        st.markdown("Required columns: `" + "`, `".join(REQUIRED_COLUMNS) + "`. See the sample_data.csv file for the expected format.")
        st.stop()
    for c in OPTIONAL_COLUMNS:
        if c not in raw.columns:
            raw[c] = "" if c not in ["age", "target", "achieved"] else 0
    df = raw.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    for c in ["enrolled", "completed", "employed", "age", "target", "achieved"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    for c in ["centre", "participant_id", "gender", "population_group", "course", "project", "employer", "activity", "indicator", "notes"]:
        df[c] = df[c].fillna("").astype(str).str.strip()
    df["quarter"] = df["date"].dt.to_period("Q").astype(str)
    df["month"] = df["date"].dt.to_period("M").astype(str)

    with st.sidebar:
        st.markdown("---")
        st.header("Filters")
        centre_options = sorted([x for x in df["centre"].dropna().unique() if x])
        selected_centres = st.multiselect("Centre", centre_options, default=centre_options)
        min_date = df["date"].min().date() if not df.empty else date.today()
        max_date = df["date"].max().date() if not df.empty else date.today()
        date_range = st.date_input("Reporting date range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
        gender_options = sorted([x for x in df["gender"].unique() if x])
        selected_gender = st.multiselect("Gender", gender_options, default=gender_options)
        group_options = sorted([x for x in df["population_group"].unique() if x])
        selected_groups = st.multiselect("Population group", group_options, default=group_options)
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = end_date = date_range
    filtered = df[(df["centre"].isin(selected_centres)) & (df["date"].dt.date >= start_date) & (df["date"].dt.date <= end_date) & (df["gender"].isin(selected_gender)) & (df["population_group"].isin(selected_groups))].copy()

    # Count unique beneficiaries where IDs are available; use summed enrolment/completion fields for program totals.
    unique_beneficiaries = filtered.loc[filtered["participant_id"].ne(""), "participant_id"].nunique()
    total_enrolled = int(filtered["enrolled"].sum())
    total_completed = int(filtered["completed"].sum())
    total_employed = int(filtered["employed"].sum())
    completion_rate = (total_completed / total_enrolled * 100) if total_enrolled else 0
    employment_rate = (total_employed / total_completed * 100) if total_completed else 0

    tab1, tab2, tab3, tab4 = st.tabs(["Dashboard", "Beneficiary statistics", "Training & employment", "Reports & exports"])
    with tab1:
        st.subheader("Programme overview")
        k1,k2,k3,k4,k5 = st.columns(5)
        k1.metric("Unique beneficiaries", f"{unique_beneficiaries:,}")
        k2.metric("Enrolments", f"{total_enrolled:,}")
        k3.metric("Completed training", f"{total_completed:,}")
        k4.metric("Recorded employed", f"{total_employed:,}")
        k5.metric("Completion rate", f"{completion_rate:.1f}%")
        left,right = st.columns(2)
        by_centre = filtered.groupby("centre", as_index=False).agg(Enrolments=("enrolled","sum"), Completed=("completed","sum"), Employed=("employed","sum"))
        with left:
            st.plotly_chart(px.bar(by_centre, x="centre", y=["Enrolments","Completed","Employed"], barmode="group", title="Training outcomes by centre"), use_container_width=True)
        with right:
            by_month = filtered.groupby("month", as_index=False).agg(Enrolments=("enrolled","sum"), Completed=("completed","sum"))
            st.plotly_chart(px.line(by_month, x="month", y=["Enrolments","Completed"], markers=True, title="Monthly training trend"), use_container_width=True)
        st.plotly_chart(px.bar(filtered.groupby("population_group", as_index=False)["participant_id"].nunique(), x="population_group", y="participant_id", title="Unique beneficiaries by population group", labels={"participant_id":"Unique beneficiaries","population_group":"Population group"}), use_container_width=True)
    with tab2:
        st.subheader("Beneficiary statistics")
        left,right = st.columns(2)
        with left:
            gender_stats = filtered.groupby("gender", as_index=False)["participant_id"].nunique().rename(columns={"participant_id":"Unique beneficiaries"})
            st.plotly_chart(px.pie(gender_stats, names="gender", values="Unique beneficiaries", title="Beneficiaries by gender"), use_container_width=True)
        with right:
            group_stats = filtered.groupby("population_group", as_index=False)["participant_id"].nunique().rename(columns={"participant_id":"Unique beneficiaries"})
            st.plotly_chart(px.pie(group_stats, names="population_group", values="Unique beneficiaries", title="Refugee / host-community breakdown"), use_container_width=True)
        st.markdown("**Beneficiaries by centre and gender**")
        pivot = filtered.pivot_table(index="centre", columns="gender", values="participant_id", aggfunc=pd.Series.nunique, fill_value=0).reset_index()
        st.dataframe(pivot, use_container_width=True, hide_index=True)
        st.caption("Unique counts depend on consistent participant IDs. Training totals use the numeric enrolled/completed fields.")
    with tab3:
        st.subheader("Training and employment tracking")
        st.metric("Employment rate among recorded completions", f"{employment_rate:.1f}%")
        show_cols = ["date","centre","participant_id","gender","population_group","course","enrolled","completed","employed","employment_date","employer","project"]
        st.dataframe(filtered[show_cols].sort_values("date", ascending=False), use_container_width=True, hide_index=True)
        employed_rows = filtered[filtered["employed"] > 0]
        st.markdown("**Employment outcomes**")
        if not employed_rows.empty:
            st.dataframe(employed_rows[["participant_id","centre","course","employment_date","employer","population_group"]], use_container_width=True, hide_index=True)
        else:
            st.info("No employment outcomes recorded for the selected filters.")
    with tab4:
        st.subheader("Monthly and quarterly reports")
        months = sorted(filtered["month"].unique().tolist())
        quarters = sorted(filtered["quarter"].unique().tolist())
        col1,col2 = st.columns(2)
        with col1:
            selected_month = st.selectbox("Monthly report period", months, index=max(0,len(months)-1) if months else None)
        with col2:
            selected_quarter = st.selectbox("Quarterly report period", quarters, index=max(0,len(quarters)-1) if quarters else None)
        report_mode = st.radio("Report to export", ["Monthly", "Quarterly", "Filtered date range"], horizontal=True)
        if report_mode == "Monthly" and months:
            report_df = filtered[filtered["month"] == selected_month].copy()
            period_label = selected_month
        elif report_mode == "Quarterly" and quarters:
            report_df = filtered[filtered["quarter"] == selected_quarter].copy()
            period_label = selected_quarter
        else:
            report_df = filtered.copy()
            period_label = f"{start_date}_to_{end_date}"
        report_summary = pd.DataFrame([
            {"Indicator":"Unique beneficiaries", "Value":report_df.loc[report_df["participant_id"].ne(""),"participant_id"].nunique()},
            {"Indicator":"Enrolments", "Value":int(report_df["enrolled"].sum())},
            {"Indicator":"Training completed", "Value":int(report_df["completed"].sum())},
            {"Indicator":"Recorded employed", "Value":int(report_df["employed"].sum())},
            {"Indicator":"Completion rate (%)", "Value":round(report_df["completed"].sum()/report_df["enrolled"].sum()*100,1) if report_df["enrolled"].sum() else 0},
        ])
        st.markdown(f"**Selected period:** {period_label}")
        st.dataframe(report_summary, use_container_width=True, hide_index=True)
        st.markdown("**Centre breakdown**")
        centre_summary = report_df.groupby("centre", as_index=False).agg(Enrolments=("enrolled","sum"), Completed=("completed","sum"), Employed=("employed","sum"), Unique_Beneficiaries=("participant_id","nunique"))
        st.dataframe(centre_summary, use_container_width=True, hide_index=True)

        def excel_bytes():
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                report_summary.to_excel(writer, sheet_name="Summary", index=False)
                centre_summary.to_excel(writer, sheet_name="By Centre", index=False)
                report_df.drop(columns=["month","quarter"], errors="ignore").to_excel(writer, sheet_name="Records", index=False)
            return output.getvalue()

        def pdf_bytes():
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import cm
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            output = io.BytesIO()
            doc = SimpleDocTemplate(output, pagesize=landscape(A4), rightMargin=1.3*cm, leftMargin=1.3*cm, topMargin=1.3*cm, bottomMargin=1.3*cm)
            styles = getSampleStyleSheet()
            story = [Paragraph("Kakuma NGO / MEAL Report", styles["Title"]), Paragraph(f"Reporting period: {period_label}", styles["Heading2"]), Spacer(1, 0.3*cm)]
            story.append(Paragraph("Summary indicators", styles["Heading2"]))
            table_data = [list(report_summary.columns)] + report_summary.astype(str).values.tolist()
            t = Table(table_data, repeatRows=1)
            t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#23415A")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.4,colors.grey),("PADDING",(0,0),(-1,-1),6)]))
            story.append(t); story.append(Spacer(1,0.4*cm)); story.append(Paragraph("Results by centre", styles["Heading2"]))
            cdata = [list(centre_summary.columns)] + centre_summary.astype(str).values.tolist()
            ct = Table(cdata, repeatRows=1)
            ct.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#23415A")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.4,colors.grey),("PADDING",(0,0),(-1,-1),5)]))
            story.append(ct); story.append(Spacer(1,0.3*cm)); story.append(Paragraph(f"Records included: {len(report_df)}. Generated from the selected data source. Verify figures before external submission.", styles["BodyText"]))
            doc.build(story)
            return output.getvalue()

        d1,d2 = st.columns(2)
        with d1:
            st.download_button("Download Excel report", data=excel_bytes(), file_name=f"MEAL_Report_{period_label}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        with d2:
            try:
                st.download_button("Download PDF report", data=pdf_bytes(), file_name=f"MEAL_Report_{period_label}.pdf", mime="application/pdf", use_container_width=True)
            except Exception as e:
                st.error(f"PDF export could not be prepared: {e}")
        st.markdown("**Underlying records for this report**")
        st.dataframe(report_df.drop(columns=["month","quarter"], errors="ignore"), use_container_width=True, hide_index=True)

    with st.expander("Data quality checks"):
        dq1,dq2,dq3 = st.columns(3)
        dq1.metric("Rows with missing participant ID", int(filtered["participant_id"].eq("").sum()))
        dq2.metric("Duplicate participant IDs", int(filtered["participant_id"].duplicated().sum()))
        dq3.metric("Records with invalid date removed", int(raw.shape[0] - len(df)))
        st.caption("Duplicate IDs are flagged as a review prompt; a participant can legitimately have multiple training records. Confirm definitions before using these counts in donor reports.")

st.markdown("---")
st.caption("Prototype for internal reporting. Add authentication, role-based access, backups, and appropriate data-protection controls before storing identifiable or sensitive beneficiary information online.")

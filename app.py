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

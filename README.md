# Kakuma NGO / MEAL Reporting System

A Streamlit web application prototype for six centres: DBK, DB1, DB2, DB3, DB4 and Kalobeyei. It provides a dashboard, beneficiary statistics, training and employment tracking, monthly/quarterly summaries, PDF/Excel exports, and basic data-quality checks.

## 1. Install on Windows

1. Install Python 3.11 or newer from https://www.python.org/downloads/ . During installation, tick **Add python.exe to PATH**.
2. Extract this project ZIP to a folder such as `C:\Users\Admin\Documents\kakuma_meal_reporting`.
3. Open Command Prompt and change to that folder (adjust if you extracted it elsewhere):

   ```cmd
   cd "%USERPROFILE%\Documents\kakuma_meal_reporting"
   ```

4. Create and activate a virtual environment:

   ```cmd
   py -m venv .venv
   .venv\Scripts\activate
   ```

5. Install packages:

   ```cmd
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

6. Start the application:

   ```cmd
   python -m streamlit run app.py
   ```

7. Open the local URL shown in CMD, usually `http://localhost:8501`.

If `py` is not recognized but `python --version` works, replace `py` with `python` in the virtual-environment command.

## 2. Connect a Google Sheet (quick setup)

1. Create a Google Sheet with one header row and the columns listed below.
2. For a quick test only, set Share → General access → **Anyone with the link** → Viewer.
3. Copy the spreadsheet URL and paste it into the app's **Google Sheets URL** box in the sidebar. The app reads the first worksheet/tab (or the tab indicated by `gid`).
4. If you change the sheet, the app refreshes cached data after about five minutes; restart the app or change source to reload immediately.

**Privacy warning:** Do not make identifiable or sensitive beneficiary data public. For confidential programme data, use the private service-account setup below or upload an export locally. Never place a service-account key in source code or commit it to GitHub.

### Private Google Sheets (recommended for real programme data)

1. In Google Cloud Console, create/select a project and enable the **Google Sheets API**.
2. Create a service account and generate a JSON key. Keep this key private.
3. In the app project folder, create `.streamlit` and then a `secrets.toml` file inside it:

   ```text
   kakuma_meal_reporting\
     .streamlit\
       secrets.toml
   ```

4. Copy the JSON key fields into this TOML structure (replace the example values with the real values; preserve the private key newlines as `\n` if required):

   ```toml
   [gcp_service_account]
   type = "service_account"
   project_id = "your-project-id"
   private_key_id = "your-private-key-id"
   private_key = "-----BEGIN PRIVATE KEY-----\nYOUR_KEY_CONTENT\n-----END PRIVATE KEY-----\n"
   client_email = "your-service-account@your-project-id.iam.gserviceaccount.com"
   client_id = "your-client-id"
   token_uri = "https://oauth2.googleapis.com/token"
   ```

   Include any other fields required from the downloaded service-account JSON if present. Do not share this file publicly.
5. Share the Google Sheet with the service account's `client_email` as a Viewer. Paste the normal Google Sheets URL into the app. The app tries public CSV access first and then authenticated service-account access.
6. Add `.streamlit/secrets.toml` to `.gitignore` if you use Git.

## 3. Expected columns

Required column names (case-insensitive; spaces are converted to underscores):

- `date` — activity/record date in a format pandas can parse, e.g. `2026-01-31`
- `centre` — DBK, DB1, DB2, DB3, DB4 or Kalobeyei
- `participant_id` — unique, pseudonymized participant identifier where possible
- `gender` — e.g. Female, Male, Other, Not recorded
- `population_group` — e.g. Refugee, Host
- `course` — course/training area
- `enrolled` — numeric 1/0 per participant enrolment record
- `completed` — numeric 1/0 per record
- `employed` — numeric 1/0 for recorded employment outcome

Optional columns: `project`, `age`, `employment_date`, `employer`, `activity`, `indicator`, `target`, `achieved`, `notes`.

See `sample_data.csv` for a fictional example. Replace sample data before using any report for management or donor submission.

## 4. Reporting notes

- Monthly and quarterly periods are based on `date`.
- Beneficiary counts use distinct `participant_id`; blank IDs are excluded from unique counts.
- Enrolment, completion, and employment totals are sums of the numeric fields. Ensure your sheet has a consistent unit of analysis and uses 1/0 flags if you want participant-level totals.
- The application filters by date, centre, gender and population group.
- Excel exports include Summary, By Centre and Records worksheets. PDF exports include summary indicators and a centre breakdown.

## 5. Important limitations before deployment

This is a prototype, not a secured production information system. Before hosting online or entering real beneficiary records, add authentication, user roles, HTTPS, secure secrets, audit logs, backups, consent/retention rules, and access controls consistent with organizational policy and applicable data-protection requirements. Do not collect unnecessary sensitive personal information. Review all figures and definitions before sharing reports externally.

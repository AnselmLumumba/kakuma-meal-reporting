
import os
import re
import hmac
import hashlib
import secrets
from datetime import datetime

import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Kakuma MEAL Reporting System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

CENTRES = [
    "DBK - Kakuma Main Centre",
    "DB1 - Training Centre 1",
    "DB2 - Training Centre 2",
    "DB3 - Training Centre 3",
    "DB4 - Training Centre 4",
    "DB Kalobeyei - ICT & Business Centre",
    "HQ - Nairobi",
]

ROLES = ["M&E Officer", "Project Officer", "Principal", "Viewer"]

ph = PasswordHasher()


# =========================================================
# STYLING
# =========================================================

st.markdown(
    """
    <style>
    .stApp {
        background-color: #f5f7fb;
    }

    [data-testid="stSidebar"] {
        background-color: #102a43;
    }

    [data-testid="stSidebar"] * {
        color: #ffffff;
    }

    .hero {
        padding: 25px;
        border-radius: 15px;
        background: linear-gradient(120deg, #102a43, #176b87);
        color: white;
        margin-bottom: 22px;
    }

    .hero h1 {
        color: white;
        margin-bottom: 8px;
    }

    .hero p {
        color: #e7f5ff;
        margin-bottom: 0;
    }

    .auth-card {
        background: white;
        padding: 24px;
        border-radius: 14px;
        border: 1px solid #e2e8f0;
    }

    div[data-testid="stMetric"] {
        background-color: white;
        padding: 16px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
    }

    footer {
        visibility: hidden;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_database_url():
    """Read the PostgreSQL URL from Streamlit Secrets or environment."""

    try:
        database_url = st.secrets.get("DATABASE_URL", "")
    except Exception:
        database_url = ""

    return database_url or os.environ.get("DATABASE_URL", "")


def get_connection():
    """Open a PostgreSQL connection."""

    database_url = get_database_url()

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is missing. Configure it in Streamlit Secrets."
        )

    return psycopg2.connect(
        database_url,
        connect_timeout=10,
        sslmode="require",
    )


def initialize_database():
    """Create the application users table if it does not exist."""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS meal_users (
                    id BIGSERIAL PRIMARY KEY,
                    full_name VARCHAR(150) NOT NULL,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    email VARCHAR(254) NOT NULL UNIQUE,
                    centre VARCHAR(150) NOT NULL,
                    role VARCHAR(50) NOT NULL DEFAULT 'Viewer',
                    password_hash TEXT NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS meal_activity_log (
                    id BIGSERIAL PRIMARY KEY,
                    username VARCHAR(50),
                    action VARCHAR(100) NOT NULL,
                    details TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )


# =========================================================
# AUDIT LOG
# =========================================================

def log_activity(username, action, details=""):
    """Record important user actions."""

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO meal_activity_log
                    (username, action, details)
                    VALUES (%s, %s, %s);
                    """,
                    (username, action, details),
                )
    except Exception:
        # Do not expose database credentials or internal errors.
        pass


# =========================================================
# USER REGISTRATION
# =========================================================

def _signup_user(
    full_name: str,
    username: str,
    email: str,
    centre: str,
    password: str,
):
    """Create a user account with an Argon2 password hash."""

    full_name = full_name.strip()
    username = username.strip().lower()
    email = email.strip().lower()

    if not all([full_name, username, email, centre, password]):
        return False, "All fields are required."

    if len(full_name) > 150:
        return False, "Full name is too long."

    if not re.fullmatch(r"[a-z0-9_.-]{3,50}", username):
        return False, (
            "Username must be 3–50 characters and contain only "
            "letters, numbers, underscores, dots, or hyphens."
        )

    if len(email) > 254 or not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+", email
    ):
        return False, "Enter a valid email address."

    if centre not in CENTRES:
        return False, "Select a valid centre."

    if len(password) < 12:
        return False, "Password must be at least 12 characters."

    if len(password) > 128:
        return False, "Password must not exceed 128 characters."

    password_hash = ph.hash(password)

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO meal_users
                    (full_name, username, email, centre, role, password_hash)
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    (
                        full_name,
                        username,
                        email,
                        centre,
                        "Viewer",
                        password_hash,
                    ),
                )

        return True, "Account created successfully. You can now sign in."

    except psycopg2.errors.UniqueViolation:
        return False, "That username or email is already registered."

    except Exception:
        return False, (
            "Registration failed. Check your database configuration "
            "and try again."
        )


# =========================================================
# USER LOGIN
# =========================================================

def _authenticate_user(username: str, password: str):
    """Authenticate an active account."""

    username = username.strip().lower()

    if not username or not password:
        return None

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, full_name, username, email, centre,
                           role, password_hash, is_active
                    FROM meal_users
                    WHERE username = %s;
                    """,
                    (username,),
                )
                user = cur.fetchone()

        if not user or not user["is_active"]:
            return None

        try:
            ph.verify(user["password_hash"], password)
        except (VerifyMismatchError, InvalidHashError):
            return None

        if ph.check_needs_rehash(user["password_hash"]):
            new_hash = ph.hash(password)
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE meal_users
                        SET password_hash = %s
                        WHERE id = %s;
                        """,
                        (new_hash, user["id"]),
                    )

        user.pop("password_hash", None)
        return dict(user)

    except Exception:
        return None


# =========================================================
# SESSION STATE
# =========================================================

if "authenticated_user" not in st.session_state:
    st.session_state.authenticated_user = None

if "auth_page" not in st.session_state:
    st.session_state.auth_page = "Login"


def logout():
    """Clear the signed-in user's session."""

    user = st.session_state.get("authenticated_user")

    if user:
        log_activity(user["username"], "Logout")

    st.session_state.authenticated_user = None
    st.session_state.auth_page = "Login"


# =========================================================
# APPLICATION HEADER
# =========================================================

def render_header():
    st.markdown(
        """
        <div class="hero">
            <h1>📊 Kakuma MEAL Reporting System</h1>
            <p>
                Monitoring, Evaluation, Accountability and Learning
                | Don Bosco TVET Centres
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# LOGIN PAGE
# =========================================================

def render_login():
    render_header()

    left, right = st.columns([1.1, 1])

    with left:
        st.subheader("Welcome back")
        st.write(
            "Sign in to access programme monitoring, centre reports, "
            "beneficiary information and MEAL dashboards."
        )

        st.markdown("**System features**")
        st.markdown(
            """
            - Centre-level monitoring and reporting
            - Programme performance tracking
            - Data quality and accountability
            - Secure user accounts
            """
        )

    with right:
        with st.container(border=True):
            st.subheader("Sign in")

            with st.form("login_form"):
                username = st.text_input(
                    "Username",
                    placeholder="Enter your username",
                )
                password = st.text_input(
                    "Password",
                    type="password",
                    placeholder="Enter your password",
                )
                submitted = st.form_submit_button(
                    "Sign in",
                    use_container_width=True,
                    type="primary",
                )

            if submitted:
                user = _authenticate_user(username, password)

                if user:
                    st.session_state.authenticated_user = user
                    log_activity(user["username"], "Login")
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

            st.divider()
            st.write("Don't have an account?")
            if st.button("Create an account", use_container_width=True):
                st.session_state.auth_page = "Register"
                st.rerun()


# =========================================================
# REGISTRATION PAGE
# =========================================================

def render_registration():
    render_header()

    with st.container(border=True):
        st.subheader("Create your MEAL account")
        st.caption(
            "New accounts receive Viewer access by default. "
            "An administrator must grant additional permissions."
        )

        with st.form("registration_form"):
            full_name = st.text_input("Full name")
            username = st.text_input(
                "Username",
                help="3–50 letters, numbers, dots, underscores or hyphens.",
            )
            email = st.text_input("Work email")

            centre = st.selectbox(
                "Centre or office",
                options=CENTRES,
                index=None,
                placeholder="Select your centre",
            )

            password = st.text_input(
                "Password",
                type="password",
                help="Use at least 12 characters.",
            )
            confirm_password = st.text_input(
                "Confirm password",
                type="password",
            )

            submitted = st.form_submit_button(
                "Register",
                use_container_width=True,
                type="primary",
            )

        if submitted:
            if password != confirm_password:
                st.error("The passwords do not match.")
            elif centre is None:
                st.error("Please select your centre.")
            else:
                success, message = _signup_user(
                    full_name,
                    username,
                    email,
                    centre,
                    password,
                )

                if success:
                    st.success(message)
                    st.session_state.auth_page = "Login"
                else:
                    st.error(message)

        if st.button("Back to login"):
            st.session_state.auth_page = "Login"
            st.rerun()


# =========================================================
# MAIN DASHBOARD
# =========================================================

def render_dashboard(user):
    with st.sidebar:
        st.title("📊 Kakuma MEAL")
        st.caption("Monitoring & Reporting")

        st.divider()

        st.write(f"**{user['full_name']}**")
        st.write(f"Role: {user['role']}")
        st.write(f"Centre: {user['centre']}")

        st.divider()

        page = st.radio(
            "Navigation",
            [
                "Overview",
                "My Profile",
                "System Information",
            ],
        )

        st.divider()

        if st.button("Sign out", use_container_width=True):
            logout()
            st.rerun()

    render_header()

    if page == "Overview":
        st.subheader("Programme overview")

        st.write(
            f"Welcome, {user['full_name']}. "
            "Your account is connected to the MEAL reporting system."
        )

        col1, col2, col3 = st.columns(3)

        col1.metric("Assigned Centre", user["centre"])
        col2.metric("Access Level", user["role"])
        col3.metric(
            "Account Status",
            "Active",
        )

        st.info(
            "This is the secure application shell. Connect your existing "
            "MEAL indicators, beneficiary records, attendance, training, "
            "livelihoods and reporting modules to display actual data."
        )

        st.subheader("Reporting modules")

        module_cols = st.columns(3)

        modules = [
            ("📋", "Programme Monitoring"),
            ("👥", "Beneficiary Tracking"),
            ("🎓", "TVET & Training"),
            ("💼", "Livelihoods & Employment"),
            ("📈", "Performance Indicators"),
            ("🗂️", "Reports & Data Quality"),
        ]

        for index, (emoji, name) in enumerate(modules):
            with module_cols[index % 3]:
                with st.container(border=True):
                    st.markdown(f"### {emoji}")
                    st.write(name)
                    st.caption("Connect your existing reporting module.")

    elif page == "My Profile":
        st.subheader("My profile")

        st.write(f"**Full name:** {user['full_name']}")
        st.write(f"**Username:** {user['username']}")
        st.write(f"**Email:** {user['email']}")
        st.write(f"**Centre:** {user['centre']}")
        st.write(f"**Role:** {user['role']}")
        st.write(f"**User ID:** {user['id']}")

    elif page == "System Information":
        st.subheader("System information")

        st.write("**Application:** Kakuma MEAL Reporting System")
        st.write("**Database:** PostgreSQL")
        st.write("**Framework:** Streamlit")
        st.write("**Authentication:** Argon2 password hashing")
        st.write(f"**Signed-in user:** {user['username']}")

        st.warning(
            "User registration is open in this starter version. "
            "For an organizational deployment, restrict account creation "
            "and implement administrator-managed roles before going live."
        )


# =========================================================
# APPLICATION ENTRY POINT
# =========================================================

def main():
    try:
        initialize_database()
    except Exception:
        st.error(
            "Unable to connect to PostgreSQL. Check DATABASE_URL, "
            "database availability, SSL settings and network permissions."
        )
        st.stop()

    user = st.session_state.authenticated_user

    if user:
        render_dashboard(user)
    elif st.session_state.auth_page == "Register":
        render_registration()
    else:
        render_login()


if __name__ == "__main__":
    main()

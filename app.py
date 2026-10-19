import io
import os
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Kakuma MEAL Reporting System", page_icon="📊", layout="wide")

CENTRES = ["DBK", "DB1", "DB2", "DB3", "DB4", "Kalobeyei"]

# ---- Authentication and account approval (PostgreSQL) ----
# Configure DATABASE_URL, ADMIN_EMAIL, and ADMIN_PASSWORD in Render's
# Environment settings before deploying this version.
import hashlib
import hmac
import secrets

def _setting(name: str, default: str = "") -> str:
    """Read a setting from host environment variables or Streamlit Secrets."""
    value = os.getenv(name)
    if value:
        return value.strip()
    try:
        return str(st.secrets.get(name, default)).strip()
    except Exception:
        return default

DATABASE_URL = _setting("DATABASE_URL")
ADMIN_EMAIL = _setting("ADMIN_EMAIL").lower()
ADMIN_PASSWORD = _setting("ADMIN_PASSWORD")

def _db_connection():
    import psycopg
    return psycopg.connect(DATABASE_URL, connect_timeout=10)

def _hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 600_000)
    return f"{salt}${digest.hex()}"

def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split("$", 1)
        actual = _hash_password(password, salt).split("$", 1)[1]
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False

def _init_auth_db():
    with _db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS meal_users (
                    id BIGSERIAL PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    username TEXT UNIQUE,
                    centre TEXT NOT NULL DEFAULT 'All Centres',
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'viewer',
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Migrate databases created by earlier versions of the app.
            cur.execute("ALTER TABLE meal_users ADD COLUMN IF NOT EXISTS username TEXT")
            cur.execute("ALTER TABLE meal_users ADD COLUMN IF NOT EXISTS centre TEXT NOT NULL DEFAULT 'All Centres'")
            cur.execute("UPDATE meal_users SET username = 'user_' || id::text WHERE username IS NULL OR username = ''")
            # Keep legacy non-admin accounts from inheriting broad, all-centres access.
            cur.execute("UPDATE meal_users SET centre = 'DBK' WHERE role <> 'admin' AND centre = 'All Centres'")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS meal_users_username_unique ON meal_users (LOWER(username))")
            # Create the first administrator only if the configured email is not registered.
            if ADMIN_EMAIL and ADMIN_PASSWORD:
                cur.execute("SELECT id FROM meal_users WHERE email = %s", (ADMIN_EMAIL,))
                if cur.fetchone() is None:
                    admin_username = (ADMIN_EMAIL.split('@')[0] or 'admin')[:60]
                    cur.execute(
                        """INSERT INTO meal_users (full_name, email, username, centre, password_hash, role, status)
                           VALUES (%s, %s, %s, 'All Centres', %s, 'admin', 'approved')""",
                        ("System Administrator", ADMIN_EMAIL, admin_username, _hash_password(ADMIN_PASSWORD))
                    )

def _find_user(identifier: str):
    with _db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, full_name, email, password_hash, role, status, username, centre
                   FROM meal_users WHERE LOWER(email) = LOWER(%s) OR LOWER(username) = LOWER(%s)
                   LIMIT 1""",
                (identifier.strip(), identifier.strip())
            )
            return cur.fetchone()

def _signup_user(full_name: str, username: str, email: str, centre: str, password: str):

"""
Password hashing and session-token management for the login portal.
Standard-library only: hashlib.pbkdf2_hmac for password hashing (no
bcrypt dependency), secrets for unguessable tokens.

Sessions are stored in the `sessions` table (see database.py) so a
server restart does not silently log everyone out.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from database import now_iso

SESSION_TTL_DAYS = 30
PBKDF2_ITERATIONS = 100_000


def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS
    )
    return digest.hex(), salt


def verify_password(password, salt, expected_hash):
    digest, _ = hash_password(password, salt)
    return hmac.compare_digest(digest, expected_hash)


def create_session(conn, user_id):
    token = secrets.token_hex(32)
    expires_at = (datetime.now() + timedelta(days=SESSION_TTL_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, user_id, now_iso(), expires_at),
    )
    conn.commit()
    return token


def delete_session(conn, token):
    if token:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()


def get_user_id_from_token(conn, token):
    if not token:
        return None
    row = conn.execute(
        "SELECT user_id, expires_at FROM sessions WHERE token = ?", (token,)
    ).fetchone()
    if row is None:
        return None
    if row["expires_at"] < now_iso():
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        return None
    return row["user_id"]


def extract_token(authorization_header):
    if not authorization_header:
        return None
    parts = authorization_header.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return authorization_header.strip()

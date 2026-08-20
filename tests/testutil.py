"""
Shared test scaffolding: points the app at a throwaway SQLite database in
a temp directory (never the real database/elderly_care.db) and exposes a
`dispatch()` helper that routes a (method, path) through the exact same
ROUTES table server.py uses, so tests exercise the real routing +
handler code without needing to spin up an actual HTTP server.

The app is multi-tenant and auth-gated, so most tests need a logged-in
user first - use `register_user()` to create one and get back a token,
then pass that token to `dispatch()`.
"""

import itertools
import os
import sys
import tempfile
from datetime import datetime
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

_tmp_dir = tempfile.mkdtemp(prefix="elderly_care_test_")
config.DATABASE_DIR = _tmp_dir
config.DATABASE_PATH = os.path.join(_tmp_dir, "test.db")

# Tests must be hermetic: never depend on network access or whatever real
# credentials a developer happens to have in their local_settings.py.
# sms.py / email_service.py read these at call time, so forcing them empty
# here makes every send in the test run a fast, offline no-op.
config.FAST2SMS_API_KEY = ""
config.SMTP_USERNAME = ""
config.SMTP_PASSWORD = ""
config.SENDER_EMAIL = ""

import database  # noqa: E402
from api.router import ROUTES, ApiError  # noqa: E402
from api import (  # noqa: E402,F401
    auth_api,
    caregiver_api,
    medication_api,
    schedule_api,
    notification_api,
    camera_api,
    device_api,
    robot_api,
    sensor_api,
)

_username_counter = itertools.count(1)


def reset_db():
    if os.path.exists(config.DATABASE_PATH):
        os.remove(config.DATABASE_PATH)
    conn = database.get_connection()
    try:
        database.init_schema(conn)
        # No demo account in tests - every test that needs a user calls
        # register_user() explicitly for a clean, isolated account.
    finally:
        conn.close()


def current_hhmm():
    """A schedule time of 'right now' so a freshly created record is
    PENDING (not immediately swept to MISSED by the grace-period check)."""
    return datetime.now().strftime("%H:%M")


def dispatch(method, path, body=None, token=None):
    """Mirrors server.py's _dispatch_api: resolves the role + effective
    patient id from the token, enforces the route's role allowlist and
    scope, and calls the handler exactly like the real server would."""
    import auth as auth_module

    parsed = urlparse(path)
    query = parse_qs(parsed.query)
    query["_token"] = [token] if token else []
    for route_method, pattern, handler, public, allowed_roles, scope in ROUTES:
        if route_method != method:
            continue
        match = pattern.match(parsed.path)
        if not match:
            continue
        conn = database.get_connection()
        try:
            raw_user_id = auth_module.get_user_id_from_token(conn, token) if token else None
            if not public and raw_user_id is None:
                return 401, {"error": "Authentication required"}

            actor_role, patient_id = (None, None)
            if raw_user_id is not None:
                actor_role, patient_id = database.resolve_actor(conn, raw_user_id)

            if not public and actor_role not in allowed_roles:
                return 403, {"error": "Your account role cannot perform this action"}

            if not public and scope == "patient" and actor_role != "PATIENT" and patient_id is None:
                return 409, {"error": "Your account is not linked to a patient yet."}

            pass_id = raw_user_id if (public or scope == "self") else patient_id

            try:
                return handler(conn, match, query, body or {}, pass_id)
            except ApiError as exc:
                return exc.status_code, {"error": exc.message}
        finally:
            conn.close()
    return 404, {"error": "Not found"}


def register_user(caregiver_email="caregiver@example.com", username=None, password="testpass123"):
    """Registers a fresh PATIENT account and returns (token, user_dict)."""
    if username is None:
        username = f"testuser{next(_username_counter)}"
    status, res = dispatch(
        "POST",
        "/api/auth/register",
        {
            "username": username,
            "password": password,
            "role": "PATIENT",
            "caregiver_name": "Test Caregiver",
            "caregiver_email": caregiver_email,
        },
    )
    assert status == 201, f"register_user failed: {status} {res}"
    return res["token"], res["user"]


def register_linked_user(patient_token, role, username=None, password="testpass123"):
    """Registers a CARETAKER/FAMILY/DOCTOR account linked to the patient
    behind patient_token (fetches their invite code first). Returns
    (token, user_dict)."""
    if username is None:
        username = f"testuser{next(_username_counter)}"
    _, me_res = dispatch("GET", "/api/auth/me", token=patient_token)
    invite_code = me_res["user"]["invite_code"]
    status, res = dispatch(
        "POST",
        "/api/auth/register",
        {"username": username, "password": password, "role": role, "invite_code": invite_code},
    )
    assert status == 201, f"register_linked_user failed: {status} {res}"
    return res["token"], res["user"]

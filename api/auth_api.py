"""
Login portal: register/login/logout/me, plus the Patient <-> Caretaker /
Family Member / Doctor linking flow.

A PATIENT account owns the actual data (medicines, schedules, cameras,
devices - see database.resolve_actor). A CARETAKER/FAMILY/DOCTOR account
owns nothing itself; it links to exactly one patient via an invite code
the patient generates here, and every other API module then operates on
that linked patient's data according to the role's permissions (enforced
per-route in server.py via the `roles=` allowlist on each @route).

Every route in this module uses scope="self" - it always acts on the
calling account's own row, never on a linked patient's data.
"""

import re

import auth
import database
from api.router import route, ApiError
from database import now_iso, provision_new_user_defaults

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{3,30}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _user_to_dict(row):
    return {
        "id": row["id"],
        "username": row["username"],
        "role": row["role"],
        "caregiver_name": row["caregiver_name"],
        "caregiver_email": row["caregiver_email"],
        "invite_code": row["invite_code"],
        "linked_patient_id": row["linked_patient_id"],
        "setup_completed": bool(row["setup_completed"]),
        "created_at": row["created_at"],
    }


@route("POST", r"^/api/auth/register$", public=True, scope="self")
def register(conn, match, query, body, user_id):
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    role = (body.get("role") or "PATIENT").strip().upper()

    if not USERNAME_RE.match(username):
        raise ApiError(400, "Username must be 3-30 characters (letters, numbers, . _ -)")
    if len(password) < 6:
        raise ApiError(400, "Password must be at least 6 characters")
    if role not in database.ROLES:
        raise ApiError(400, f"'role' must be one of {database.ROLES}")

    existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing is not None:
        raise ApiError(409, "That username is already taken")

    caregiver_name = None
    caregiver_email = None
    linked_patient_id = None
    setup_completed = 0

    if role == "PATIENT":
        caregiver_name = (body.get("caregiver_name") or "").strip()
        caregiver_email = (body.get("caregiver_email") or "").strip()
        if not EMAIL_RE.match(caregiver_email):
            raise ApiError(400, "A valid caregiver/family member's email address is required")
    else:
        invite_code = (body.get("invite_code") or "").strip().upper()
        if not invite_code:
            raise ApiError(400, "An invite code from the patient's account is required")
        patient = conn.execute(
            "SELECT id FROM users WHERE invite_code = ? AND role = 'PATIENT'", (invite_code,)
        ).fetchone()
        if patient is None:
            raise ApiError(400, "Invalid invite code")
        linked_patient_id = patient["id"]
        setup_completed = 1  # no onboarding wizard for linked accounts

    password_hash, salt = auth.hash_password(password)
    ts = now_iso()
    cur = conn.execute(
        """INSERT INTO users
           (username, password_hash, password_salt, role, caregiver_name, caregiver_email,
            linked_patient_id, setup_completed, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (username, password_hash, salt, role, caregiver_name, caregiver_email,
         linked_patient_id, setup_completed, ts),
    )
    conn.commit()
    new_user_id = cur.lastrowid

    if role == "PATIENT":
        provision_new_user_defaults(conn, new_user_id)
        # Seed the caregiver/family recipients list with this first
        # contact so low-stock/taken/missed emails work immediately -
        # further recipients can be added in Settings via /api/caregivers.
        conn.execute(
            """INSERT INTO caregivers (user_id, name, email, active, created_at, updated_at)
               VALUES (?, ?, ?, 1, ?, ?)""",
            (new_user_id, caregiver_name or "Caregiver", caregiver_email, ts, ts),
        )
        conn.commit()

    token = auth.create_session(conn, new_user_id)
    row = conn.execute("SELECT * FROM users WHERE id = ?", (new_user_id,)).fetchone()
    return 201, {"token": token, "user": _user_to_dict(row)}


@route("POST", r"^/api/auth/login$", public=True, scope="self")
def login(conn, match, query, body, user_id):
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""

    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if row is None or not auth.verify_password(password, row["password_salt"], row["password_hash"]):
        raise ApiError(401, "Invalid username or password")

    token = auth.create_session(conn, row["id"])
    return 200, {"token": token, "user": _user_to_dict(row)}


@route("POST", r"^/api/auth/logout$", scope="self")
def logout(conn, match, query, body, user_id):
    token = (query.get("_token") or [None])[0]
    auth.delete_session(conn, token)
    return 200, {"success": True}


@route("GET", r"^/api/auth/me$", scope="self")
def me(conn, match, query, body, user_id):
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise ApiError(401, "Authentication required")

    # Convenience: a Patient account always has a working invite code to
    # show in Settings, generated lazily on first fetch rather than
    # forcing an extra click before it exists.
    if row["role"] == "PATIENT" and not row["invite_code"]:
        code = database.generate_invite_code(conn)
        conn.execute("UPDATE users SET invite_code = ? WHERE id = ?", (code, user_id))
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    return 200, {"user": _user_to_dict(row)}


@route("PUT", r"^/api/auth/me$", scope="self")
def update_me(conn, match, query, body, user_id):
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise ApiError(401, "Authentication required")

    caregiver_name = row["caregiver_name"]
    caregiver_email = row["caregiver_email"]
    setup_completed = row["setup_completed"]

    if "caregiver_name" in body:
        caregiver_name = (body.get("caregiver_name") or "").strip()
    if "caregiver_email" in body:
        caregiver_email = (body.get("caregiver_email") or "").strip()
        if not EMAIL_RE.match(caregiver_email):
            raise ApiError(400, "A valid caregiver/family member's email address is required")
    if "setup_completed" in body:
        setup_completed = 1 if body.get("setup_completed") else 0

    conn.execute(
        "UPDATE users SET caregiver_name = ?, caregiver_email = ?, setup_completed = ? WHERE id = ?",
        (caregiver_name, caregiver_email, setup_completed, user_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return 200, {"user": _user_to_dict(row)}


@route("POST", r"^/api/auth/invite-code/regenerate$", roles=["PATIENT"], scope="self")
def regenerate_invite_code(conn, match, query, body, user_id):
    code = database.generate_invite_code(conn)
    conn.execute("UPDATE users SET invite_code = ? WHERE id = ?", (code, user_id))
    conn.commit()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return 200, {"user": _user_to_dict(row)}


@route("GET", r"^/api/auth/linked-accounts$", roles=["PATIENT"], scope="self")
def linked_accounts(conn, match, query, body, user_id):
    rows = conn.execute(
        "SELECT id, username, role, created_at FROM users WHERE linked_patient_id = ? ORDER BY role, username",
        (user_id,),
    ).fetchall()
    return 200, {
        "accounts": [
            {"id": r["id"], "username": r["username"], "role": r["role"], "created_at": r["created_at"]}
            for r in rows
        ]
    }


@route("POST", r"^/api/auth/linked-accounts/(\d+)/revoke$", roles=["PATIENT"], scope="self")
def revoke_linked_account(conn, match, query, body, user_id):
    account_id = int(match.group(1))
    row = conn.execute(
        "SELECT id FROM users WHERE id = ? AND linked_patient_id = ?", (account_id, user_id)
    ).fetchone()
    if row is None:
        raise ApiError(404, "Linked account not found")
    conn.execute("UPDATE users SET linked_patient_id = NULL WHERE id = ?", (account_id,))
    # Also kill any active sessions for that account so revocation takes
    # effect immediately rather than at next token expiry.
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (account_id,))
    conn.commit()
    return 200, {"success": True}

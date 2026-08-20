"""
Caregiver / family member recipient list. A Patient can configure any
number of named recipients, each with an email address and an
active/inactive flag - only ACTIVE recipients ever receive an email (see
database.create_notification). Managing this list is Patient-only, same
as the invite code and other account-level settings.
"""

import re

from api.router import route, ApiError
from database import now_iso

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _caregiver_to_dict(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "active": bool(row["active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _get_owned_caregiver(conn, caregiver_id, user_id):
    row = conn.execute(
        "SELECT * FROM caregivers WHERE id = ? AND user_id = ?", (caregiver_id, user_id)
    ).fetchone()
    if row is None:
        raise ApiError(404, "Caregiver not found")
    return row


@route("GET", r"^/api/caregivers$", roles=["PATIENT"])
def list_caregivers(conn, match, query, body, user_id):
    rows = conn.execute(
        "SELECT * FROM caregivers WHERE user_id = ? ORDER BY created_at", (user_id,)
    ).fetchall()
    return 200, {"caregivers": [_caregiver_to_dict(r) for r in rows]}


@route("POST", r"^/api/caregivers$", roles=["PATIENT"])
def create_caregiver(conn, match, query, body, user_id):
    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip()
    if not name:
        raise ApiError(400, "'name' is required")
    if not EMAIL_RE.match(email):
        raise ApiError(400, "A valid email address is required")
    active = 1 if body.get("active", True) else 0

    ts = now_iso()
    cur = conn.execute(
        """INSERT INTO caregivers (user_id, name, email, active, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, name, email, active, ts, ts),
    )
    conn.commit()
    row = _get_owned_caregiver(conn, cur.lastrowid, user_id)
    return 201, {"caregiver": _caregiver_to_dict(row)}


@route("PUT", r"^/api/caregivers/(\d+)$", roles=["PATIENT"])
def update_caregiver(conn, match, query, body, user_id):
    caregiver_id = int(match.group(1))
    row = _get_owned_caregiver(conn, caregiver_id, user_id)

    name = row["name"]
    email = row["email"]
    active = row["active"]

    if "name" in body:
        name = (body.get("name") or "").strip()
        if not name:
            raise ApiError(400, "'name' cannot be empty")
    if "email" in body:
        email = (body.get("email") or "").strip()
        if not EMAIL_RE.match(email):
            raise ApiError(400, "A valid email address is required")
    if "active" in body:
        active = 1 if body.get("active") else 0

    conn.execute(
        "UPDATE caregivers SET name = ?, email = ?, active = ?, updated_at = ? WHERE id = ?",
        (name, email, active, now_iso(), caregiver_id),
    )
    conn.commit()
    row = _get_owned_caregiver(conn, caregiver_id, user_id)
    return 200, {"caregiver": _caregiver_to_dict(row)}


@route("DELETE", r"^/api/caregivers/(\d+)$", roles=["PATIENT"])
def delete_caregiver(conn, match, query, body, user_id):
    caregiver_id = int(match.group(1))
    _get_owned_caregiver(conn, caregiver_id, user_id)
    conn.execute("DELETE FROM caregivers WHERE id = ?", (caregiver_id,))
    conn.commit()
    return 200, {"success": True}

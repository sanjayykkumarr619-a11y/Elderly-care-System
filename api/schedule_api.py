"""
Medication schedule CRUD. A schedule is "medicine X at time T, dosage D,
active or not"; medication_records (the per-day taken/missed instances)
are generated from active schedules by medication_api.ensure_today_records.

Schedules don't carry their own user_id column - ownership is always
checked by joining through the medicine they belong to (which does).
"""

import re
from datetime import date

from api.router import route, ApiError
from database import now_iso

TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
# Patients and linked Family Members can create/edit/delete schedules.
WRITE_ROLES = ["PATIENT", "FAMILY"]


def _schedule_to_dict(row):
    return {
        "id": row["id"],
        "medicine_id": row["medicine_id"],
        "medicine_name": row["medicine_name"] if "medicine_name" in row.keys() else None,
        "scheduled_time": row["scheduled_time"],
        "dosage": row["dosage"],
        "active": bool(row["active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


_SCHEDULE_SELECT = """
    SELECT s.*, m.name AS medicine_name
    FROM medication_schedules s
    JOIN medicines m ON m.id = s.medicine_id
"""


def _get_owned_schedule(conn, schedule_id, user_id):
    row = conn.execute(
        _SCHEDULE_SELECT + " WHERE s.id = ? AND m.user_id = ?", (schedule_id, user_id)
    ).fetchone()
    if row is None:
        raise ApiError(404, "Schedule not found")
    return row


@route("GET", r"^/api/schedules$")
def list_schedules(conn, match, query, body, user_id):
    sql = _SCHEDULE_SELECT + " WHERE m.user_id = ?"
    params = [user_id]
    if query.get("medicine_id"):
        sql += " AND s.medicine_id = ?"
        params.append(int(query["medicine_id"][0]))
    sql += " ORDER BY s.scheduled_time"
    rows = conn.execute(sql, params).fetchall()
    return 200, {"schedules": [_schedule_to_dict(r) for r in rows]}


@route("POST", r"^/api/schedules$", roles=WRITE_ROLES)
def create_schedule(conn, match, query, body, user_id):
    medicine_id = body.get("medicine_id")
    if medicine_id is None:
        raise ApiError(400, "'medicine_id' is required")
    medicine = conn.execute(
        "SELECT * FROM medicines WHERE id = ? AND user_id = ?", (medicine_id, user_id)
    ).fetchone()
    if medicine is None:
        raise ApiError(404, "Medicine not found")

    scheduled_time = (body.get("scheduled_time") or "").strip()
    if not TIME_RE.match(scheduled_time):
        raise ApiError(400, "'scheduled_time' must be in HH:MM 24-hour format")

    try:
        dosage = float(body.get("dosage"))
    except (TypeError, ValueError):
        raise ApiError(400, "'dosage' must be a positive number")
    if dosage <= 0:
        raise ApiError(400, "'dosage' must be a positive number")

    active = 1 if body.get("active", True) else 0
    ts = now_iso()
    cur = conn.execute(
        """INSERT INTO medication_schedules
           (medicine_id, scheduled_time, dosage, active, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (medicine_id, scheduled_time, dosage, active, ts, ts),
    )
    conn.commit()
    row = _get_owned_schedule(conn, cur.lastrowid, user_id)
    return 201, {"schedule": _schedule_to_dict(row)}


def _retract_today_pending_record_if_disabled(conn, schedule_id, active):
    """Disabling a schedule must retract its still-pending dose for today
    (created earlier by medication_api.ensure_today_records) so it stops
    appearing as upcoming and stops alarming. Only ever deletes a
    still-PENDING row for *today* - TAKEN/MISSED history is untouched.
    Re-enabling later the same day naturally regenerates a fresh PENDING
    record the next time ensure_today_records runs, since none exists."""
    if active:
        return
    today = date.today().isoformat()
    conn.execute(
        "DELETE FROM medication_records WHERE schedule_id = ? AND scheduled_date = ? AND status = 'PENDING'",
        (schedule_id, today),
    )


@route("PUT", r"^/api/schedules/(\d+)$", roles=WRITE_ROLES)
def update_schedule(conn, match, query, body, user_id):
    """Only the active flag (Enable/Disable) can be changed here - time,
    dosage, and medicine are fixed once a schedule is created. Delete the
    schedule and add a new one to change those instead."""
    schedule_id = int(match.group(1))
    _get_owned_schedule(conn, schedule_id, user_id)

    if "active" not in body or any(f in body for f in ("medicine_id", "scheduled_time", "dosage")):
        raise ApiError(
            400,
            "Only 'active' can be updated here - delete this schedule and add a new one to "
            "change its medicine, time, or dosage.",
        )

    active = 1 if body.get("active") else 0
    conn.execute(
        "UPDATE medication_schedules SET active = ?, updated_at = ? WHERE id = ?",
        (active, now_iso(), schedule_id),
    )
    _retract_today_pending_record_if_disabled(conn, schedule_id, active)
    conn.commit()
    row = _get_owned_schedule(conn, schedule_id, user_id)
    return 200, {"schedule": _schedule_to_dict(row)}


@route("DELETE", r"^/api/schedules/(\d+)$", roles=WRITE_ROLES)
def delete_schedule(conn, match, query, body, user_id):
    schedule_id = int(match.group(1))
    _get_owned_schedule(conn, schedule_id, user_id)
    conn.execute("DELETE FROM medication_schedules WHERE id = ?", (schedule_id,))
    conn.commit()
    return 200, {"success": True}

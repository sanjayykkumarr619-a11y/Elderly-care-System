"""
Medicines, stock, and the core taken/missed medication-record logic.

This is the most important module in the prototype. The rules enforced
here (in order of importance):

  1. Stock only ever decreases when a dose is confirmed TAKEN. A MISSED
     dose never touches stock, because the system cannot know whether the
     patient actually consumed it outside the app.
  2. A medication record can only transition out of PENDING once. Taken
     and missed are both terminal states, which is what makes duplicate
     "taken" clicks and post-hoc "un-missing" a record impossible.
  3. Stock can never go negative, and confirming a dose the current stock
     can't cover is rejected rather than silently allowed.

Every medicine/schedule/record belongs to exactly one user account
(multi-tenant); every query here is scoped to the authenticated
user_id so one account can never see or affect another's data.

All of this is enforced here on the backend; the frontend's numbers are
never trusted.
"""

import config
from datetime import datetime, timedelta, date

from api.router import route, ApiError
from database import now_iso, create_notification

# Patients and linked Family Members can manage the medicine list. Stock
# adjustments and dose confirmation remain Patient-only operations.
MEDICINE_WRITE_ROLES = ["PATIENT", "FAMILY"]
STOCK_WRITE_ROLES = ["PATIENT"]


def _parse_body_number(body, key, allow_zero=False, required=True):
    if key not in body or body[key] is None:
        if required:
            raise ApiError(400, f"'{key}' is required")
        return None
    try:
        value = float(body[key])
    except (TypeError, ValueError):
        raise ApiError(400, f"'{key}' must be a number")
    if value < 0 or (value == 0 and not allow_zero):
        raise ApiError(400, f"'{key}' must be a positive number")
    return value


def _get_medicine_or_404(conn, medicine_id, user_id):
    row = conn.execute(
        "SELECT * FROM medicines WHERE id = ? AND user_id = ?", (medicine_id, user_id)
    ).fetchone()
    if row is None:
        raise ApiError(404, "Medicine not found")
    return row


def _medicine_to_dict(row):
    status = "LOW_STOCK" if row["current_stock"] <= row["low_stock_threshold"] else "NORMAL"
    return {
        "id": row["id"],
        "name": row["name"],
        "initial_stock": row["initial_stock"],
        "current_stock": row["current_stock"],
        "low_stock_threshold": row["low_stock_threshold"],
        "stock_status": status,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _check_low_stock(conn, user_id, medicine_id):
    """Call after ANY operation that changes a medicine's current_stock
    (taken, refill/add-stock, manual stock adjustment) - never after a
    missed dose, which never touches stock. Fires the LOW_STOCK dashboard
    notification + caregiver emails exactly once per low-stock "episode":
    medicines.low_stock_alerted tracks whether the alert has already gone
    out, so a page refresh or repeated GETs never re-send it. Once stock
    rises back above the threshold (e.g. a refill), the flag resets so a
    future dip alerts again.
    """
    medicine = conn.execute("SELECT * FROM medicines WHERE id = ?", (medicine_id,)).fetchone()
    if medicine is None:
        return

    is_low = medicine["current_stock"] <= medicine["low_stock_threshold"]
    already_alerted = bool(medicine["low_stock_alerted"])

    if is_low and not already_alerted:
        stock_display = f"{medicine['current_stock']:g}"
        threshold_display = f"{medicine['low_stock_threshold']:g}"
        ts = now_iso()

        dashboard_message = (
            f"{medicine['name']} has reached the minimum stock threshold.\n"
            f"Only {stock_display} unit(s) remain. Please refill the medicine."
        )
        email_body = (
            "Low Medicine Stock Alert\n\n"
            f"Medicine: {medicine['name']}\n"
            f"Remaining Stock: {stock_display} unit(s)\n"
            f"Minimum Threshold: {threshold_display} unit(s)\n\n"
            "The medicine has reached the configured minimum stock level.\n\n"
            "Please refill the medicine.\n\n"
            f"Time: {ts}\n\n"
            "This is an automated notification from the Elderly Care Medication\n"
            "Tracking System."
        )

        create_notification(
            conn,
            user_id,
            ntype="LOW_STOCK",
            title="LOW MEDICINE STOCK",
            message=dashboard_message,
            related_medicine_id=medicine_id,
            recipient_type="BOTH",
            email_subject=f"LOW MEDICINE STOCK ALERT - {medicine['name']}",
            email_body=email_body,
        )
        conn.execute("UPDATE medicines SET low_stock_alerted = 1 WHERE id = ?", (medicine_id,))
        conn.commit()
    elif not is_low and already_alerted:
        conn.execute("UPDATE medicines SET low_stock_alerted = 0 WHERE id = ?", (medicine_id,))
        conn.commit()


def _record_to_dict(row):
    return {
        "id": row["id"],
        "medicine_id": row["medicine_id"],
        "medicine_name": row["medicine_name"] if "medicine_name" in row.keys() else None,
        "schedule_id": row["schedule_id"],
        "scheduled_date": row["scheduled_date"],
        "scheduled_time": row["scheduled_time"],
        "dosage": row["dosage"],
        "status": row["status"],
        "confirmed_at": row["confirmed_at"],
        "stock_after": row["stock_after"],
        "created_at": row["created_at"],
    }


# ---------------------------------------------------------------------------
# Record generation / missed-detection sweep
# Shared with schedule_api.py (today's view) so both always see fresh state.
# ---------------------------------------------------------------------------

def ensure_today_records(conn, user_id):
    today = date.today().isoformat()
    schedules = conn.execute(
        """SELECT s.* FROM medication_schedules s
           JOIN medicines m ON m.id = s.medicine_id
           WHERE s.active = 1 AND m.user_id = ?""",
        (user_id,),
    ).fetchall()
    for s in schedules:
        exists = conn.execute(
            "SELECT id FROM medication_records WHERE schedule_id = ? AND scheduled_date = ?",
            (s["id"], today),
        ).fetchone()
        if exists is None:
            conn.execute(
                """INSERT INTO medication_records
                   (medicine_id, schedule_id, scheduled_date, scheduled_time, dosage, status, created_at)
                   VALUES (?, ?, ?, ?, ?, 'PENDING', ?)""",
                (s["medicine_id"], s["id"], today, s["scheduled_time"], s["dosage"], now_iso()),
            )
    conn.commit()


def sweep_missed_records(conn, user_id):
    """Any PENDING record whose scheduled time + grace period has passed
    (even across a server restart) becomes MISSED. Stock is untouched."""
    now = datetime.now()
    pending = conn.execute(
        """SELECT mr.* FROM medication_records mr
           JOIN medicines m ON m.id = mr.medicine_id
           WHERE mr.status = 'PENDING' AND m.user_id = ?""",
        (user_id,),
    ).fetchall()
    for r in pending:
        try:
            scheduled_dt = datetime.strptime(
                f"{r['scheduled_date']} {r['scheduled_time']}", "%Y-%m-%d %H:%M"
            )
        except ValueError:
            continue
        if now >= scheduled_dt + timedelta(minutes=config.GRACE_PERIOD_MINUTES):
            conn.execute(
                "UPDATE medication_records SET status = 'MISSED' WHERE id = ?", (r["id"],)
            )
            medicine = conn.execute(
                "SELECT name FROM medicines WHERE id = ?", (r["medicine_id"],)
            ).fetchone()
            med_name = medicine["name"] if medicine else "A medicine"
            create_notification(
                conn,
                user_id,
                ntype="MISSED",
                title="Medication Missed",
                message=f"{med_name} scheduled for {r['scheduled_time']} was missed.",
                related_medicine_id=r["medicine_id"],
                related_record_id=r["id"],
                recipient_type="BOTH",
            )
    conn.commit()


def refresh_records(conn, user_id):
    ensure_today_records(conn, user_id)
    sweep_missed_records(conn, user_id)


# ---------------------------------------------------------------------------
# Medicines CRUD
# ---------------------------------------------------------------------------

@route("GET", r"^/api/medicines$")
def list_medicines(conn, match, query, body, user_id):
    rows = conn.execute(
        "SELECT * FROM medicines WHERE user_id = ? ORDER BY name", (user_id,)
    ).fetchall()
    return 200, {"medicines": [_medicine_to_dict(r) for r in rows]}


@route("POST", r"^/api/medicines$", roles=MEDICINE_WRITE_ROLES)
def create_medicine(conn, match, query, body, user_id):
    name = (body.get("name") or "").strip()
    if not name:
        raise ApiError(400, "'name' is required")
    initial_stock = _parse_body_number(body, "initial_stock", allow_zero=True)
    low_stock_threshold = _parse_body_number(body, "low_stock_threshold", allow_zero=True, required=False)
    if low_stock_threshold is None:
        low_stock_threshold = 5

    ts = now_iso()
    cur = conn.execute(
        """INSERT INTO medicines
           (user_id, name, initial_stock, current_stock, low_stock_threshold, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, name, initial_stock, initial_stock, low_stock_threshold, ts, ts),
    )
    conn.commit()
    row = _get_medicine_or_404(conn, cur.lastrowid, user_id)
    return 201, {"medicine": _medicine_to_dict(row)}


@route("GET", r"^/api/medicines/(\d+)$")
def get_medicine(conn, match, query, body, user_id):
    row = _get_medicine_or_404(conn, int(match.group(1)), user_id)
    return 200, {"medicine": _medicine_to_dict(row)}


@route("PUT", r"^/api/medicines/(\d+)$", roles=MEDICINE_WRITE_ROLES)
def update_medicine(conn, match, query, body, user_id):
    medicine_id = int(match.group(1))
    row = _get_medicine_or_404(conn, medicine_id, user_id)

    name = body.get("name", row["name"])
    if not str(name).strip():
        raise ApiError(400, "'name' cannot be empty")
    low_stock_threshold = row["low_stock_threshold"]
    if "low_stock_threshold" in body:
        low_stock_threshold = _parse_body_number(body, "low_stock_threshold", allow_zero=True)

    conn.execute(
        """UPDATE medicines SET name = ?, low_stock_threshold = ?, updated_at = ?
           WHERE id = ? AND user_id = ?""",
        (name, low_stock_threshold, now_iso(), medicine_id, user_id),
    )
    conn.commit()
    row = _get_medicine_or_404(conn, medicine_id, user_id)
    return 200, {"medicine": _medicine_to_dict(row)}


@route("DELETE", r"^/api/medicines/(\d+)$", roles=MEDICINE_WRITE_ROLES)
def delete_medicine(conn, match, query, body, user_id):
    medicine_id = int(match.group(1))
    _get_medicine_or_404(conn, medicine_id, user_id)
    conn.execute("DELETE FROM medicines WHERE id = ? AND user_id = ?", (medicine_id, user_id))
    conn.commit()
    return 200, {"success": True}


# ---------------------------------------------------------------------------
# Stock
# ---------------------------------------------------------------------------

@route("GET", r"^/api/stock$")
def get_stock(conn, match, query, body, user_id):
    rows = conn.execute(
        "SELECT * FROM medicines WHERE user_id = ? ORDER BY name", (user_id,)
    ).fetchall()
    return 200, {"stock": [_medicine_to_dict(r) for r in rows]}


@route("GET", r"^/api/stock/alerts$")
def get_stock_alerts(conn, match, query, body, user_id):
    rows = conn.execute(
        "SELECT * FROM medicines WHERE user_id = ? AND current_stock <= low_stock_threshold ORDER BY name",
        (user_id,),
    ).fetchall()
    return 200, {"alerts": [_medicine_to_dict(r) for r in rows]}


@route("POST", r"^/api/stock/(\d+)/add$", roles=STOCK_WRITE_ROLES)
def add_stock(conn, match, query, body, user_id):
    medicine_id = int(match.group(1))
    medicine = _get_medicine_or_404(conn, medicine_id, user_id)
    amount = _parse_body_number(body, "amount")

    new_stock = medicine["current_stock"] + amount
    ts = now_iso()
    conn.execute(
        "UPDATE medicines SET current_stock = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (new_stock, ts, medicine_id, user_id),
    )
    create_notification(
        conn,
        user_id,
        ntype="REFILL",
        title="Stock Refilled",
        message=f"{medicine['name']} stock refilled by {amount:g}. New stock: {new_stock:g}.",
        related_medicine_id=medicine_id,
        recipient_type="BOTH",
    )
    conn.commit()
    _check_low_stock(conn, user_id, medicine_id)
    row = _get_medicine_or_404(conn, medicine_id, user_id)
    return 200, {"medicine": _medicine_to_dict(row)}


@route("PUT", r"^/api/stock/(\d+)$", roles=STOCK_WRITE_ROLES)
def set_stock(conn, match, query, body, user_id):
    medicine_id = int(match.group(1))
    _get_medicine_or_404(conn, medicine_id, user_id)
    new_stock = _parse_body_number(body, "current_stock", allow_zero=True)

    conn.execute(
        "UPDATE medicines SET current_stock = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (new_stock, now_iso(), medicine_id, user_id),
    )
    conn.commit()
    _check_low_stock(conn, user_id, medicine_id)
    row = _get_medicine_or_404(conn, medicine_id, user_id)
    return 200, {"medicine": _medicine_to_dict(row)}


# ---------------------------------------------------------------------------
# Today / History
# ---------------------------------------------------------------------------

_RECORD_SELECT = """
    SELECT mr.*, m.name AS medicine_name
    FROM medication_records mr
    JOIN medicines m ON m.id = mr.medicine_id
"""


@route("GET", r"^/api/medications/today$")
def medications_today(conn, match, query, body, user_id):
    refresh_records(conn, user_id)
    today = date.today().isoformat()
    rows = conn.execute(
        _RECORD_SELECT + " WHERE mr.scheduled_date = ? AND m.user_id = ? ORDER BY mr.scheduled_time",
        (today, user_id),
    ).fetchall()
    return 200, {"date": today, "records": [_record_to_dict(r) for r in rows]}


@route("GET", r"^/api/medication-history$")
def medication_history(conn, match, query, body, user_id):
    refresh_records(conn, user_id)
    clauses = ["m.user_id = ?"]
    params = [user_id]
    if query.get("date"):
        clauses.append("mr.scheduled_date = ?")
        params.append(query["date"][0])
    if query.get("medicine_id"):
        clauses.append("mr.medicine_id = ?")
        params.append(int(query["medicine_id"][0]))
    if query.get("status"):
        clauses.append("mr.status = ?")
        params.append(query["status"][0].upper())

    sql = _RECORD_SELECT + " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY mr.scheduled_date DESC, mr.scheduled_time DESC"

    rows = conn.execute(sql, params).fetchall()
    return 200, {"records": [_record_to_dict(r) for r in rows]}


# ---------------------------------------------------------------------------
# Taken / Missed
# ---------------------------------------------------------------------------

def _get_owned_record(conn, record_id, user_id):
    record = conn.execute(
        """SELECT mr.* FROM medication_records mr
           JOIN medicines m ON m.id = mr.medicine_id
           WHERE mr.id = ? AND m.user_id = ?""",
        (record_id, user_id),
    ).fetchone()
    if record is None:
        raise ApiError(404, "Medication record not found")
    return record


@route("POST", r"^/api/medications/(\d+)/taken$", roles=STOCK_WRITE_ROLES)
def mark_taken(conn, match, query, body, user_id):
    record_id = int(match.group(1))
    record = _get_owned_record(conn, record_id, user_id)

    if record["status"] != "PENDING":
        # Already TAKEN or MISSED: both are terminal. This is what makes a
        # duplicate "Taken" click a no-op instead of a double stock deduction,
        # and what prevents un-missing a record through this endpoint.
        raise ApiError(409, f"Record already {record['status']}; cannot confirm again")

    medicine = _get_medicine_or_404(conn, record["medicine_id"], user_id)
    new_stock = medicine["current_stock"] - record["dosage"]
    if new_stock < 0:
        raise ApiError(400, "Insufficient stock to confirm this dose. Please refill stock first.")

    ts = now_iso()
    cur = conn.execute(
        """UPDATE medication_records
           SET status = 'TAKEN', confirmed_at = ?, stock_after = ?
           WHERE id = ? AND status = 'PENDING'""",
        (ts, new_stock, record_id),
    )
    if cur.rowcount == 0:
        # Lost a race with another confirmation of the same record between
        # the SELECT above and this UPDATE: treat as already processed
        # rather than deducting stock twice.
        raise ApiError(409, "Record already processed")

    conn.execute(
        "UPDATE medicines SET current_stock = ?, updated_at = ? WHERE id = ?",
        (new_stock, ts, medicine["id"]),
    )

    create_notification(
        conn,
        user_id,
        ntype="TAKEN",
        title="Medication Taken",
        message=f"{medicine['name']} was taken at {ts.split(' ')[1]}.",
        related_medicine_id=medicine["id"],
        related_record_id=record_id,
        recipient_type="BOTH",
    )

    conn.commit()
    _check_low_stock(conn, user_id, medicine["id"])

    updated = conn.execute(_RECORD_SELECT + " WHERE mr.id = ?", (record_id,)).fetchone()
    updated_medicine = _get_medicine_or_404(conn, medicine["id"], user_id)
    return 200, {"record": _record_to_dict(updated), "medicine": _medicine_to_dict(updated_medicine)}


@route("POST", r"^/api/medications/(\d+)/missed$", roles=STOCK_WRITE_ROLES)
def mark_missed(conn, match, query, body, user_id):
    record_id = int(match.group(1))
    record = _get_owned_record(conn, record_id, user_id)

    if record["status"] != "PENDING":
        raise ApiError(409, f"Record already {record['status']}; cannot change")

    medicine = _get_medicine_or_404(conn, record["medicine_id"], user_id)

    cur = conn.execute(
        "UPDATE medication_records SET status = 'MISSED' WHERE id = ? AND status = 'PENDING'",
        (record_id,),
    )
    if cur.rowcount == 0:
        raise ApiError(409, "Record already processed")

    create_notification(
        conn,
        user_id,
        ntype="MISSED",
        title="Medication Missed",
        message=f"{medicine['name']} scheduled for {record['scheduled_time']} was missed.",
        related_medicine_id=medicine["id"],
        related_record_id=record_id,
        recipient_type="BOTH",
    )
    conn.commit()

    updated = conn.execute(_RECORD_SELECT + " WHERE mr.id = ?", (record_id,)).fetchone()
    return 200, {"record": _record_to_dict(updated)}

"""
Hardware-ready API for a future medicine-dispensing robot/arm. Fully
simulated for now: every action just updates the calling user's
robot_status row and logs a notification, but the request/response
contract is what a Raspberry Pi-driven dispenser would need to
implement for real.
"""

from api.router import route, ApiError
from database import now_iso, create_notification, get_or_create_robot_status

# Same rule as cameras/smart-home devices: Patient/Family Member only.
VIEW_ROLES = ["PATIENT", "FAMILY"]
WRITE_ROLES = ["PATIENT", "FAMILY"]


def _status_to_dict(row):
    return {
        "status": row["status"],
        "last_event": row["last_event"],
        "updated_at": row["updated_at"],
    }


def _set_status(conn, user_id, status, last_event):
    get_or_create_robot_status(conn, user_id)
    conn.execute(
        "UPDATE robot_status SET status = ?, last_event = ?, updated_at = ? WHERE user_id = ?",
        (status, last_event, now_iso(), user_id),
    )


@route("GET", r"^/api/robot/status$", roles=VIEW_ROLES)
def robot_status(conn, match, query, body, user_id):
    row = get_or_create_robot_status(conn, user_id)
    return 200, {"robot": _status_to_dict(row)}


@route("POST", r"^/api/robot/dispense$", roles=WRITE_ROLES)
def robot_dispense(conn, match, query, body, user_id):
    medicine_id = body.get("medicine_id")
    dosage = body.get("dosage")
    label = "medicine"
    if medicine_id is not None:
        medicine = conn.execute(
            "SELECT * FROM medicines WHERE id = ? AND user_id = ?", (medicine_id, user_id)
        ).fetchone()
        if medicine is None:
            raise ApiError(404, "Medicine not found")
        label = medicine["name"]

    event = f"Simulated dispense: {label}" + (f" x{dosage}" if dosage else "")
    _set_status(conn, user_id, "IDLE", event)
    create_notification(
        conn,
        user_id,
        ntype="ROBOT",
        title="Robot Dispense (Simulated)",
        message=event + ". No physical dispenser connected in this prototype.",
        related_medicine_id=medicine_id,
        recipient_type="BOTH",
    )
    conn.commit()
    row = get_or_create_robot_status(conn, user_id)
    return 200, {"robot": _status_to_dict(row)}


@route("POST", r"^/api/robot/alarm$", roles=WRITE_ROLES)
def robot_alarm(conn, match, query, body, user_id):
    _set_status(conn, user_id, "ALARM", "Alarm triggered (simulated)")
    create_notification(
        conn,
        user_id,
        ntype="ROBOT",
        title="Robot Alarm Triggered",
        message="Simulated alarm triggered via robot API.",
        recipient_type="BOTH",
    )
    conn.commit()
    row = get_or_create_robot_status(conn, user_id)
    return 200, {"robot": _status_to_dict(row)}


@route("POST", r"^/api/robot/stop$", roles=WRITE_ROLES)
def robot_stop(conn, match, query, body, user_id):
    _set_status(conn, user_id, "IDLE", "Stopped")
    conn.commit()
    row = get_or_create_robot_status(conn, user_id)
    return 200, {"robot": _status_to_dict(row)}

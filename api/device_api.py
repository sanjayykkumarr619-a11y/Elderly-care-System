"""
Smart home / IoT device control. All actual state changes are delegated
to devices.device_manager, which is the only place that knows whether a
device is virtual or (in the future) a real Raspberry Pi-connected one.
Ownership (this device belongs to the calling user) is always checked
here, before device_manager ever touches a row.
"""

from api.router import route, ApiError
from database import now_iso
from devices import device_manager

VALID_TYPES = ("light", "fan", "ac", "tv", "plug", "buzzer", "other")

# Smart-home is a Patient/Family Member thing: both get full control
# (view + add/remove/command). Caretaker and Doctor have no access at
# all, not even to view.
VIEW_ROLES = ["PATIENT", "FAMILY"]
WRITE_ROLES = ["PATIENT", "FAMILY"]


def _device_to_dict(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "device_type": row["device_type"],
        "location": row["location"],
        "state": row["state"],
        "connection_type": row["connection_type"],
        "hardware_id": row["hardware_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _get_device_or_404(conn, device_id, user_id):
    row = conn.execute(
        "SELECT * FROM smart_devices WHERE id = ? AND user_id = ?", (device_id, user_id)
    ).fetchone()
    if row is None:
        raise ApiError(404, "Device not found")
    return row


@route("GET", r"^/api/devices$", roles=VIEW_ROLES)
def list_devices(conn, match, query, body, user_id):
    rows = conn.execute(
        "SELECT * FROM smart_devices WHERE user_id = ? ORDER BY name", (user_id,)
    ).fetchall()
    return 200, {"devices": [_device_to_dict(r) for r in rows]}


@route("POST", r"^/api/devices$", roles=WRITE_ROLES)
def create_device(conn, match, query, body, user_id):
    name = (body.get("name") or "").strip()
    if not name:
        raise ApiError(400, "'name' is required")
    device_type = (body.get("device_type") or "other").strip().lower()
    if device_type not in VALID_TYPES:
        device_type = "other"
    location = (body.get("location") or "").strip()

    ts = now_iso()
    cur = conn.execute(
        """INSERT INTO smart_devices
           (user_id, name, device_type, location, state, connection_type, hardware_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'OFF', 'virtual', NULL, ?, ?)""",
        (user_id, name, device_type, location, ts, ts),
    )
    conn.commit()
    row = _get_device_or_404(conn, cur.lastrowid, user_id)
    return 201, {"device": _device_to_dict(row)}


@route("DELETE", r"^/api/devices/(\d+)$", roles=WRITE_ROLES)
def delete_device(conn, match, query, body, user_id):
    device_id = int(match.group(1))
    _get_device_or_404(conn, device_id, user_id)
    conn.execute("DELETE FROM smart_devices WHERE id = ?", (device_id,))
    conn.commit()
    return 200, {"success": True}


@route("GET", r"^/api/devices/(\d+)$", roles=VIEW_ROLES)
def get_device(conn, match, query, body, user_id):
    row = _get_device_or_404(conn, int(match.group(1)), user_id)
    return 200, {"device": _device_to_dict(row)}


@route("GET", r"^/api/devices/(\d+)/status$", roles=VIEW_ROLES)
def device_status(conn, match, query, body, user_id):
    device_id = int(match.group(1))
    _get_device_or_404(conn, device_id, user_id)
    status = device_manager.get_device_status(conn, device_id)
    return 200, {"id": device_id, **status}


@route("POST", r"^/api/devices/(\d+)/command$", roles=WRITE_ROLES)
def device_command(conn, match, query, body, user_id):
    device_id = int(match.group(1))
    _get_device_or_404(conn, device_id, user_id)
    command = (body.get("command") or "").strip().upper()
    if command not in ("ON", "OFF"):
        raise ApiError(400, "'command' must be 'ON' or 'OFF'")

    try:
        new_state = device_manager.send_command(conn, device_id, command)
    except ValueError as exc:
        raise ApiError(400, str(exc))

    if new_state is None:
        raise ApiError(404, "Device not found")

    return 200, {"success": True, "device_id": device_id, "state": new_state}

"""
Hardware-ready API for environment/safety sensors (motion, door,
temperature, ...). Currently backed by simulated values stored in
SQLite; POST /api/sensors/{id}/data is the exact endpoint a real sensor
attached to a Raspberry Pi would push readings to. Each account gets its
own default sensor fixtures on registration (see
database.provision_new_user_defaults).
"""

from api.router import route, ApiError
from database import now_iso

# Same rule as cameras/smart-home devices: Patient/Family Member only.
VIEW_ROLES = ["PATIENT", "FAMILY"]
WRITE_ROLES = ["PATIENT", "FAMILY"]


def _sensor_to_dict(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "sensor_type": row["sensor_type"],
        "location": row["location"],
        "last_value": row["last_value"],
        "unit": row["unit"],
        "status": row["status"],
        "updated_at": row["updated_at"],
    }


def _get_sensor_or_404(conn, sensor_id, user_id):
    row = conn.execute(
        "SELECT * FROM sensors WHERE id = ? AND user_id = ?", (sensor_id, user_id)
    ).fetchone()
    if row is None:
        raise ApiError(404, "Sensor not found")
    return row


@route("GET", r"^/api/sensors$", roles=VIEW_ROLES)
def list_sensors(conn, match, query, body, user_id):
    rows = conn.execute(
        "SELECT * FROM sensors WHERE user_id = ? ORDER BY name", (user_id,)
    ).fetchall()
    return 200, {"sensors": [_sensor_to_dict(r) for r in rows]}


@route("GET", r"^/api/sensors/(\d+)/status$", roles=VIEW_ROLES)
def sensor_status(conn, match, query, body, user_id):
    row = _get_sensor_or_404(conn, int(match.group(1)), user_id)
    return 200, {"sensor": _sensor_to_dict(row)}


@route("POST", r"^/api/sensors/(\d+)/data$", roles=WRITE_ROLES)
def sensor_push_data(conn, match, query, body, user_id):
    sensor_id = int(match.group(1))
    _get_sensor_or_404(conn, sensor_id, user_id)
    if "value" not in body:
        raise ApiError(400, "'value' is required")

    conn.execute(
        "UPDATE sensors SET last_value = ?, updated_at = ? WHERE id = ?",
        (str(body["value"]), now_iso(), sensor_id),
    )
    conn.commit()
    row = _get_sensor_or_404(conn, sensor_id, user_id)
    return 200, {"sensor": _sensor_to_dict(row)}

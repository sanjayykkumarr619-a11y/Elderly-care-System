"""
Camera monitoring - software-only prototype.

A camera's `status` (OFFLINE / ONLINE / STREAMING) and `stream_url` are
simulated entirely in SQLite. The connect/disconnect/status/stream
contract below is exactly what a real camera integration would need to
satisfy (e.g. an adapter that connects to an RTSP URL or a Raspberry Pi
camera module), so the frontend and this API never have to change when
physical cameras are added - only what happens inside connect_camera /
get_camera_stream would.
"""

from api.router import route, ApiError
from database import now_iso

# Cameras are a Patient/Family Member thing: both get full control (view
# + add/remove/connect/disconnect). Caretaker and Doctor have no camera
# access at all, not even to view.
VIEW_ROLES = ["PATIENT", "FAMILY"]
WRITE_ROLES = ["PATIENT", "FAMILY"]


def _camera_to_dict(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "location": row["location"],
        "status": row["status"],
        "stream_url": row["stream_url"],
        "created_at": row["created_at"],
    }


def _get_camera_or_404(conn, camera_id, user_id):
    row = conn.execute(
        "SELECT * FROM cameras WHERE id = ? AND user_id = ?", (camera_id, user_id)
    ).fetchone()
    if row is None:
        raise ApiError(404, "Camera not found")
    return row


@route("GET", r"^/api/cameras$", roles=VIEW_ROLES)
def list_cameras(conn, match, query, body, user_id):
    rows = conn.execute(
        "SELECT * FROM cameras WHERE user_id = ? ORDER BY name", (user_id,)
    ).fetchall()
    return 200, {"cameras": [_camera_to_dict(r) for r in rows]}


@route("POST", r"^/api/cameras$", roles=WRITE_ROLES)
def create_camera(conn, match, query, body, user_id):
    name = (body.get("name") or "").strip()
    if not name:
        raise ApiError(400, "'name' is required")
    location = (body.get("location") or "").strip()

    cur = conn.execute(
        "INSERT INTO cameras (user_id, name, location, status, stream_url, created_at) "
        "VALUES (?, ?, ?, 'OFFLINE', NULL, ?)",
        (user_id, name, location, now_iso()),
    )
    camera_id = cur.lastrowid
    conn.execute(
        "UPDATE cameras SET stream_url = ? WHERE id = ?",
        (f"simulated://camera/{camera_id}", camera_id),
    )
    conn.commit()
    row = _get_camera_or_404(conn, camera_id, user_id)
    return 201, {"camera": _camera_to_dict(row)}


@route("GET", r"^/api/cameras/(\d+)$", roles=VIEW_ROLES)
def get_camera(conn, match, query, body, user_id):
    row = _get_camera_or_404(conn, int(match.group(1)), user_id)
    return 200, {"camera": _camera_to_dict(row)}


@route("PUT", r"^/api/cameras/(\d+)$", roles=WRITE_ROLES)
def update_camera(conn, match, query, body, user_id):
    camera_id = int(match.group(1))
    row = _get_camera_or_404(conn, camera_id, user_id)
    name = body.get("name", row["name"])
    if not str(name).strip():
        raise ApiError(400, "'name' cannot be empty")
    location = body.get("location", row["location"])

    conn.execute("UPDATE cameras SET name = ?, location = ? WHERE id = ?", (name, location, camera_id))
    conn.commit()
    row = _get_camera_or_404(conn, camera_id, user_id)
    return 200, {"camera": _camera_to_dict(row)}


@route("DELETE", r"^/api/cameras/(\d+)$", roles=WRITE_ROLES)
def delete_camera(conn, match, query, body, user_id):
    camera_id = int(match.group(1))
    _get_camera_or_404(conn, camera_id, user_id)
    conn.execute("DELETE FROM cameras WHERE id = ?", (camera_id,))
    conn.commit()
    return 200, {"success": True}


@route("POST", r"^/api/cameras/(\d+)/connect$", roles=WRITE_ROLES)
def connect_camera(conn, match, query, body, user_id):
    camera_id = int(match.group(1))
    _get_camera_or_404(conn, camera_id, user_id)
    conn.execute("UPDATE cameras SET status = 'STREAMING' WHERE id = ?", (camera_id,))
    conn.commit()
    row = _get_camera_or_404(conn, camera_id, user_id)
    return 200, {"camera": _camera_to_dict(row)}


@route("POST", r"^/api/cameras/(\d+)/disconnect$", roles=WRITE_ROLES)
def disconnect_camera(conn, match, query, body, user_id):
    camera_id = int(match.group(1))
    _get_camera_or_404(conn, camera_id, user_id)
    conn.execute("UPDATE cameras SET status = 'OFFLINE' WHERE id = ?", (camera_id,))
    conn.commit()
    row = _get_camera_or_404(conn, camera_id, user_id)
    return 200, {"camera": _camera_to_dict(row)}


@route("GET", r"^/api/cameras/(\d+)/status$", roles=VIEW_ROLES)
def camera_status(conn, match, query, body, user_id):
    row = _get_camera_or_404(conn, int(match.group(1)), user_id)
    return 200, {"id": row["id"], "status": row["status"]}


@route("GET", r"^/api/cameras/(\d+)/stream$", roles=VIEW_ROLES)
def camera_stream(conn, match, query, body, user_id):
    row = _get_camera_or_404(conn, int(match.group(1)), user_id)
    if row["status"] != "STREAMING":
        raise ApiError(409, "Camera is offline. Connect it first to view the simulated stream.")
    return 200, {
        "id": row["id"],
        "status": row["status"],
        "simulated": True,
        "message": "Simulated feed - no physical camera connected. A future Raspberry Pi "
                   "camera adapter would return a real frame/stream URL here instead.",
        "stream_url": row["stream_url"],
    }

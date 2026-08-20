"""Notification center: list + mark-as-read. Notifications themselves are
created by medication_api, camera_api, device_api, and robot_api as they
process events. Includes email delivery status/target since every
CAREGIVER/BOTH notification also attempts to email the account's
caregiver address (see database.create_notification)."""

from api.router import route, ApiError


def _notification_to_dict(row):
    return {
        "id": row["id"],
        "type": row["type"],
        "title": row["title"],
        "message": row["message"],
        "related_medicine_id": row["related_medicine_id"],
        "related_record_id": row["related_record_id"],
        "recipient_type": row["recipient_type"],
        "is_read": bool(row["is_read"]),
        "email_status": row["email_status"],
        "email_to": row["email_to"],
        "created_at": row["created_at"],
    }


@route("GET", r"^/api/notifications$")
def list_notifications(conn, match, query, body, user_id):
    sql = "SELECT * FROM notifications WHERE user_id = ?"
    params = [user_id]
    if query.get("is_read") is not None:
        sql += " AND is_read = ?"
        params.append(1 if query["is_read"][0] in ("1", "true", "True") else 0)
    sql += " ORDER BY created_at DESC, id DESC"
    rows = conn.execute(sql, params).fetchall()
    return 200, {"notifications": [_notification_to_dict(r) for r in rows]}


@route("POST", r"^/api/notifications/(\d+)/read$")
def mark_notification_read(conn, match, query, body, user_id):
    notification_id = int(match.group(1))
    row = conn.execute(
        "SELECT * FROM notifications WHERE id = ? AND user_id = ?", (notification_id, user_id)
    ).fetchone()
    if row is None:
        raise ApiError(404, "Notification not found")
    conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
    conn.commit()
    row = conn.execute("SELECT * FROM notifications WHERE id = ?", (notification_id,)).fetchone()
    return 200, {"notification": _notification_to_dict(row)}

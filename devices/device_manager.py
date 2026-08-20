"""
DeviceManager: the single point through which the API layer talks to
devices. It looks at a device's `connection_type` column and hands the
request to the matching adapter (VirtualDevice today, RaspberryPiDevice
once real hardware exists), persists the resulting state back to SQLite,
and logs a device_events row.

    API  -->  DeviceManager  -->  VirtualDevice        (today)
    API  -->  DeviceManager  -->  RaspberryPiDevice     (future)

Nothing above this module ever imports VirtualDevice or
RaspberryPiDevice directly.
"""

from database import now_iso
from devices.virtual_device import VirtualDevice
from devices.raspberry_pi_adapter import RaspberryPiDevice


def _get_adapter(device_row):
    if device_row["connection_type"] == "raspberry_pi":
        return RaspberryPiDevice(device_row)
    return VirtualDevice(device_row)


def get_device_status(conn, device_id):
    row = conn.execute("SELECT * FROM smart_devices WHERE id = ?", (device_id,)).fetchone()
    if row is None:
        return None
    adapter = _get_adapter(row)
    return adapter.get_status()


def send_command(conn, device_id, command):
    """Returns the new state string, or None if the device does not exist.
    Raises ValueError for an invalid command."""
    row = conn.execute("SELECT * FROM smart_devices WHERE id = ?", (device_id,)).fetchone()
    if row is None:
        return None

    adapter = _get_adapter(row)
    new_state = adapter.execute_command(command)

    ts = now_iso()
    conn.execute(
        "UPDATE smart_devices SET state = ?, updated_at = ? WHERE id = ?",
        (new_state, ts, device_id),
    )
    conn.execute(
        """INSERT INTO device_events (device_id, event_type, command, value, created_at)
           VALUES (?, 'COMMAND', ?, ?, ?)""",
        (device_id, command, new_state, ts),
    )
    conn.commit()
    return new_state

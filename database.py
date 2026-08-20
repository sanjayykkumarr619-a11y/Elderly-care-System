"""
SQLite database layer for the Elderly Care System.

Everything the rest of the app needs to touch the database goes through
here: connection creation, schema initialization (auto-run on first
startup), a demo account for quick evaluation, and a couple of small
shared helpers (timestamps, notifications) used by every API module.

The app is multi-tenant: every user account owns a private set of
medicines, schedules, cameras, smart devices, sensors and notifications
(see the user_id column on each of those tables). There is no shared/
global data - a brand new account starts empty and is walked through the
setup wizard (frontend/setup.html) to create its own.
"""

import os
import secrets
import sqlite3
import string
from datetime import datetime

import config
import email_service

ROLES = ("PATIENT", "CARETAKER", "FAMILY", "DOCTOR")
NON_PATIENT_ROLES = ("CARETAKER", "FAMILY", "DOCTOR")


def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_connection():
    os.makedirs(config.DATABASE_DIR, exist_ok=True)
    conn = sqlite3.connect(config.DATABASE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'PATIENT',
    caregiver_name TEXT,
    caregiver_mobile TEXT,
    caregiver_email TEXT,
    invite_code TEXT,
    linked_patient_id INTEGER,
    setup_completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (linked_patient_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS medicines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    dosage_unit TEXT NOT NULL DEFAULT 'tablet',
    initial_stock REAL NOT NULL,
    current_stock REAL NOT NULL,
    low_stock_threshold REAL NOT NULL DEFAULT 5,
    low_stock_alerted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS caregivers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS medication_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    medicine_id INTEGER NOT NULL,
    scheduled_time TEXT NOT NULL,
    dosage REAL NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS medication_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    medicine_id INTEGER NOT NULL,
    schedule_id INTEGER,
    scheduled_date TEXT NOT NULL,
    scheduled_time TEXT NOT NULL,
    dosage REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    confirmed_at TEXT,
    stock_after REAL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE,
    FOREIGN KEY (schedule_id) REFERENCES medication_schedules(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    related_medicine_id INTEGER,
    related_record_id INTEGER,
    recipient_type TEXT NOT NULL DEFAULT 'BOTH',
    is_read INTEGER NOT NULL DEFAULT 0,
    sms_status TEXT NOT NULL DEFAULT 'NOT_APPLICABLE',
    sms_to TEXT,
    email_status TEXT NOT NULL DEFAULT 'NOT_APPLICABLE',
    email_to TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cameras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    location TEXT,
    status TEXT NOT NULL DEFAULT 'OFFLINE',
    stream_url TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS smart_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    device_type TEXT NOT NULL,
    location TEXT,
    state TEXT NOT NULL DEFAULT 'OFF',
    connection_type TEXT NOT NULL DEFAULT 'virtual',
    hardware_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS device_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    command TEXT,
    value TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (device_id) REFERENCES smart_devices(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Hardware-ready extension tables (not in the base spec list, but needed
-- to back the robot/sensor prototype APIs without inventing extra state
-- outside the database).

CREATE TABLE IF NOT EXISTS robot_status (
    user_id INTEGER PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'IDLE',
    last_event TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sensors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    sensor_type TEXT NOT NULL,
    location TEXT,
    last_value TEXT,
    unit TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""


def _migrate_schema(conn):
    """Add columns introduced after the table already existed on disk.
    CREATE TABLE IF NOT EXISTS never alters an existing table, so role-based
    accounts need this to upgrade a database created before roles existed
    without losing any data. Each ALTER TABLE is tried independently and a
    'duplicate column' failure is silently ignored."""
    migrations = [
        "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'PATIENT'",
        "ALTER TABLE users ADD COLUMN invite_code TEXT",
        "ALTER TABLE users ADD COLUMN linked_patient_id INTEGER",
        "ALTER TABLE users ADD COLUMN caregiver_email TEXT",
        "ALTER TABLE notifications ADD COLUMN email_status TEXT NOT NULL DEFAULT 'NOT_APPLICABLE'",
        "ALTER TABLE notifications ADD COLUMN email_to TEXT",
        "ALTER TABLE medicines ADD COLUMN low_stock_alerted INTEGER NOT NULL DEFAULT 0",
    ]
    for statement in migrations:
        try:
            conn.execute(statement)
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists

    _backfill_caregivers_from_legacy_field(conn)


def _backfill_caregivers_from_legacy_field(conn):
    """Older accounts (and the demo account) may only have the legacy
    single users.caregiver_name/caregiver_email fields, from before the
    multi-recipient caregivers table existed. Seed one caregiver row from
    that for any patient who doesn't already have at least one - safe to
    run every startup since it only acts on patients with zero rows."""
    patients = conn.execute(
        """SELECT id, caregiver_name, caregiver_email FROM users
           WHERE role = 'PATIENT' AND caregiver_email IS NOT NULL AND caregiver_email != ''"""
    ).fetchall()
    ts = now_iso()
    for patient in patients:
        has_any = conn.execute(
            "SELECT 1 FROM caregivers WHERE user_id = ? LIMIT 1", (patient["id"],)
        ).fetchone()
        if has_any:
            continue
        conn.execute(
            """INSERT INTO caregivers (user_id, name, email, active, created_at, updated_at)
               VALUES (?, ?, ?, 1, ?, ?)""",
            (patient["id"], patient["caregiver_name"] or "Caregiver", patient["caregiver_email"], ts, ts),
        )
    conn.commit()


def init_schema(conn):
    """Create tables if they do not exist yet. Safe to call every startup."""
    conn.executescript(SCHEMA)
    conn.commit()
    _migrate_schema(conn)


def init_db(seed_demo=True):
    """Create tables if they do not exist yet, optionally seeding a demo
    account. Safe to call every startup - seeding only ever happens once
    (when the users table is completely empty)."""
    conn = get_connection()
    try:
        init_schema(conn)
        if seed_demo:
            seed_demo_account(conn)
    finally:
        conn.close()


def generate_invite_code(conn):
    """An 8-character, human-typeable code (excludes ambiguous characters
    like 0/O/1/I) that is guaranteed unique among current invite codes."""
    alphabet = "".join(c for c in string.ascii_uppercase + string.digits if c not in "0O1I")
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(8))
        exists = conn.execute("SELECT id FROM users WHERE invite_code = ?", (code,)).fetchone()
        if exists is None:
            return code


def resolve_actor(conn, user_id):
    """Given the token owner's user_id, returns (role, effective_patient_id).
    For a PATIENT, the effective patient is themselves. For a linked
    CARETAKER/FAMILY/DOCTOR account, it's whichever patient they linked to
    (None if they haven't linked yet) - every data table is scoped by that
    id, never by the token owner's own id, so Caretaker/Family/Doctor
    accounts operate on the Patient's shared record instead of an empty
    private one."""
    row = conn.execute("SELECT role, linked_patient_id FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        return None, None
    if row["role"] == "PATIENT":
        return "PATIENT", user_id
    return row["role"], row["linked_patient_id"]


def get_or_create_robot_status(conn, user_id):
    row = conn.execute("SELECT * FROM robot_status WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO robot_status (user_id, status, last_event, updated_at) VALUES (?, 'IDLE', NULL, ?)",
            (user_id, now_iso()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM robot_status WHERE user_id = ?", (user_id,)).fetchone()
    return row


def seed_demo_account(conn):
    """Create a ready-to-explore 'demo' / 'demo1234' account the first
    time the app ever runs (only when the users table is completely
    empty), so the app can be evaluated immediately without registering.
    Real accounts created afterwards always start empty and go through
    the setup wizard instead."""
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
        return

    import auth  # local import: avoids a circular import at module load time

    ts = now_iso()
    password_hash, salt = auth.hash_password("demo1234")
    cur = conn.execute(
        """INSERT INTO users
           (username, password_hash, password_salt, role, caregiver_name, caregiver_mobile, caregiver_email, setup_completed, created_at)
           VALUES (?, ?, ?, 'PATIENT', ?, ?, ?, 1, ?)""",
        ("demo", password_hash, salt, "Demo Caregiver", "9999999999", "demo.caregiver@example.com", ts),
    )
    user_id = cur.lastrowid

    conn.execute(
        """INSERT INTO caregivers (user_id, name, email, active, created_at, updated_at)
           VALUES (?, ?, ?, 1, ?, ?)""",
        (user_id, "Demo Caregiver", "demo.caregiver@example.com", ts, ts),
    )

    cur = conn.execute(
        """INSERT INTO medicines
           (user_id, name, dosage_unit, initial_stock, current_stock, low_stock_threshold, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, "Tablet A", "tablet", 30, 30, 5, ts, ts),
    )
    medicine_id = cur.lastrowid
    for scheduled_time in ("08:00", "14:00", "20:00"):
        conn.execute(
            """INSERT INTO medication_schedules
               (medicine_id, scheduled_time, dosage, active, created_at, updated_at)
               VALUES (?, ?, ?, 1, ?, ?)""",
            (medicine_id, scheduled_time, 1, ts, ts),
        )

    for name, location in (("Bedroom Light", "Bedroom"), ("Living Room Light", "Living Room"),
                            ("Fan", "Living Room"), ("AC", "Bedroom"), ("TV", "Living Room")):
        device_type = "light" if "Light" in name else name.lower()
        conn.execute(
            """INSERT INTO smart_devices
               (user_id, name, device_type, location, state, connection_type, hardware_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'OFF', 'virtual', NULL, ?, ?)""",
            (user_id, name, device_type, location, ts, ts),
        )

    for name, location in (("Bedroom Camera", "Bedroom"), ("Living Room Camera", "Living Room")):
        cur = conn.execute(
            """INSERT INTO cameras (user_id, name, location, status, stream_url, created_at)
               VALUES (?, ?, ?, 'OFFLINE', NULL, ?)""",
            (user_id, name, location, ts),
        )
        cam_id = cur.lastrowid
        conn.execute("UPDATE cameras SET stream_url = ? WHERE id = ?", (f"simulated://camera/{cam_id}", cam_id))

    for name, sensor_type, location, value, unit in (
        ("Bedroom Motion Sensor", "motion", "Bedroom", "NO_MOTION", None),
        ("Front Door Sensor", "door", "Entrance", "CLOSED", None),
        ("Living Room Temperature", "temperature", "Living Room", "24.0", "C"),
    ):
        conn.execute(
            """INSERT INTO sensors (user_id, name, sensor_type, location, last_value, unit, status, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?)""",
            (user_id, name, sensor_type, location, value, unit, ts),
        )

    conn.execute(
        "INSERT OR REPLACE INTO system_settings (key, value) VALUES ('grace_period_minutes', ?)",
        (str(config.GRACE_PERIOD_MINUTES),),
    )
    conn.commit()


def provision_new_user_defaults(conn, user_id):
    """Give a freshly registered (non-demo) account its default sensor
    fixtures - sensors have no create endpoint of their own (they
    represent fixed environmental hardware points), everything else
    (medicines, cameras, smart devices) is created by the user via the
    setup wizard or the regular pages."""
    ts = now_iso()
    for name, sensor_type, location, value, unit in (
        ("Bedroom Motion Sensor", "motion", "Bedroom", "NO_MOTION", None),
        ("Front Door Sensor", "door", "Entrance", "CLOSED", None),
        ("Living Room Temperature", "temperature", "Living Room", "24.0", "C"),
    ):
        conn.execute(
            """INSERT INTO sensors (user_id, name, sensor_type, location, last_value, unit, status, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?)""",
            (user_id, name, sensor_type, location, value, unit, ts),
        )
    conn.commit()


def create_notification(conn, user_id, ntype, title, message, related_medicine_id=None,
                         related_record_id=None, recipient_type="BOTH",
                         email_subject=None, email_body=None):
    """Insert a notification row and, for CAREGIVER/BOTH recipients,
    attempt to email every ACTIVE caregiver/family recipient configured
    for this account (see the caregivers table / api/caregiver_api.py).
    Email delivery is best-effort and fans out to all active recipients
    independently - a failure for one address never blocks the others or
    the caller. `email_subject`/`email_body` let a caller send different
    wording to email than what's shown on the in-app notification (the
    low-stock alert does this - see api/medication_api.py); both default
    to `title`/`message` for every other notification type.

    email_status on the stored row is:
      NOT_APPLICABLE - recipient_type was PATIENT-only, no email attempted
      SKIPPED        - CAREGIVER/BOTH but no active recipients configured
      SENT           - delivered to every active recipient
      PARTIAL        - delivered to some but not all
      FAILED         - delivered to none
    """
    email_status = "NOT_APPLICABLE"
    email_to = None

    if recipient_type in ("CAREGIVER", "BOTH"):
        recipients = conn.execute(
            "SELECT email FROM caregivers WHERE user_id = ? AND active = 1", (user_id,)
        ).fetchall()
        addresses = [r["email"] for r in recipients if r["email"]]
        if addresses:
            email_to = ", ".join(addresses)
            subject = email_subject if email_subject is not None else title
            body = email_body if email_body is not None else message
            successes = 0
            for address in addresses:
                ok, _detail = email_service.send_email(address, subject, body)
                if ok:
                    successes += 1
            if successes == len(addresses):
                email_status = "SENT"
            elif successes > 0:
                email_status = "PARTIAL"
            else:
                email_status = "FAILED"
        else:
            email_status = "SKIPPED"

    conn.execute(
        """INSERT INTO notifications
           (user_id, type, title, message, related_medicine_id, related_record_id, recipient_type,
            is_read, email_status, email_to, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)""",
        (user_id, ntype, title, message, related_medicine_id, related_record_id, recipient_type,
         email_status, email_to, now_iso()),
    )

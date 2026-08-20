# Elderly Care System (Prototype)

AI-assisted elderly care web app: a role-based login portal (Patient,
Caretaker, Family Member, Doctor), medication stock tracking, taken/
missed reminders with real caregiver email alerts, simulated camera
monitoring, and simulated smart-home control. This is a **software-only
prototype** - no Raspberry Pi, sensors, relays, motors, or physical
cameras are required to run or demo it. The backend is built with a
device abstraction layer so real hardware can be plugged in later
without changing the frontend.

## Requirements

- Python 3.8+
- A modern web browser (Chrome, Edge, Firefox)
- No external Python packages (standard library only - see `requirements.txt`)
- Optional: an SMTP account (Gmail + App Password works well), to send
  real caregiver alert emails instead of just logging them

## Installation & Run

1. Open a terminal in the project directory.
2. Run:

   ```
   python server.py
   ```

3. Open your browser to:

   ```
   http://localhost:8000
   ```

You'll land on the login page. Either log in with the built-in demo
account (**username `demo`, password `demo1234`**, a Patient account,
fully pre-populated) or click "Create Account". Registering as a
**Patient** asks for a caregiver/family member's email address up front,
then walks you through a short setup wizard (add medicines + starting
stock/threshold, schedule times, cameras, smart devices) before landing
on the dashboard. Registering as a **Caretaker / Family Member / Doctor**
instead asks for an invite code - get one from a Patient's Settings page
(Invite Code section) - and skips straight to the dashboard, no wizard.

The SQLite database (`database/elderly_care.db`) is created automatically
on first run. Data is owned by Patient accounts; Caretaker/Family/Doctor
accounts don't have their own data, they link to one Patient's account
and act on it according to their role's permissions (see below).

### Enabling real caregiver email alerts (optional)

Taken/missed/low-stock/refill events always create an in-app notification.
If SMTP credentials are configured, the same event also gets **emailed**
to every ACTIVE recipient in the account's Caregiver/Family Recipients
list (Settings page, backed by `/api/caregivers`). Without credentials,
sending is skipped and logged to the console - the app still works
fully, it just won't send real emails.

To enable it:

1. Create (or use) a Gmail account to send FROM - a dedicated one is
   recommended, not your personal inbox. (Any SMTP provider works, not
   just Gmail - see `.env.example`.)
2. Turn on **2-Step Verification**: https://myaccount.google.com/security
3. Generate an **App Password**: https://myaccount.google.com/apppasswords
   → choose "Mail" → copy the 16-character password. This is NOT your
   normal Gmail password; Gmail blocks plain-password SMTP login.
4. **Never paste the address/password into chat or commit them** -
   instead set environment variables before starting the server
   (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`,
   `SENDER_EMAIL` - see `.env.example`), or copy `local_settings.py.example`
   to `local_settings.py` (already git-ignored) and put them there.

Each notification's delivery result is visible per-record in the
Notification Center (`email_status`: `SENT` / `PARTIAL` / `FAILED` /
`SKIPPED` / `NOT_APPLICABLE`, plus the recipient address(es) it targeted).
`PARTIAL` means it reached some active recipients but not all. Delivery
is best-effort and never blocks the medication flow - a bad password or
network hiccup just gets logged and recorded as `FAILED`, and the stock
change / notification itself is never rolled back.

## Project Structure

```
elderly-care-system/
├── server.py                  Basic Python HTTP server (stdlib only) + auth middleware
├── database.py                 SQLite schema + connection + demo account + notifications/email
├── auth.py                     Password hashing (PBKDF2) + session tokens
├── email_service.py            Standalone SMTP client (smtplib/email, stdlib only)
├── sms.py                      Fast2SMS gateway client (legacy, unused - kept for reference)
├── config.py                   Paths and tunable constants (+ SMTP/Fast2SMS credential loading)
├── local_settings.py.example   Template for your local (git-ignored) credentials
├── .env.example                Template for the same credentials as real env vars
├── requirements.txt
├── README.md
│
├── database/
│   └── elderly_care.db         Created automatically
│
├── frontend/assets/
│   └── medication-alarm.mp3    The audible reminder alarm sound
│
├── api/                         REST endpoint handlers (JSON in/out)
│   ├── router.py                Tiny regex route registry (method, pattern, handler, public?)
│   ├── auth_api.py              Register / login / logout / me (the login portal)
│   ├── caregiver_api.py         Caregiver/family recipient list CRUD (name/email/active)
│   ├── medication_api.py        Medicines, stock, taken/missed, today, history, low-stock checker
│   ├── schedule_api.py          Medication schedule CRUD
│   ├── notification_api.py      Notification center (incl. email delivery status)
│   ├── camera_api.py            Camera CRUD + connect/disconnect/stream
│   ├── device_api.py            Smart-home device CRUD + command
│   ├── robot_api.py             Hardware-ready dispensing-robot API
│   └── sensor_api.py            Hardware-ready sensor API
│
├── devices/                     Device abstraction layer
│   ├── virtual_device.py        Software-simulated device (used today)
│   ├── device_manager.py        Routes commands to the right adapter, persists state
│   └── raspberry_pi_adapter.py  Placeholder for a future physical adapter
│
├── frontend/                    HTML5 + CSS3 + vanilla JS (no frameworks)
│   ├── login.html               Log in / create account (asks for caregiver email)
│   ├── setup.html               First-run onboarding wizard
│   ├── index.html, medication.html, schedule.html, history.html,
│   │   stock.html, cameras.html, smart-home.html, notifications.html,
│   │   settings.html
│   ├── css/style.css
│   └── js/ (api.js, common.js, login.js, setup.js, dashboard.js,
│            medication.js, schedule.js, history.js, stock.js, cameras.js,
│            smart-home.js, notifications.js, settings.js)
│
└── tests/
    ├── testutil.py              Test harness (temp SQLite DB + route dispatcher + register_user())
    ├── test_medication.py
    ├── test_stock.py
    ├── test_api.py
    ├── test_roles.py            Role linking + permission-matrix tests
    └── test_low_stock.py        Low-stock acceptance scenario + caregiver CRUD tests
```

## Running the tests

```
python -m unittest discover -s tests -v
```

Tests use a throwaway SQLite database in a temp folder - they never touch
`database/elderly_care.db`, and every test registers its own isolated
user account.

## Login Portal & Roles

Four account roles, one shared patient record per household:

- **Patient** - owns the data (medicines, schedules, cameras, devices)
  and has full control of everything. Registering as a Patient asks for
  a caregiver/family email address and runs the setup wizard. Only
  Patients can edit the caregiver contact, generate/regenerate the
  invite code, and revoke a linked account's access (all in Settings).
- **Family Member** - links to a Patient via invite code. Full control
  of cameras and smart-home devices (add/remove/connect/disconnect/
  ON-off), same as the Patient. Read-only on medicine data - can see
  medicines/schedule/stock/history but not mark a dose taken or edit
  anything medical.
- **Caretaker** - links to a Patient via invite code. The narrowest
  role: read-only access to the medicine log (medicines, schedule,
  history, stock) and the notification center - no marking doses taken,
  no editing medicines/stock/schedule, and **no camera or smart-home
  access at all** (not even to view - those nav links don't appear).
  Effectively an inbox: they watch the log and receive the caregiver
  alert emails.
- **Doctor** - links to a Patient via invite code. Same shape as
  Caretaker: read-only medicine log + notifications, zero camera/
  smart-home access. Kept as a distinct role/badge for clarity even
  though its permissions currently match Caretaker's.

| Action | Patient | Family Member | Caretaker | Doctor |
|---|---|---|---|---|
| Mark taken/missed | Yes | No | No | No |
| Add/edit/delete medicines, stock, schedule | Yes | No (view only) | No (view only) | No (view only) |
| View history/notifications | Yes | Yes | Yes | Yes |
| Cameras / smart-home view | Yes | Yes | **No access** | **No access** |
| Cameras / smart-home control | Yes | Yes | **No access** | **No access** |
| Manage caregiver contact / invite code | Yes | No | No | No |

**How linking works**: a Patient's Settings page shows an 8-character
invite code (generated on first visit, regenerable any time - old code
stops working for *new* sign-ups, but accounts already linked keep their
access). A Caretaker/Family Member/Doctor enters that code at
registration instead of a caregiver email address. The Patient can see
and revoke linked accounts from the same Settings page; revoking kills
that account's active session immediately.

**Auth mechanics**: registering/logging in returns a session token
(stored server-side in the `sessions` table, kept client-side in
`localStorage`) sent as `Authorization: Bearer <token>` on every API
request. Every request resolves the *effective patient id* (the
account's own id for a Patient, the linked patient's id for the other
three roles) and every medicine/schedule/record/notification/camera/
device/sensor/robot-status row is scoped to that id - enforced on every
query, not just hidden in the UI. Role permissions are enforced the same
way: each API route declares which roles may call it; anything else gets
`403`.

- **First-run setup wizard** (`setup.html`, Patient only): walks through
  adding medicines (with starting stock + low-stock threshold), schedule
  times, cameras, and smart devices before the dashboard unlocks. It's
  re-enterable if you refresh mid-way through. Caretaker/Family/Doctor
  accounts skip it entirely - there's nothing for them to set up.
- **Demo account**: `demo` / `demo1234` (Patient role), seeded once on
  first-ever server start with a full working example (medicine + 3x/day
  schedule, 5 devices, 2 cameras, 3 sensors) so the app can be evaluated
  instantly.

## Core Feature: Medication Tracking

- **Medicines**: add/edit/delete, with an initial physical quantity that
  becomes the starting virtual stock.
- **Schedules**: any number of times per day per medicine.
- **Reminders (the "alarm")**: the browser polls `/api/medications/today`
  and pops an in-app modal the moment a dose's scheduled time arrives,
  playing a real, looping audible alarm (`frontend/assets/medication-alarm.mp3`
  via `HTMLAudioElement`) alongside a native browser notification (if
  permission is granted). A one-time "Enable Medication Alarm" button on
  the dashboard unlocks autoplay with a genuine user gesture (browsers
  block un-requested audio otherwise); after that it's remembered in
  `localStorage`. A STOP ALARM button in the modal silences it. This runs
  entirely client-side with no hardware required; it's deliberately kept
  software-only per the current scope.
- **Taken**: `POST /api/medications/{id}/taken` - validated on the
  backend, reduces stock by the dose, is idempotent (a second click
  returns `409` instead of deducting stock again), emails the caregiver,
  and triggers a low-stock check/alert if the new stock is at or below
  the threshold.
- **Missed**: any `PENDING` record more than 30 minutes past its
  scheduled time is automatically marked `MISSED` (checked on every
  today/history request and at server startup) - stock is **never**
  touched for a missed dose, no low-stock check runs, and the caregiver
  is emailed.
- **History & Stock pages**: full audit trail and low-stock alerts, with
  a manual "Add Stock"/"Set Stock" action for physical refills or
  corrections (also emails the caregiver and re-evaluates low-stock
  state).

## Main API Endpoints

All endpoints below except `/api/auth/register` and `/api/auth/login`
require `Authorization: Bearer <token>` and are scoped to that token's
account.

```
POST          /api/auth/register       POST /api/auth/login
POST          /api/auth/logout         GET  /api/auth/me      PUT /api/auth/me
POST          /api/auth/invite-code/regenerate         (Patient only)
GET           /api/auth/linked-accounts                (Patient only)
POST          /api/auth/linked-accounts/{id}/revoke     (Patient only)

GET/POST      /api/medicines            GET/PUT/DELETE /api/medicines/{id}
GET           /api/stock                GET /api/stock/alerts
POST          /api/stock/{id}/add       PUT /api/stock/{id}
GET/POST      /api/schedules            PUT/DELETE /api/schedules/{id}
GET           /api/medications/today
GET           /api/medication-history
POST          /api/medications/{id}/taken
POST          /api/medications/{id}/missed
GET           /api/notifications        POST /api/notifications/{id}/read

GET/POST      /api/caregivers           GET/PUT/DELETE /api/caregivers/{id}    (Patient only)

GET/POST      /api/cameras              GET/PUT/DELETE /api/cameras/{id}
POST          /api/cameras/{id}/connect POST /api/cameras/{id}/disconnect
GET           /api/cameras/{id}/status  GET /api/cameras/{id}/stream

GET/POST      /api/devices              GET/DELETE /api/devices/{id}
GET           /api/devices/{id}/status  POST /api/devices/{id}/command

GET           /api/robot/status         POST /api/robot/dispense
POST          /api/robot/alarm          POST /api/robot/stop

GET           /api/sensors              GET /api/sensors/{id}/status
POST          /api/sensors/{id}/data
```

## Fully Functional Now

- Role-based login portal: Patient/Caretaker/Family Member/Doctor,
  invite-code linking, per-route role permissions, PBKDF2 password
  hashing, server-side session tokens
- Real caregiver email alerts via SMTP (falls back to a logged no-op if
  credentials aren't configured), sent to a named list of Caregiver/Family
  Recipients managed on the Settings page (each with its own Active/
  Inactive toggle, backed by `/api/caregivers`)
- First-run setup wizard for medicines/stock/threshold/schedule/cameras/devices
- Medicine stock tracking (add/edit/delete/refill, low-stock alerts)
- Automatic low-stock notification: fires once per low-stock "episode"
  right after a taken dose, refill, or manual adjustment drops stock to
  or below its threshold (never after a missed dose), resets when stock
  is refilled back above threshold, and re-fires on the next dip
- Medication scheduling (multiple times/day)
- Taken/missed reminder engine with a real looping audible alarm +
  in-app modal + browser notification, backed by server-side validation
- Medication history with filters
- Notification center (taken, missed, low stock, refill events) with
  per-notification email delivery status, plus an unread-count badge in
  the sidebar

## Simulated (software-only, hardware-ready)

- Camera feeds (status + a placeholder "live" tile; real feed swapped in
  later behind the same connect/disconnect/stream API)
- Smart-home devices (lights, fan, AC, TV, ... - ON/OFF through the same
  DeviceManager a Raspberry Pi relay would use; addable/removable from
  the Smart Home page or the setup wizard)
- Dispensing robot and environmental sensors (endpoints exist and persist
  state; nothing physical is attached)
- The medication alarm is currently the in-browser audible alarm/modal
  only (by design, for this phase) - see Known Limitations.

## How This Is Hardware-Ready

Every device/camera command flows through a fixed interface
(`execute_command` / `get_status`) implemented today by
`devices/virtual_device.py`. `devices/device_manager.py` is the only code
that decides which implementation to use, based on a device's
`connection_type` column (`virtual` today, `raspberry_pi` in the future).
`devices/raspberry_pi_adapter.py` is a documented placeholder implementing
the same interface. To connect real hardware later: implement that
adapter (GPIO/serial/network calls), flip a device's `connection_type` to
`raspberry_pi`, and set its `hardware_id`. Nothing in `api/`, `server.py`,
or `frontend/` needs to change. The same pattern applies to caregiver
alerts (`email_service.py` is a small, swappable client - `sms.py` is
kept alongside it as an alternate channel that's easy to re-enable) and
could apply to a future physical buzzer by adding it as a `smart_devices`
row with `device_type = "buzzer"`.

## Server Reliability Note

`server.py` sets `protocol_version = "HTTP/1.1"` on the request handler
so connections are kept alive across a page's several requests (HTML,
CSS, each JS file, each API call). Python's `http.server` defaults to
HTTP/1.0 (a fresh TCP connection per request), which under Windows can
occasionally abort a request mid-transfer when a page fires off several
requests at once (e.g. a truncated `<script>` fails to execute with no
visible error, silently breaking event listeners). HTTP/1.1 keep-alive
fixes this; every response here already sends an exact `Content-Length`,
which is what keep-alive requires.

## Known Limitations

- The reminder engine (and its alarm) runs in the browser tab (polling
  every 15s); it won't fire if no browser tab is open, but the backend's
  own missed-dose sweep still runs on every `today`/`history` request and
  at server startup, so status stays correct either way. There is no
  physical buzzer/hardware alarm in this phase.
- Browsers block un-requested audio, so the audible alarm needs the
  "Enable Medication Alarm" button clicked once per browser (a real user
  gesture) before it can autoplay; this is remembered afterwards via
  `localStorage`, not a server-side setting.
- Low-stock alert state is a single boolean per medicine
  (`low_stock_alerted`), tracking only whether the *current* dip has
  already been notified - it's not a full history of every alert ever
  sent (the Notification Center itself is the history/audit trail).
- SQLite is used with WAL mode for reasonable concurrent access, but this
  is not designed for many simultaneous users.
- Session tokens don't expire until 30 days or a manual logout - there is
  no password reset flow (not needed for a local prototype).
- Email delivery depends on the configured SMTP provider's own limits
  (a personal/free Gmail account has a daily sending cap - fine for
  demo/prototype volume, not meant for production-scale alerting).

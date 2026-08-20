"""
Elderly Care System - basic Python HTTP backend.

Standard-library only (http.server + sqlite3 + json). Serves the static
frontend and a small REST-style JSON API. Run with:

    python server.py

then open http://localhost:8000
"""

import json
import mimetypes
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import auth
import config
import database
from api.router import ROUTES, ApiError

# Import every api module so their @route decorators register into ROUTES.
from api import auth_api  # noqa: F401
from api import caregiver_api  # noqa: F401
from api import medication_api  # noqa: F401
from api import schedule_api  # noqa: F401
from api import notification_api  # noqa: F401
from api import camera_api  # noqa: F401
from api import device_api  # noqa: F401
from api import robot_api  # noqa: F401
from api import sensor_api  # noqa: F401


class Handler(BaseHTTPRequestHandler):
    server_version = "ElderlyCareHTTP/1.0"
    # HTTP/1.1 enables persistent (keep-alive) connections. Without this,
    # BaseHTTPRequestHandler defaults to HTTP/1.0 - a fresh TCP connection
    # per resource (html/css/js/api calls). Under Windows especially, that
    # much rapid connection churn on page load can intermittently abort a
    # request mid-transfer (a truncated <script> then fails silently,
    # breaking event listeners with no console error). Every response
    # here already sends an exact Content-Length, which is what HTTP/1.1
    # keep-alive requires to know where one response ends and the next
    # begins.
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stdout.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    # -- helpers -----------------------------------------------------

    def _send_json(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ApiError(400, "Invalid JSON in request body")
        if not isinstance(data, dict):
            raise ApiError(400, "Request body must be a JSON object")
        return data

    def _get_token(self):
        return auth.extract_token(self.headers.get("Authorization"))

    def _dispatch_api(self, method):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        try:
            body = self._read_body() if method in ("POST", "PUT") else {}
        except ApiError as exc:
            self._send_json(exc.status_code, {"error": exc.message})
            return

        for route_method, pattern, handler, public, allowed_roles, scope in ROUTES:
            if route_method != method:
                continue
            match = pattern.match(path)
            if not match:
                continue

            conn = database.get_connection()
            try:
                token = self._get_token()
                query["_token"] = [token] if token else []
                raw_user_id = auth.get_user_id_from_token(conn, token) if token else None

                if not public and raw_user_id is None:
                    self._send_json(401, {"error": "Authentication required"})
                    return

                actor_role, patient_id = (None, None)
                if raw_user_id is not None:
                    actor_role, patient_id = database.resolve_actor(conn, raw_user_id)

                if not public and actor_role not in allowed_roles:
                    self._send_json(403, {"error": "Your account role cannot perform this action"})
                    return

                if not public and scope == "patient" and actor_role != "PATIENT" and patient_id is None:
                    self._send_json(
                        409,
                        {"error": "Your account is not linked to a patient yet. Enter your invite code in Settings."},
                    )
                    return

                pass_id = raw_user_id if (public or scope == "self") else patient_id

                try:
                    status_code, response = handler(conn, match, query, body, pass_id)
                    self._send_json(status_code, response)
                except ApiError as exc:
                    self._send_json(exc.status_code, {"error": exc.message})
                except Exception:
                    traceback.print_exc()
                    self._send_json(500, {"error": "Internal server error"})
            finally:
                conn.close()
            return

        self._send_json(404, {"error": "Not found"})

    # -- static file serving ------------------------------------------

    def _serve_static(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            path = "/index.html"

        safe_path = os.path.normpath(path).lstrip("\\/")
        full_path = os.path.join(config.FRONTEND_DIR, safe_path)
        full_path = os.path.abspath(full_path)

        frontend_root = os.path.abspath(config.FRONTEND_DIR)
        if not full_path.startswith(frontend_root) or not os.path.isfile(full_path):
            self._send_json(404, {"error": "File not found"})
            return

        content_type, _ = mimetypes.guess_type(full_path)
        content_type = content_type or "application/octet-stream"

        with open(full_path, "rb") as f:
            data = f.read()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # -- HTTP verbs ------------------------------------------------

    def do_GET(self):
        if self.path.startswith("/api/"):
            self._dispatch_api("GET")
        else:
            self._serve_static()

    def do_POST(self):
        self._dispatch_api("POST")

    def do_PUT(self):
        self._dispatch_api("PUT")

    def do_DELETE(self):
        self._dispatch_api("DELETE")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()


def main():
    print("Initializing database...")
    database.init_db()
    print(f"Database ready at {config.DATABASE_PATH}")
    if not config.FAST2SMS_API_KEY:
        print("[sms] FAST2SMS_API_KEY not set - caregiver SMS alerts will be logged, not sent. "
              "See README.md / local_settings.py.example to enable real SMS.")

    # Catch up on any medication records that should already be marked
    # MISSED if the server was off past their grace period, for every
    # existing account.
    conn = database.get_connection()
    try:
        patient_ids = [row["id"] for row in conn.execute("SELECT id FROM users WHERE role = 'PATIENT'").fetchall()]
        for patient_id in patient_ids:
            medication_api.refresh_records(conn, patient_id)
    finally:
        conn.close()

    server = ThreadingHTTPServer((config.HOST, config.PORT), Handler)
    print(f"Elderly Care System running at http://localhost:{config.PORT}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()

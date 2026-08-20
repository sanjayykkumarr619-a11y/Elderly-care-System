"""
Standalone email delivery service. Uses only Python's standard library
(smtplib + email.message) - no third-party SDK, no external dependency.
Deliberately kept separate from medication/stock logic (see
api/medication_api.py's _check_low_stock and database.create_notification)
so those modules never touch SMTP directly - they just call send_email().

Configuration comes from environment variables (see .env.example):
    SMTP_HOST       default: smtp.gmail.com
    SMTP_PORT       default: 587
    SMTP_USERNAME   the mailbox to authenticate as (e.g. a Gmail address)
    SMTP_PASSWORD   an app password, never the account's real login password
    SENDER_EMAIL    the "From" address (defaults to SMTP_USERNAME)

config.py reads these (env vars first, with a local_settings.py fallback
for local dev - see that file). Credentials are never hardcoded here. If
they're missing, send_email() logs and reports failure instead of
raising, so the rest of the app keeps working without them.

Module is named email_service.py (not email.py) specifically so it does
not shadow the standard library's own `email` package.
"""

import smtplib
from email.message import EmailMessage

import config


def send_email(to_address, subject, body):
    """Returns (success: bool, detail: str). Never raises - any SMTP or
    network error is caught and reported as a failure so a misconfigured
    or unreachable mail server can never break medication tracking."""
    host = config.SMTP_HOST
    port = config.SMTP_PORT
    username = config.SMTP_USERNAME
    password = (config.SMTP_PASSWORD or "").replace(" ", "")
    sender = config.SENDER_EMAIL or username

    if not username or not password or not sender:
        print(f"[email_service] SMTP credentials not configured - skipping email to {to_address}: {subject}")
        return False, "Email service not configured"

    if not to_address:
        return False, "No recipient email address given"

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"Elderly Care System <{sender}>"
    message["To"] = to_address
    message.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(message)
        return True, "sent"
    except smtplib.SMTPAuthenticationError as exc:
        detail = f"SMTP authentication failed: {exc}"
        print(f"[email_service] {detail}")
        return False, detail
    except (smtplib.SMTPException, OSError, TimeoutError) as exc:
        detail = f"Failed to send to {to_address}: {exc}"
        print(f"[email_service] {detail}")
        return False, detail

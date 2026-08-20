"""
Central configuration for the Elderly Care System prototype.
All paths and tunable constants live here so nothing is hardcoded
across the rest of the application.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE_DIR = os.path.join(BASE_DIR, "database")
DATABASE_PATH = os.path.join(DATABASE_DIR, "elderly_care.db")

FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

HOST = "0.0.0.0"
PORT = 8000

# A PENDING dose becomes MISSED this many minutes after its scheduled time
# if it has not been confirmed as TAKEN.
GRACE_PERIOD_MINUTES = 30

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M"

# --- Caregiver SMS (Fast2SMS) -------------------------------------------
# Never hardcode the real key here or paste it into chat. Preferred:
# set the FAST2SMS_API_KEY environment variable before starting the
# server. Alternative for local dev: create a file named
# local_settings.py (next to this file, already git-ignored) containing:
#     FAST2SMS_API_KEY = "your-real-key-here"
# It is imported below if present and never committed/shared.
FAST2SMS_API_KEY = os.environ.get("FAST2SMS_API_KEY", "")

try:
    from local_settings import FAST2SMS_API_KEY  # noqa: F811
except ImportError:
    pass

# --- Caregiver email (email_service.py / SMTP) --------------------------
# The active notification channel: taken/missed/low-stock/refill alerts
# are emailed to every active caregiver/family recipient configured in
# Settings, sent FROM this mailbox. Same rule as above - never hardcode
# the real values here or paste them into chat. Set these as environment
# variables (see .env.example), or in local_settings.py:
#     SMTP_HOST = "smtp.gmail.com"
#     SMTP_PORT = 587
#     SMTP_USERNAME = "your-app-gmail-address@gmail.com"
#     SMTP_PASSWORD = "xxxx xxxx xxxx xxxx"
#     SENDER_EMAIL = "your-app-gmail-address@gmail.com"
# For Gmail, SMTP_PASSWORD must be a 16-character "App Password" (not
# your normal Gmail password) - see local_settings.py.example for how to
# generate one.
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")

try:
    from local_settings import SMTP_HOST  # noqa: F811
except ImportError:
    pass

try:
    from local_settings import SMTP_PORT  # noqa: F811
except ImportError:
    pass

try:
    from local_settings import SMTP_USERNAME  # noqa: F811
except ImportError:
    pass

try:
    from local_settings import SMTP_PASSWORD  # noqa: F811
except ImportError:
    pass

try:
    from local_settings import SENDER_EMAIL  # noqa: F811
except ImportError:
    pass

if not SENDER_EMAIL:
    SENDER_EMAIL = SMTP_USERNAME

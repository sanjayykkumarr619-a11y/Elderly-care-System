"""
Real SMS delivery to a caregiver/family member's mobile number, via the
Fast2SMS "Quick SMS" REST API (https://www.fast2sms.com). Uses only
Python's standard-library urllib - no third-party SDK.

The API key is never hardcoded here. It is read from the FAST2SMS_API_KEY
environment variable, or from config.FAST2SMS_API_KEY as a fallback for
local development (see config.py). If no key is configured, send_sms()
simply logs and reports failure instead of raising, so the rest of the
app keeps working without it.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

import config

FAST2SMS_URL = "https://www.fast2sms.com/dev/bulkV2"


def _digits_only(mobile):
    return "".join(ch for ch in mobile if ch.isdigit())[-10:]


def send_sms(mobile, message):
    """Returns (success: bool, detail: str). Never raises - any network
    or API error is caught and reported as a failure so a flaky SMS
    gateway can never break medication tracking."""
    api_key = config.FAST2SMS_API_KEY
    if not api_key:
        print(f"[sms] FAST2SMS_API_KEY not configured - skipping SMS to {mobile}: {message}")
        return False, "SMS gateway not configured"

    number = _digits_only(mobile)
    if len(number) != 10:
        return False, f"'{mobile}' is not a valid 10-digit mobile number"

    payload = {
        "route": "q",
        "message": message[:900],
        "language": "english",
        "flash": 0,
        "numbers": number,
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(
        FAST2SMS_URL,
        data=data,
        method="POST",
        headers={
            "authorization": api_key,
            "Content-Type": "application/x-www-form-urlencoded",
            "Cache-Control": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            body = json.loads(response.read().decode("utf-8"))
            if body.get("return") is True:
                return True, "sent"
            return False, str(body)
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8")
        except Exception:
            detail = str(exc)
        print(f"[sms] Fast2SMS HTTP error sending to {mobile}: {detail}")
        return False, detail
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"[sms] Fast2SMS request failed for {mobile}: {exc}")
        return False, str(exc)

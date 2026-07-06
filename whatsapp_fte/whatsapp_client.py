"""WhatsApp Cloud API client (shared delivery layer).

A single, importable place that actually talks to the WhatsApp Cloud API. Both
the MCP server (for the `adk web` demo) and the live webhook product import this,
so there is ONE code path for sending messages / checking status.

Credentials are read from the project .env at import time (never hard-coded):
  WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID
"""

import os

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Load the single source of truth: whatsapp_fte/.env (same file ADK uses).
_HERE = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(_HERE, ".env"))

GRAPH_API_VERSION = "v22.0"  # WhatsApp Cloud API (Graph API) version

# This ISP has flaky/intermittent connectivity to graph.facebook.com: DNS hands
# out several edge IPs and some time out on connect (30s hangs) while others
# connect in ~2s. So use a SHORT connect timeout (fail a dead IP fast) plus
# automatic retries, which re-resolve DNS and usually land on a reachable IP.
_CONNECT_TIMEOUT = 8   # seconds to establish the TCP connection
_READ_TIMEOUT = 30     # seconds to wait for the response body
_TIMEOUT = (_CONNECT_TIMEOUT, _READ_TIMEOUT)

_session = requests.Session()
_session.mount(
    "https://",
    HTTPAdapter(max_retries=Retry(
        total=5, connect=5, read=2, backoff_factor=1.0,
        status_forcelist=(500, 502, 503, 504),
    )),
)


def _creds():
    """Read credentials fresh each call (token is regenerated ~every 24h)."""
    return os.getenv("WHATSAPP_ACCESS_TOKEN"), os.getenv("WHATSAPP_PHONE_NUMBER_ID")


def send_text(recipient: str, message: str) -> dict:
    """Send a free-form text WhatsApp message via the Cloud API.

    Args:
        recipient: Phone number in international format (with or without '+').
                   Must be a verified test recipient while in sandbox.
        message: The text body to send.

    Note: free-form text is only delivered inside the 24-hour customer service
    window (after the customer has messaged the business first).
    """
    token, phone_id = _creds()
    if not token or not phone_id:
        return {"status": "error", "detail": "WhatsApp credentials missing in .env"}

    to = recipient.lstrip("+")  # Cloud API expects the number without '+'
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": message},
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        resp = _session.post(url, json=payload, headers=headers, timeout=_TIMEOUT)
        data = resp.json()
        if resp.status_code == 200:
            return {"status": "sent", "to": to, "whatsapp_response": data}
        return {"status": "error", "code": resp.status_code, "detail": data}
    except Exception as exc:  # network / API failure — report, don't crash
        return {"status": "error", "detail": str(exc)}


def get_status() -> dict:
    """Verify the WhatsApp connection is live (token valid, number active)."""
    token, phone_id = _creds()
    if not token or not phone_id:
        return {"status": "error", "detail": "WhatsApp credentials missing in .env"}

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_id}"
    params = {"fields": "display_phone_number,verified_name,quality_rating"}
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = _session.get(url, params=params, headers=headers, timeout=_TIMEOUT)
        data = resp.json()
        if resp.status_code == 200:
            return {"status": "online", "details": data}
        return {"status": "error", "code": resp.status_code, "detail": data}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}

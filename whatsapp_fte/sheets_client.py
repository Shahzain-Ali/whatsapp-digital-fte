"""Google Sheets client — the booking backend.

Reads the doctor's weekly availability and the confirmed bookings, and appends new
confirmed bookings. One shared authorized client (opened lazily). The service-account
key path + sheet id come from .env (GOOGLE_SA_KEY_PATH, BOOKING_SHEET_ID); the key
file lives in .secrets/ and its contents are never read/printed here beyond auth.
"""
import os
from datetime import date, datetime

from dotenv import load_dotenv

_HERE = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(_HERE, ".env"))

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
_ACTIVE = ("confirmed", "pending")

_sheet = None


def _open():
    """Authorise and open the spreadsheet once, then reuse it."""
    global _sheet
    if _sheet is None:
        from google.oauth2.service_account import Credentials
        import gspread

        key_path = os.getenv("GOOGLE_SA_KEY_PATH")
        sheet_id = os.getenv("BOOKING_SHEET_ID")
        if not key_path or not sheet_id:
            raise RuntimeError("GOOGLE_SA_KEY_PATH / BOOKING_SHEET_ID missing in .env")
        creds = Credentials.from_service_account_file(key_path, scopes=SCOPES)
        _sheet = gspread.authorize(creds).open_by_key(sheet_id)
    return _sheet


def get_availability() -> dict:
    """Return {Day: {Open, Close, SlotMinutes}} from the Availability tab."""
    rows = _open().worksheet("Availability").get_all_records()
    out = {}
    for r in rows:
        day = str(r.get("Day", "")).strip()
        if day:
            out[day] = {
                "Open": str(r.get("Open", "")),
                "Close": str(r.get("Close", "")),
                "SlotMinutes": int(r.get("SlotMinutes", 30) or 30),
            }
    return out


def get_bookings() -> list:
    """Return all rows from the Bookings tab as a list of dicts."""
    return _open().worksheet("Bookings").get_all_records()


def append_booking(appt_date: str, time: str, name: str, phone: str,
                   status: str = "confirmed", service: str = "") -> None:
    """Append one confirmed booking row to the Bookings tab.

    Header-aware: values are placed under whatever columns the sheet actually has
    (so an added "Service" column works wherever it sits). RAW input so date/time/
    phone stay as literal text ("2026-07-06", "09:00") — keeps reads predictable.
    """
    ws = _open().worksheet("Bookings")
    header = ws.row_values(1)
    data = {
        "Date": appt_date,
        "Time": time,
        "PatientName": name,
        "Service": service,
        "Phone": phone,
        "Status": status,
        "CreatedAt": datetime.now().isoformat(timespec="seconds"),
    }
    row = [str(data.get(col, "")) for col in header]
    ws.append_row(row, value_input_option="RAW")


def _parse_date(s: str):
    """Parse a booking date cell to a date object (ISO first, common fallbacks)."""
    s = str(s or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def has_upcoming_booking(phone: str) -> bool:
    """Guardrail: does this phone have a confirmed booking that is TODAY or later?

    Past appointments don't count — once the date passes the customer can book
    again (no manual 'arrived' marking needed). Pending bookings are handled
    separately in booking_store.
    """
    today = date.today()
    try:
        for b in get_bookings():
            if str(b.get("Phone")) != str(phone):
                continue
            if str(b.get("Status", "")).lower() not in _ACTIVE:
                continue
            d = _parse_date(b.get("Date", ""))
            if d and d >= today:
                return True
        return False
    except Exception as e:
        # Fail open (don't block a real customer), but make the failure visible.
        print(f"[guardrail] sheet read failed, allowing booking: {e}", flush=True)
        return False

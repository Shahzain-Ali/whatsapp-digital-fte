"""Appointment-slot availability logic (pure functions, no I/O).

Given the doctor's weekly availability and current bookings, work out which slots
are free, whether a requested slot is available, and the next open slots. Kept
I/O-free so it can be unit-tested without Google Sheets.

Data shapes:
  availability: {"Monday": {"Open": "09:00", "Close": "17:00", "SlotMinutes": 30}, ...}
  bookings:     [{"Date": "2026-07-06", "Time": "17:00", "Status": "confirmed"}, ...]
Dates are ISO "YYYY-MM-DD"; times normalise to 24-hour "HH:MM".
"""
from datetime import datetime, timedelta

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_ACTIVE = ("confirmed", "pending")  # statuses that occupy a slot

# Google Sheets may hand a time cell back in several shapes ("09:00", "9:00:00",
# "9:00:00 AM"), so accept them all and normalise to "HH:MM".
_TIME_FORMATS = ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M:%S %p", "%I:%M%p", "%I %p", "%I%p")


def normalize_time(t: str) -> str:
    """Normalise a time to 24-hour 'HH:MM'. Returns '' if unparseable."""
    t = str(t or "").strip().upper().replace(".", "")
    if not t:
        return ""
    for fmt in _TIME_FORMATS:
        try:
            return datetime.strptime(t, fmt).strftime("%H:%M")
        except ValueError:
            continue
    return ""


def weekday_name(date_iso: str) -> str:
    return DAYS[datetime.strptime(date_iso, "%Y-%m-%d").weekday()]


def day_slots(avail_row: dict) -> list[str]:
    """All slot start times 'HH:MM' for a day given its Open/Close/SlotMinutes."""
    open_s = normalize_time(avail_row.get("Open", ""))
    close_s = normalize_time(avail_row.get("Close", ""))
    if not open_s or not close_s:
        return []
    step = int(avail_row.get("SlotMinutes", 30) or 30)
    cur = datetime.strptime(open_s, "%H:%M")
    end = datetime.strptime(close_s, "%H:%M")
    slots = []
    while cur < end:
        slots.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=step)
    return slots


def free_slots(date_iso: str, availability: dict, bookings: list) -> list[str]:
    """Free 'HH:MM' slots for a date = the day's slots minus already-taken ones."""
    row = availability.get(weekday_name(date_iso))
    if not row:  # clinic closed that day
        return []
    taken = {
        normalize_time(b.get("Time"))
        for b in bookings
        if str(b.get("Date")) == date_iso and str(b.get("Status", "")).lower() in _ACTIVE
    }
    return [s for s in day_slots(row) if s not in taken]


def is_available(date_iso: str, time_hhmm: str, availability: dict, bookings: list) -> bool:
    return normalize_time(time_hhmm) in free_slots(date_iso, availability, bookings)


def suggest_alternatives(date_iso: str, availability: dict, bookings: list,
                         max_slots: int = 3, look_days: int = 7) -> list[tuple[str, str]]:
    """Next open (date, time) pairs from date_iso onward (across up to look_days days)."""
    out: list[tuple[str, str]] = []
    start = datetime.strptime(date_iso, "%Y-%m-%d")
    for i in range(look_days):
        di = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        for s in free_slots(di, availability, bookings):
            out.append((di, s))
            if len(out) >= max_slots:
                return out
    return out

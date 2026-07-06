"""Pending-booking store for cross-channel Human-in-the-Loop (HITL) approval.

When a customer asks to book, the AI does NOT confirm on its own. It records a
PENDING booking here (with the exact date + time) and notifies the business owner
on WhatsApp. The owner replies YES/NO from their own phone; the webhook resolves
the booking, writes it to the Bookings Google Sheet, and tells the customer.

In-memory (single-process). Confirmed bookings live permanently in the Sheet.
"""

import threading

_lock = threading.Lock()
# booking_id -> {customer_name, customer_phone, date, time, appointment_time, status}
_pending: dict[str, dict] = {}
_counter = 0


def add_pending(customer_name: str, customer_phone: str, date: str, time: str,
                service: str = "") -> str:
    """Record a new pending booking (date/time/service structured) and return its id."""
    global _counter
    with _lock:
        _counter += 1
        bid = str(_counter)
        _pending[bid] = {
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "date": date,
            "time": time,
            "service": service,
            "appointment_time": f"{date} at {time}",
            "status": "pending",
        }
        return bid


def get(bid: str) -> dict | None:
    with _lock:
        return _pending.get(bid)


def latest_pending_id() -> str | None:
    """The oldest still-pending booking (so the owner can just reply 'YES')."""
    with _lock:
        for bid, b in _pending.items():
            if b["status"] == "pending":
                return bid
        return None


def has_pending_for_phone(phone: str) -> bool:
    """Guardrail: does this phone already have a pending booking awaiting approval?"""
    with _lock:
        return any(
            b["customer_phone"] == phone and b["status"] == "pending"
            for b in _pending.values()
        )


def resolve(bid: str, approved: bool) -> dict | None:
    """Mark a booking approved/rejected. Returns the booking dict (or None)."""
    with _lock:
        booking = _pending.get(bid)
        if not booking or booking["status"] != "pending":
            return None
        booking["status"] = "approved" if approved else "rejected"
        return booking


def all_pending() -> dict:
    with _lock:
        return {k: v for k, v in _pending.items() if v["status"] == "pending"}

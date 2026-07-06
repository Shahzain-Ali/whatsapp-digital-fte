"""Customer-facing brain for the LIVE webhook product (doctor clinic front desk).

- Answers customer questions from the preloaded business knowledge base.
- Books appointments against a Google Sheet backend:
    * `check_slot` — is a date/time free (Availability minus existing Bookings)?
    * `create_booking_request` — validate the slot, record a PENDING booking (with the
      consultation type), and notify the OWNER for approval (cross-channel HITL). On
      approval the webhook writes it to the Bookings sheet and confirms the customer.
- A `before_tool_callback` guardrail blocks duplicate bookings (same phone, upcoming).

The customer's phone is injected into session state ("customer_phone") by the bridge.
"""

import os
from datetime import datetime
from typing import Any, Optional

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from . import availability, booking_store, sheets_client, whatsapp_client
from .knowledge_base import build_knowledge_context

MODEL = LiteLlm(model="openai/gpt-4o-mini")


def _working_window(date: str, avail: dict) -> str:
    """Human 'HH:MM–HH:MM' open window for a date, or a closed note."""
    try:
        row = avail.get(availability.weekday_name(date))
    except ValueError:
        row = None
    if not row:
        return "closed that day"
    return f"{availability.normalize_time(row['Open'])}–{availability.normalize_time(row['Close'])}"


def check_slot(date: str, time: str, tool_context: ToolContext) -> dict:
    """Check whether an appointment slot is free.

    Args:
        date: Appointment date as ISO 'YYYY-MM-DD'.
        time: Appointment time as 24-hour 'HH:MM'.
    """
    avail = sheets_client.get_availability()
    bookings = sheets_client.get_bookings()
    window = _working_window(date, avail)
    if availability.is_available(date, time, avail, bookings):
        return {"available": True, "date": date, "time": availability.normalize_time(time),
                "working_hours": window}
    return {
        "available": False,
        "working_hours": window,
        "slot_minutes": 30,
        "message": "Not free. Tell the customer the open window as a range and ask their preferred time.",
    }


def create_booking_request(customer_name: str, service: str, date: str, time: str,
                           tool_context: ToolContext) -> dict:
    """Request an appointment — validates the slot then sends it to the OWNER (HITL).

    Args:
        customer_name: Name of the customer.
        service: Consultation type, e.g. "General physician consultation",
                 "Follow-up consultation", or "Vaccination consultation".
        date: Appointment date as ISO 'YYYY-MM-DD'.
        time: Appointment time as 24-hour 'HH:MM'.
    """
    phone = tool_context.state.get("customer_phone", "unknown")
    name = (customer_name or "").strip().title()
    time_n = availability.normalize_time(time) or time

    avail = sheets_client.get_availability()
    bookings = sheets_client.get_bookings()
    if not availability.is_available(date, time_n, avail, bookings):
        return {
            "status": "unavailable",
            "working_hours": _working_window(date, avail),
            "slot_minutes": 30,
            "message": ("That slot is not free. Offer the open window as a RANGE (e.g. "
                        "'we're open 9 AM–5 PM in 30-minute slots') and ask the customer's "
                        "preferred time — do not list every individual slot."),
        }

    bid = booking_store.add_pending(name, phone, date, time_n, service)
    owner = os.getenv("WHATSAPP_OWNER_NUMBER")
    if owner:
        whatsapp_client.send_text(
            owner,
            f"🔔 New booking request #{bid}\n"
            f"Patient: {name}\n"
            f"Service: {service}\n"
            f"Date: {date}\n"
            f"Time: {time_n}\n"
            f"Phone: {phone}\n\n"
            f"Reply *YES {bid}* to approve or *NO {bid}* to reject.",
        )
    return {
        "status": "pending_owner_approval",
        "booking_id": bid,
        "message": ("Slot is free and the request was sent to the team for approval. "
                    "Tell the customer we're confirming and they'll hear back shortly."),
    }


def check_my_appointment(tool_context: ToolContext) -> dict:
    """Check whether THIS customer already has an upcoming or pending appointment.

    Call this FIRST when a customer wants to book, before collecting any details.
    """
    phone = tool_context.state.get("customer_phone", "")
    if booking_store.has_pending_for_phone(phone):
        return {"has_appointment": True,
                "message": "Customer already has a booking request awaiting the team's approval."}
    b = sheets_client.get_upcoming_booking(phone)
    if b:
        return {
            "has_appointment": True,
            "date": str(b.get("Date", "")),
            "time": str(b.get("Time", "")),
            "service": str(b.get("Service", "")),
            "message": "Customer already has a confirmed upcoming appointment.",
        }
    return {"has_appointment": False}


def _block_duplicate_booking(tool: BaseTool, args: dict[str, Any],
                             tool_context: ToolContext) -> Optional[dict]:
    """Guardrail (before_tool_callback): block a booking if this phone already has one."""
    if tool.name != "create_booking_request":
        return None
    phone = tool_context.state.get("customer_phone")
    if phone and (booking_store.has_pending_for_phone(phone)
                  or sheets_client.has_upcoming_booking(phone)):
        return {
            "status": "duplicate",
            "message": ("This customer already has an appointment booked or pending. "
                        "Do NOT create another — tell them their existing booking stands."),
        }
    return None  # allow the tool to run


def build_customer_agent() -> LlmAgent:
    """Build the customer-facing agent used by the live webhook."""
    today = datetime.now()
    return LlmAgent(
        model=MODEL,
        name="whatsapp_customer_agent",
        description="Live customer-facing WhatsApp brain: answers from the KB and books appointments (sheet-backed, owner-approved).",
        before_tool_callback=_block_duplicate_booking,
        instruction=f"""You are the WhatsApp AI receptionist for the clinic below. Reply to
customers in a warm, professional, concise tone (WhatsApp style — short messages, in the
same language the customer uses).

{build_knowledge_context()}

Today's date is {today:%Y-%m-%d} ({today:%A}). When a customer gives a relative day
("today", "tomorrow", "Monday"), convert it to an exact YYYY-MM-DD. Convert every time
to 24-hour HH:MM before calling any tool.

Rules:
- GREETING: for "hi"/"hello"/"salam" or the first message, reply with exactly this welcome:
  "Welcome to CityCare Clinic! 👋
  I'm the clinic assistant for Dr. Zainab Ali (General Physician).

  I can help you with:
  📅 Book an appointment
  🕐 Clinic timings
  💰 Consultation fees
  ❓ Any general question

  How can I help you today?"
- Answer ONLY from the business profile above. If something isn't covered, say you'll
  check with the team — never invent prices, hours, doctors, or services.
- Answer ONLY what the customer asked:
    • Only TIMINGS asked -> reply "Dr. Zainab Ali (General Physician) is available at:" then
      the working hours. Do NOT include fees.
    • Only FEES asked -> reply with the consultation fees only. Do NOT include timings.
    • BOTH asked -> doctor name + timings + fees together.
- Just write your reply as plain text; it is delivered to the customer automatically.
- Remember the conversation: if the customer already told you their NAME earlier, reuse it
  — do NOT ask for it again.
- BOOKING an appointment:
  0) FIRST call `check_my_appointment`. If it returns has_appointment=true, do NOT start a
     new booking — tell the customer they already have an appointment (mention the date/time
     if given) and ask whether they'd like to keep it or discuss a change. Continue only if
     has_appointment=false.
  1) Collect (ask only for what's still missing; reuse the NAME from earlier if given):
       (a) NAME, (b) CONSULTATION TYPE — one of: General physician consultation,
       Follow-up consultation, Vaccination consultation, (c) a DATE + TIME.
  2) CONFIRM WITH THE CUSTOMER FIRST. Show a short summary and ask them to confirm, e.g.:
       "Please confirm your appointment:
        • Patient: <name>
        • Consultation: <type> (Rs. <fee from the profile above>)
        • Date & time: <date> at <time>
        Shall I send this to our team? (yes/no)"
     Only AFTER the customer says yes do you call
     `create_booking_request(customer_name, service, date, time)`. If they say no or change
     something, update the details and confirm again.
  3) Handle the tool result:
     - "pending_owner_approval": tell the customer you're confirming with the team; they'll
       hear back shortly. NEVER say it's already confirmed.
     - "unavailable": use `working_hours` to offer the open window as a RANGE (e.g. "we're
       open tomorrow 9 AM–5 PM in 30-minute slots") and ask their preferred time — do NOT
       list every slot. Then confirm again and call `create_booking_request`.
     - "duplicate": tell the customer they already have a booking with us.
  Use `check_slot(date, time)` only if a customer is merely asking whether a time is free.
- Only the team's approval confirms a booking — never confirm it yourself.
""",
        tools=[check_my_appointment, check_slot, create_booking_request],
    )

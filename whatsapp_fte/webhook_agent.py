"""Customer-facing brain for the LIVE webhook product (doctor clinic front desk).

- Answers customer questions from the preloaded business knowledge base.
- Books appointments against a Google Sheet backend:
    * `check_slot` — is a date/time free (Availability minus existing Bookings)?
    * `create_booking_request` — validate the slot, then EITHER confirm end-to-end
      (default: write the confirmed booking straight to the Bookings sheet) OR, when
      REQUIRE_APPROVAL=true, record a PENDING booking and notify the OWNER for approval
      (cross-channel HITL) — on YES the webhook writes it to the sheet and confirms.
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
from google.genai import types

from . import availability, booking_store, sheets_client, whatsapp_client
from .knowledge_base import build_knowledge_context
from .prompt_loader import load_instruction_from_file

MODEL = LiteLlm(model="openai/gpt-4o-mini")

# Cap the length (and cost) of every reply. This is a per-response limit — ADK's
# generate_content_config.max_output_tokens maps to the model's max output tokens.
MAX_OUTPUT_TOKENS = 500

# Human-in-the-loop (HITL) toggle. Default OFF -> the AI books end-to-end (writes the
# confirmed booking straight to the sheet and confirms the customer immediately).
# Set REQUIRE_APPROVAL=true to restore the owner-approval flow: the booking stays
# PENDING until the owner replies YES/NO on WhatsApp. The slot check and the
# duplicate-booking guardrail run in BOTH modes.
REQUIRE_APPROVAL = os.getenv("REQUIRE_APPROVAL", "false").strip().lower() == "true"


def _customer_phone(tool_context: ToolContext) -> str:
    """The customer's phone from session state, or DEMO_CUSTOMER_PHONE as a fallback.

    In production the webhook bridge always seeds `customer_phone`, so the fallback is
    never used there. It only applies when running via `adk web` (which has no per-
    customer phone) — set DEMO_CUSTOMER_PHONE in .env to a number that has a booking in
    the sheet, so the duplicate check / guardrail can be demoed in the adk web UI.
    """
    return tool_context.state.get("customer_phone") or os.getenv("DEMO_CUSTOMER_PHONE", "")


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
    """Book an appointment — validates the slot, then either confirms it end-to-end
    (default) or, when REQUIRE_APPROVAL=true, sends it to the OWNER for approval (HITL).

    Args:
        customer_name: Name of the customer.
        service: Consultation type, e.g. "General physician consultation",
                 "Follow-up consultation", or "Vaccination consultation".
        date: Appointment date as ISO 'YYYY-MM-DD'.
        time: Appointment time as 24-hour 'HH:MM'.
    """
    phone = _customer_phone(tool_context) or "unknown"
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

    if REQUIRE_APPROVAL:
        # HITL mode: record a PENDING booking and ask the owner to approve on WhatsApp.
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

    # Auto mode (default): confirm end-to-end — write straight to the Bookings sheet.
    try:
        sheets_client.append_booking(date, time_n, name, phone, "confirmed", service=service)
    except Exception as e:
        print(f"[booking] sheet write FAILED: {e}", flush=True)
        return {
            "status": "error",
            "message": ("Could not save the booking just now. Tell the customer there was a "
                        "temporary issue and the team will follow up shortly."),
        }
    return {
        "status": "confirmed",
        "message": (f"Booking saved. Tell the customer their {service} appointment on "
                    f"{date} at {time_n} is CONFIRMED. See you then!"),
    }


def check_my_appointment(tool_context: ToolContext) -> dict:
    """Check whether THIS customer already has an upcoming or pending appointment.

    Call this FIRST when a customer wants to book, before collecting any details.
    """
    phone = _customer_phone(tool_context)
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
    phone = _customer_phone(tool_context)
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
    # Load the system prompt from its own file, then fill the dynamic parts
    # (business knowledge base + today's date) into the template placeholders.
    instruction = (
        load_instruction_from_file("customer_agent.txt")
        .replace("{{KNOWLEDGE_BASE}}", build_knowledge_context())
        .replace("{{TODAY_DATE}}", today.strftime("%Y-%m-%d"))
        .replace("{{TODAY_DAY}}", today.strftime("%A"))
    )
    return LlmAgent(
        model=MODEL,
        name="whatsapp_customer_agent",
        description="Live customer-facing WhatsApp brain: answers from the KB and books appointments end-to-end (sheet-backed; owner-approval optional via REQUIRE_APPROVAL).",
        before_tool_callback=_block_duplicate_booking,
        generate_content_config=types.GenerateContentConfig(max_output_tokens=MAX_OUTPUT_TOKENS),
        instruction=instruction,
        tools=[check_my_appointment, check_slot, create_booking_request],
    )

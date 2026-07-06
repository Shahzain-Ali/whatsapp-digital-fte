"""WhatsApp Agent.

The live "employee": it answers customer questions from the preloaded business
knowledge base and sends replies through the WhatsApp Cloud API (via the MCP
server). Sensitive actions (booking an appointment) require OWNER approval first
— our Human-in-the-Loop (HITL) security control.

Multi-agent role: the orchestrator delegates here for CUSTOMER conversations.
"""

import os
import sys

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.adk.tools.tool_context import ToolContext
from mcp import StdioServerParameters

from ..knowledge_base import build_knowledge_context

MODEL = LiteLlm(model="openai/gpt-4o-mini")

# Absolute path to the WhatsApp MCP server script (ADK launches it over stdio).
_HERE = os.path.abspath(os.path.dirname(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
MCP_SERVER_PATH = os.path.join(_PROJECT_ROOT, "whatsapp_mcp_server", "server.py")


def book_appointment(
    customer_name: str,
    appointment_time: str,
    tool_context: ToolContext,
) -> dict:
    """Book an appointment for a customer — REQUIRES owner approval (HITL).

    This is a sensitive action (a real commitment on the business's behalf), so
    the agent pauses and asks the owner to approve or reject before confirming.

    Args:
        customer_name: Name of the customer requesting the appointment.
        appointment_time: Requested date/time, e.g. "Tomorrow 5 PM".
    """
    confirmation = tool_context.tool_confirmation

    # First call: no decision yet -> pause and request the owner's approval.
    if not confirmation:
        tool_context.request_confirmation(
            hint=(
                f"Approve booking for {customer_name} at {appointment_time}? "
                "Reply confirmed=true to approve or confirmed=false to reject."
            ),
            payload={"approved": False},
        )
        return {"status": "pending_owner_approval",
                "message": f"Waiting for owner to approve {customer_name}'s booking at {appointment_time}."}

    # Owner rejected.
    if not confirmation.confirmed:
        return {"status": "rejected",
                "message": "The owner did not approve this appointment."}

    # Owner approved -> finalise the booking.
    return {"status": "confirmed",
            "message": f"Appointment confirmed for {customer_name} at {appointment_time}."}


whatsapp_agent = LlmAgent(
    model=MODEL,
    name="whatsapp_agent",
    description=(
        "Handles live CUSTOMER conversations on WhatsApp: answers questions from the "
        "business knowledge base and books appointments (with owner approval)."
    ),
    instruction=f"""You are the WhatsApp AI employee for the business below. You reply to
customers in a warm, professional, concise tone (WhatsApp style — short messages).

{build_knowledge_context()}

Rules:
- Answer ONLY from the business profile above. If something isn't covered, say you'll
  check with the team — never make up prices, hours, or services.
- To actually deliver a reply to the customer on WhatsApp, call `send_whatsapp_message`
  with their phone number and your message text.
- If a customer wants to BOOK an appointment, call `book_appointment`. This needs the
  owner's approval first — tell the customer you're confirming with the team, and only
  send a confirmation once it is approved.
- Use `check_whatsapp_status` if asked whether the service is online.
""",
    tools=[
        # WhatsApp actions come from our MCP server (send message, check status).
        McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,  # same interpreter/venv -> mcp + requests available
                    args=[MCP_SERVER_PATH],
                ),
                # WSL /mnt (Windows drive) is slow to boot the subprocess + import mcp,
                # so allow more time than the ~5s default to avoid connection timeouts.
                timeout=60,
            ),
        ),
        # Sensitive action guarded by Human-in-the-Loop approval.
        book_appointment,
    ],
)

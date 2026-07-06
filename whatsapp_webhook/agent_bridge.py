"""Bridge between the WhatsApp webhook and the ADK agent.

Holds one long-lived ADK Runner and turns an incoming customer message into a
reply string. Each customer's phone number is its own session, so the AI keeps
short-term memory of that conversation (session_id = phone number).
"""

import sys
import os

# Make the whatsapp_fte package importable when uvicorn runs this from anywhere.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from whatsapp_fte.webhook_agent import build_customer_agent  # noqa: E402

APP_NAME = "whatsapp_fte"

_runner = InMemoryRunner(agent=build_customer_agent(), app_name=APP_NAME)


async def _ensure_session(phone: str):
    """Get (or lazily create) the per-customer session, seeding their phone number."""
    session = await _runner.session_service.get_session(
        app_name=APP_NAME, user_id=phone, session_id=phone
    )
    if session is None:
        session = await _runner.session_service.create_session(
            app_name=APP_NAME,
            user_id=phone,
            session_id=phone,
            state={"customer_phone": phone},
        )
    return session


async def get_reply(phone: str, text: str) -> str:
    """Run the agent for one customer message and return the final reply text."""
    await _ensure_session(phone)
    msg = types.Content(role="user", parts=[types.Part(text=text)])

    final_text = ""
    async for event in _runner.run_async(user_id=phone, session_id=phone, new_message=msg):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if getattr(part, "text", None) and part.text.strip():
                    final_text = part.text.strip()

    return final_text or "Thanks for your message! Our team will get back to you shortly."

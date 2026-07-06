"""ADK entry point for `adk web` / `adk run` — debugging & demo only.

The LIVE product runs through the FastAPI webhook (whatsapp_webhook/), which builds
its own agent via `build_customer_agent()`. This module exposes that SAME agent as
`root_agent` so the conversation and every tool call can be inspected in the adk web UI
(great for debugging and for the demo video).

Heads-up: adk web does not inject `customer_phone` into session state (the webhook
bridge does that per customer). So inside adk web the booking tools see an empty phone —
the Q&A, tool calls, and guardrail are fully visible, but the cross-channel owner-approval
step is webhook-only and won't complete here.
"""

from .webhook_agent import build_customer_agent

# adk web / adk run discover this module-level `root_agent`.
root_agent = build_customer_agent()

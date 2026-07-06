# The `whatsapp_fte` package: the live customer agent + booking backend used by
# the WhatsApp webhook (see whatsapp_webhook/). The real product runs via FastAPI;
# `agent.py` additionally exposes `root_agent` so `adk web` can inspect the same
# agent for debugging and the demo video (ADK convention: `from . import agent`).
from . import agent  # noqa: F401

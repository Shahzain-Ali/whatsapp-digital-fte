"""WhatsApp MCP Server.

Exposes WhatsApp Cloud API actions as MCP tools so the ADK WhatsApp agent (in the
`adk web` demo) can send real messages. ADK connects to this script over stdio via
`McpToolset` (see whatsapp_fte/sub_agents/whatsapp_agent.py).

The actual API calls live in whatsapp_fte/whatsapp_client.py — the SAME delivery
layer the live webhook uses — so there is one code path everywhere.

Tools:
  - send_whatsapp_message(recipient, message): send a free-form text reply.
  - check_whatsapp_status(): verify the connection / that the AI employee is "online".
"""

import os
import sys

from mcp.server.fastmcp import FastMCP

# This server runs as its own subprocess, so add the project root to sys.path to
# import the shared client package (whatsapp_fte.whatsapp_client loads the .env).
_PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT not in sys.path:
    sys.path.insert(0, _PROJECT)

from whatsapp_fte import whatsapp_client  # noqa: E402

mcp = FastMCP("whatsapp")


@mcp.tool()
def send_whatsapp_message(recipient: str, message: str) -> dict:
    """Send a free-form text WhatsApp message to a customer via the WhatsApp Cloud API.

    Args:
        recipient: Customer phone number in international format (e.g. "923001234567").
                   Must be a verified test recipient while in sandbox.
        message: The text body to send.

    Note: free-form text is only delivered inside the 24-hour customer service
    window (after the customer has messaged the business first).
    """
    return whatsapp_client.send_text(recipient, message)


@mcp.tool()
def check_whatsapp_status() -> dict:
    """Verify the WhatsApp connection is live (token valid, number active)."""
    return whatsapp_client.get_status()


if __name__ == "__main__":
    # Run as an MCP server over stdio (how ADK's McpToolset launches it).
    mcp.run(transport="stdio")

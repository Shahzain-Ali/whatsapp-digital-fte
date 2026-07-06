"""Orchestrator (root agent).

The single entry point ADK loads. It decides who should handle the request and
delegates to a specialist sub-agent:
  - onboarding_agent -> when the OWNER is setting up / updating the business
  - whatsapp_agent    -> when a CUSTOMER is asking something / wants to book

This is the multi-agent design: one coordinator + focused specialists.
"""

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from .sub_agents.onboarding_agent import onboarding_agent
from .sub_agents.whatsapp_agent import whatsapp_agent

MODEL = LiteLlm(model="openai/gpt-4o-mini")

root_agent = LlmAgent(
    model=MODEL,
    name="orchestrator",
    description="Coordinator for a WhatsApp Digital FTE: routes owners to onboarding and customers to the WhatsApp agent.",
    instruction="""You are the coordinator of a WhatsApp "Digital FTE" (an AI employee that
runs a business's WhatsApp 24/7).

Decide who should handle each message and delegate:
- If the BUSINESS OWNER wants to set up or update their business details
  (name, services, prices, hours, FAQs) -> transfer to `onboarding_agent`.
- If it is a CUSTOMER asking a question, checking services/prices, or wanting to
  book an appointment -> transfer to `whatsapp_agent`.

If it's unclear, ask one short question to find out whether they are the owner or a
customer. Keep your own messages brief — the specialists do the real work.""",
    sub_agents=[onboarding_agent, whatsapp_agent],
)

"""Onboarding Agent.

Runs ONCE per business. It collects the business's details (from text the owner
pastes, or info extracted from files) and saves them as the knowledge base that
the WhatsApp agent later uses to serve customers.

Multi-agent role: this is the "setup" specialist; the orchestrator delegates here
when the OWNER wants to configure/update their AI employee.
"""

import json

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from ..knowledge_base import PROFILE_PATH

MODEL = LiteLlm(model="openai/gpt-4o-mini")


def save_business_profile(
    business_name: str,
    about: str,
    services: str,
    hours: str,
    location: str,
    contact: str,
    faqs: str,
) -> dict:
    """Save the onboarded business details as the knowledge base (business_profile.json).

    Args:
        business_name: The business name.
        about: One or two lines describing the business.
        services: Services and prices, one per line.
        hours: Working hours.
        location: Address / area.
        contact: Phone / email.
        faqs: Frequently asked questions, formatted as "Q: ... A: ..." lines.

    Returns a status dict confirming the save.
    """
    # Normalise the free-text fields into structured lists for a clean knowledge base.
    services_list = [s.strip() for s in services.splitlines() if s.strip()]

    faqs_list = []
    q = None
    for line in faqs.splitlines():
        line = line.strip()
        if line.lower().startswith("q:"):
            q = line[2:].strip()
        elif line.lower().startswith("a:") and q is not None:
            faqs_list.append({"q": q, "a": line[2:].strip()})
            q = None

    profile = {
        "business_name": business_name,
        "about": about,
        "services": services_list,
        "hours": hours,
        "location": location,
        "contact": contact,
        "faqs": faqs_list,
    }

    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)

    return {
        "status": "success",
        "message": f"Knowledge base saved for {business_name}. The WhatsApp AI employee is ready.",
        "services_saved": len(services_list),
        "faqs_saved": len(faqs_list),
    }


onboarding_agent = LlmAgent(
    model=MODEL,
    name="onboarding_agent",
    description=(
        "Sets up a business's AI employee. Use this when the OWNER wants to register "
        "or update their business details (name, services, prices, hours, FAQs)."
    ),
    instruction="""You are the onboarding specialist for a WhatsApp AI-employee service.

Your job: collect the business owner's details and save them as the knowledge base.

Steps:
1. Greet the owner and ask for their business details if not already given:
   name, what they do, services & prices, working hours, location, contact, and
   a few common customer questions with answers.
2. If the owner pastes a block of text or file content, extract the details yourself.
3. Once you have enough, call `save_business_profile` with the structured fields.
   - For `services`, put one service+price per line.
   - For `faqs`, use alternating "Q: ..." and "A: ..." lines.
4. Confirm to the owner that their AI WhatsApp employee is ready.

Be concise and friendly. Do not invent details the owner did not provide.""",
    tools=[save_business_profile],
)

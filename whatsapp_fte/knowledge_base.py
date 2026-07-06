"""Business Knowledge Base.

Design decision (see docs/architecture-decisions.md #1): the data per business is
small, so we PRELOAD the whole profile into the agent's instruction instead of
using RAG. RAG only pays off for large / frequently-changing knowledge.

The profile lives in `business_profile.json`. The onboarding agent writes this
file during setup; the WhatsApp agent reads it at startup to answer customers.
(In production this would be a per-tenant store / vector DB — future note in the
decisions doc.)
"""

import json
import os

_HERE = os.path.abspath(os.path.dirname(__file__))
PROFILE_PATH = os.path.join(_HERE, "business_profile.json")


def load_business_profile() -> dict:
    """Load the current business profile from disk (returns {} if not onboarded yet)."""
    if not os.path.exists(PROFILE_PATH):
        return {}
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_knowledge_context() -> str:
    """Render the business profile as a compact text block to preload into the
    WhatsApp agent's instruction. Kept plain and short so it stays cheap in context.
    """
    p = load_business_profile()
    if not p:
        return "NO BUSINESS PROFILE FOUND. Ask the owner to complete onboarding first."

    faqs = "\n".join(f"- Q: {item['q']}\n  A: {item['a']}" for item in p.get("faqs", []))
    services = "\n".join(f"- {s}" for s in p.get("services", []))

    return f"""BUSINESS PROFILE (your single source of truth — never invent facts beyond this):
Name: {p.get('business_name', 'N/A')}
Doctor: {p.get('doctor', 'N/A')}
About: {p.get('about', 'N/A')}
Location: {p.get('location', 'N/A')}
Contact: {p.get('contact', 'N/A')}
Working hours: {p.get('hours', 'N/A')}

Services & prices:
{services or '- (none listed)'}

Frequently asked questions:
{faqs or '- (none listed)'}"""

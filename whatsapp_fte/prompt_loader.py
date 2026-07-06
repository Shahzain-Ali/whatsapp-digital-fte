"""Reusable prompt/instruction loader (ADK convention).

Instead of hard-coding a long instruction inside the agent file, we keep prompts as
plain `.txt` files under `prompts/` and load them with one generic helper. This mirrors
the standard ADK pattern `load_instruction_from_file("some_prompt.txt")`: the agent file
stays short, and any prompt can be edited without touching code.
"""

import os

_HERE = os.path.abspath(os.path.dirname(__file__))
PROMPTS_DIR = os.path.join(_HERE, "prompts")


def load_instruction_from_file(filename: str, default_instruction: str = "") -> str:
    """Load an instruction/prompt file from the `prompts/` folder and return its text.

    Generic and reusable — pass any filename, e.g. load_instruction_from_file("customer_agent.txt").
    Dynamic values (like the knowledge base or today's date) are substituted by the caller
    after loading, so this function stays a pure file reader.

    Args:
        filename: File name inside the prompts/ folder (e.g. "customer_agent.txt").
        default_instruction: Returned if the file is missing (keeps the agent alive).
    """
    filepath = os.path.join(PROMPTS_DIR, filename)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"[prompt_loader] WARNING: prompt file not found: {filepath} — using default.", flush=True)
        return default_instruction

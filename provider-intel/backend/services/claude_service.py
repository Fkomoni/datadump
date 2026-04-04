"""Claude API integration for AI-powered insights."""

import os
from anthropic import Anthropic

client = None


def get_client():
    global client
    if client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")
        client = Anthropic(api_key=api_key)
    return client


def ask_claude(system: str, user: str, max_tokens: int = 2048) -> str:
    """Send a prompt to Claude and return the text response."""
    c = get_client()
    response = c.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text

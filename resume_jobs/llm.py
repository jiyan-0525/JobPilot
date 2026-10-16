"""Shared Groq / OpenAI-compatible client (lazy initialization)."""
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_client = None


def get_client() -> OpenAI:
    """Get or create the OpenAI-compatible client pointed at Groq."""
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY not found in the environment.\n"
                "Add it to your .env file:\n"
                "  GROQ_API_KEY=your_key_from_https://console.groq.com/keys"
            )
        _client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    return _client

"""Step framing: role + task + expected_output + context.

A step reduces to a system prompt (role) and a user prompt made of `task`,
`expected_output`, and upstream `context`. `run_step` returns prose;
`run_step_tool` forces a tool call and returns a parsed structure.
"""
from __future__ import annotations

import json
from typing import Any, Optional, Sequence

from resume_jobs.llm import get_model

MODEL = get_model()

# Grounding guard: included in every step prompt.
NO_FABRICATION = (
    "Ground every statement in the provided context. Never invent skills, tools, "
    "technologies, certifications, or experience that are not explicitly present there."
)


def build_messages(
    role: str,
    task: str,
    expected_output: str,
    context: Optional[Sequence[str]] = None,
) -> list[dict]:
    """Compose the system + user messages for a step."""
    system = f"You are {role}. {NO_FABRICATION}"
    parts: list[str] = []
    for i, block in enumerate(context or [], start=1):
        parts.append(f"### Context {i}\n{block}")
    parts.append(f"### Task\n{task}")
    parts.append(f"### Expected output\n{expected_output}")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


def _client_or_default(client: Any) -> Any:
    if client is not None:
        return client
    from resume_jobs.llm import get_client  # lazy: no API key needed at import time

    return get_client()


def run_step(
    role: str,
    task: str,
    expected_output: str,
    context: Optional[Sequence[str]] = None,
    client: Any = None,
    model: str = MODEL,
    temperature: float = 0.2,
    max_tokens: int = 3000,
) -> str:
    """One step = one LLM call. Returns the assistant text."""
    client = _client_or_default(client)
    resp = client.chat.completions.create(
        model=model,
        messages=build_messages(role, task, expected_output, context),
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""


def run_step_tool(
    role: str,
    task: str,
    expected_output: str,
    context: Optional[Sequence[str]],
    tool: dict,
    client: Any = None,
    model: str = MODEL,
    temperature: float = 0.0,
    max_tokens: int = 3000,
) -> dict:
    """Like run_step, but forces a single tool call and returns its arguments.

    Use this when a step must produce structure (not prose).
    """
    client = _client_or_default(client)
    name = tool["function"]["name"]
    resp = client.chat.completions.create(
        model=model,
        messages=build_messages(role, task, expected_output, context),
        tools=[tool],
        tool_choice={"type": "function", "function": {"name": name}},
        temperature=temperature,
        max_tokens=max_tokens,
    )
    message = resp.choices[0].message
    tool_calls = getattr(message, "tool_calls", None)
    if not tool_calls:
        raise ValueError(f"model did not call {name}")
    return json.loads(tool_calls[0].function.arguments)

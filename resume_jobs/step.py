"""Step framing: role + task + expected_output + context.

A step reduces to a system prompt (role) and a user prompt made of `task`,
`expected_output`, and upstream `context`. `run_step` returns prose;
`run_step_tool` forces a tool call and returns a parsed structure.
"""
from __future__ import annotations

import json
import time
from typing import Any, Optional, Sequence

from openai import BadRequestError

from resume_jobs.llm import get_model

MODEL = get_model()

# Grounding guard: included in every step prompt.
NO_FABRICATION = (
    "Ground every statement in the provided context. Never invent skills, tools, "
    "technologies, certifications, or experience that are not explicitly present there."
)

# Groq returns this 400 when a forced tool call comes back without one — gpt-oss
# intermittently answers in prose instead (or spends its whole budget on
# reasoning). It is transient, so retry a couple of times before giving up.
_TOOL_USE_FAILED = "tool_use_failed"
_TOOL_ATTEMPTS = 3
_RETRY_BACKOFF_S = 1.5


def _is_tool_use_failed(exc: Exception) -> bool:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and error.get("code") == _TOOL_USE_FAILED:
            return True
    return _TOOL_USE_FAILED in str(exc)


def _request_kwargs(model: str) -> dict:
    """Per-model tuning for the forced-tool-call request.

    On gpt-oss, reasoning tokens count against `max_tokens`; capping reasoning
    keeps room for the tool call that `tool_choice` demands.
    """
    if "gpt-oss" in model:
        return {"extra_body": {"reasoning_effort": "low"}}
    return {}


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


def _extract_json_from_text(text: Optional[str]) -> Optional[dict]:
    """Attempt to extract a JSON dictionary from free-form text or markdown code blocks."""
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    if "```" in text:
        for chunk in text.split("```"):
            chunk = chunk.strip()
            if chunk.startswith("json"):
                chunk = chunk[4:].strip()
            try:
                data = json.loads(chunk)
                if isinstance(data, dict):
                    return data
            except Exception:
                continue

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    return None


def _extract_failed_generation(exc: Exception) -> Optional[dict]:
    """Groq often embeds the model's unparsed generation inside error.failed_generation."""
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            fg = error.get("failed_generation")
            if isinstance(fg, str):
                return _extract_json_from_text(fg)
    return None


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

    last_error: Optional[Exception] = None
    for attempt in range(_TOOL_ATTEMPTS):
        # On retries, slightly vary temperature to prevent repeating deterministic parser failures
        attempt_temp = temperature if attempt == 0 else min(0.6, temperature + 0.15 * attempt)
        request = dict(
            model=model,
            messages=build_messages(role, task, expected_output, context),
            tools=[tool],
            tool_choice={"type": "function", "function": {"name": name}},
            temperature=attempt_temp,
            max_tokens=max_tokens,
            **_request_kwargs(model),
        )
        try:
            resp = client.chat.completions.create(**request)
            message = resp.choices[0].message
            tool_calls = getattr(message, "tool_calls", None)
            if tool_calls:
                return json.loads(tool_calls[0].function.arguments)

            # Fallback 1: check if the model returned valid JSON in message.content
            content = getattr(message, "content", None)
            extracted = _extract_json_from_text(content)
            if extracted is not None:
                return extracted

            last_error = ValueError(f"model did not call {name}")
        except BadRequestError as exc:
            # Fallback 2: Groq tool_use_failed often includes the generated JSON in failed_generation
            extracted = _extract_failed_generation(exc)
            if extracted is not None:
                return extracted

            if not _is_tool_use_failed(exc):
                raise
            last_error = exc
        if attempt < _TOOL_ATTEMPTS - 1:
            time.sleep(_RETRY_BACKOFF_S * (attempt + 1))

    raise ValueError(
        f"model did not call {name} after {_TOOL_ATTEMPTS} attempts"
    ) from last_error


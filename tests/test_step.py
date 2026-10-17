"""Tests for the step framing (role / task / expected_output / context)."""
import json
from types import SimpleNamespace

import httpx
import pytest
from openai import BadRequestError

from resume_jobs.step import build_messages, run_step, run_step_tool


class FakeTextClient:
    """Mimics the OpenAI client returning plain assistant text."""

    def __init__(self, text):
        self.text = text
        self.requests = []
        self.completions = self

    @property
    def chat(self):
        return self

    def create(self, **kwargs):
        self.requests.append(kwargs)
        message = SimpleNamespace(content=self.text)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_build_messages_has_role_task_expected_output_and_context():
    messages = build_messages(
        "a technical recruiter",
        "Rank the jobs",
        "A ranking array",
        ["Profile: X", "Jobs: Y"],
    )
    assert messages[0]["role"] == "system"
    assert "a technical recruiter" in messages[0]["content"]
    assert "Never invent" in messages[0]["content"]

    user = messages[1]["content"]
    assert "### Context 1\nProfile: X" in user
    assert "### Context 2\nJobs: Y" in user
    assert "### Task\nRank the jobs" in user
    assert "### Expected output\nA ranking array" in user


def test_build_messages_without_context():
    user = build_messages("r", "t", "e")[1]["content"]
    assert "Context 1" not in user
    assert user.startswith("### Task")


def test_run_step_returns_text_and_sends_system_message():
    client = FakeTextClient("hello")
    assert run_step("a recruiter", "do it", "a string", client=client) == "hello"

    request = client.requests[0]
    assert request["messages"][0]["role"] == "system"
    assert request["messages"][1]["role"] == "user"
    assert request["temperature"] == 0.2


TOOL = {
    "type": "function",
    "function": {
        "name": "emit",
        "parameters": {"type": "object", "properties": {"ok": {"type": "boolean"}}},
    },
}


def _bad_request(code):
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return BadRequestError(
        "Tool choice is required, but model did not call a tool",
        response=httpx.Response(400, request=request),
        body={"error": {"code": code, "message": "Tool choice is required"}},
    )


class FakeToolClient:
    """Fails the first `failures` forced-tool calls, then returns a tool call."""

    def __init__(self, payload, failures=0, code="tool_use_failed"):
        self.payload = payload
        self.failures = failures
        self.code = code
        self.requests = []
        self.completions = self

    @property
    def chat(self):
        return self

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.failures > 0:
            self.failures -= 1
            raise _bad_request(self.code)
        name = kwargs["tool_choice"]["function"]["name"]
        call = SimpleNamespace(
            function=SimpleNamespace(name=name, arguments=json.dumps(self.payload))
        )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[call]))]
        )


def test_run_step_tool_retries_transient_tool_use_failed(monkeypatch):
    monkeypatch.setattr("resume_jobs.step.time.sleep", lambda *_: None)
    client = FakeToolClient({"ok": True}, failures=1)
    result = run_step_tool("r", "t", "e", None, TOOL, client=client)
    assert result == {"ok": True}
    assert len(client.requests) == 2


def test_run_step_tool_gives_up_after_attempts(monkeypatch):
    monkeypatch.setattr("resume_jobs.step.time.sleep", lambda *_: None)
    client = FakeToolClient({"ok": True}, failures=99)
    with pytest.raises(ValueError):
        run_step_tool("r", "t", "e", None, TOOL, client=client)
    assert len(client.requests) == 3


def test_run_step_tool_does_not_retry_unrelated_400(monkeypatch):
    monkeypatch.setattr("resume_jobs.step.time.sleep", lambda *_: None)
    client = FakeToolClient({"ok": True}, failures=99, code="invalid_request_error")
    with pytest.raises(BadRequestError):
        run_step_tool("r", "t", "e", None, TOOL, client=client)
    assert len(client.requests) == 1


def test_run_step_tool_caps_reasoning_for_gpt_oss():
    client = FakeToolClient({"ok": True})
    run_step_tool("r", "t", "e", None, TOOL, client=client, model="openai/gpt-oss-120b")
    assert client.requests[0]["extra_body"] == {"reasoning_effort": "low"}

    other = FakeToolClient({"ok": True})
    run_step_tool("r", "t", "e", None, TOOL, client=other, model="llama-3.3-70b-versatile")
    assert "extra_body" not in other.requests[0]


def test_run_step_tool_extracts_json_from_content_fallback():
    # Model returned text with JSON markdown instead of calling a tool directly
    client = FakeTextClient("Here is the result:\n```json\n{\"ok\": true}\n```")
    result = run_step_tool("r", "t", "e", None, TOOL, client=client)
    assert result == {"ok": True}


def test_run_step_tool_extracts_from_failed_generation():
    # Groq rejected tool formatting but preserved generation in failed_generation
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    exc = BadRequestError(
        "Failed to call function",
        response=httpx.Response(400, request=request),
        body={
            "error": {
                "code": "tool_use_failed",
                "message": "Failed to call a function",
                "failed_generation": "```json\n{\"ok\": true}\n```",
            }
        },
    )

    class FailingClient:
        def __init__(self):
            self.completions = self

        @property
        def chat(self):
            return self

        def create(self, **kwargs):
            raise exc

    result = run_step_tool("r", "t", "e", None, TOOL, client=FailingClient())
    assert result == {"ok": True}


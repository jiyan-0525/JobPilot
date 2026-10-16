"""Tests for the step framing (role / task / expected_output / context)."""
from types import SimpleNamespace

from resume_jobs.step import build_messages, run_step


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

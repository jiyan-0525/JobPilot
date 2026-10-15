from agent import calculator, chat_with_tools


def test_calculator():
    result = calculator("2 + 3")
    assert "5" in result


def test_agent_import():
    assert callable(chat_with_tools)


def test_code_linting():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "py_compile", "agent.py"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
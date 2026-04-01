def test_calculator():
    result = calculator("2 + 3")
    assert "5" in result
    
def test_agent_import():
    from agent import chat_with_tools
    
def test_code_linting():
    import subprocess
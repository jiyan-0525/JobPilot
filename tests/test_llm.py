from resume_jobs import llm


def test_get_model_uses_groq_setting(monkeypatch):
    monkeypatch.setenv("GROQ_MODEL", "groq-model")
    assert llm.get_model() == "groq-model"

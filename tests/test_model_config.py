import pytest
from langchain.chat_models import init_chat_model


@pytest.mark.parametrize(
    ("model", "env", "class_name"),
    [
        ("google_genai:gemini-2.5-flash", "GOOGLE_API_KEY", "ChatGoogleGenerativeAI"),
    ],
)
def test_llm_model_setting_picks_provider(monkeypatch, model, env, class_name):
    monkeypatch.setenv(env, "test-key")

    assert type(init_chat_model(model)).__name__ == class_name

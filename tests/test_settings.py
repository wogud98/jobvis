"""화면에서 넣은 LLM 키 저장(agent/settings.py) (v0.6 F4, F5, D6)."""

import os

import pytest

from agent import settings

KEY = "AIzaSyFAKE-test-key-1234"


@pytest.fixture
def clean(monkeypatch, tmp_path):
    for name in ("GOOGLE_API_KEY", "ANTHROPIC_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LLM_MODEL", "google_genai:gemini-flash-lite-latest")
    return tmp_path / "data" / "settings.env"


def test_save_writes_file_and_sets_environment(clean):
    settings.save_key(f"  {KEY}\n", clean)

    assert clean.read_text(encoding="utf-8").strip() == f"GOOGLE_API_KEY={KEY}"
    assert os.environ["GOOGLE_API_KEY"] == KEY and settings.has_key()


def test_load_fills_only_missing_or_blank_values(clean, monkeypatch):
    clean.parent.mkdir()
    clean.write_text(f"GOOGLE_API_KEY={KEY}\n", encoding="utf-8")

    monkeypatch.setenv("GOOGLE_API_KEY", "")  # .env에 빈칸으로 적힌 경우
    settings.load(clean)
    assert os.environ["GOOGLE_API_KEY"] == KEY

    monkeypatch.setenv("GOOGLE_API_KEY", "from-dotenv")  # .env에 적은 키가 우선
    settings.load(clean)
    assert os.environ["GOOGLE_API_KEY"] == "from-dotenv"


def test_load_without_file_does_nothing(clean):
    settings.load(clean)

    assert not settings.has_key() and settings.masked() == ""


@pytest.mark.parametrize("bad", ["", "   ", "abc def", "abc\ndef"])
def test_bad_key_is_rejected_without_echoing_it(clean, bad):
    with pytest.raises(ValueError) as error:
        settings.save_key(bad, clean)

    assert not clean.exists()
    if bad.strip():
        assert bad.strip() not in str(error.value)  # 문구에 키가 들어가지 않음 (F5)


def test_masked_shows_last_four_only(clean):
    settings.save_key(KEY, clean)

    assert settings.masked() == "••••1234" and KEY[:-4] not in settings.masked()


def test_short_key_is_fully_hidden(clean, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "abc")

    assert settings.masked() == "••••"


def test_key_name_follows_model(clean, monkeypatch):
    assert settings.key_name() == "GOOGLE_API_KEY" and "aistudio" in settings.key_page()

    monkeypatch.setenv("LLM_MODEL", "anthropic:claude-sonnet-5-5")
    assert settings.key_name() == "ANTHROPIC_API_KEY"

    monkeypatch.setenv("LLM_MODEL", "unknown:model")
    assert settings.key_name() == "GOOGLE_API_KEY"


def test_save_replaces_old_key(clean):
    settings.save_key(KEY, clean)
    settings.save_key("AIzaSyNEW-key-9876", clean)

    assert clean.read_text(encoding="utf-8").count("GOOGLE_API_KEY=") == 1
    assert settings.masked() == "••••9876"


# ---- v0.6.1 키 지키기 ----


def test_delete_removes_saved_key_and_environment(clean):
    settings.save_key(KEY, clean)

    assert settings.delete_key(clean) is True  # F14
    assert "GOOGLE_API_KEY" not in clean.read_text(encoding="utf-8")
    assert not settings.has_key()


def test_delete_key_from_dotenv_only_clears_this_run(clean, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", KEY)  # .env에서 읽은 키. 저장 파일 없음

    assert settings.delete_key(clean) is False  # .env는 건드리지 않는다
    assert not settings.has_key() and not clean.exists()


def test_redact_hides_key_in_any_text(clean, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", KEY)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-FAKE-9999")

    text = settings.redact(f"400 Bad Request url=...?key={KEY} header=sk-ant-FAKE-9999")

    assert KEY not in text and "sk-ant-FAKE-9999" not in text  # F12
    assert text.count("••••") == 2


def test_redact_leaves_text_without_key_and_ignores_short_values(clean, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "abc")  # 너무 짧은 값은 흔한 글자까지 가릴 수 있어 건너뜀

    assert settings.redact("abc 연결 실패") == "abc 연결 실패"

"""화면에서 넣은 LLM 키를 data/settings.env에 저장하고 읽는다 (v0.6 F4, F5, D6).

`.env`를 먼저 읽고 그다음 이 파일을 읽는다. 비어 있는 값만 채우므로 `.env`에 직접 쓴 키가 우선이다.
키는 화면·로그·오류 문구에 다시 보이지 않는다. 보여줄 때는 masked()로 끝 4자리만.
"""

import contextlib
import os
from pathlib import Path

from dotenv import dotenv_values, set_key

from agent.graph import llm_model

PATH = Path("data/settings.env")  # data/는 .gitignore와 Docker 볼륨에 들어 있다
KEY_NAMES = {"google_genai": "GOOGLE_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
KEY_PAGES = {
    "GOOGLE_API_KEY": "https://aistudio.google.com/apikey",
    "ANTHROPIC_API_KEY": "https://console.anthropic.com/settings/keys",
}


def load(path: Path = PATH) -> None:
    """저장해 둔 값 중 환경에 없거나 빈 것만 넣는다."""
    if not path.exists():
        return
    for name, value in dotenv_values(path).items():
        if value and not os.environ.get(name, "").strip():
            os.environ[name] = value


def key_name() -> str:
    """지금 모델(LLM_MODEL)이 쓰는 키 이름. 모르는 제공자는 Gemini 키로 본다."""
    return KEY_NAMES.get(llm_model().split(":", 1)[0], "GOOGLE_API_KEY")


def key_page() -> str:
    return KEY_PAGES[key_name()]


def has_key() -> bool:
    return bool(os.environ.get(key_name(), "").strip())


def save_key(key: str, path: Path = PATH) -> None:
    """파일에 쓰고 지금 실행에도 바로 쓴다. 틀린 모양이면 ValueError (문구에 키를 넣지 않는다)."""
    key = key.strip()
    if not key:
        raise ValueError("키를 붙여넣어 주세요.")
    if any(ch.isspace() for ch in key):
        raise ValueError("키에 빈칸이나 줄바꿈이 있습니다. 발급 화면에서 다시 복사해 주세요.")
    path.parent.mkdir(parents=True, exist_ok=True)
    set_key(path, key_name(), key, quote_mode="never")
    with contextlib.suppress(OSError):  # 윈도우 등 권한을 바꿀 수 없는 곳은 그대로 둔다
        path.chmod(0o600)
    os.environ[key_name()] = key


def masked() -> str:
    """화면에 보일 키. 끝 4자리만 (F5)."""
    key = os.environ.get(key_name(), "").strip()
    if not key:
        return ""
    return f"••••{key[-4:]}" if len(key) >= 8 else "••••"

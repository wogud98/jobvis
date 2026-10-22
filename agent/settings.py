"""화면에서 넣은 LLM 키를 data/settings.env에 저장하고 읽는다 (v0.6 F4, F5, D6).

`.env`를 먼저 읽고 그다음 이 파일을 읽는다. 비어 있는 값만 채우므로 `.env`에 직접 쓴 키가 우선이다.
키는 화면·로그·오류 문구에 다시 보이지 않는다. 보여줄 때는 masked()로 끝 4자리만.
"""

import contextlib
import os
from pathlib import Path

from dotenv import dotenv_values, set_key, unset_key

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


KEY_LABELS = {"GOOGLE_API_KEY": "제미나이 API 키", "ANTHROPIC_API_KEY": "Claude API 키"}


def key_label() -> str:
    """화면 안내에 쓰는 키 이름 (v0.6.2 F14)."""
    return KEY_LABELS[key_name()]


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


def delete_key(path: Path = PATH) -> bool:
    """이 PC에 저장한 키를 지운다 (v0.6.1 F14). Google에서 키를 파기하지는 않는다.

    `.env`에 적은 키는 파일을 건드리지 않고 지금 실행에서만 뺀다. 저장 파일에서 지웠으면 True.
    """
    removed = False
    if path.exists() and key_name() in dotenv_values(path):
        unset_key(path, key_name(), quote_mode="never")
        removed = True
    os.environ.pop(key_name(), None)
    return removed


def redact(text: str) -> str:
    """화면·로그로 나가는 글에서 키와 같은 글자를 가린다 (v0.6.1 F12). 라이브러리 오류에 키가 섞여도 보이지 않게."""
    for name in KEY_NAMES.values():
        key = os.environ.get(name, "").strip()
        if len(key) >= 8 and key in text:
            text = text.replace(key, "••••")
    return text


def masked() -> str:
    """화면에 보일 키. 끝 4자리만 (F5)."""
    key = os.environ.get(key_name(), "").strip()
    if not key:
        return ""
    return f"••••{key[-4:]}" if len(key) >= 8 else "••••"

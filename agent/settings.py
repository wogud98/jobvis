"""화면에서 넣은 LLM 키와 메일 설정을 data/settings.env에 저장하고 읽는다 (v0.6 F4, F5, D6, v0.7 D4).

`.env`를 먼저 읽고 그다음 이 파일을 읽는다. 비어 있는 값만 채우므로 `.env`에 직접 쓴 키가 우선이다.
키는 화면·로그·오류 문구에 다시 보이지 않는다. 보여줄 때는 masked()로 끝 4자리만.
"""

import contextlib
import os
import re
from dataclasses import dataclass
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
    """화면·로그로 나가는 글에서 키와 같은 글자를 가린다 (v0.6.1 F12). 라이브러리 오류에 키가 섞여도 보이지 않게.

    메일 앱 비밀번호도 빈칸 뺀 모양과 4자씩 띄운 모양 모두 가린다 (v0.7 D5).
    """
    secrets = [os.environ.get(name, "").strip() for name in KEY_NAMES.values()]
    password = os.environ.get(MAIL_PASSWORD, "").strip()
    if password:
        secrets += [password, " ".join(password[i : i + 4] for i in range(0, len(password), 4))]
    for secret in secrets:
        if len(secret) >= 8 and secret in text:
            text = text.replace(secret, "••••")
    return text


def masked() -> str:
    """화면에 보일 키. 끝 4자리만 (F5)."""
    key = os.environ.get(key_name(), "").strip()
    if not key:
        return ""
    return f"••••{key[-4:]}" if len(key) >= 8 else "••••"


MAIL_FROM, MAIL_PASSWORD, MAIL_TO = "JOBVIS_MAIL_FROM", "JOBVIS_MAIL_PASSWORD", "JOBVIS_MAIL_TO"  # v0.7 D4
MAIL_NAMES = (MAIL_FROM, MAIL_PASSWORD, MAIL_TO)
MAIL_PAGE = "https://myaccount.google.com/apppasswords"  # 앱 비밀번호 만드는 곳 (F8)
_ADDRESS = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")  # 이름@도메인.점 모양만 본다. 도메인은 막지 않음 (D4)


@dataclass
class MailConfig:
    sender: str
    password: str
    to: str


def mail_config() -> MailConfig | None:
    """저장한 메일 설정. 보내는 주소나 앱 비밀번호가 없으면 None (F1)."""
    sender = os.environ.get(MAIL_FROM, "").strip()
    password = os.environ.get(MAIL_PASSWORD, "").strip()
    if not sender or not password:
        return None
    return MailConfig(sender, password, os.environ.get(MAIL_TO, "").strip() or sender)


def _check_address(address: str, what: str) -> str:
    address = address.strip()
    if not _ADDRESS.fullmatch(address):
        raise ValueError(f"{what} 주소 형식이 맞지 않습니다. name@gmail.com 처럼 넣어 주세요.")
    return address


def save_mail(sender: str, password: str, to: str = "", path: Path = PATH) -> MailConfig:
    """확인하고 파일과 지금 실행에 넣는다. 틀리면 ValueError (문구에 비밀번호를 넣지 않는다) (F8, F9).

    비밀번호를 비워 두면 이미 저장한 비밀번호를 그대로 쓴다(주소만 바꿀 때).
    """
    sender = _check_address(sender, "보내는")
    to = _check_address(to, "받는") if to.strip() else sender  # 비우면 보내는 주소 (D4)
    password = "".join(password.split())  # Google은 4자씩 띄워 보여 준다
    if not password:
        password = os.environ.get(MAIL_PASSWORD, "").strip()
        if not password:
            raise ValueError("Gmail 앱 비밀번호를 넣어 주세요.")
    elif len(password) != 16 or not password.isascii() or not password.isalpha():
        raise ValueError("앱 비밀번호는 영문 16자입니다. Google 앱 비밀번호 화면에서 다시 복사해 주세요.")
    path.parent.mkdir(parents=True, exist_ok=True)
    for name, value in zip(MAIL_NAMES, (sender, password, to), strict=True):
        set_key(path, name, value, quote_mode="never")
        os.environ[name] = value
    with contextlib.suppress(OSError):
        path.chmod(0o600)
    return MailConfig(sender, password, to)


def delete_mail(path: Path = PATH) -> None:
    """이 PC의 메일 설정을 지운다 (F8). Google의 앱 비밀번호는 그대로다."""
    saved = dotenv_values(path) if path.exists() else {}
    for name in MAIL_NAMES:
        if name in saved:
            unset_key(path, name, quote_mode="never")
        os.environ.pop(name, None)


def mail_masked() -> str:
    """화면에 보일 앱 비밀번호. 끝 4자리만 (F8, N2)."""
    password = os.environ.get(MAIL_PASSWORD, "").strip()
    return f"••••{password[-4:]}" if len(password) >= 8 else ("••••" if password else "")

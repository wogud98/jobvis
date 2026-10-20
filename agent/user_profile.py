"""평가에 쓸 내 프로필(마크다운 파일)을 읽는다."""

from pathlib import Path

EXAMPLE = "profile.example.md"


class ProfileError(Exception):
    """프로필 파일이 없거나 비어 있음 (F6)."""


def load(path: str) -> str:
    file = Path(path)
    if not file.is_file():
        raise ProfileError(f"프로필 파일이 없습니다: {path}\n{EXAMPLE}를 복사해 {path}로 저장하고 내용을 채워 주세요.")
    text = file.read_text(encoding="utf-8").strip()
    if not text:
        raise ProfileError(f"프로필 파일이 비어 있습니다: {path}\n{EXAMPLE}를 참고해 내용을 채워 주세요.")
    return text

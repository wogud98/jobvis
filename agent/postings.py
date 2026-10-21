"""공고 원문: 본문 HTML에서 글자·이미지 주소 뽑기, PC에 원문 저장·읽기, 본문 상태 정하기."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

DIR = Path("data/postings")  # .gitignore에 있음. 커밋하지 않는다 (N5)
MIN_TEXT = 200  # 이보다 짧으면 본문 미확보 (F15a)
OCR_MARK = "--- 이미지 글자 ---"

# "본문" 열 값 (F15)
TEXT = "글자"
TEXT_AND_IMAGE = "글자+이미지"
PARTLY_UNREAD = "이미지 일부 못 읽음"
MISSING = "본문 미확보"

_HIDDEN_STYLE = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden", re.I)


@dataclass
class Detail:
    text: str = ""
    images: list[str] = field(default_factory=list)  # 절대 주소, 나온 순서대로


def extract(html: str, selector: str, base_url: str) -> Detail:
    """selector 위치의 본문에서 글자와 이미지 주소를 뽑는다. 위치가 없으면 빈 본문."""
    container = BeautifulSoup(html, "html.parser").select_one(selector)
    if container is None:
        return Detail()
    # 화면에 안 보이는 글은 버린다 (F11). 숨은 글로 LLM에 지시를 넣는 것도 함께 막는다.
    for tag in container.find_all(["script", "style", "noscript", "template"]):
        tag.decompose()
    for tag in container.find_all(_is_hidden):
        tag.decompose()
    images = []
    for img in container.find_all("img"):
        src = (img.get("src") or img.get("data-src") or "").strip()
        if src and not src.startswith("data:"):
            url = urljoin(base_url, src)
            if url not in images:
                images.append(url)
    lines = [line.strip() for line in container.get_text("\n").splitlines()]
    return Detail(text="\n".join(line for line in lines if line), images=images)


def _is_hidden(tag: Tag) -> bool:
    return tag.has_attr("hidden") or bool(_HIDDEN_STYLE.search(tag.get("style", "")))


def path(source: str, job_id: str) -> Path:
    return DIR / f"{source}_{job_id}.txt"


def compose(text: str, ocr_texts: list[str]) -> str:
    ocr = "\n".join(t for t in ocr_texts if t.strip())
    return f"{text}\n\n{OCR_MARK}\n{ocr}" if ocr else text


def split(content: str) -> tuple[str, list[str]]:
    """원문을 글자 본문과 이미지 글자로 나눈다. compose의 반대."""
    text, mark, ocr = content.partition(f"\n\n{OCR_MARK}\n")
    if not mark and content.startswith(f"{OCR_MARK}\n"):  # 글자 본문이 빈 원문
        text, ocr = "", content[len(OCR_MARK) + 1 :]
    return text, [ocr] if ocr.strip() else []


def add_ocr(content: str | None, texts: list[str]) -> str:
    """원문의 이미지 글자 뒤에 새로 읽은 글자를 붙인다. 원문이 없으면 글자 본문은 빈칸 (v0.5 F39)."""
    text, ocr = split(content or "")
    return compose(text, ocr + texts)


def save(source: str, job_id: str, content: str) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    path(source, job_id).write_text(content, encoding="utf-8")


def load(source: str, job_id: str) -> str | None:
    file = path(source, job_id)
    return file.read_text(encoding="utf-8") if file.exists() else None


def remove(source: str, job_id: str) -> None:
    path(source, job_id).unlink(missing_ok=True)


def status(text: str, ocr_texts: list[str], unread: int) -> str:
    """unread는 받거나 읽다가 오류가 난 이미지 수. robots 금지, 300px 미만, OCR 미설치는 넣지 않는다."""
    ocr_length = sum(len(t.strip()) for t in ocr_texts)
    if len(text.strip()) + ocr_length < MIN_TEXT:
        return MISSING
    if unread:
        return PARTLY_UNREAD
    if ocr_length:
        return TEXT_AND_IMAGE
    return TEXT

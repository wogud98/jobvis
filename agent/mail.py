"""고른 공고를 메일로 만들어 Gmail로 보낸다 (v0.7 F5–F9, D1, D2, D5).

LLM·사이트 요청이 없다(N1, N4). 보내기는 파이썬 기본 smtplib로 smtp.gmail.com:465(SSL)에 앱 비밀번호로 로그인한다.
테스트는 smtp 자리에 가짜 클래스를 넣어 실제 메일을 보내지 않는다 (N3).
"""

import smtplib
from datetime import date
from email.message import EmailMessage
from html import escape

from agent import view

MAX = 30  # 한 번에 보낼 수 있는 공고 수 (F3)
HOST, PORT = "smtp.gmail.com", 465
TIMEOUT = 20  # 초
NOT_SCORED = view.NOT_SCORED
AUTH_ERROR = "Gmail 앱 비밀번호가 맞지 않습니다. 앱 비밀번호를 다시 만들어 넣어 주세요."
CONNECT_ERROR = "메일 서버에 연결하지 못했습니다. 인터넷 연결을 확인해 주세요."


class MailError(Exception):
    """화면에 그대로 보일 할 일 문구. 원래 예외 글(계정·서버 응답)은 버린다 (D5)."""


def subject(count: int, today: date) -> str:
    return f"[JOBVIS] 공고 {count}건 ({today:%Y-%m-%d})"  # F5


def _link(url: str) -> str:
    """http(s) 주소만 링크로 쓴다. 그 밖(javascript: 등)은 빈 글자 (F7)."""
    url = url.strip()
    return url if url.lower().startswith(("http://", "https://")) else ""


def _score(card: view.Card) -> str:
    if card.score is None:
        return card.verdict if card.verdict != view.NOT_SCORED else NOT_SCORED  # 제외 공고는 "제외 (경력 요구)"
    return f"{card.score}점 · {card.verdict}"


def _deadline(card: view.Card, today: date) -> str:
    badge = view.deadline_badge(card.deadline, today)
    text = card.deadline.strip() or "상시"
    return f"{text} ({badge[0]})" if badge else text


def _lines(card: view.Card, today: date) -> list[tuple[str, str]]:
    """공고 한 건의 (이름, 값) 줄. 글자판과 HTML이 같이 쓴다 (F6)."""
    lines = [
        ("점수", _score(card)),
        ("마감", _deadline(card, today)),
        ("출처", f"{card.source} · {card.experience}"),
    ]
    if card.strengths:
        lines.append(("강점", card.strengths[0]))
    if card.gaps:
        lines.append(("부족한 점", card.gaps[0]))
    return lines


def _text(cards: list[view.Card], today: date) -> str:
    parts = [f"JOBVIS에서 고른 공고 {len(cards)}건입니다.", ""]
    for number, card in enumerate(cards, 1):
        parts.append(f"{number}. {card.company} · {card.title}")
        parts += [f"   {name}: {value}" for name, value in _lines(card, today)]
        if link := _link(card.url):
            parts.append(f"   원문: {link}")
        parts.append("")
    return "\n".join(parts)


def _html(cards: list[view.Card], today: date) -> str:
    # 메일 앱은 <style>을 많이 버려서 표와 인라인 스타일만 쓴다 (D2)
    rows = []
    for card in cards:
        name = f"{escape(card.company)} · {escape(card.title)}"
        link = _link(card.url)
        head = f'<a href="{escape(link)}" style="color:#1d4ed8">{name}</a>' if link else name
        details = "".join(
            f'<tr><td style="color:#6b7280;padding:2px 12px 2px 0;white-space:nowrap">{escape(label)}</td>'
            f'<td style="padding:2px 0">{escape(value)}</td></tr>'
            for label, value in _lines(card, today)
        )
        rows.append(
            '<tr><td style="padding:12px 0;border-bottom:1px solid #e5e7eb">'
            f'<div style="font-size:16px;font-weight:700;margin-bottom:4px">{head}</div>'
            f'<table style="font-size:14px;border-collapse:collapse">{details}</table></td></tr>'
        )
    return (
        '<div style="font-family:sans-serif;color:#141414;max-width:640px">'
        f'<p style="font-size:15px">JOBVIS에서 고른 공고 <b>{len(cards)}건</b>입니다.</p>'
        f'<table style="width:100%;border-collapse:collapse">{"".join(rows)}</table></div>'
    )


def build(cards: list[view.Card], sender: str, to: str, today: date) -> EmailMessage:
    """고른 공고 메일. 0건이거나 MAX를 넘으면 MailError (F3)."""
    if not cards:
        raise MailError("보낼 공고를 골라 주세요.")
    if len(cards) > MAX:
        raise MailError(f"한 번에 {MAX}건까지 보낼 수 있습니다. 지금 {len(cards)}건을 골랐습니다.")
    message = EmailMessage()
    message["Subject"] = subject(len(cards), today)
    message["From"] = sender
    message["To"] = to
    message.set_content(_text(cards, today))
    message.add_alternative(_html(cards, today), subtype="html")
    return message


def test_message(sender: str, to: str) -> EmailMessage:
    """설정 확인용 시험 메일 (F8)."""
    message = EmailMessage()
    message["Subject"] = "[JOBVIS] 시험 메일"
    message["From"] = sender
    message["To"] = to
    message.set_content("JOBVIS 메일 설정이 잘 됐습니다. 이제 공고를 골라 보낼 수 있습니다.")
    return message


def send(message: EmailMessage, sender: str, password: str, smtp=smtplib.SMTP_SSL) -> None:
    """앱 비밀번호로 로그인해 보낸다. 실패는 할 일 문구의 MailError로 바꾼다 (F9, D5)."""
    try:
        with smtp(HOST, PORT, timeout=TIMEOUT) as server:
            server.login(sender, password)
            server.send_message(message)
    except smtplib.SMTPAuthenticationError:
        raise MailError(AUTH_ERROR) from None
    except (smtplib.SMTPException, OSError):  # TimeoutError·연결 거부·DNS 실패는 OSError
        raise MailError(CONNECT_ERROR) from None

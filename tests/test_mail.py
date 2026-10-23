"""메일 만들기·보내기(agent/mail.py). 실제 메일 서버에 연결하지 않는다 (v0.7 N3)."""

import smtplib
from datetime import date

import pytest

from agent import mail, sheets, view

TODAY = date(2026, 10, 23)
PASSWORD = "abcdefghijklmnop"


def card(number: int, **changes) -> view.Card:
    row = dict.fromkeys(sheets.KEYS, "")
    row |= {
        "row": number,
        "company": f"회사{number}",
        "title": "백엔드",
        "deadline": "2026-10-30",
        "url": f"https://www.saramin.co.kr/{number}",
        "id": str(number),
        "experience": "신입",
        "source": "사람인",
        "score": "82",
        "verdict": "추천",
        "strengths": "Python 경험, SQL",
        "gaps": "AWS 경험 없음, Docker",
    }
    return view.cards([row | changes])[0]


def parts(message) -> tuple[str, str]:
    text = message.get_body(("plain",)).get_content()
    html = message.get_body(("html",)).get_content()
    return text, html


def test_build_has_subject_addresses_and_both_bodies():
    message = mail.build([card(2), card(3)], "me@gmail.com", "you@example.com", TODAY)

    assert message["Subject"] == "[JOBVIS] 공고 2건 (2026-10-23)"  # F5
    assert message["From"] == "me@gmail.com" and message["To"] == "you@example.com"
    text, html = parts(message)  # 글자판과 HTML 두 판 (F6)
    for body in (text, html):
        assert "회사2 · 백엔드" in body and "회사3 · 백엔드" in body
        assert "82점 · 추천" in body
        assert "2026-10-30 (D-7)" in body  # 마감 D-n
        assert "사람인 · 신입" in body
        assert "Python 경험" in body and "SQL" not in body  # 강점 첫 줄만
        assert "AWS 경험 없음" in body and "Docker" not in body  # 부족한 점 첫 줄만
    assert 'href="https://www.saramin.co.kr/2"' in html
    assert "원문: https://www.saramin.co.kr/3" in text


def test_unscored_and_excluded_cards():
    message = mail.build(
        [card(2, score="", verdict=""), card(3, score="", verdict="제외 (경력 요구)")], "a@b.co", "a@b.co", TODAY
    )
    text, _ = parts(message)

    assert "점수: 평가 전" in text  # F6
    assert "점수: 제외 (경력 요구)" in text


def test_sheet_text_is_escaped_and_only_http_links():
    bad = card(2, company="<b>회사</b>", title='x"><script>', url="javascript:alert(1)", strengths="<i>강점</i>")
    _, html = parts(mail.build([bad], "a@b.co", "a@b.co", TODAY))

    assert "<b>회사</b>" not in html and "&lt;b&gt;회사&lt;/b&gt;" in html  # F7
    assert "<script>" not in html and "<i>" not in html
    assert "javascript:" not in html and "href" not in html  # http(s)만 링크


def test_deadline_without_date_is_shown_as_is():
    text, _ = parts(mail.build([card(2, deadline="")], "a@b.co", "a@b.co", TODAY))

    assert "마감: 상시" in text


@pytest.mark.parametrize("count", [0, mail.MAX + 1])
def test_build_rejects_zero_or_too_many(count):
    with pytest.raises(mail.MailError):  # F3
        mail.build([card(n) for n in range(2, 2 + count)], "a@b.co", "a@b.co", TODAY)


def test_build_accepts_max():
    message = mail.build([card(n) for n in range(2, 2 + mail.MAX)], "a@b.co", "a@b.co", TODAY)

    assert message["Subject"].startswith(f"[JOBVIS] 공고 {mail.MAX}건")


class FakeSMTP:
    """smtplib.SMTP_SSL 자리에 넣는 가짜. 무엇을 불렀는지 기록한다."""

    calls: list = []
    fail: Exception | None = None

    def __init__(self, host, port, timeout):
        FakeSMTP.calls.append(("connect", host, port))
        if isinstance(FakeSMTP.fail, OSError):
            raise FakeSMTP.fail

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def login(self, user, password):
        FakeSMTP.calls.append(("login", user, password))
        if FakeSMTP.fail is not None:
            raise FakeSMTP.fail

    def send_message(self, message):
        FakeSMTP.calls.append(("send", message["Subject"]))


@pytest.fixture
def smtp():
    FakeSMTP.calls, FakeSMTP.fail = [], None
    return FakeSMTP


def test_send_logs_in_with_app_password_and_sends(smtp):
    mail.send(mail.test_message("me@gmail.com", "me@gmail.com"), "me@gmail.com", PASSWORD, smtp=smtp)

    assert smtp.calls == [
        ("connect", "smtp.gmail.com", 465),
        ("login", "me@gmail.com", PASSWORD),
        ("send", "[JOBVIS] 시험 메일"),
    ]  # N1


@pytest.mark.parametrize(
    ("error", "text"),
    [
        (smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted abcdefghijklmnop"),
         mail.AUTH_ERROR),
        (ConnectionRefusedError("refused me@gmail.com"), mail.CONNECT_ERROR),
        (TimeoutError("timed out"), mail.CONNECT_ERROR),
        (smtplib.SMTPServerDisconnected("closed"), mail.CONNECT_ERROR),
    ],
)  # fmt: skip
def test_send_errors_become_what_to_do_without_secrets(smtp, error, text):
    smtp.fail = error

    with pytest.raises(mail.MailError) as caught:
        mail.send(mail.test_message("me@gmail.com", "me@gmail.com"), "me@gmail.com", PASSWORD, smtp=smtp)

    assert str(caught.value) == text  # F9
    assert PASSWORD not in str(caught.value) and "me@gmail.com" not in str(caught.value)  # N2
    assert caught.value.__cause__ is None and caught.value.__suppress_context__  # 원래 예외 글은 버림 (D5)

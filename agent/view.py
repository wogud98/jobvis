"""화면에 보일 내용 만들기: 공고 카드, 정렬, 필터, 차트 자료, 요약 칸, 오류 문구 (v0.5 F2–F10, F34, F47, v0.5.1 F2).

Streamlit을 import하지 않는다. app.py는 이 결과를 그리기만 해서, 규칙은 가짜 데이터로 테스트한다 (N5).
"""

import re
from dataclasses import dataclass, field

import gspread
import requests

from agent import postings, scoring, sheets

UNKNOWN_SOURCE = "미상"  # 출처 칸이 빈 예전 줄 (F6)
BLANK_EXPERIENCE = "(없음)"  # 경력 칸이 빈 줄의 필터 값
CAREER_GROUPS = ("신입", "경력", "무관")  # 경력 필터 보기 (v0.5.2 F30)
OTHER_CAREER = "기타"  # 묶음으로 나누지 못한 경력 글자 (예: 인턴)
NOT_SCORED = "평가 전"
NONE = "없음"  # 빈 칸 표시 (F3)
RECOMMENDED = ("강력 추천", "추천")  # 요약 칸 "추천 이상" (v0.5.1 F2)
UPLOADABLE = (postings.MISSING, postings.PARTLY_UNREAD)  # 이미지 넣는 칸을 보일 본문 상태 (F47)


@dataclass
class Card:
    row: int
    company: str
    title: str
    deadline: str
    url: str
    source: str  # 사이트 이름. 빈 출처는 "미상"
    source_code: str  # saramin / jobkorea. 이미지 저장 이름에만 쓴다
    job_id: str
    score: int | None
    stars: str
    verdict: str
    experience: str
    trust: str
    adjust: str
    body: str
    details: dict[str, str] = field(default_factory=dict)

    @property
    def dim(self) -> bool:
        return self.trust == scoring.LOW  # 신뢰 낮음 카드는 흐리게 (F34)

    @property
    def can_upload(self) -> bool:
        return self.body in UPLOADABLE and bool(self.job_id)


@dataclass
class Filters:
    """비어 있는 목록은 거르지 않음(전체) (v0.5.2 F29)."""

    sources: list[str]
    experiences: list[str]  # CAREER_GROUPS 중에서
    show_unscored: bool = False


def _score(value: str) -> int | None:
    try:
        return int(value.strip())
    except ValueError:
        return None  # 비었거나 사람이 숫자가 아닌 값을 넣은 줄


def _or_none(value: str) -> str:
    return value.strip() or NONE


def _trust(row: dict) -> str:
    # v0.4에서 평가한 줄은 신뢰 칸이 없고 판정에 "(본문 미확보)"가 붙어 있다
    if not row["trust"] and postings.MISSING in row["verdict"]:
        return scoring.LOW
    return row["trust"]


def _card(row: dict) -> Card:
    score = _score(row["score"])
    verdict = row["verdict"].strip()
    if score is None and verdict != scoring.EXCLUDED:
        verdict = NOT_SCORED
    details = {
        "요약": row["requirements"],
        "주요업무": row["duties"],
        "우대사항": row["preferred"],
        "기술스택": row["stack"],
        "기술": row["skills"],
        "경력": row["experience_score"],
        "문화": row["culture"],
        "방향": row["career"],
        "강점": row["strengths"],
        "부족한 점": row["gaps"],
    }
    return Card(
        row=row["row"],
        company=row["company"],
        title=row["title"],
        deadline=row["deadline"],
        url=row["url"],
        source=row["source"].strip() or UNKNOWN_SOURCE,  # 시트에는 사이트 이름으로 적혀 있다
        source_code=sheets.source_code(row["source"]),
        job_id=row["id"],
        score=score,
        stars=row["stars"],
        verdict=verdict,
        experience=row["experience"].strip() or BLANK_EXPERIENCE,
        trust=_trust(row),
        adjust=row["adjust"],
        body=row["body"],
        details={name: _or_none(value) for name, value in details.items()},
    )


def cards(rows: list[dict]) -> list[Card]:
    """점수 높은 순(같으면 시트 줄 순), 그 뒤에 점수 없는 카드를 시트 줄 순으로 (F2)."""
    made = [_card(row) for row in rows]
    scored = sorted((c for c in made if c.score is not None), key=lambda c: (-c.score, c.row))
    unscored = sorted((c for c in made if c.score is None), key=lambda c: c.row)
    return scored + unscored


def career_groups(experience: str) -> list[str]:
    """경력 글자를 신입·경력·무관 묶음으로 (v0.5.2 F30). "신입·경력"처럼 둘 다면 둘 다, 못 나누면 기타."""
    text = experience.replace(" ", "")
    if not text or experience == BLANK_EXPERIENCE:
        return [BLANK_EXPERIENCE]
    groups = ["무관"] if "무관" in text else []
    rest = text.replace("경력무관", "").replace("무관", "")
    if "신입" in rest:
        groups.append("신입")
    if "경력" in rest or re.search(r"\d+년", rest):
        groups.append("경력")
    return [group for group in CAREER_GROUPS if group in groups] or [OTHER_CAREER]


def options(items: list[Card]) -> tuple[list[str], list[str]]:
    """필터에 보일 (출처 목록, 경력 묶음 목록). 출처는 나온 순서, 경력은 정해진 순서로 있는 것만."""
    sources = list(dict.fromkeys(card.source for card in items))
    found = {group for card in items for group in career_groups(card.experience)}
    return sources, [group for group in (*CAREER_GROUPS, OTHER_CAREER, BLANK_EXPERIENCE) if group in found]


def apply(items: list[Card], filters: Filters) -> list[Card]:
    return [
        card
        for card in items
        if (not filters.sources or card.source in filters.sources)
        and (not filters.experiences or set(career_groups(card.experience)) & set(filters.experiences))
        and (filters.show_unscored or card.score is not None)
    ]


def chart(items: list[Card]) -> list[tuple[str, int]]:
    """막대 차트 자료 [(막대 이름, 종합점수)]. 점수 있는 카드만, 같은 이름은 뒤에 번호 (F5)."""
    data, used = [], {}
    for card in items:
        if card.score is None:
            continue
        name = f"{card.company} · {card.title}"
        used[name] = used.get(name, 0) + 1
        data.append((name if used[name] == 1 else f"{name} ({used[name]})", card.score))
    return data


def summary(items: list[Card]) -> list[tuple[str, int, str]]:
    """요약 칸 4개 [(이름, 수, 설명)]. 필터와 상관없이 시트 전체 기준 (v0.5.1 F2)."""
    return [
        ("전체 공고", len(items), "시트에 있는 공고"),
        ("평가 완료", sum(card.score is not None for card in items), "점수가 있는 공고"),
        ("추천 이상", sum(card.verdict in RECOMMENDED for card in items), "강력 추천 + 추천"),
        ("본문 미확보", sum(card.body == postings.MISSING for card in items), "이미지를 넣으면 채워짐"),
    ]


def error_message(error: Exception) -> str:
    """시트 읽기 실패를 화면 문구로. 예외 메시지에는 경로나 키가 섞일 수 있어 쓰지 않는다 (F9)."""
    if isinstance(error, (KeyError, FileNotFoundError)):
        return (
            "인증 정보를 찾지 못했습니다. .env의 GOOGLE_SERVICE_ACCOUNT_FILE, GOOGLE_SHEET_ID와 "
            "인증 파일 위치를 확인해 주세요."
        )
    if isinstance(error, (gspread.SpreadsheetNotFound, gspread.exceptions.APIError)):
        return "시트를 열지 못했습니다. 시트 ID와 서비스 계정 공유 설정을 확인해 주세요."
    if isinstance(error, (requests.ConnectionError, requests.Timeout)):
        return "네트워크 오류입니다. 인터넷 연결을 확인하고 새로고침해 주세요."
    return f"시트를 읽지 못했습니다 ({type(error).__name__})."

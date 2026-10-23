"""화면에 보일 내용 만들기: 공고 카드, 정렬, 필터, 차트 자료, 요약 칸, 오류 문구 (v0.5 F2–F10, F34, F47, v0.5.1 F2).

Streamlit을 import하지 않는다. app.py는 이 결과를 그리기만 해서, 규칙은 가짜 데이터로 테스트한다 (N5).
"""

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import gspread
import requests
import sqlalchemy.exc

from agent import gaps, postings, scoring, sheets, skills, store

UNKNOWN_SOURCE = "미상"  # 출처 칸이 빈 예전 줄 (F6)
BLANK_EXPERIENCE = "(없음)"  # 경력 칸이 빈 줄의 필터 값
CAREER_GROUPS = ("신입", "경력", "무관")  # 경력 필터 보기 (v0.5.2 F30)
OTHER_CAREER = "기타"  # 묶음으로 나누지 못한 경력 글자 (예: 인턴)
NOT_SCORED = "평가 전"
NONE = "없음"  # 빈 칸 표시 (F3)
PREVIEW = 600  # 평가 전 카드에 보일 원문 글자 수 (v0.5.2 F31)
PAGE_SIZE = 10  # 한 쪽에 보일 카드 수 (v0.5.2 F41)
TOP = 5  # 종합점수 차트 막대 수 (v0.5.2 F42)
RECOMMENDED = ("강력 추천", "추천")  # 요약 칸 "추천 이상" (v0.5.1 F2)
UPLOADABLE = (postings.MISSING, postings.PARTLY_UNREAD)  # 이미지 넣는 칸을 보일 본문 상태 (F47)
SCORE_NAMES = ("기술", "경력", "문화", "방향")  # 항목 점수 (v0.5.3 F1)
LAST_SEEN = Path("data/last_seen.txt")  # 화면을 마지막으로 연 시각, 커밋 안 함 (v0.5.3 F9, N3)
SOON = 7  # 마감까지 이 날수 이하면 빨간 D-n 배지, 넘으면 흰 배지 (v0.5.3 F7, v0.5.4 F4)
SORTS = ("score_desc", "score_asc", "deadline")  # 점수 높은 순, 낮은 순(v0.5.2 F40), 마감 임박 순(v0.5.3 F8)
_SPLIT = re.compile(r"\s*[,，;\n]\s*|\s+[/·]\s+")  # 글머리표로 나눌 곳. "CI/CD", "Python·SQL"처럼 붙은 /·는 그대로


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
    info: dict[str, str] = field(default_factory=dict)  # 수집 때 받은 칸. 평가 전에도 보인다 (v0.5.2 F31)
    checked: bool = False  # 시트 "평가" 체크박스 (v0.5.2 F39)
    hidden: bool = False  # 시트 "관심없음" (v0.5.2 F44)
    applied: bool = False  # 시트 "지원" (v0.5.3 F11)
    saved_at: str = ""  # 시트 "저장시각" (v0.5.3 F9)
    scores: dict[str, int | None] = field(default_factory=dict)  # 항목 점수, 근거 없으면 None (v0.5.3 F1, F6)
    strengths: list[str] = field(default_factory=list)  # v0.5.3 F2, F12
    gaps: list[str] = field(default_factory=list)

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
    scored_only: bool = False  # 기본은 평가 전 공고도 보인다 (v0.5.2 F32)
    sort: str = "score_desc"  # SORTS 중 하나. 점수 정렬에서 평가 전은 늘 아래 (v0.5.2 F40, v0.5.3 F8)
    hidden_only: bool = False  # 관심 없음으로 뺀 공고만. 기본은 뺀 공고를 숨김 (v0.5.2 F44)
    query: str = ""  # 회사명·직무 검색 (v0.5.3 F10)
    applied_only: bool = False  # 지원한 공고만 (v0.5.3 F11)
    image_only: bool = False  # 이미지를 넣어야 하는 공고만 (v0.5.4 F2)
    recommended_only: bool = False  # 강력 추천 + 추천만 (v0.5.4 F12)
    unscored_only: bool = False  # 평가 전 공고만 (v0.7.2 F3)


def _score(value: str) -> int | None:
    try:
        return int(value.strip())
    except ValueError:
        return None  # 비었거나 사람이 숫자가 아닌 값을 넣은 줄


_SCORE_KEYS = ("skills", "experience_score", "culture", "career")


def split_items(text: str) -> list[str]:
    """시트 한 칸 글을 글머리표 항목으로 (v0.5.3 F2, F3). 빈 항목은 뺀다."""
    return [item.strip() for item in _SPLIT.split(text or "") if item.strip()]


def _skill_key(name: str) -> str:
    return skills.key(name)  # 띄어쓰기·대소문자, 같은 말 사전 (v0.7.3 F2, F3)


def stack_chips(stack: str, known: list[str]) -> list[tuple[str, bool]]:
    """기술스택 칩 [(기술, 내 프로필에 있는지)] (v0.5.3 F4). 대소문자·공백 무시, 같은 말은 같게 (v0.7.3 F3)."""
    mine = {_skill_key(name) for name in known}
    return [(item, _skill_key(item) in mine) for item in split_items(stack)]


def days_left(deadline: str, today: date) -> int | None:
    """마감까지 남은 날. 상시·빈칸·모르는 글자는 None (v0.5.3 F7)."""
    try:
        return (date.fromisoformat(deadline.strip()[:10]) - today).days
    except ValueError:
        return None


def deadline_badge(deadline: str, today: date) -> tuple[str, str] | None:
    """(배지 글자, 색) 또는 None. 남은 날 D-n(7일 이하 빨강), 당일 D-day, 지나면 마감 (F7, v0.5.4 F4)."""
    days = days_left(deadline, today)
    if days is None:
        return None
    if days < 0:
        return "마감", "closed"
    return ("D-day" if days == 0 else f"D-{days}"), "low" if days <= SOON else "plain"


def _parse_time(text: str) -> datetime | None:
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text.strip(), pattern)
        except ValueError:
            continue
    return None


def is_new(card: Card, last_seen: datetime | None) -> bool:
    """화면을 마지막으로 연 뒤 저장된 공고 (v0.5.3 F9). 처음(None)이거나 저장시각을 모르면 아님."""
    saved = _parse_time(card.saved_at)
    return last_seen is not None and saved is not None and saved > last_seen


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
    info = {
        "지역": row["location"],
        "경력": row["experience"],
        "학력": row["education"],
        "키워드": row["keywords"],
        "마감": row["deadline"],
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
        info={name: value.strip() for name, value in info.items() if value.strip()},
        checked=scoring.is_true(row.get("check", "")),  # scoring.select_targets와 같은 규칙
        hidden=scoring.is_true(row.get("hidden", "")),
        applied=scoring.is_true(row.get("applied", "")),
        saved_at=row.get("saved_at", "").strip(),
        scores={name: _score(row[key]) for name, key in zip(SCORE_NAMES, _SCORE_KEYS, strict=True)},
        strengths=split_items(row["strengths"]),
        gaps=split_items(row["gaps"]),
    )


def preview(card: Card, limit: int = PREVIEW) -> str:
    """저장해 둔 원문 앞부분 (v0.5.2 F31). 없으면 빈 글자. 이미지 글자도 이어 붙인다."""
    content = postings.load(card.source_code, card.job_id) if card.job_id else None
    if not content:
        return ""
    text, ocr = postings.split(content)
    whole = "\n".join(part.strip() for part in (text, *ocr) if part.strip())
    return whole if len(whole) <= limit else whole[:limit].rstrip() + " …"


def with_checks(
    rows: list[dict],
    checks: dict[int, bool],
    hidden: dict[int, bool] | None = None,
    applied: dict[int, bool] | None = None,
) -> list[dict]:
    """화면에서 바꾼 체크·관심 없음·지원을 읽어 둔 시트 줄에 덮는다. 시트를 다시 읽지 않고 맞춘다.

    (v0.5.2 F39, F44, v0.5.3 F11)
    """
    changed = []
    for row in rows:
        number = row["row"]
        for key, overrides in (("check", checks), ("hidden", hidden), ("applied", applied)):
            if overrides and number in overrides:
                row = row | {key: "TRUE" if overrides[number] else "FALSE"}
        changed.append(row)
    return changed


def read_last_seen(path: Path) -> datetime | None:
    """화면을 마지막으로 연 시각 (v0.5.3 F9). 없거나 읽지 못하면 None (N3)."""
    try:
        return _parse_time(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_last_seen(path: Path, now: datetime) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{now:%Y-%m-%d %H:%M:%S}", encoding="utf-8")
    except OSError:
        pass  # 못 써도 화면은 뜬다. 다음에 NEW가 더 많이 보일 뿐 (N3)


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


def apply(items: list[Card], filters: Filters, today: date | None = None) -> list[Card]:
    """거르고 정렬한다. items는 cards()의 순서(점수 높은 순, 같으면 시트 줄 순, 평가 전은 뒤)."""
    shown = [
        card
        for card in items
        if (not filters.sources or card.source in filters.sources)
        and (not filters.experiences or set(career_groups(card.experience)) & set(filters.experiences))
        and (not filters.scored_only or card.score is not None)
        and (not filters.unscored_only or card.verdict == NOT_SCORED)  # 제외 공고는 평가한 것
        and card.hidden == filters.hidden_only
        and (not filters.applied_only or card.applied)
        and (not filters.image_only or card.can_upload)
        and (not filters.recommended_only or card.verdict in RECOMMENDED)
        and _matches(card, filters.query)
    ]
    if filters.sort == "score_asc":  # 같은 점수는 시트 줄 순 그대로 (F40)
        scored = sorted((c for c in shown if c.score is not None), key=lambda c: (c.score, c.row))
        shown = scored + [c for c in shown if c.score is None]
    elif filters.sort == "deadline":
        shown = sorted(shown, key=lambda c: _deadline_key(c, today or date.today()))
    return shown


def _matches(card: Card, query: str) -> bool:
    words = query.casefold().split()
    text = f"{card.company} {card.title}".casefold()
    return all(word in text for word in words)  # 여러 낱말이면 모두 들어 있어야 (F10)


def _deadline_key(card: Card, today: date) -> tuple[int, int, int]:
    # 남은 마감 → 상시·빈칸 → 지난 공고, 같으면 시트 줄 순 (v0.5.3 F8)
    days = days_left(card.deadline, today)
    if days is None:
        return 1, 0, card.row
    return (2, -days, card.row) if days < 0 else (0, days, card.row)


def page(items: list[Card], number: int, size: int = PAGE_SIZE) -> tuple[list[Card], int, int]:
    """(그 쪽 카드, 실제 쪽 번호, 전체 쪽 수). 범위 밖 번호는 처음·끝 쪽으로 (v0.5.2 F41)."""
    pages = max(1, -(-len(items) // size))
    number = min(max(1, number), pages)
    return items[(number - 1) * size : number * size], number, pages


def chart(items: list[Card], limit: int = TOP) -> list[tuple[str, int]]:
    """막대 차트 자료 [(막대 이름, 종합점수)]. 점수 높은 limit개만, 같은 이름은 뒤에 번호 (F5, v0.5.2 F42).

    정렬(F40)과 상관없이 높은 순이다.
    """
    best = sorted((c for c in items if c.score is not None), key=lambda c: (-c.score, c.row))[:limit]
    data, used = [], {}
    for card in best:
        name = f"{card.company} · {card.title}"
        used[name] = used.get(name, 0) + 1
        data.append((name if used[name] == 1 else f"{name} ({used[name]})", card.score))
    return data


def summary(items: list[Card]) -> list[tuple[str, int, str]]:
    """요약 칸 4개 [(이름, 수, 설명)]. 필터와 상관없이 시트 전체 기준 (v0.5.1 F2)."""
    return [
        ("전체 공고", len(items), "시트에 있는 공고" if store.kind() == "sheet" else "저장된 공고"),  # v0.6 D12
        ("평가 완료", sum(card.score is not None for card in items), "점수가 있는 공고"),
        ("추천 이상", sum(card.verdict in RECOMMENDED for card in items), "강력 추천 + 추천"),
        # 본문 미확보 + 이미지 일부 못 읽음. "이미지 필요한 공고만 보기"와 같은 기준 (v0.5.4 F3)
        ("이미지 필요", sum(card.can_upload for card in items), "넣으면 점수가 정확해짐"),
    ]


def stack_rank(items: list[Card], known: list[str], top: int | None = None) -> list[tuple[str, int, bool]]:
    """기술 스택 순위 [(기술, 나온 공고 수, 내 프로필에 있는지)] (v0.7 F11, D8, N5). 기본은 전부 (v0.7.3 F1).

    띄어쓰기·대소문자만 다른 이름과 같은 말 사전에 있는 이름은 같은 기술로 묶고(v0.7.3 F2), 한 공고 안에서는
    한 번만 센다. 이름은 사전에 있으면 대표 이름, 없으면 처음 나온 모양. 같은 수면 이름 순.
    내 기술 판단은 자세히의 기술 칩(stack_chips)과 같다.
    """
    mine = {_skill_key(name) for name in known}
    names: dict[str, str] = {}
    counts: dict[str, int] = {}
    for card in items:
        stack = card.details.get("기술스택", "")
        seen = set()
        for item in split_items("" if stack == NONE else stack):
            key = _skill_key(item)
            names.setdefault(key, skills.display(item))
            if key not in seen:
                seen.add(key)
                counts[key] = counts.get(key, 0) + 1
    ranked = sorted(counts, key=lambda key: (-counts[key], names[key].casefold()))
    return [(names[key], counts[key], key in mine) for key in ranked[:top]]


def gap_rank(items: list[Card], top: int | None = None) -> tuple[list[tuple[str, float, int]], int]:
    """부족한 점 순위 ([(이름, 가중 합, 공고 수)], 점수 없어 뺀 공고 수) (v0.7 F12, D7). 기본은 전부 (v0.7.3 F1).

    v0.3 --gaps와 같은 함수(gaps.analyze)를 써서 (100 − 종합점수)로 가중한다.
    """
    rows = [{"score": "" if card.score is None else str(card.score), "gaps": ",".join(card.gaps)} for card in items]
    ranked, _, excluded = gaps.analyze(rows, top)
    return ranked, excluded


def split_once(ranked: list[tuple], count_at: int) -> tuple[list[tuple], list[tuple]]:
    """순위를 (2건 이상, 1건만)으로 나눈다 (v0.7.4 F1). 1건은 이름순. count_at은 공고 수가 있는 자리."""
    many = [item for item in ranked if item[count_at] > 1]
    once = sorted((item for item in ranked if item[count_at] <= 1), key=lambda item: item[0].casefold())
    return many, once


def stats_csv(stack: list[tuple[str, int, bool]], gap: list[tuple[str, float, int]]) -> bytes:
    """기술 모아보기를 엑셀에서 바로 열리는 CSV로 (v0.7.4 F4). 한글이 깨지지 않게 UTF-8 BOM."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["구분", "순위", "이름", "공고 수", "내 기술", "가중치"])
    for number, (name, count, mine) in enumerate(stack, 1):
        writer.writerow(["많이 찾는 기술", number, name, count, "O" if mine else "", ""])
    for number, (name, weight, count) in enumerate(gap, 1):
        writer.writerow(["내가 부족한 것", number, name, count, "", f"{weight:.2f}"])
    return out.getvalue().encode("utf-8-sig")


def stats_text(stack: list[tuple[str, int, bool]], gap: list[tuple[str, float, int]], total: int) -> str:
    """기술 모아보기 전체를 붙여넣기 좋은 글로 (v0.7.4 F5). 1건짜리는 한 줄로 묶는다(F1과 같게)."""
    lines = [f"JOBVIS 기술 모아보기 (공고 {total}건 기준)"]
    for title, ranked, mark in (
        ("많이 찾는 기술", stack, lambda item: " (내 기술)" if item[2] else ""),
        ("내가 부족한 것", [(name, count, False) for name, _, count in gap], lambda item: ""),
    ):
        lines += ["", f"[{title}]"]
        many, once = split_once(ranked, 1)
        lines += [f"{number}. {item[0]} {item[1]}건{mark(item)}" for number, item in enumerate(many, 1)]
        if once:
            lines.append(f"1건씩: {', '.join(item[0] + mark(item) for item in once)}")
        if not ranked:
            lines.append("없음")
    return "\n".join(lines)


def filter_labels(filters: Filters) -> list[str]:
    """모아 보기 창 위에 보일 켜진 필터 이름 (v0.7 F10). 아무것도 없으면 빈 목록."""
    labels = []
    if filters.query.strip():
        labels.append(f"검색 '{filters.query.strip()}'")
    if filters.sources:
        labels.append("출처 " + "·".join(filters.sources))
    if filters.experiences:
        labels.append("경력 " + "·".join(filters.experiences))
    toggles = (
        (filters.scored_only, "평가된 공고만"),
        (filters.unscored_only, "평가 전 공고만"),
        (filters.recommended_only, "추천 이상만"),
        (filters.applied_only, "지원한 공고만"),
        (filters.image_only, "이미지 필요한 공고만"),
        (filters.hidden_only, "관심 없는 공고만"),
    )
    return labels + [name for on, name in toggles if on]


def error_message(error: Exception) -> str:
    """시트·DB 읽기 실패를 화면 문구로. 예외 메시지에는 경로나 키가 섞일 수 있어 쓰지 않는다 (F9)."""
    try:
        where = store.kind()
    except store.StorageError as wrong:  # JOBVIS_STORAGE 값이 틀림
        return str(wrong)
    if where == "db":  # v0.6 F6. DB 주소에는 비밀번호가 들어 있어 예외 글을 보여주지 않는다
        if isinstance(error, KeyError):
            return "DB 주소(DATABASE_URL)가 없습니다. docker compose로 실행했는지 확인해 주세요."
        if isinstance(error, sqlalchemy.exc.SQLAlchemyError):
            return "DB에 연결하지 못했습니다. docker compose ps로 db가 떠 있는지 확인해 주세요."
        return f"DB를 읽지 못했습니다 ({type(error).__name__})."
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

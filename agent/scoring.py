"""적합도: LLM 응답 검증, 종합 점수·별점·판정 계산, 점수 보정, 평가할 줄 고르기."""

import math
from dataclasses import dataclass

from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field, field_validator

from agent import postings

# ai-job-search 원본 가중치 (F11)
WEIGHTS = {"skills": 30, "experience": 25, "culture": 15, "career": 30}
MAX_ITEMS = 3  # 강점·부족한 점 최대 개수 (F9)

# 점수 보정 (v0.5 F26–F29). 부족 연수 → 경력점수 상한. 3년 이상 부족은 모두 30.
EXPERIENCE_CAPS = {1: 60, 2: 45, 3: 30}
CAP_SHORT = 79  # 경력이 부족한 공고의 종합 상한 (F27)
CAP_LOW_TRUST = 69  # 신뢰 낮음 공고의 종합 상한 (F29)
EXCLUDED = "제외 (경력 요구)"  # 신입 제외 판정 (F36)

# "신뢰" 열 값 (F28)
HIGH, MEDIUM, LOW = "높음", "보통", "낮음"


class Evaluation(BaseModel):
    summary: str
    skills: int = Field(ge=0, le=100)
    experience: int = Field(ge=0, le=100)
    culture: int | None = Field(ge=0, le=100)  # 공고에 근거가 없으면 null (F10)
    career: int = Field(ge=0, le=100)
    strengths: list[str] = []
    gaps: list[str] = []
    # 본문 요약 세 칸 (v0.4 F18). 본문에 없으면 빈 문자열이고, 빠지거나 null이어도 실패로 보지 않는다.
    duties: str = ""
    preferred: str = ""
    stack: str = ""
    # 공고가 요구하는 최소 경력 연수 (v0.5 F25). 신입·무관은 0, 공고에 없거나 빠지면 null
    required_years: int | None = Field(default=None, ge=0)

    @field_validator("summary")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("요약이 비어 있음")
        return value.strip()

    @field_validator("duties", "preferred", "stack", mode="before")
    @classmethod
    def _text_or_blank(cls, value) -> str:
        return "" if value is None else str(value).strip()

    @field_validator("strengths", "gaps")
    @classmethod
    def _first_items(cls, values: list[str]) -> list[str]:
        return [v.strip() for v in values if v.strip()][:MAX_ITEMS]


def parse(text: str) -> Evaluation:
    # ```json 코드 블록으로 감싸 와도 JsonOutputParser가 벗긴다. 형식이 틀리면 ValueError 계열 예외 (F15).
    return Evaluation.model_validate(JsonOutputParser().parse(text))


def _half_up(value: float) -> int:
    # 파이썬 round는 2.5를 2로 만드는 은행가 반올림이라 쓰지 않는다.
    return math.floor(value + 0.5)


def overall(evaluation: Evaluation) -> int:
    scores = {name: getattr(evaluation, name) for name in WEIGHTS}
    used = {name: score for name, score in scores.items() if score is not None}  # 근거 없는 항목은 뺀다
    total_weight = sum(WEIGHTS[name] for name in used)
    return _half_up(sum(WEIGHTS[name] * score for name, score in used.items()) / total_weight)


def verdict(score: int) -> str:
    if score >= 80:
        return "강력 추천"
    if score >= 60:
        return "추천"
    if score >= 40:
        return "보통"
    return "비추천"


def stars(score: int) -> str:
    filled = _half_up(score / 20)
    return "★" * filled + "☆" * (5 - filled)


def trust(body: str, with_body: bool) -> str:
    """원문으로 채점하지 못했으면 낮음, 이미지 일부 못 읽음이면 보통, 나머지는 높음 (F28)."""
    if not with_body:
        return LOW
    return MEDIUM if body == postings.PARTLY_UNREAD else HIGH


def excluded(experience: str, years: int) -> bool:
    """신입(0년)인데 경력 칸에 신입·무관이 없으면 평가하지 않는다. 경력 칸이 비면 평가한다 (F36)."""
    text = experience.strip()
    return years == 0 and bool(text) and "신입" not in text and "무관" not in text


@dataclass
class Adjusted:
    experience: int
    total: int
    stars: str
    verdict: str
    note: str  # "보정" 열 문구 (F32). 적용한 것이 없으면 빈칸


def adjust(evaluation: Evaluation, years: int, trust_level: str) -> Adjusted:
    """경력 상한 → 종합점수 → 종합 상한 → 별점·판정 순서로 계산한다 (F35)."""
    notes = []
    experience = evaluation.experience
    required = evaluation.required_years
    short = 0 if required is None else required - years
    if short >= 1:
        cap = EXPERIENCE_CAPS[min(short, 3)]
        if experience > cap:  # LLM 점수가 상한보다 높을 때만 낮춘다 (F26)
            notes.append(f"경력 {experience}→{cap} ({required}년 요구, {years}년)")
            experience = cap
    total = overall(evaluation.model_copy(update={"experience": experience}))
    caps = []
    if short >= 1:
        caps.append((CAP_SHORT, "경력 부족"))
    if trust_level == LOW:
        caps.append((CAP_LOW_TRUST, "신뢰 낮음"))
    if caps:
        cap, reason = min(caps)  # 둘 다 걸리면 낮은 쪽 하나만
        if total > cap:
            notes.append(f"종합 {total}→{cap} ({reason})")
            total = cap
    return Adjusted(experience, total, stars(total), verdict(total), ", ".join(notes))


def is_true(value: str) -> bool:
    """시트 체크박스 값. 대소문자 무시 ("TRUE", "true")."""
    return str(value).strip().upper() == "TRUE"


def select_targets(rows: list[dict], mode: str) -> tuple[list[dict], list[dict]]:
    """mode가 checked면 체크한 줄(F7), all이면 점수 없는 줄(F8). 공고 정보가 없는 줄은 건너뛴다(F16).

    all은 신입 제외 줄을 고르지 않는다. 점수 칸이 비어 매번 다시 골라지기 때문이다 (v0.5 설계).
    관심 없음으로 뺀 줄은 어느 쪽도 고르지 않는다 (v0.5.2 F44).
    """
    rows = [row for row in rows if not is_true(row.get("hidden", ""))]
    if mode == "checked":
        chosen = [row for row in rows if is_true(row.get("check", ""))]
    else:
        chosen = [
            row for row in rows if not row.get("score", "").strip() and row.get("verdict", "").strip() != EXCLUDED
        ]
    targets, skipped = [], []
    for row in chosen:
        has_info = any(row.get(key, "").strip() for key in ("experience", "education", "keywords"))
        (targets if has_info else skipped).append(row)
    return targets, skipped

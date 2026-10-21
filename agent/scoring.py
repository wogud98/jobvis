"""적합도: LLM 응답 검증, 종합 점수·별점·판정 계산, 평가할 줄 고르기."""

import math

from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field, field_validator

# ai-job-search 원본 가중치 (F11)
WEIGHTS = {"skills": 30, "experience": 25, "culture": 15, "career": 30}
MAX_ITEMS = 3  # 강점·부족한 점 최대 개수 (F9)


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


def select_targets(rows: list[dict], mode: str) -> tuple[list[dict], list[dict]]:
    """mode가 checked면 체크한 줄(F7), all이면 점수 없는 줄(F8). 공고 정보가 없는 줄은 건너뛴다(F16)."""
    if mode == "checked":
        chosen = [row for row in rows if row.get("check", "").strip().upper() == "TRUE"]
    else:
        chosen = [row for row in rows if not row.get("score", "").strip()]
    targets, skipped = [], []
    for row in chosen:
        has_info = any(row.get(key, "").strip() for key in ("experience", "education", "keywords"))
        (targets if has_info else skipped).append(row)
    return targets, skipped

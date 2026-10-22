"""평가에 쓸 내 프로필(profile.yaml)을 읽고, 검사하고, 저장하고, LLM에 넘길 글로 바꾼다 (v0.5 F11–F24)."""

import os
import tempfile
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError, model_validator


def default_path() -> str:
    """기본 프로필 경로. Docker는 볼륨 안 data/profile.yaml을 JOBVIS_PROFILE로 넣는다 (v0.6 D7)."""
    return os.getenv("JOBVIS_PROFILE", "").strip() or "profile.yaml"


DEFAULT = default_path()  # 실행 환경 변수로 정해진다. .env는 import 뒤에 읽어 여기 반영되지 않는다
EXAMPLE = "profile.example.yaml"
LEGACY = "profile.md"  # v0.3–v0.4 프로필. 자동으로 바꾸지 않는다 (F16)
MAX_YEARS = 50


class ProfileError(Exception):
    """프로필 파일이 없거나, 깨졌거나, 필수 칸이 틀림 (F13, F16)."""


def _as_list(value) -> list[str]:
    # 목록 칸에 글자 하나만 적어도 한 항목 목록으로 받는다. 빈 항목과 앞뒤 공백은 지운다.
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        raise ValueError("목록이어야 함")
    return [str(item).strip() for item in value if item is not None and str(item).strip()]


def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        raise ValueError("글자여야 함")
    return str(value).strip()


TextList = Annotated[list[str], BeforeValidator(_as_list)]
Text = Annotated[str, BeforeValidator(_as_text)]
Required = Annotated[list[str], BeforeValidator(_as_list), Field(min_length=1)]


def _whole_number(value):
    # 2.5, "2년", true는 틀림 (F12). YAML의 true는 bool이라 int로 넘어가지 않게 먼저 막는다.
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("정수여야 함")
    return value


class _Part(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Skills(_Part):
    main: Required
    can_use: TextList = []  # 써 본 기술도 여기에 (v0.5.2 F36)
    certificates: TextList = []

    @model_validator(mode="after")
    def _no_overlap(self):
        # 주력에 있는 기술은 다룰 수 있음에서 뺀다. 칸 안에서 겹치는 것도 한 번만 (v0.5.2 F37)
        self.main = list(dict.fromkeys(self.main))
        self.can_use = [item for item in dict.fromkeys(self.can_use) if item not in self.main]
        return self


class Experience(_Part):
    years: Annotated[int, BeforeValidator(_whole_number), Field(ge=0, le=MAX_YEARS)]
    projects: TextList = []
    degree: Text = ""
    training: TextList = []


class Direction(_Part):
    jobs: Required
    goals: Text = ""
    locations: TextList = []


class Profile(_Part):
    skills: Skills
    experience: Experience
    direction: Direction
    culture: TextList = []


_REASONS = {
    "missing": "필수 칸이 없음",
    "too_short": "1개 이상 적어야 함",
    "greater_than_equal": f"0–{MAX_YEARS} 사이 정수여야 함",
    "less_than_equal": f"0–{MAX_YEARS} 사이 정수여야 함",
    "model_type": "칸 아래에 항목을 적어야 함",
    "model_attributes_type": "칸 아래에 항목을 적어야 함",
}


def _messages(error: ValidationError) -> list[str]:
    # Pydantic 메시지에는 입력값이 들어가므로 칸 경로와 이유만 쓴다 (N2).
    lines = []
    for item in error.errors():
        where = ".".join(str(part) for part in item["loc"])
        reason = _REASONS.get(item["type"])
        if reason is None:
            message = str(item.get("ctx", {}).get("error", "")) or "형식이 틀림"
            reason = message.removeprefix("Value error, ")
        lines.append(f"{where}: {reason}")
    return lines


def _unknown(data: dict, model: type[BaseModel], prefix: str = "") -> list[str]:
    # 모르는 칸(오타 등)을 "skills.mian"처럼 경로로 찾는다 (F14).
    names = []
    for key, value in data.items():
        field = model.model_fields.get(key)
        path = f"{prefix}{key}"
        if field is None:
            names.append(path)
        elif isinstance(value, dict) and isinstance(field.annotation, type) and issubclass(field.annotation, BaseModel):
            names.extend(_unknown(value, field.annotation, f"{path}."))
    return names


def upgrade(data):
    """예전 skills.tried(써 본 적 있음)를 can_use 뒤에 붙인다 (v0.5.2 F36). 받은 dict는 바꾸지 않는다."""
    skills = data.get("skills") if isinstance(data, dict) else None
    if not isinstance(skills, dict) or "tried" not in skills:
        return data
    skills = dict(skills)
    tried = skills.pop("tried")
    can_use = skills.get("can_use")
    lists = [value if isinstance(value, list) else [value] for value in (can_use, tried) if value is not None]
    skills["can_use"] = [item for value in lists for item in value]
    return data | {"skills": skills}


def validate(data) -> tuple[Profile, list[str]]:
    """dict를 검사해 (Profile, 모르는 칸 경고)를 돌려준다. 틀리면 칸 경로가 담긴 ProfileError."""
    if not isinstance(data, dict):
        raise ProfileError("프로필 형식이 틀립니다: skills, experience, direction 칸이 있어야 합니다")
    data = upgrade(data)
    try:
        profile = Profile.model_validate(data)
    except ValidationError as e:
        raise ProfileError("프로필을 고쳐 주세요.\n" + "\n".join(f"  {line}" for line in _messages(e))) from None
    return profile, [f"모르는 칸(무시함): {name}" for name in _unknown(data, Profile)]


def parse(text: str) -> tuple[Profile, list[str]]:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        where = f" ({mark.line + 1}번째 줄 근처)" if mark else ""
        raise ProfileError(f"프로필 YAML 형식이 깨졌습니다{where}") from None
    if data is None:
        raise ProfileError(f"프로필 파일이 비어 있습니다. {EXAMPLE}를 참고해 내용을 채워 주세요.")
    return validate(data)


def missing_message(path: str) -> str:
    lines = [
        f"프로필 파일이 없습니다: {path}",
        "만드는 방법: streamlit run app.py 를 열어 프로필 탭에서 저장하거나,"
        f" {EXAMPLE} 를 {DEFAULT} 로 복사해 채우세요.",
    ]
    if Path(path).with_name(LEGACY).is_file():
        lines.append(f"예전 {LEGACY} 가 있습니다. 내용을 옮겨 적어 주세요 (자동으로 바꾸지 않습니다).")
    return "\n".join(lines)


def load(path: str) -> tuple[Profile, list[str]]:
    file = Path(path)
    if not file.is_file():
        raise ProfileError(missing_message(path))
    return parse(file.read_text(encoding="utf-8"))


def to_dict(profile: Profile) -> dict:
    # 요구사항 예시와 같은 칸 순서
    return profile.model_dump()


def dump(profile: Profile) -> str:
    return yaml.safe_dump(to_dict(profile), allow_unicode=True, sort_keys=False)


def save(profile: Profile, path: str) -> None:
    """임시 파일에 쓰고 바꿔 끼운다. 쓰다 실패해도 기존 파일은 그대로 (설계 "프로필 탭")."""
    target = Path(path)
    fd, temp = tempfile.mkstemp(dir=target.parent or ".", prefix=".profile-", suffix=".yaml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(dump(profile))
        Path(temp).replace(target)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


def read_raw(path: str) -> dict | None:
    """화면용. 파일 내용을 검사 없이 dict로 (없으면 None). 깨진 YAML이면 ProfileError (F21)."""
    file = Path(path)
    if not file.is_file():
        return None
    try:
        data = yaml.safe_load(file.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        raise ProfileError("프로필 YAML 형식이 깨져서 화면에서 저장하지 않습니다. 파일을 직접 고쳐 주세요.") from None
    return data if isinstance(data, dict) else {}


def _join(values: list[str]) -> str:
    return ", ".join(values) if values else "없음"


def to_prompt(profile: Profile) -> str:
    """LLM에 넘기는 프로필 글. 점수 항목별 제목으로 나눈다 (F22–F24)."""
    skills, experience, direction = profile.skills, profile.experience, profile.direction
    years = f"{experience.years}년" + (" (신입)" if experience.years == 0 else "")
    culture = [f"- {item}" for item in profile.culture] or ["- 선호 문화 정보 없음"]
    return "\n".join(
        [
            "## 기술",
            f"- 주력: {_join(skills.main)}",
            f"- 다룰 수 있음: {_join(skills.can_use)}",
            f"- 자격증: {_join(skills.certificates)}",
            "## 경력",
            f"- 경력 연수: {years}",
            f"- 학력: {experience.degree or '없음'}",
            f"- 프로젝트: {_join(experience.projects)}",
            f"- 교육 이수: {_join(experience.training)}",
            "## 방향",
            f"- 희망 직무: {_join(direction.jobs)}",
            f"- 하고 싶은 일: {direction.goals or '없음'}",
            f"- 희망 지역: {_join(direction.locations)}",
            "## 문화",
            *culture,
        ]
    )

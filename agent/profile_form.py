"""프로필 탭 입력란: 칸 목록, 추천 목록, 파일 값 ↔ 입력란 값 바꾸기 (v0.5 F17–F21, v0.5.1 F8–F15).

Streamlit을 import하지 않는다. app.py는 이 결과로 입력란을 그리기만 해서, 규칙은 가짜 데이터로 테스트한다 (N4).
저장 형식(profile.yaml)은 v0.5와 같다 (N2). 검사는 user_profile.validate가 한다.
"""

from dataclasses import dataclass

from agent import user_profile

SLIDER_MAX = 10  # 경력 슬라이더 최댓값 (v0.5 F18, v0.7.2 F13 30→10). 파일 값이 더 크면 그 값까지 늘린다

# 추천 목록 (F10, F11). 코드에 고정. 목록에 없는 값은 화면에서 직접 입력해 추가한다
SKILLS = [
    "Python", "Java", "C", "C++", "C#", "JavaScript", "TypeScript", "Kotlin", "Go", "SQL",
    "Oracle", "MySQL", "PostgreSQL", "Spring Boot", "Django", "FastAPI", "Node.js", "React", "Vue",
    "Linux", "Git", "Docker", "Kubernetes", "AWS", "GCP", "LangChain", "LangGraph", "PyTorch",
    "TensorFlow", "OpenCV", "Pandas",
]  # fmt: skip
CERTIFICATES = [
    "정보처리기사", "정보처리산업기사", "SQLD", "SQLP", "ADsP", "ADP", "빅데이터분석기사",
    "리눅스마스터 1급", "리눅스마스터 2급", "정보보안기사", "네트워크관리사 2급", "AWS SAA",
    "컴퓨터활용능력 1급", "TOEIC", "OPIc",
]  # fmt: skip
JOBS = [
    "백엔드 개발", "프론트엔드 개발", "풀스택 개발", "AI 서비스 개발", "ML 엔지니어", "데이터 엔지니어",
    "데이터 분석", "DevOps·인프라", "임베디드·펌웨어", "시뮬레이션·M&S", "QA·테스트",
    "FDE(Forward Deployed Engineer)", "솔루션 엔지니어", "기술 지원",
]  # fmt: skip
LOCATIONS = [
    "서울", "경기", "인천", "대전", "세종", "충북", "충남", "대구", "경북", "부산", "울산", "경남",
    "광주", "전북", "전남", "강원", "제주", "재택·원격",
]  # fmt: skip
CULTURE = [
    "코드 리뷰 문화", "문서화가 잘 된 팀", "멘토링·신입 교육", "기술 공유·스터디", "교육비·성장 지원",
    "자율 출퇴근", "재택 가능", "수평적인 소통", "목적과 방향이 분명한 조직", "안정적으로 오래 다닐 곳",
    "몰입할 수 있는 환경", "빠르게 실행하는 팀",
]  # fmt: skip
DEGREES = ["고등학교 졸업", "전문대 졸업(2–3년)", "대학교 졸업(4년)", "석사", "박사"]  # F13

GROUPS = [  # 묶음 (F9). (파일 첫 칸, 제목, 설명)
    ("skills", "🛠 기술", "기술 점수에 씀"),
    ("experience", "💼 경력", "경력 점수에 씀"),
    ("direction", "🧭 방향", "방향 점수에 씀"),
    ("culture", "🤝 문화", "문화 점수에 씀 · 비워도 됨"),
]


@dataclass(frozen=True)
class Field:
    keys: tuple[str, ...]  # 파일 칸 경로
    label: str
    kind: str  # pick / lines / text / years / degree / culture
    help: str = ""
    placeholder: str = ""
    suggestions: tuple[str, ...] = ()
    required: bool = False


FIELDS = [
    Field(
        ("skills", "main"),
        "주력 기술",
        "pick",
        "실무나 프로젝트에서 주로 쓴 것. 1개 이상",
        "골라 주세요",
        tuple(SKILLS),
        True,
    ),
    Field(
        ("skills", "can_use"),
        "다룰 수 있음",
        "pick",
        "찾아보며 쓸 수 있거나 공부·실습으로 써 본 것. 주력 기술에 고른 것은 빠짐",
        "골라 주세요",
        tuple(SKILLS),
    ),
    Field(("skills", "certificates"), "자격증", "pick", "", "골라 주세요", tuple(CERTIFICATES)),
    Field(("experience", "years"), "경력 연수", "years", "직무 경력 연수. 신입은 0", required=True),
    Field(("experience", "degree"), "최종 학력", "degree", "고르고 전공을 적습니다", "예: 컴퓨터공학"),
    Field(
        ("experience", "projects"),
        "프로젝트",
        "lines",
        "한 줄에 하나",
        "예: LangGraph로 채용공고 수집·평가 에이전트 개발 (JOBVIS)",
    ),
    Field(("experience", "training"), "교육 이수", "lines", "한 줄에 하나", "예: SSAFY 수료"),
    Field(
        ("direction", "jobs"),
        "희망 직무",
        "pick",
        "지원하려는 직무. 1개 이상",
        "1개 이상 골라 주세요",
        tuple(JOBS),
        True,
    ),
    Field(("direction", "locations"), "희망 지역", "pick", "", "골라 주세요", tuple(LOCATIONS)),
    Field(
        ("direction", "goals"),
        "하고 싶은 일",
        "text",
        "방향 점수의 근거. 구체적일수록 좋음",
        "예: LLM을 활용한 서비스 개발, API 서버 설계",
    ),
    Field(
        ("culture",),
        "선호 문화",
        "culture",
        "골라 누르고, 없으면 아래에 한 줄에 하나씩",
        "예: 목적이 분명하고 몰입할 수 있는 환경",
        tuple(CULTURE),
    ),
]


def _get(data, keys: tuple[str, ...]):
    for key in keys:
        data = data.get(key) if isinstance(data, dict) else None
    return data


def _items(value) -> list[str]:
    """파일 값(검사 전)을 목록으로. 글자 하나면 한 항목, 목록·글자가 아니면 빈 목록. 같은 항목은 한 번만."""
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    items = [str(item).strip() for item in value if item is not None and not isinstance(item, (dict, list))]
    return list(dict.fromkeys(item for item in items if item))


def options(suggestions: tuple[str, ...], current: list[str]) -> list[str]:
    """고르기 칸의 보기: 추천 목록 뒤에 파일에만 있는 값을 붙인다. 파일 값을 잃지 않게 (F11)."""
    return list(suggestions) + [item for item in current if item not in suggestions]


def split_degree(text: str) -> tuple[str, str]:
    """ "대학교 졸업(4년), 컴퓨터공학" → (학력, 전공). 학력으로 시작하지 않으면 전체를 전공 칸에 (F13)."""
    text = text.strip()
    for degree in DEGREES:
        if text == degree or text.startswith(degree + ","):
            return degree, text[len(degree) :].lstrip(",").strip()
    return "", text


def join_degree(degree: str, major: str) -> str:
    return ", ".join(part for part in (degree.strip(), major.strip()) if part)


def split_culture(items: list[str]) -> tuple[list[str], str]:
    """선호 문화를 (추천에서 고른 것, 직접 적은 줄 글자)로 (F12)."""
    picked = [item for item in items if item in CULTURE]
    return picked, "\n".join(item for item in items if item not in CULTURE)


def _lines(text: str) -> list[str]:
    return [line.strip() for line in str(text).splitlines() if line.strip()]


# 앞 칸에 고른 기술은 뒤 칸에서 고를 수 없다 (v0.5.2 F37). 뒤 칸 → 앞 칸
TAKEN_BY = {("skills", "can_use"): ("skills", "main")}


def taken(values: dict, keys: tuple[str, ...]) -> list[str]:
    """이 칸에서 고를 수 없는 항목 (앞 칸에 이미 고른 것)."""
    owner = TAKEN_BY.get(keys)
    return list(values.get(owner) or []) if owner else []


def without_taken(values: dict) -> dict:
    """앞 칸과 겹치는 항목을 뒤 칸에서 뺀 입력란 값."""
    values = dict(values)
    for keys in TAKEN_BY:
        values[keys] = [item for item in values.get(keys) or [] if item not in taken(values, keys)]
    return values


def to_form(data: dict | None) -> dict:
    """파일 내용(검사 전)을 입력란 기본값으로. 틀린 값은 빈 값으로 (연수는 0).

    예전 써 본 적 있음(tried)은 다룰 수 있음에 붙이고, 주력과 겹치는 기술은 뺀다 (v0.5.2 F36, F37).
    """
    data = user_profile.upgrade(data or {})
    values = {}
    for field in FIELDS:
        value = _get(data, field.keys)
        if field.kind == "years":
            ok = isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= user_profile.MAX_YEARS
            values[field.keys] = value if ok else 0
        elif field.kind == "pick":
            values[field.keys] = _items(value)
        elif field.kind == "lines":
            values[field.keys] = "\n".join(_items(value))
        elif field.kind == "culture":
            values[field.keys] = split_culture(_items(value))
        else:
            text = "" if value is None or isinstance(value, (dict, list)) else str(value)
            values[field.keys] = split_degree(text) if field.kind == "degree" else text
    return without_taken(values)


def from_form(values: dict) -> dict:
    """입력란 값을 프로필 dict로. 빈 항목·앞뒤 공백·겹치는 항목(칸 사이 포함)은 지운다."""
    data: dict = {}
    values = without_taken(values)
    for field in FIELDS:
        value = values.get(field.keys)
        if field.kind == "pick":
            value = _items(list(value or []))
        elif field.kind == "lines":
            value = _lines(value or "")
        elif field.kind == "degree":
            value = join_degree(*(value or ("", "")))
        elif field.kind == "culture":
            picked, others = value or ([], "")
            value = _items(list(picked) + _lines(others))
        elif field.kind == "text":
            value = str(value or "").strip()
        target = data
        for key in field.keys[:-1]:
            target = target.setdefault(key, {})
        target[field.keys[-1]] = value
    return data


def required_status(values: dict) -> list[tuple[str, bool]]:
    """필수 칸 배지 (F8). (칸 이름, 채웠는지). 경력 연수는 0도 값이라 늘 채움."""
    status = []
    for field in FIELDS:
        if field.required:
            value = values.get(field.keys)
            done = isinstance(value, int) if field.kind == "years" else bool(_items(list(value or [])))
            status.append((field.label, done))
    return status


def group_fields(group: str) -> list[Field]:
    return [field for field in FIELDS if field.keys[0] == group]

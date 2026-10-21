from pathlib import Path

import pytest

from agent import profile_form, user_profile

ROOT = Path(__file__).parent.parent
MAIN, YEARS, DEGREE = ("skills", "main"), ("experience", "years"), ("experience", "degree")
JOBS, CULTURE, PROJECTS = ("direction", "jobs"), ("culture",), ("experience", "projects")
CAN_USE = ("skills", "can_use")


def blank() -> dict:
    return profile_form.to_form(None)


def test_form_round_trip_from_example_file():
    raw = user_profile.read_raw(str(ROOT / "profile.example.yaml"))

    values = profile_form.to_form(raw)

    assert values[MAIN] == ["Python", "SQL"]  # 고르기 칸 (F10)
    assert values[YEARS] == 0
    assert values[DEGREE] == ("대학교 졸업(4년)", "컴퓨터공학")  # F13
    assert values[PROJECTS] == "LangGraph로 채용공고 수집·평가 에이전트 개발 (JOBVIS)"  # 한 줄에 하나
    profile, _ = user_profile.validate(profile_form.from_form(values))
    assert profile == user_profile.load(str(ROOT / "profile.example.yaml"))[0]  # 저장 형식은 v0.5와 같음 (N2)


def test_form_defaults_for_missing_or_wrong_values():
    values = profile_form.to_form({"experience": {"years": "2년", "degree": ["x"]}, "skills": "Python"})

    assert values[YEARS] == 0
    assert values[MAIN] == []  # skills가 dict가 아니면 빈 값
    assert values[DEGREE] == ("", "")
    assert blank()[CULTURE] == ([], "")


def test_single_text_in_pick_field_becomes_one_item():
    values = profile_form.to_form({"skills": {"main": "Python", "can_use": [None, " ", "Go", "Go"]}})

    assert values[MAIN] == ["Python"]
    assert values[CAN_USE] == ["Go"]  # 빈 항목·겹치는 항목 지움


def test_old_tried_joins_can_use_and_main_is_removed():
    data = {"skills": {"main": ["Python"], "can_use": "Java", "tried": ["Docker", "Python", "Java"]}}

    values = profile_form.to_form(data)

    assert values[CAN_USE] == ["Java", "Docker"]  # 써 본 적 있음은 다룰 수 있음으로 (v0.5.2 F36), 주력과 겹침 뺌 (F37)
    assert ("skills", "tried") not in values
    assert data["skills"]["tried"] == ["Docker", "Python", "Java"]  # 받은 dict는 바꾸지 않음


def test_from_form_removes_skills_already_in_main():
    values = blank() | {MAIN: ["Python", "SQL"], CAN_USE: ["SQL", "Git", "Git"], YEARS: 1}

    data = profile_form.from_form(values)

    assert data["skills"]["main"] == ["Python", "SQL"]
    assert data["skills"]["can_use"] == ["Git"]  # 칸 사이 중복도 지움 (F37)
    assert "tried" not in data["skills"]


def test_taken_and_without_taken():
    values = {MAIN: ["Python"], CAN_USE: ["Python", "Go"]}

    assert profile_form.taken(values, CAN_USE) == ["Python"]
    assert profile_form.taken(values, MAIN) == []  # 주력은 다른 칸에 막히지 않음
    assert profile_form.without_taken(values)[CAN_USE] == ["Go"]
    assert values[CAN_USE] == ["Python", "Go"]  # 받은 값은 바꾸지 않음


def test_options_keep_file_values_not_in_suggestions():
    choices = profile_form.options(("Python", "Java"), ["Java", "VB6"])

    assert choices == ["Python", "Java", "VB6"]  # 파일에만 있는 값도 보기에 남음 (F11)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("대학교 졸업(4년), 컴퓨터공학", ("대학교 졸업(4년)", "컴퓨터공학")),
        ("석사", ("석사", "")),
        ("목원대 지능로봇공학과 학사", ("", "목원대 지능로봇공학과 학사")),  # 형식이 다르면 전공 칸에 그대로
        ("석사과정 수료", ("", "석사과정 수료")),  # 학력 이름으로 시작해도 쉼표가 없으면 그대로
        ("", ("", "")),
    ],
)
def test_split_degree(text, expected):
    assert profile_form.split_degree(text) == expected


def test_join_degree_round_trip_and_blanks():
    assert profile_form.join_degree("대학교 졸업(4년)", " 컴퓨터공학 ") == "대학교 졸업(4년), 컴퓨터공학"
    assert profile_form.join_degree("", "목원대 지능로봇공학과 학사") == "목원대 지능로봇공학과 학사"
    assert profile_form.join_degree("석사", "") == "석사"
    assert profile_form.join_degree("", "") == ""


def test_culture_splits_into_picked_and_own_lines_without_losing_items():
    items = ["코드 리뷰 문화", "목적이 분명한 팀", "재택 가능"]

    picked, others = profile_form.to_form({"culture": items})[CULTURE]

    assert picked == ["코드 리뷰 문화", "재택 가능"]
    assert others == "목적이 분명한 팀"  # 목록에 없는 것은 직접 적기 칸으로 (F12)
    data = profile_form.from_form(blank() | {CULTURE: (picked, others)})
    assert sorted(data["culture"]) == sorted(items)


def test_culture_picked_and_typed_same_item_is_saved_once():
    data = profile_form.from_form(blank() | {CULTURE: (["재택 가능"], "재택 가능\n\n  야근 없는 곳 \n")})

    assert data["culture"] == ["재택 가능", "야근 없는 곳"]


def test_form_cleans_items_and_lines():
    values = blank() | {
        MAIN: [" Python ", "Python", "", "SQL"],
        YEARS: 2,
        JOBS: ["백엔드 개발"],
        PROJECTS: "A\n\n  B  \n",
        ("direction", "goals"): "  API 서버  ",
    }

    data = profile_form.from_form(values)

    assert data["skills"]["main"] == ["Python", "SQL"]
    assert data["experience"]["projects"] == ["A", "B"]
    assert data["direction"]["goals"] == "API 서버"
    assert data["culture"] == []
    assert user_profile.validate(data)[0].direction.jobs == ["백엔드 개발"]


def test_form_without_required_fields_is_rejected():
    with pytest.raises(user_profile.ProfileError) as exc_info:
        user_profile.validate(profile_form.from_form(blank()))

    assert "skills.main" in str(exc_info.value) and "direction.jobs" in str(exc_info.value)


def test_required_status_badges():
    assert profile_form.required_status(blank()) == [("주력 기술", False), ("경력 연수", True), ("희망 직무", False)]
    filled = blank() | {MAIN: ["Python"], JOBS: [" ", "FDE"]}
    assert [done for _, done in profile_form.required_status(filled)] == [True, True, True]  # F8


def test_every_file_field_has_one_input_in_a_group():
    groups = {group for group, _, _ in profile_form.GROUPS}

    assert all(field.keys[0] in groups for field in profile_form.FIELDS)  # 4묶음 (F9)
    assert len({field.keys for field in profile_form.FIELDS}) == len(profile_form.FIELDS) == 11
    assert [field.label for field in profile_form.FIELDS if field.required] == ["주력 기술", "경력 연수", "희망 직무"]
    assert all(field.suggestions for field in profile_form.FIELDS if field.kind in ("pick", "culture"))

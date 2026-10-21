from pathlib import Path

import pytest
import yaml

from agent import user_profile

ROOT = Path(__file__).parent.parent
VALID = "skills: {main: [Python]}\nexperience: {years: 0}\ndirection: {jobs: [백엔드]}\n"


def write(tmp_path, text: str) -> str:
    path = tmp_path / "profile.yaml"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_example_file_in_repo_is_valid():
    profile, warnings = user_profile.load(str(ROOT / "profile.example.yaml"))

    assert profile.skills.main == ["Python", "SQL"]
    assert profile.skills.certificates == ["정보처리기사"]
    assert profile.experience.years == 0
    assert profile.experience.degree == "대학교 졸업(4년), 컴퓨터공학"
    assert profile.direction.locations == ["서울", "경기"]
    assert len(profile.culture) == 2
    assert warnings == []


def test_single_text_in_list_field_becomes_one_item_list(tmp_path):
    text = "skills: {main: Python, tried: '  '}\nexperience: {years: 3}\ndirection: {jobs: 백엔드}\nculture:\n"
    profile, _ = user_profile.load(write(tmp_path, text))

    assert profile.skills.main == ["Python"]
    assert profile.skills.tried == []  # 빈 항목은 지운다
    assert profile.direction.jobs == ["백엔드"]
    assert profile.culture == []


@pytest.mark.parametrize(
    ("text", "where"),
    [
        ("skills: {main: []}\nexperience: {years: 0}\ndirection: {jobs: [a]}", "skills.main: 1개 이상"),
        ("skills: {main: [a]}\nexperience: {years: 0}\ndirection: {goals: x}", "direction.jobs: 필수 칸이 없음"),
        ("skills: {main: [a]}\nexperience: {}\ndirection: {jobs: [a]}", "experience.years: 필수 칸이 없음"),
        ("skills: {main: [a]}\nexperience: {years: 2.5}\ndirection: {jobs: [a]}", "experience.years: 정수여야 함"),
        ("skills: {main: [a]}\nexperience: {years: '2년'}\ndirection: {jobs: [a]}", "experience.years: 정수여야 함"),
        ("skills: {main: [a]}\nexperience: {years: true}\ndirection: {jobs: [a]}", "experience.years: 정수여야 함"),
        ("skills: {main: [a]}\nexperience: {years: 51}\ndirection: {jobs: [a]}", "experience.years: 0–50"),
        ("skills: {main: [a]}\nexperience: {years: -1}\ndirection: {jobs: [a]}", "experience.years: 0–50"),
        ("skills: [a]\nexperience: {years: 0}\ndirection: {jobs: [a]}", "skills: 칸 아래에 항목"),
    ],
)
def test_wrong_required_fields_name_the_field(tmp_path, text, where):
    with pytest.raises(user_profile.ProfileError) as exc_info:
        user_profile.load(write(tmp_path, text))

    assert where in str(exc_info.value)


def test_error_does_not_show_profile_content(tmp_path):
    # 개인정보라 오류에는 칸 이름만 쓴다 (N2)
    text = "skills: {main: [a]}\nexperience: {years: '비밀경력이야기'}\ndirection: {jobs: [a]}"

    with pytest.raises(user_profile.ProfileError) as exc_info:
        user_profile.load(write(tmp_path, text))

    assert "비밀경력이야기" not in str(exc_info.value)


def test_broken_yaml(tmp_path):
    with pytest.raises(user_profile.ProfileError, match="YAML 형식이 깨졌습니다"):
        user_profile.load(write(tmp_path, "skills: [Python\nexperience: 0\n"))


@pytest.mark.parametrize("text", ["", "  \n", "# 주석만\n"])
def test_blank_file(tmp_path, text):
    with pytest.raises(user_profile.ProfileError, match="비어 있습니다"):
        user_profile.load(write(tmp_path, text))


def test_not_a_mapping(tmp_path):
    with pytest.raises(user_profile.ProfileError, match="형식이 틀립니다"):
        user_profile.load(write(tmp_path, "- Python\n"))


def test_unknown_fields_are_warnings_only(tmp_path):
    profile, warnings = user_profile.load(
        write(tmp_path, VALID.replace("[Python]}", "[Python], mian: x}") + "hobby: 1\n")
    )

    assert profile.skills.main == ["Python"]
    assert warnings == ["모르는 칸(무시함): skills.mian", "모르는 칸(무시함): hobby"]


def test_missing_file_points_to_screen_and_example(tmp_path):
    path = tmp_path / "profile.yaml"

    with pytest.raises(user_profile.ProfileError) as exc_info:
        user_profile.load(str(path))

    message = str(exc_info.value)
    assert str(path) in message
    assert "streamlit run app.py" in message and "profile.example.yaml" in message
    assert "profile.md" not in message


def test_missing_file_mentions_old_markdown_profile(tmp_path):
    (tmp_path / "profile.md").write_text("# 예전 프로필", encoding="utf-8")

    with pytest.raises(user_profile.ProfileError) as exc_info:
        user_profile.load(str(tmp_path / "profile.yaml"))

    assert "예전 profile.md" in str(exc_info.value)  # F16. 자동 변환은 하지 않는다
    assert not (tmp_path / "profile.yaml").exists()


def test_to_prompt_has_four_sections():
    profile, _ = user_profile.load(str(ROOT / "profile.example.yaml"))

    text = user_profile.to_prompt(profile)

    assert [line for line in text.splitlines() if line.startswith("## ")] == [
        "## 기술",
        "## 경력",
        "## 방향",
        "## 문화",
    ]
    assert "- 자격증: 정보처리기사" in text  # 자격증은 기술 아래 (F23)
    assert "- 경력 연수: 0년 (신입)" in text
    assert "- 학력: 대학교 졸업(4년), 컴퓨터공학" in text  # 학력은 경력 아래
    assert "- 희망 지역: 서울, 경기" in text  # 희망 지역은 방향 아래
    assert "- 코드 리뷰와 문서화를 하는 팀" in text


def test_to_prompt_marks_blank_fields_and_missing_culture(tmp_path):
    profile, _ = user_profile.parse(VALID.replace("years: 0", "years: 4"))

    text = user_profile.to_prompt(profile)

    assert "- 선호 문화 정보 없음" in text  # F24
    assert "- 경력 연수: 4년\n" in text
    assert "- 다룰 수 있음: 없음" in text and "- 하고 싶은 일: 없음" in text


def test_save_round_trip_keeps_field_order_and_korean(tmp_path):
    profile, _ = user_profile.load(str(ROOT / "profile.example.yaml"))
    path = tmp_path / "profile.yaml"

    user_profile.save(profile, str(path))

    text = path.read_text(encoding="utf-8")
    assert "정보처리기사" in text  # \u 이스케이프 없이
    assert list(yaml.safe_load(text)) == ["skills", "experience", "direction", "culture"]
    assert user_profile.load(str(path))[0] == profile
    assert [p.name for p in tmp_path.iterdir()] == ["profile.yaml"]  # 임시 파일이 남지 않음


def test_failed_save_keeps_old_file(tmp_path, monkeypatch):
    path = tmp_path / "profile.yaml"
    path.write_text(VALID, encoding="utf-8")
    profile, _ = user_profile.parse(VALID)

    def broken_dump(profile):
        raise OSError("디스크 가득 참")

    monkeypatch.setattr(user_profile, "dump", broken_dump)
    with pytest.raises(OSError):
        user_profile.save(profile, str(path))

    assert path.read_text(encoding="utf-8") == VALID
    assert [p.name for p in tmp_path.iterdir()] == ["profile.yaml"]


# ---- 프로필 탭 입력란 (F17–F21) ----


def test_form_round_trip_from_example_file():
    raw = user_profile.read_raw(str(ROOT / "profile.example.yaml"))

    values = user_profile.to_form(raw)

    assert values[("skills", "main")] == "Python\nSQL"  # 한 줄에 하나 (F19)
    assert values[("experience", "years")] == 0
    assert values[("direction", "goals")] == "LLM을 활용한 서비스 개발, API 서버 설계"
    profile, _ = user_profile.validate(user_profile.from_form(values))
    assert profile == user_profile.load(str(ROOT / "profile.example.yaml"))[0]


def test_form_defaults_for_missing_or_wrong_values():
    values = user_profile.to_form({"experience": {"years": "2년"}, "skills": "Python"})

    assert values[("experience", "years")] == 0
    assert values[("skills", "main")] == ""
    assert user_profile.to_form(None)[("culture",)] == ""


def test_form_lines_become_items_and_blank_lines_are_dropped():
    values = {keys: "" for keys, _, _ in user_profile.FORM_FIELDS} | {
        ("skills", "main"): "Python\n\n  SQL  \n",
        ("experience", "years"): 2,
        ("direction", "jobs"): "백엔드",
    }

    data = user_profile.from_form(values)

    assert data["skills"]["main"] == ["Python", "SQL"]
    assert data["experience"]["years"] == 2
    assert data["culture"] == []
    assert user_profile.validate(data)[0].direction.jobs == ["백엔드"]


def test_form_without_required_fields_is_rejected():
    values = {keys: "" for keys, _, _ in user_profile.FORM_FIELDS} | {("experience", "years"): 0}

    with pytest.raises(user_profile.ProfileError) as exc_info:
        user_profile.validate(user_profile.from_form(values))

    assert "skills.main" in str(exc_info.value) and "direction.jobs" in str(exc_info.value)


def test_read_raw_missing_and_broken(tmp_path):
    assert user_profile.read_raw(str(tmp_path / "profile.yaml")) is None
    with pytest.raises(user_profile.ProfileError, match="화면에서 저장하지 않습니다"):
        user_profile.read_raw(write(tmp_path, "skills: [Python\n"))
    assert user_profile.read_raw(write(tmp_path, "- 목록\n")) == {}

import pytest

from agent import scoring


def make_evaluation(**changes):
    data = {
        "summary": "신입 가능, 대졸, Java 필수",
        "skills": 72,
        "experience": 60,
        "culture": None,
        "career": 80,
        "strengths": ["Java 프로젝트"],
        "gaps": ["Spring Boot", "AWS"],
    }
    return scoring.Evaluation(**(data | changes))


def test_overall_uses_all_four_weights():
    evaluation = make_evaluation(skills=80, experience=60, culture=40, career=100)

    # (30×80 + 25×60 + 15×40 + 30×100) / 100 = 75
    assert scoring.overall(evaluation) == 75


def test_overall_drops_culture_without_evidence():
    # (30×72 + 25×60 + 30×80) / 85 = 71.29
    assert scoring.overall(make_evaluation()) == 71


def test_overall_rounds_half_up():
    # 150 / 100 = 1.5 → 2
    assert scoring.overall(make_evaluation(skills=0, experience=0, culture=0, career=5)) == 2
    # (30×5 + 25×5 + 15×5 + 30×0) / 100 = 3.5 → 4
    assert scoring.overall(make_evaluation(skills=5, experience=5, culture=5, career=0)) == 4
    # 25 / 10 = 2.5 → 3 (파이썬 round면 2)
    assert scoring.overall(make_evaluation(skills=0, experience=10, culture=0, career=0)) == 3


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (100, "강력 추천"),
        (80, "강력 추천"),
        (79, "추천"),
        (60, "추천"),
        (59, "보통"),
        (40, "보통"),
        (39, "비추천"),
        (0, "비추천"),
    ],
)
def test_verdict_boundaries(score, expected):
    assert scoring.verdict(score) == expected


@pytest.mark.parametrize(
    ("score", "expected"),
    [(0, "☆☆☆☆☆"), (9, "☆☆☆☆☆"), (10, "★☆☆☆☆"), (20, "★☆☆☆☆"), (71, "★★★★☆"), (90, "★★★★★"), (100, "★★★★★")],
)
def test_stars(score, expected):
    assert scoring.stars(score) == expected


def test_parse_plain_json():
    text = (
        '{"summary": " 신입, Java ", "skills": 72, "experience": 60, "culture": null, "career": 80,'
        ' "strengths": ["a"], "gaps": ["Docker"]}'
    )

    evaluation = scoring.parse(text)

    assert evaluation.summary == "신입, Java"
    assert evaluation.culture is None
    assert evaluation.gaps == ["Docker"]


def test_parse_json_in_code_block():
    text = (
        '```json\n{"summary": "s", "skills": 1, "experience": 2, "culture": 3, "career": 4,'
        ' "strengths": [], "gaps": []}\n```'
    )

    assert scoring.parse(text).culture == 3


def test_parse_keeps_first_three_items_and_drops_blanks():
    text = (
        '{"summary": "s", "skills": 1, "experience": 2, "culture": null, "career": 4,'
        ' "strengths": ["a", " ", "b", "c", "d"], "gaps": [" Docker ", "AWS", "Git", "Linux"]}'
    )

    evaluation = scoring.parse(text)

    assert evaluation.strengths == ["a", "b", "c"]
    assert evaluation.gaps == ["Docker", "AWS", "Git"]


@pytest.mark.parametrize(
    "text",
    [
        '{"summary": "s", "skills": 1, "experience": 2, "culture": null}',  # career 누락
        '{"summary": "s", "skills": 101, "experience": 2, "culture": null, "career": 4}',  # 범위 밖
        '{"summary": "s", "skills": -1, "experience": 2, "culture": null, "career": 4}',
        '{"summary": "s", "skills": 1, "experience": 2, "culture": 120, "career": 4}',
        '{"summary": "  ", "skills": 1, "experience": 2, "culture": null, "career": 4}',  # 요약 빈칸
        '{"skills": 1, "experience": 2, "culture": null, "career": 4}',  # 요약 누락
        '{"summary": "s", "skills": 1, "experience": 2, "career": 4}',  # culture 키 누락
        "점수는 72점입니다",  # JSON 아님
        "",  # 빈 응답
    ],
)
def test_parse_rejects_bad_answers(text):
    with pytest.raises(ValueError):
        scoring.parse(text)


def row(number, check="FALSE", score="", experience="신입", education="", keywords=""):
    return {
        "row": number,
        "check": check,
        "score": score,
        "experience": experience,
        "education": education,
        "keywords": keywords,
    }


def test_select_checked_rows():
    rows = [row(2, check="TRUE"), row(3), row(4, check="TRUE", score="70")]

    targets, skipped = scoring.select_targets(rows, "checked")

    assert [r["row"] for r in targets] == [2, 4]  # 점수가 있어도 체크하면 다시 평가 (F7)
    assert skipped == []


def test_select_rows_without_score():
    rows = [row(2, score="70"), row(3), row(4, check="TRUE")]

    targets, _ = scoring.select_targets(rows, "all")

    assert [r["row"] for r in targets] == [3, 4]


def test_rows_without_posting_info_are_skipped():
    old = row(2, experience="")  # v0.3 이전 줄
    rows = [old, row(3, experience="", keywords="Python")]

    targets, skipped = scoring.select_targets(rows, "all")

    assert [r["row"] for r in targets] == [3]
    assert skipped == [old]


# ---- v0.5: 점수 보정 (F25–F36) ----


def test_select_all_skips_excluded_rows_but_checked_picks_them():
    excluded = row(2) | {"verdict": scoring.EXCLUDED}
    rows = [excluded | {"check": "TRUE"}, row(3)]

    assert [r["row"] for r in scoring.select_targets(rows, "all")[0]] == [3]
    assert [r["row"] for r in scoring.select_targets(rows, "checked")[0]] == [2]


@pytest.mark.parametrize(("value", "expected"), [(0, 0), (3, 3), (None, None)])
def test_required_years_values(value, expected):
    assert make_evaluation(required_years=value).required_years == expected


def test_required_years_missing_is_null():
    text = '{"summary": "s", "skills": 1, "experience": 2, "culture": null, "career": 4}'

    assert scoring.parse(text).required_years is None


@pytest.mark.parametrize("value", ["-1", '"3년"'])
def test_required_years_negative_or_text_is_rejected(value):
    text = '{"summary": "s", "skills": 1, "experience": 2, "culture": null, "career": 4, "required_years": ' + value
    with pytest.raises(ValueError):
        scoring.parse(text + "}")


@pytest.mark.parametrize(
    ("required", "years", "experience"),
    [
        (2, 2, 75),  # 부족 0년: 그대로
        (3, 2, 60),  # 1년 부족
        (3, 1, 45),  # 2년 부족
        (3, 0, 30),  # 3년 부족
        (8, 0, 30),  # 3년 넘게 부족해도 30
        (None, 0, 75),  # 공고에 경력 요구가 없음
    ],
)
def test_experience_cap_by_short_years(required, years, experience):
    adjusted = scoring.adjust(make_evaluation(experience=75, required_years=required), years, scoring.HIGH)

    assert adjusted.experience == experience


def test_lower_llm_score_is_kept_without_note():
    # 경력 40은 상한 60보다 낮아 그대로. 종합 (30×72 + 25×40 + 30×80)/85 = 65.4 → 65 (상한 79 아래)
    adjusted = scoring.adjust(make_evaluation(experience=40, required_years=3), 2, scoring.HIGH)

    assert (adjusted.experience, adjusted.total, adjusted.note) == (40, 65, "")


def test_short_experience_caps_total_at_79():
    evaluation = make_evaluation(skills=95, experience=90, culture=None, career=95, required_years=3)

    adjusted = scoring.adjust(evaluation, 2, scoring.HIGH)

    # 경력 90 → 60. 종합 (30×95 + 25×60 + 30×95)/85 = 84.7 → 85 → 79, 판정은 "추천"까지 (F27)
    assert (adjusted.experience, adjusted.total, adjusted.verdict) == (60, 79, "추천")
    assert adjusted.stars == scoring.stars(79)
    assert adjusted.note == "경력 90→60 (3년 요구, 2년), 종합 85→79 (경력 부족)"


def test_short_experience_caps_total_even_when_experience_score_is_already_low():
    # F27은 "경력이 부족한 공고"면 건다. 경력점수를 깎지 않았어도 종합 상한은 적용 (v0.5 설계)
    evaluation = make_evaluation(skills=100, experience=50, culture=None, career=100, required_years=2)

    adjusted = scoring.adjust(evaluation, 1, scoring.HIGH)

    assert adjusted.experience == 50
    assert adjusted.note == "종합 85→79 (경력 부족)"


def test_low_trust_caps_total_at_69():
    adjusted = scoring.adjust(make_evaluation(skills=90, experience=90, career=90), 3, scoring.LOW)

    assert (adjusted.total, adjusted.verdict, adjusted.note) == (69, "추천", "종합 90→69 (신뢰 낮음)")


def test_short_experience_and_low_trust_use_lower_cap():
    evaluation = make_evaluation(skills=95, experience=90, culture=None, career=95, required_years=3)

    adjusted = scoring.adjust(evaluation, 2, scoring.LOW)

    assert adjusted.total == 69
    assert adjusted.note == "경력 90→60 (3년 요구, 2년), 종합 85→69 (신뢰 낮음)"


def test_no_adjustment_leaves_note_blank():
    adjusted = scoring.adjust(make_evaluation(required_years=0), 0, scoring.MEDIUM)

    assert (adjusted.experience, adjusted.total, adjusted.verdict, adjusted.note) == (60, 71, "추천", "")


@pytest.mark.parametrize(
    ("body", "with_body", "expected"),
    [
        ("글자", True, "높음"),
        ("글자+이미지", True, "높음"),
        ("", True, "높음"),  # v0.4 이전 줄의 빈 상태
        ("이미지 일부 못 읽음", True, "보통"),
        ("본문 미확보", False, "낮음"),
        ("글자", False, "낮음"),  # 원문 파일 없음
    ],
)
def test_trust_levels(body, with_body, expected):
    assert scoring.trust(body, with_body) == expected


@pytest.mark.parametrize(
    ("experience", "years", "expected"),
    [
        ("경력 3년↑", 0, True),
        ("경력2~10년", 0, True),
        ("신입·경력", 0, False),
        ("경력무관", 0, False),
        ("신입", 0, False),
        ("", 0, False),  # 경력 칸이 비면 평가한다
        ("  ", 0, False),
        ("경력 3년↑", 1, False),  # 신입이 아니면 제외하지 않는다
    ],
)
def test_newcomer_exclusion(experience, years, expected):
    assert scoring.excluded(experience, years) is expected

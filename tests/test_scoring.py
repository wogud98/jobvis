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

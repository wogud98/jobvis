import gspread
import pytest
import requests

from agent import sheets, view


def make_row(number: int, **changes) -> dict:
    row = dict.fromkeys(sheets.KEYS, "")
    row |= {
        "row": number,
        "company": f"회사{number}",
        "title": "백엔드 개발자",
        "deadline": "2026-11-01",
        "url": f"https://saramin.test/{number}",
        "id": str(number),
        "experience": "신입",
        "source": "사람인",
        "body": "글자",
    }
    return row | changes


def scored(number: int, score: int, **changes) -> dict:
    return make_row(number, **({"score": str(score), "stars": "★★★★☆", "verdict": "추천", "trust": "높음"} | changes))


def test_cards_sorted_by_score_then_row_and_unscored_last():
    rows = [make_row(2), scored(3, 70), scored(4, 85), scored(5, 70), make_row(6, verdict="제외 (경력 요구)")]

    items = view.cards(rows)

    assert [card.row for card in items] == [4, 3, 5, 2, 6]
    assert items[3].verdict == "평가 전"  # F2
    assert items[4].verdict == "제외 (경력 요구)"  # 제외 판정은 그대로


def test_score_with_text_is_unscored():
    card = view.cards([make_row(2, score="높음", verdict="추천")])[0]

    assert card.score is None and card.verdict == "평가 전"


def test_details_show_blank_as_none():
    card = view.cards([scored(2, 80, requirements="Java 필수", duties="  ", gaps="AWS")])[0]

    assert card.details["요약"] == "Java 필수"
    assert card.details["주요업무"] == "없음"  # F3
    assert card.details["부족한 점"] == "AWS"
    assert list(card.details) == [
        "요약",
        "주요업무",
        "우대사항",
        "기술스택",
        "기술",
        "경력",
        "문화",
        "방향",
        "강점",
        "부족한 점",
    ]


def test_blank_source_is_unknown_but_saved_as_saramin():
    card = view.cards([make_row(2, source="")])[0]

    assert card.source == "미상"  # F6
    assert card.source_code == "saramin"  # 이미지 저장 이름에는 사람인 (v0.3까지 사람인 API 줄)


def test_v04_verdict_with_missing_body_means_low_trust():
    old = scored(2, 70, verdict="추천 (본문 미확보)", trust="")

    card = view.cards([old])[0]

    assert card.trust == "낮음" and card.dim


def test_upload_box_only_for_missing_or_partly_unread_body():
    rows = [make_row(2, body="본문 미확보"), make_row(3, body="이미지 일부 못 읽음"), make_row(4), make_row(5, id="")]
    rows[3]["body"] = "본문 미확보"

    assert [card.can_upload for card in view.cards(rows)] == [True, True, False, False]  # 공고ID가 없으면 못 넣음


def test_options_and_filters():
    rows = [
        scored(2, 80),
        scored(3, 60, source="잡코리아", experience="경력 3년↑"),
        make_row(4, source="", experience=""),
    ]
    items = view.cards(rows)

    sources, experiences = view.options(items)

    assert sources == ["사람인", "잡코리아", "미상"]
    assert experiences == ["신입", "경력 3년↑", "(없음)"]
    assert [c.row for c in view.apply(items, view.Filters(sources, experiences))] == [2, 3]  # 평가 전은 기본으로 숨김
    assert [c.row for c in view.apply(items, view.Filters(sources, experiences, show_unscored=True))] == [2, 3, 4]
    assert [c.row for c in view.apply(items, view.Filters(["잡코리아"], experiences, True))] == [3]
    assert [c.row for c in view.apply(items, view.Filters(sources, ["(없음)"], True))] == [4]


def test_chart_has_scored_cards_only_and_unique_names():
    items = view.cards([scored(2, 80), scored(3, 70), make_row(4), scored(5, 60, company="회사9")])
    items[1].company = "회사2"  # 회사·직무가 같은 공고

    assert view.chart(items) == [
        ("회사2 · 백엔드 개발자", 80),
        ("회사2 · 백엔드 개발자 (2)", 70),
        ("회사9 · 백엔드 개발자", 60),
    ]


def test_summary_counts_whole_sheet():
    rows = [
        scored(2, 85, verdict="강력 추천"),
        scored(3, 70),
        scored(4, 50, verdict="보류", body="본문 미확보"),
        make_row(5, body="본문 미확보"),
        make_row(6, verdict="제외 (경력 요구)"),
    ]

    assert [(label, value) for label, value, _ in view.summary(view.cards(rows))] == [
        ("전체 공고", 5),
        ("평가 완료", 3),
        ("추천 이상", 2),
        ("본문 미확보", 2),
    ]  # v0.5.1 F2


def test_summary_of_empty_or_unscored_sheet():
    assert [value for _, value, _ in view.summary([])] == [0, 0, 0, 0]
    assert [value for _, value, _ in view.summary(view.cards([make_row(2), make_row(3)]))] == [2, 0, 0, 0]


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (KeyError("GOOGLE_SHEET_ID"), "인증 정보를 찾지 못했습니다"),
        (FileNotFoundError("C:/secret/service_account.json"), "인증 정보를 찾지 못했습니다"),
        (gspread.SpreadsheetNotFound(), "시트를 열지 못했습니다"),
        (requests.ConnectionError("token=abc"), "네트워크 오류"),
        (requests.Timeout(), "네트워크 오류"),
        (ValueError("key=secret"), "시트를 읽지 못했습니다 (ValueError)"),
    ],
)
def test_error_message_hides_details(error, expected):
    message = view.error_message(error)

    assert expected in message
    assert "secret" not in message and "abc" not in message  # 경로·키를 보이지 않는다 (F9)

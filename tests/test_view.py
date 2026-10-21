import gspread
import pytest
import requests

from agent import postings, sheets, view


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
    assert experiences == ["신입", "경력", "(없음)"]  # 글자 그대로가 아니라 묶음 (v0.5.2 F30)
    assert [c.row for c in view.apply(items, view.Filters([], []))] == [2, 3, 4]  # 비면 전체, 평가 전도 (F29, F32)
    assert [c.row for c in view.apply(items, view.Filters([], [], scored_only=True))] == [2, 3]
    assert [c.row for c in view.apply(items, view.Filters(sources, experiences))] == [2, 3, 4]
    assert [c.row for c in view.apply(items, view.Filters(["잡코리아"], []))] == [3]
    assert [c.row for c in view.apply(items, view.Filters([], ["경력"]))] == [3]
    assert [c.row for c in view.apply(items, view.Filters([], ["(없음)"]))] == [4]
    assert [c.row for c in view.apply(items, view.Filters([], ["(없음)"], True))] == []
    assert [c.row for c in view.apply(items, view.Filters(["사람인"], ["경력"]))] == []


@pytest.mark.parametrize(
    ("text", "groups"),
    [
        ("신입", ["신입"]),
        ("경력 3년↑", ["경력"]),
        ("3~5년", ["경력"]),
        ("경력무관", ["무관"]),
        ("신입·경력", ["신입", "경력"]),
        ("신입/경력(연차무관)", ["신입", "경력", "무관"]),
        ("신입 · 경력 1년↑", ["신입", "경력"]),
        ("인턴", ["기타"]),
        ("", ["(없음)"]),
        ("(없음)", ["(없음)"]),
    ],
)
def test_career_groups(text, groups):
    assert view.career_groups(text) == groups


def test_mixed_career_posting_matches_both_groups():
    items = view.cards([scored(2, 80, experience="신입·경력"), scored(3, 70, experience="경력무관")])

    assert [c.row for c in view.apply(items, view.Filters([], ["신입"]))] == [2]
    assert [c.row for c in view.apply(items, view.Filters([], ["경력", "무관"]))] == [2, 3]
    assert view.options(items)[1] == ["신입", "경력", "무관"]


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


def test_card_info_has_collected_fields_only():
    card = view.cards([make_row(2, location="서울 강남구", education="대졸", keywords="Python, AWS", deadline="")])[0]

    assert card.info == {"지역": "서울 강남구", "경력": "신입", "학력": "대졸", "키워드": "Python, AWS"}  # v0.5.2 F31


def test_preview_reads_saved_body_and_cuts(tmp_path, monkeypatch):
    monkeypatch.setattr(postings, "DIR", tmp_path)
    card = view.cards([make_row(2, source="사람인")])[0]
    postings.save(card.source_code, card.job_id, postings.compose("가" * 30, ["이미지 글자"]))

    assert view.preview(card) == "가" * 30 + "\n이미지 글자"  # 이미지 글자도 이어 붙임 (F31)
    assert view.preview(card, limit=10) == "가" * 10 + " …"


def test_preview_without_saved_body_or_id_is_blank(tmp_path, monkeypatch):
    monkeypatch.setattr(postings, "DIR", tmp_path)
    no_file, no_id = view.cards([make_row(2), make_row(3, id="")])

    assert view.preview(no_file) == "" and view.preview(no_id) == ""


def test_card_checked_and_with_checks():
    rows = [make_row(2, check="TRUE"), make_row(3, check="false"), make_row(4)]

    assert [c.checked for c in view.cards(rows)] == [True, False, False]  # v0.5.2 F39

    changed = view.with_checks(rows, {2: False, 4: True})
    assert [row["check"] for row in changed] == ["FALSE", "false", "TRUE"]  # 바꾼 줄만 덮음
    assert rows[0]["check"] == "TRUE"  # 받은 줄은 바꾸지 않음


# ---- v0.5.2 정렬·페이지·TOP 5 ----


def test_sort_lowest_first_keeps_unscored_last():
    items = view.cards([scored(2, 70), make_row(3), scored(4, 85), scored(5, 70), make_row(6)])

    assert [c.row for c in view.apply(items, view.Filters([], []))] == [4, 2, 5, 3, 6]  # 높은 순 (기본)
    low = view.apply(items, view.Filters([], [], lowest_first=True))
    assert [c.row for c in low] == [2, 5, 4, 3, 6]  # 낮은 순, 같은 점수는 줄 순, 평가 전은 아래 (F40)
    assert [c.row for c in view.apply(items, view.Filters([], [], True, True))] == [2, 5, 4]


def test_page_splits_and_clamps():
    items = view.cards([scored(n, 50) for n in range(2, 25)])  # 23건

    first, number, pages = view.page(items, 1)
    assert (len(first), number, pages) == (10, 1, 3)  # F41
    last, number, _ = view.page(items, 3)
    assert (len(last), number) == (3, 3)
    assert view.page(items, 9)[1] == 3 and view.page(items, 0)[1] == 1  # 범위 밖은 끝·처음 쪽
    assert view.page([], 1) == ([], 1, 1)


def test_chart_shows_top_five_by_score_whatever_the_sort():
    items = view.cards([scored(n, 40 + n) for n in range(2, 10)] + [make_row(10)])
    low = view.apply(items, view.Filters([], [], lowest_first=True))

    assert [score for _, score in view.chart(low)] == [49, 48, 47, 46, 45]  # 높은 5개 (F42)
    assert len(view.chart(low, limit=10)) == 8


def test_hidden_cards_only_in_hidden_view():
    rows = [scored(2, 80), scored(3, 70, hidden="TRUE"), make_row(4, hidden="true")]
    items = view.cards(rows)

    assert [c.hidden for c in items] == [False, True, True]
    assert [c.row for c in view.apply(items, view.Filters([], []))] == [2]  # 기본은 뺀 공고 숨김 (F44)
    assert [c.row for c in view.apply(items, view.Filters([], [], hidden_only=True))] == [3, 4]

    changed = view.with_checks(rows, {}, {2: True, 3: False})
    assert [row["hidden"] for row in changed] == ["TRUE", "FALSE", "true"]

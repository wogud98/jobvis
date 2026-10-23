from datetime import date, datetime

import gspread
import pytest
import requests
import sqlalchemy.exc

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
        ("이미지 필요", 2),
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
    low = view.apply(items, view.Filters([], [], sort="score_asc"))
    assert [c.row for c in low] == [2, 5, 4, 3, 6]  # 낮은 순, 같은 점수는 줄 순, 평가 전은 아래 (F40)
    assert [c.row for c in view.apply(items, view.Filters([], [], scored_only=True, sort="score_asc"))] == [2, 5, 4]


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
    low = view.apply(items, view.Filters([], [], sort="score_asc"))

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


# ---- v0.5.3 ----

TODAY = date(2026, 10, 22)


@pytest.mark.parametrize(
    ("text", "items"),
    [
        ("Python, AWS", ["Python", "AWS"]),
        ("API 개발 · 배포 자동화", ["API 개발", "배포 자동화"]),
        ("CI/CD 구축 / 모니터링", ["CI/CD 구축", "모니터링"]),  # 붙은 /는 그대로
        ("Python·LangGraph 경험, 신입 지원 가능", ["Python·LangGraph 경험", "신입 지원 가능"]),  # 붙은 ·도 그대로
        ("첫째\n둘째;셋째", ["첫째", "둘째", "셋째"]),
        ("", []),
        (" , ", []),
    ],
)
def test_split_items(text, items):
    assert view.split_items(text) == items  # v0.5.3 F2, F3


def test_stack_chips_mark_my_skills_ignoring_case_and_spaces():
    chips = view.stack_chips("python, Spring Boot, AWS", ["Python", "springboot"])

    assert chips == [("python", True), ("Spring Boot", True), ("AWS", False)]  # F4
    assert view.stack_chips("", ["Python"]) == []


@pytest.mark.parametrize(
    ("deadline", "badge"),
    [
        ("2026-10-22", ("D-day", "low")),
        ("2026-10-25", ("D-3", "low")),
        ("2026-10-29", ("D-7", "low")),
        ("2026-10-30", ("D-8", "plain")),  # 8일 남음
        ("2026-10-21", ("마감", "closed")),
        ("상시", None),
        ("", None),
    ],
)
def test_deadline_badge(deadline, badge):
    assert view.deadline_badge(deadline, TODAY) == badge  # F7


def test_sort_by_deadline_soonest_then_open_then_closed():
    rows = [
        scored(2, 90, deadline="2026-11-30"),
        make_row(3, deadline="2026-10-24"),
        scored(4, 50, deadline="상시"),
        scored(5, 80, deadline="2026-10-01"),
        make_row(6, deadline=""),
        scored(7, 70, deadline="2026-10-24"),
    ]

    shown = view.apply(view.cards(rows), view.Filters([], [], sort="deadline"), today=TODAY)

    assert [c.row for c in shown] == [3, 7, 2, 4, 6, 5]  # 같은 날은 줄 순, 점수와 상관없이 (F8)


def test_search_matches_company_or_title_all_words():
    items = view.cards([scored(2, 80, company="카카오", title="백엔드 개발자"), scored(3, 70, company="네이버")])

    assert [c.row for c in view.apply(items, view.Filters([], [], query="카카오"))] == [2]
    assert [c.row for c in view.apply(items, view.Filters([], [], query="  백엔드  "))] == [2, 3]  # 직무도
    assert [c.row for c in view.apply(items, view.Filters([], [], query="네이버 백엔드"))] == [3]  # 모두 들어 있어야
    assert [c.row for c in view.apply(items, view.Filters([], [], query="없는회사"))] == []  # F10


def test_applied_only_and_override():
    rows = [scored(2, 80, applied="TRUE"), scored(3, 70)]
    items = view.cards(rows)

    assert [c.applied for c in items] == [True, False]
    assert [c.row for c in view.apply(items, view.Filters([], [], applied_only=True))] == [2]  # F11
    assert [row["applied"] for row in view.with_checks(rows, {}, {}, {3: True})] == ["TRUE", "TRUE"]


def test_scores_strengths_gaps_on_card():
    card = view.cards(
        [scored(2, 80, skills="85", experience_score="60", culture="-", career="90", strengths="A, B", gaps="Docker")]
    )[0]

    assert card.scores == {"기술": 85, "경력": 60, "문화": None, "방향": 90}  # 문화 "-"는 None (F6)
    assert card.strengths == ["A", "B"] and card.gaps == ["Docker"]


def test_is_new_and_last_seen_file(tmp_path):
    card = view.cards([make_row(2, saved_at="2026-10-22 09:30")])[0]
    path = tmp_path / "data" / "last_seen.txt"

    assert view.read_last_seen(path) is None  # 처음엔 없음 → NEW 없음 (F9)
    assert not view.is_new(card, None)
    view.write_last_seen(path, datetime(2026, 10, 22, 9, 0))
    seen = view.read_last_seen(path)
    assert seen == datetime(2026, 10, 22, 9, 0)
    assert view.is_new(card, seen)
    assert not view.is_new(card, datetime(2026, 10, 22, 10, 0))
    assert not view.is_new(view.cards([make_row(3, saved_at="모름")])[0], seen)


def test_last_seen_broken_or_unwritable_is_ignored(tmp_path):
    broken = tmp_path / "last_seen.txt"
    broken.write_text("깨진 값", encoding="utf-8")
    blocked = tmp_path / "file"
    blocked.write_text("", encoding="utf-8")

    assert view.read_last_seen(broken) is None
    view.write_last_seen(blocked / "last_seen.txt", datetime(2026, 10, 22))  # 폴더 자리에 파일: 오류 없이 넘어감 (N3)


# ---- v0.5.4 이미지 필요·추천 이상 필터 ----


def test_image_only_keeps_missing_and_partly_unread_with_id():
    rows = [
        scored(2, 80),
        scored(3, 60, body="본문 미확보", trust="낮음"),
        make_row(4, body="이미지 일부 못 읽음"),
        make_row(5, body="본문 미확보", id=""),  # 공고 번호가 없으면 이미지를 넣을 수 없다
    ]
    items = view.cards(rows)

    assert [c.row for c in view.apply(items, view.Filters([], [], image_only=True))] == [3, 4]  # F2
    assert view.summary(items)[3][:2] == ("이미지 필요", 2)  # 요약 칸과 같은 기준 (F3)


def test_recommended_only_keeps_strong_and_recommended():
    rows = [scored(2, 85, verdict="강력 추천"), scored(3, 65), scored(4, 45, verdict="보통"), make_row(5)]

    shown = view.apply(view.cards(rows), view.Filters([], [], recommended_only=True))

    assert [c.row for c in shown] == [2, 3]  # F12


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (KeyError("DATABASE_URL"), "DATABASE_URL"),
        (sqlalchemy.exc.OperationalError("connect", {}, Exception("postgresql://jobvis:secret@db")), "DB에 연결하지"),
        (ValueError("secret"), "DB를 읽지 못했습니다 (ValueError)"),
    ],
)
def test_error_message_for_db_hides_address(monkeypatch, error, expected):
    monkeypatch.setenv("JOBVIS_STORAGE", "db")

    message = view.error_message(error)

    assert expected in message and "secret" not in message  # DB 주소의 비밀번호를 보이지 않음 (v0.6)


def test_error_message_for_wrong_storage_setting(monkeypatch):
    monkeypatch.setenv("JOBVIS_STORAGE", "excel")

    assert "sheet 또는 db" in view.error_message(ValueError("x"))


def test_summary_says_saved_postings_for_db(monkeypatch):
    monkeypatch.setenv("JOBVIS_STORAGE", "db")

    assert view.summary([])[0][2] == "저장된 공고"  # v0.6 D12


# ---- 모아 보기 집계 (v0.7 F11, F12, N5) ----


def test_stack_rank_counts_postings_once_and_merges_case_and_spaces():
    items = view.cards(
        [
            scored(2, 80, stack="Python, Spring Boot, python"),  # 같은 공고 안 중복은 한 번
            scored(3, 70, stack="springboot, AWS"),
            make_row(4, stack="AWS, Docker"),
            make_row(5),  # 기술스택 칸 없음
        ]
    )

    ranked = view.stack_rank(items, ["Python"])

    # 같은 수면 이름 순, 이름은 처음 나온 모양 (D8)
    assert ranked == [
        ("AWS", 2, False), ("Spring Boot", 2, False), ("Docker", 1, False), ("Python", 1, True),
    ]  # fmt: skip
    assert view.stack_rank(items, [], top=1) == [("AWS", 2, False)]


def test_stack_rank_shows_all_and_merges_same_words():
    many = ", ".join(f"Tool{n}" for n in range(14))
    items = view.cards(
        [
            scored(2, 80, stack=f"LLM Agent, k8s, MySQL, {many}"),
            scored(3, 70, stack="Agentic AI, Kubernetes, SQL, JavaScript, Java"),
        ]
    )

    ranked = view.stack_rank(items, ["쿠버네티스", "js"])

    assert len(ranked) == 2 + 1 + 1 + 14 + 2  # 10개로 자르지 않고 전부 (v0.7.3 F1)
    assert ranked[:2] == [("AI 에이전트", 2, False), ("Kubernetes", 2, True)]  # 같은 말은 대표 이름 (F2, F3)
    names = {name: mine for name, _, mine in ranked}
    assert {"MySQL", "SQL", "Java", "JavaScript"} <= set(names)  # 다른 기술은 따로
    assert names["JavaScript"] and not names["Java"]


def test_stack_chips_mark_same_words_as_mine():
    assert view.stack_chips("k8s, Java, Postgres", ["Kubernetes", "PostgreSQL"]) == [
        ("k8s", True), ("Java", False), ("Postgres", True),
    ]  # fmt: skip


def test_stack_rank_empty():
    assert view.stack_rank([], ["Python"]) == []
    assert view.stack_rank(view.cards([make_row(2)]), []) == []


def test_gap_rank_weights_like_gaps_command_and_counts_excluded():
    items = view.cards(
        [
            scored(2, 40, gaps="Gradle, Docker"),  # 가중 0.6
            scored(3, 90, gaps="gradle"),  # 0.1
            make_row(4, gaps="Kubernetes"),  # 점수 없음 → 뺌
        ]
    )

    ranked, excluded = view.gap_rank(items)

    # 사전에 없는 이름은 목록(점수 높은 순)에서 처음 나온 모양
    ranked_rows = [(name, round(weight, 2), count) for name, weight, count in ranked]
    assert ranked_rows == [("gradle", 0.7, 2), ("Docker", 0.6, 1)]
    assert excluded == 1  # F12


def test_gap_rank_empty():
    assert view.gap_rank([]) == ([], 0)


def test_filter_labels_lists_only_what_is_on():
    assert view.filter_labels(view.Filters(sources=[], experiences=[])) == []
    filters = view.Filters(
        sources=["사람인"], experiences=["신입", "무관"], query=" 백엔드 ", scored_only=True, applied_only=True
    )

    assert view.filter_labels(filters) == [
        "검색 '백엔드'", "출처 사람인", "경력 신입·무관", "평가된 공고만", "지원한 공고만",
    ]  # F10  # fmt: skip


def test_unscored_only_shows_only_cards_before_scoring():
    rows = [scored(2, 80), make_row(3), make_row(4, verdict=view.scoring.EXCLUDED)]
    items = view.cards(rows)

    shown = view.apply(items, view.Filters([], [], unscored_only=True))
    assert [c.row for c in shown] == [3]  # 제외 공고는 평가한 것이라 뺌 (v0.7.2 F3)
    assert view.filter_labels(view.Filters([], [], unscored_only=True)) == ["평가 전 공고만"]


# ---- 1건 묶음·엑셀·전체 복사 (v0.7.4 F1, F4, F5) ----


def test_split_once_keeps_order_of_repeated_and_sorts_single_by_name():
    ranked = [("Python", 3, True), ("AWS", 2, False), ("redis", 1, False), ("Airflow", 1, True)]

    many, once = view.split_once(ranked, 1)

    assert many == [("Python", 3, True), ("AWS", 2, False)]
    assert once == [("Airflow", 1, True), ("redis", 1, False)]
    assert view.split_once([], 1) == ([], [])


def test_stats_csv_opens_in_excel_with_korean():
    data = view.stats_csv([("Python", 3, True), ("Go", 1, False)], [("AWS 경험", 0.7, 2)])

    assert data.startswith(b"\xef\xbb\xbf")  # 엑셀이 한글을 UTF-8로 읽는 BOM
    lines = data.decode("utf-8-sig").splitlines()
    assert lines == [
        "구분,순위,이름,공고 수,내 기술,가중치",
        "많이 찾는 기술,1,Python,3,O,",
        "많이 찾는 기술,2,Go,1,,",
        "내가 부족한 것,1,AWS 경험,2,,0.70",
    ]


def test_stats_csv_quotes_names_with_commas():
    data = view.stats_csv([('C, "C++"', 2, False)], [])

    assert data.decode("utf-8-sig").splitlines()[1] == '많이 찾는 기술,1,"C, ""C++""",2,,'


def test_stats_text_groups_single_postings_in_one_line():
    text = view.stats_text(
        [("Python", 3, True), ("AWS", 2, False), ("Go", 1, False), ("django", 1, True)],
        [("AWS 경험", 0.7, 2), ("Kafka", 0.2, 1)],
        5,
    )

    assert text.splitlines() == [
        "JOBVIS 기술 모아보기 (공고 5건 기준)",
        "",
        "[많이 찾는 기술]",
        "1. Python 3건 (내 기술)",
        "2. AWS 2건",
        "1건씩: django (내 기술), Go",
        "",
        "[내가 부족한 것]",
        "1. AWS 경험 2건",
        "1건씩: Kafka",
    ]


def test_stats_text_without_items_says_none():
    assert view.stats_text([], [], 0).splitlines()[2:] == ["[많이 찾는 기술]", "없음", "", "[내가 부족한 것]", "없음"]

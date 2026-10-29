from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from agent import saramin

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 10, 21)


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_list_reads_ten_fields_and_skips_cards_without_id():
    jobs = saramin.parse_list(read("saramin_list.html"), TODAY)

    assert [job["id"] for job in jobs] == ["1001", "1002", "1003"]  # 공고ID 없는 광고 카드 제외
    assert jobs[0] == {
        "source": "saramin",
        "id": "1001",
        "company": "가나다소프트",
        "title": "백엔드 개발자 (Python)",
        "experience": "신입·경력",
        "education": "대학교졸업(4년)이상",
        "location": "서울 강남구",
        "deadline": "2026-11-12",
        "keywords": "Python, Django",
        "url": "https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=1001",
    }


def test_parse_list_handles_missing_education_and_special_deadlines():
    jobs = saramin.parse_list(read("saramin_list.html"), TODAY)

    assert jobs[1]["education"] == ""
    assert jobs[1]["experience"] == "경력 3년↑"
    assert jobs[1]["deadline"] == "상시"
    assert jobs[2]["deadline"] == "2026-10-22"  # 내일마감
    assert jobs[2]["education"] == "학력무관"
    assert jobs[2]["keywords"] == ""


def test_parse_list_returns_empty_for_unknown_page():
    assert saramin.parse_list("<html><body><p>점검 중</p></body></html>", TODAY) == []


@pytest.mark.parametrize(
    ("text", "today", "expected"),
    [
        ("~ 11/12(목)", TODAY, "2026-11-12"),
        ("~ 10/21(수)", TODAY, "2026-10-21"),  # 오늘 마감은 올해
        ("~ 01/05(화)", date(2026, 12, 20), "2027-01-05"),  # 12월에 본 1월 마감
        ("~ 2026.11.30", TODAY, "2026-11-30"),
        ("상시채용", TODAY, "상시"),
        ("채용시", TODAY, "상시"),
        ("오늘마감", TODAY, "2026-10-21"),
        ("내일마감", TODAY, "2026-10-22"),
        ("~ 02/30(월)", TODAY, ""),  # 없는 날짜
        ("", TODAY, ""),
    ],
)
def test_parse_deadline(text, today, expected):
    assert saramin.parse_deadline(text, today) == expected


def test_search_url_puts_conditions_in_address():
    url = saramin.search_url("백엔드 신입", {"region_codes": ["101000"], "job_code": "84", "career": "신입"})

    parts = urlsplit(url)
    assert parts.netloc == "www.saramin.co.kr"
    assert parts.path == "/zf_user/search/recruit"
    query = parse_qs(parts.query)
    assert query["searchword"] == ["백엔드 신입"]
    assert query["loc_mcd"] == ["101000"]
    assert query["cat_kewd"] == ["84"]
    assert query["exp_cd"] == ["1"]
    assert query["sort"] == ["RD"]


def test_search_url_without_conditions():
    query = parse_qs(urlsplit(saramin.search_url("백엔드", {})).query)

    assert set(query) == {"searchword", "recruitPageCount", "sort"}


def test_detail_url():
    assert saramin.detail_url("1001") == "https://www.saramin.co.kr/zf_user/jobs/relay/view-detail?rec_idx=1001"


def test_parse_detail_keeps_visible_text_and_absolute_images():
    detail = saramin.parse_detail(read("saramin_detail.html"))

    assert detail.text.splitlines() == [
        "주요업무",
        "주문·결제 API 개발과 운영",
        "자격요건",
        "Python 또는 Java 경험",
        "SQL 기본",
    ]
    # 스크립트, 스타일, noscript, 숨은 요소는 버린다 (F11)
    for hidden in ("버려야 할 스크립트", "100점", "숨은 글", "스크립트 꺼짐"):
        assert hidden not in detail.text
    # 상대 주소는 절대 주소로, 같은 이미지는 한 번만, data: 이미지는 뺀다
    assert detail.images == [
        "https://www.saramin.co.kr/images/detail1.png",
        "https://example-company.co.kr/recruit/detail2.jpg",
    ]


def test_parse_detail_without_body_area_is_empty():
    detail = saramin.parse_detail("<html><body><div class='other'>본문 아님</div></body></html>")

    assert detail.text == ""
    assert detail.images == []


def test_search_url_joins_several_regions_with_comma():
    """여러 지역은 loc_mcd 하나에 쉼표로 (v0.6.1 F29). 사람인이 받는지는 재리 PC에서 확인 (미확인)."""
    query = parse_qs(urlsplit(saramin.search_url("백엔드", {"region_codes": ["101000", "102000"]})).query)

    assert query["loc_mcd"] == ["101000,102000"]


def test_search_url_without_region_has_no_loc_mcd():
    query = parse_qs(urlsplit(saramin.search_url("백엔드", {"region_codes": []})).query)

    assert "loc_mcd" not in query


def test_search_url_next_page():
    assert "recruitPage" not in parse_qs(urlsplit(saramin.search_url("백엔드", {})).query)  # 첫 쪽은 그대로
    query = parse_qs(urlsplit(saramin.search_url("백엔드", {}, page=2)).query)
    assert query["recruitPage"] == ["2"] and query["recruitPageCount"] == ["40"]  # v0.7.6 F2

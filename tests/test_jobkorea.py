from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from agent import jobkorea

FIXTURES = Path(__file__).parent / "fixtures"


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_list_reads_cards_and_deadlines_from_next_data():
    jobs = jobkorea.parse_list(read("jobkorea_list.html"))

    assert [job["id"] for job in jobs] == ["2001", "2002", "2003"]  # 데이터에 없는 광고 카드 제외 (F6)
    assert jobs[0] == {
        "source": "jobkorea",
        "id": "2001",
        "company": "차카타시스템즈",
        "title": "Forward Deployed Engineer",
        "experience": "경력무관",
        "education": "",
        "location": "서울 강남구 외 1",  # 장소 아이콘 GrayChip (직무 GrayChip은 무시)
        "deadline": "2026-11-12",
        "keywords": "",
        "url": "https://www.jobkorea.co.kr/Recruit/GI_Read/2001",
    }


def test_location_and_experience_mixed_in_one_chip_are_split():
    # 2026-10-21 FDE 시험 수집 버그: 지역·경력이 한 칸에 섞여 둘 다 같은 값이 들어감
    jobs = jobkorea.parse_list(read("jobkorea_list.html"))

    assert (jobs[1]["location"], jobs[1]["experience"]) == ("경기 성남시", "경력 3년↑")
    assert (jobs[2]["location"], jobs[2]["experience"]) == ("부산 해운대구", "신입")
    assert all(job["location"] != job["experience"] for job in jobs)


def test_deadline_null_is_always_open_and_iso_is_cut_to_date():
    jobs = jobkorea.parse_list(read("jobkorea_list.html"))

    assert [job["deadline"] for job in jobs] == ["2026-11-12", "상시", "2026-10-31"]


def test_cards_without_next_data_are_kept_with_blank_deadline():
    html = read("jobkorea_list.html").split("<script>")[0]

    jobs = jobkorea.parse_list(html)

    assert [job["id"] for job in jobs] == ["2001", "2002", "2003", "9999"]
    assert {job["deadline"] for job in jobs} == {""}


def test_parse_list_returns_empty_for_unknown_page():
    assert jobkorea.parse_list("<html><body><div>검색 결과 없음</div></body></html>") == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("서울 강남구 경력 3년↑", ("서울 강남구", "경력 3년↑")),
        ("경기 성남시 · 신입·경력", ("경기 성남시", "신입·경력")),
        ("대전 유성구 경력2~10년", ("대전 유성구", "경력2~10년")),
        ("5년 이상", ("", "5년 이상")),
        ("경력무관", ("", "경력무관")),
        ("서울 송파구", ("서울 송파구", "")),
    ],
)
def test_split_condition(text, expected):
    assert jobkorea.split_condition(text) == expected


def test_search_url_has_keyword_only():
    parts = urlsplit(jobkorea.search_url("FDE", {"region_codes": ["101000"], "job_code": "84", "career": "신입"}))

    assert parts.netloc == "www.jobkorea.co.kr"
    assert parts.path == "/Search/"
    assert parse_qs(parts.query) == {"stext": ["FDE"], "tabType": ["recruit"]}


def test_detail_url_and_parse_detail():
    assert jobkorea.detail_url("2001") == "https://www.jobkorea.co.kr/Recruit/GI_Read_Comt_Ifrm?Gno=2001"

    detail = jobkorea.parse_detail(read("jobkorea_detail.html"))

    assert detail.text == "고객사 현장에 배치되어 AI 솔루션을 구축합니다.\nPython, LLM 경험 우대"
    assert detail.images == ["https://file1.jobkorea.co.kr/Net/Recruit/image.jpg"]


def test_parse_detail_without_body_area_is_empty():
    assert jobkorea.parse_detail("<html><body></body></html>").text == ""


def test_search_url_next_page():
    assert parse_qs(urlsplit(jobkorea.search_url("FDE", {}, page=3)).query) == {
        "stext": ["FDE"], "tabType": ["recruit"], "Page_No": ["3"],
    }  # v0.7.6 F2  # fmt: skip

"""사람인 공개 검색 결과와 상세 본문 페이지를 읽는다. 요청은 crawler.py가 한다."""

import re
from datetime import date, timedelta
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from agent import postings

SOURCE = "saramin"
NAME = "사람인"
BASE = "https://www.saramin.co.kr"
PAGE_SIZE = 40  # 검색 결과 1페이지 개수

# 검색 주소의 경력 조건 (추정, 설계 미확인 항목)
EXPERIENCE_CODES = {"신입": "1", "경력": "2"}


def search_url(keyword: str, filters: dict) -> str:
    params = {"searchword": keyword, "recruitPageCount": PAGE_SIZE, "sort": "RD"}  # 등록일순
    if filters.get("region_code"):
        params["loc_mcd"] = filters["region_code"]
    if filters.get("job_code"):
        params["cat_kewd"] = filters["job_code"]
    if filters.get("career"):
        params["exp_cd"] = EXPERIENCE_CODES[filters["career"]]
    return f"{BASE}/zf_user/search/recruit?{urlencode(params)}"


def detail_url(job_id: str) -> str:
    return f"{BASE}/zf_user/jobs/relay/view-detail?rec_idx={job_id}"


def view_url(job_id: str) -> str:
    return f"{BASE}/zf_user/jobs/relay/view?rec_idx={job_id}"


def parse_deadline(text: str, today: date | None = None) -> str:
    """ "~ 11/12(목)"은 오늘 이후 가장 가까운 날짜로, 상시·채용시는 "상시"로 바꾼다 (F5). 모르면 빈칸."""
    today = today or date.today()
    text = text.strip()
    if "상시" in text or "채용시" in text:
        return "상시"
    if "오늘마감" in text:
        return today.isoformat()
    if "내일마감" in text:
        return (today + timedelta(days=1)).isoformat()
    full = re.search(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})", text)
    if full:
        return date(*map(int, full.groups())).isoformat()
    short = re.search(r"(\d{1,2})[./](\d{1,2})", text)
    if not short:
        return ""
    month, day = map(int, short.groups())
    try:
        candidate = date(today.year, month, day)
        if candidate < today:
            candidate = date(today.year + 1, month, day)  # 12월에 본 1월 마감
    except ValueError:  # 2/29 같은 없는 날짜
        return ""
    return candidate.isoformat()


def parse_list(html: str, today: date | None = None) -> list[dict]:
    jobs = []
    for item in BeautifulSoup(html, "html.parser").select("div.item_recruit"):
        job_id = (item.get("value") or "").strip()
        title = item.select_one("h2.job_tit a")
        company = item.select_one("strong.corp_name a")
        if not (job_id.isdigit() and title and company):
            continue  # 공고ID가 없는 카드(광고 등)는 건너뛴다
        experience = education = location = ""
        for span in item.select("div.job_condition > span"):
            text = " ".join(span.get_text(" ").split())
            if span.find("a"):
                location = location or text
            elif "신입" in text or "경력" in text:
                experience = experience or text
            elif "졸" in text or "학력" in text:
                education = education or text
        date_tag = item.select_one("div.job_date span.date")
        sector = [a.get_text(strip=True) for a in item.select("div.job_sector a")]
        jobs.append(
            {
                "source": SOURCE,
                "id": job_id,
                "company": company.get_text(strip=True),
                "title": (title.get("title") or title.get_text(" ")).strip(),
                "experience": experience,
                "education": education,
                "location": location,
                "deadline": parse_deadline(date_tag.get_text(" ") if date_tag else "", today),
                "keywords": ", ".join(s for s in sector if s),
                "url": view_url(job_id),
            }
        )
    return jobs


def parse_detail(html: str) -> postings.Detail:
    return postings.extract(html, "div.user_content", BASE)

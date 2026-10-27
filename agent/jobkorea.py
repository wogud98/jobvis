"""잡코리아 공개 검색 결과와 상세 본문 창을 읽는다. 요청은 crawler.py가 한다."""

import re
from urllib.parse import urlencode

from bs4 import BeautifulSoup, Tag

from agent import codes, postings

SOURCE = "jobkorea"
NAME = "잡코리아"
BASE = "https://www.jobkorea.co.kr"

_ID = re.compile(r"/Recruit/GI_Read/(\d+)")
_PLACE_ICON = "emoji--basicemoji-place"
_CHIP = "span.flex-shrink-0.text-gray700.text-typo-c1-13"
# 경력 글자: 신입·경력, 경력무관, 경력 3년↑, 경력 2~10년, 5년 이상, 신입, 경력
_EXPERIENCE = re.compile(
    r"신입\s*[·,/]\s*경력|경력\s*무관|경력\s*\d+\s*(?:[~\-]\s*\d+\s*)?년\s*(?:이상|↑)?|\d+\s*년\s*(?:이상|↑)|신입|경력"
)
_PERIOD = re.compile(r'"applicationPeriod"\s*:\s*\{[^{}]*?"end"\s*:\s*(null|"[^"]*")')


def search_url(keyword: str, filters: dict, page: int = 1) -> str:
    # 지역·직무·경력은 주소에 넣지 않고 받은 목록에서 거른다 (설계 "검색 주소와 조건")
    params = {"stext": keyword, "tabType": "recruit"}
    if page > 1:
        params["Page_No"] = page  # 다음 쪽 (v0.7.6 F2)
    return f"{BASE}/Search/?{urlencode(params)}"


def detail_url(job_id: str) -> str:
    return f"{BASE}/Recruit/GI_Read_Comt_Ifrm?Gno={job_id}"


def view_url(job_id: str) -> str:
    return f"{BASE}/Recruit/GI_Read/{job_id}"


def split_condition(text: str) -> tuple[str, str]:
    """한 칸에 섞인 "서울 강남구 경력 3년↑" 같은 글자를 (지역, 경력)으로 나눈다."""
    text = " ".join(text.split())
    match = _EXPERIENCE.search(text)
    if not match:
        return text, ""
    rest = (text[: match.start()] + " " + text[match.end() :]).strip(" ·,|/")
    return " ".join(rest.split()).strip(" ·,|/"), match.group().strip()


def _looks_like_location(text: str) -> bool:
    return any(text.startswith(name) for name in codes.REGIONS)


def _conditions(card: Tag) -> tuple[str, str]:
    location = experience = ""
    # 2026-10-21 실제 화면: 지역은 장소 아이콘(emoji--basicemoji-place2)이 든 GrayChip의 span.truncate에 있음
    for chip in card.select('[data-sentry-component="GrayChip"]'):
        if chip.select_one(f"[class*='{_PLACE_ICON}']"):
            text = chip.select_one("span.truncate") or chip
            location = " ".join(text.get_text(" ").split())
            break
    # 경력은 회색 글자 칩. 지역이 섞여 나오면 나눠 읽는다 (2026-10-21 FDE 시험 수집)
    for chip in card.select(_CHIP):
        place = chip.select_one(f"[class*='{_PLACE_ICON}']") or (
            isinstance(chip.find_previous_sibling(), Tag) and _PLACE_ICON in str(chip.find_previous_sibling())
        )
        rest, found = split_condition(chip.get_text(" "))
        experience = experience or found
        if rest and not location and (place or _looks_like_location(rest)):
            location = rest
    return location, experience


def _card(title: Tag) -> Tag:
    # 제목 링크에서 위로 올라가며, 공고 하나만 담은 가장 큰 상자를 카드로 본다.
    card = title
    while card.parent is not None and len(card.parent.select('a[data-sentry-component="Title"]')) == 1:
        card = card.parent
    return card


def _deadlines(soup: BeautifulSoup, ids: list[str]) -> dict[str, str] | None:
    """Next.js 데이터에서 공고ID마다 마감일을 찾는다. 데이터에 없는 ID는 광고 카드로 본다 (F6, 추정).

    데이터를 아예 찾지 못하면 None.
    """
    data = "\n".join(script.get_text() for script in soup.find_all("script")).replace('\\"', '"')
    positions = {job_id: [m.start() for m in re.finditer(rf"(?<!\d){job_id}(?!\d)", data)] for job_id in ids}
    if not any(positions.values()):
        return None
    found = dict.fromkeys((job_id for job_id, pos in positions.items() if pos), "")
    for match in _PERIOD.finditer(data):
        # 마감일 칸과 가장 가까이 적힌 공고ID를 그 마감일의 주인으로 본다 (추정)
        nearest = min(
            ((abs(p - match.start()), job_id) for job_id, pos in positions.items() for p in pos),
            default=None,
        )
        if nearest and not found[nearest[1]]:
            end = match.group(1)
            found[nearest[1]] = "상시" if end == "null" or end == '""' else end.strip('"')[:10]
    return found


def parse_list(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = []
    for title in soup.select('a[data-sentry-component="Title"]'):
        match = _ID.search(title.get("href", ""))
        if match and match.group(1) not in [c[0] for c in cards]:
            cards.append((match.group(1), title))
    deadlines = _deadlines(soup, [job_id for job_id, _ in cards])
    jobs = []
    for job_id, title in cards:
        if deadlines is not None and job_id not in deadlines:
            continue  # 광고 카드
        card = _card(title)
        company = card.select_one("span.mb-5 a span.truncate")
        location, experience = _conditions(card)
        jobs.append(
            {
                "source": SOURCE,
                "id": job_id,
                "company": company.get_text(strip=True) if company else "",
                "title": " ".join(title.get_text(" ").split()),
                "experience": experience,
                "education": "",  # 목록에 학력 글자가 없음 (F4)
                "location": location,
                "deadline": deadlines.get(job_id, "") if deadlines else "",
                "keywords": "",
                "url": view_url(job_id),
            }
        )
    return jobs


def parse_detail(html: str) -> postings.Detail:
    return postings.extract(html, "div.section-content", BASE)

"""사람인 오픈API에서 채용공고를 가져온다."""

import os
from datetime import datetime

import requests

API_URL = "https://oapi.saramin.co.kr/job-search"


class SaraminAPIError(Exception):
    """사람인 API 호출 실패. 메시지에 API 키가 담긴 요청 주소를 넣지 않는다."""


def fetch_jobs(keyword: str, location: str | None = None, count: int = 1) -> list[dict]:
    params = {
        "access-key": os.environ["SARAMIN_API_KEY"],
        "keywords": keyword,
        "count": count,
        "sort": "pd",  # 최신 게시순
    }
    if location:
        params["loc_mcd"] = location  # 사람인 지역 코드 (예: 101000 = 서울)
    # requests의 오류 메시지는 access-key가 붙은 전체 주소를 담으므로 원본 예외를 버리고 다시 던진다.
    try:
        resp = requests.get(API_URL, params=params, headers={"Accept": "application/json"}, timeout=10)
    except requests.RequestException as e:
        raise SaraminAPIError(f"사람인 API 연결 실패 ({type(e).__name__})") from None
    if not resp.ok:
        raise SaraminAPIError(f"사람인 API 오류 (HTTP {resp.status_code})")
    return [_to_row(job) for job in resp.json()["jobs"]["job"]]


def _to_row(job: dict) -> dict:
    position = job.get("position", {})
    expires = job.get("expiration-timestamp")
    return {
        "company": job["company"]["detail"]["name"],
        "title": position.get("title", ""),
        "experience": position.get("experience-level", {}).get("name", ""),
        "education": position.get("required-education-level", {}).get("name", ""),
        "keywords": job.get("keyword", ""),
        "deadline": datetime.fromtimestamp(int(expires)).strftime("%Y-%m-%d") if expires else "상시",
        "url": job.get("url", ""),
    }

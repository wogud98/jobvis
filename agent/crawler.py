"""공개 페이지 요청 규칙 한 곳: robots.txt 확인, 이름 밝힌 User-Agent, 호스트별 요청 간격, 차단 시 멈춤."""

import time
import urllib.robotparser
from urllib.parse import urlsplit

import requests

USER_AGENT = "JOBVIS/0.4 (personal job search)"  # 브라우저로 꾸미지 않는다 (N3)
DELAY = 3  # 같은 호스트 요청 사이 최소 간격(초) (N4)
TIMEOUT = 10

# 테스트에서 시계와 대기를 가짜로 바꾼다.
_clock = time.monotonic
_sleep = time.sleep

_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}  # 호스트 -> 규칙, None이면 전체 금지
_last_request: dict[str, float] = {}


class CrawlError(Exception):
    """요청 실패. 메시지에는 호스트와 이유만 담고 주소 전체는 담지 않는다."""


class Disallowed(CrawlError):
    """robots.txt가 금지한 주소. 요청하지 않았다."""


class Blocked(CrawlError):
    """403·429 응답. 그 사이트 수집을 멈춘다."""


class StructureChanged(CrawlError):
    """검색 결과에서 공고를 하나도 못 읽음. 사이트 구조가 바뀌었을 수 있다."""


def reset() -> None:
    """실행 중 기억한 robots 규칙과 요청 시각을 지운다 (테스트용)."""
    _robots.clear()
    _last_request.clear()


def _host(url: str) -> str:
    return urlsplit(url).netloc


def _wait(host: str) -> None:
    last = _last_request.get(host)
    if last is not None:
        remaining = DELAY - (_clock() - last)
        if remaining > 0:
            _sleep(remaining)
    _last_request[host] = _clock()


def _request(url: str) -> requests.Response:
    host = _host(url)
    _wait(host)
    try:
        return requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    except requests.RequestException as e:
        # requests 예외 메시지에는 주소 전체가 들어가므로 버린다.
        raise CrawlError(f"{host} 연결 실패 ({type(e).__name__})") from None


def _load_robots(url: str) -> urllib.robotparser.RobotFileParser | None:
    parts = urlsplit(url)
    host = parts.netloc
    if host not in _robots:
        rules = None
        try:
            resp = _request(f"{parts.scheme}://{host}/robots.txt")
            if resp.status_code == 404:
                rules = urllib.robotparser.RobotFileParser()
                rules.parse([])  # 규칙 없음 = 전부 허용
            elif resp.ok:
                rules = urllib.robotparser.RobotFileParser()
                rules.parse(resp.text.splitlines())
            # 그 밖의 응답은 그 호스트 전체를 금지로 본다 (N2)
        except CrawlError:
            pass
        _robots[host] = rules
    return _robots[host]


def allowed(url: str) -> bool:
    rules = _load_robots(url)
    return rules is not None and rules.can_fetch(USER_AGENT, url)


def _get(url: str) -> requests.Response:
    host = _host(url)
    if not allowed(url):
        raise Disallowed(f"{host} robots.txt 금지")
    resp = _request(url)
    if resp.status_code in (403, 429):
        raise Blocked(f"{host} 차단 (HTTP {resp.status_code})")
    if not resp.ok:
        raise CrawlError(f"{host} 오류 (HTTP {resp.status_code})")
    return resp


def get_text(url: str) -> str:
    resp = _get(url)
    # 헤더에 문자셋이 없으면 requests가 ISO-8859-1로 보고 한글이 깨지므로 내용으로 추정한다.
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding
    return resp.text


def get_bytes(url: str) -> bytes:
    return _get(url).content

import pytest
import requests

from agent import crawler

ROBOTS = "User-agent: *\nDisallow: /private/\n"


class FakeResponse:
    def __init__(self, status=200, text="", content=b"", encoding="utf-8"):
        self.status_code = status
        self.text = text
        self.content = content
        self.encoding = encoding
        self.apparent_encoding = "utf-8"

    @property
    def ok(self):
        return self.status_code < 400


class FakeWeb:
    """주소별 응답을 돌려주는 가짜 인터넷. 시계도 가짜로 바꿔 3초 대기를 바로 확인한다."""

    def __init__(self, monkeypatch, pages):
        self.pages = pages
        self.requests = []
        self.sleeps = []
        self.now = 100.0
        crawler.reset()

        def fake_get(url, headers, timeout):
            self.requests.append((url, headers["User-Agent"], timeout))
            page = self.pages.get(url, FakeResponse(404))
            if isinstance(page, Exception):
                raise page
            return page

        def fake_sleep(seconds):
            self.sleeps.append(seconds)
            self.now += seconds

        monkeypatch.setattr(crawler.requests, "get", fake_get)
        monkeypatch.setattr(crawler, "_clock", lambda: self.now)
        monkeypatch.setattr(crawler, "_sleep", fake_sleep)

    def urls(self):
        return [url for url, _, _ in self.requests]


def test_allowed_page_is_fetched_with_named_user_agent(monkeypatch):
    web = FakeWeb(
        monkeypatch,
        {"https://a.test/robots.txt": FakeResponse(text=ROBOTS), "https://a.test/jobs": FakeResponse(text="목록")},
    )

    assert crawler.get_text("https://a.test/jobs") == "목록"

    assert web.urls() == ["https://a.test/robots.txt", "https://a.test/jobs"]
    assert {ua for _, ua, _ in web.requests} == {"JOBVIS/0.4 (personal job search)"}
    assert "Mozilla" not in crawler.USER_AGENT  # 브라우저로 꾸미지 않음 (N3)
    assert {timeout for _, _, timeout in web.requests} == {10}


def test_waits_three_seconds_between_requests_to_same_host(monkeypatch):
    web = FakeWeb(
        monkeypatch,
        {
            "https://a.test/robots.txt": FakeResponse(text=ROBOTS),
            "https://a.test/1": FakeResponse(text="1"),
            "https://a.test/2": FakeResponse(text="2"),
            "https://b.test/robots.txt": FakeResponse(404),
            "https://b.test/1": FakeResponse(text="b"),
        },
    )

    crawler.get_text("https://a.test/1")
    crawler.get_text("https://a.test/2")
    crawler.get_text("https://b.test/1")

    # a.test는 robots → 1 → 2 사이 두 번, b.test는 robots → 1 사이 한 번. robots.txt 요청도 간격에 셈 (N4).
    # 다른 호스트로 넘어갈 때(a/2 → b robots)는 기다리지 않음.
    assert web.sleeps == [crawler.DELAY, crawler.DELAY, crawler.DELAY]
    assert web.urls().count("https://a.test/robots.txt") == 1  # 호스트마다 한 번만 읽음


def test_disallowed_page_is_not_requested(monkeypatch):
    web = FakeWeb(monkeypatch, {"https://a.test/robots.txt": FakeResponse(text=ROBOTS)})

    with pytest.raises(crawler.Disallowed):
        crawler.get_text("https://a.test/private/1")

    assert web.urls() == ["https://a.test/robots.txt"]


def test_robots_404_allows_everything(monkeypatch):
    FakeWeb(monkeypatch, {"https://a.test/img.png": FakeResponse(content=b"PNG")})

    assert crawler.get_bytes("https://a.test/img.png") == b"PNG"


@pytest.mark.parametrize("robots", [FakeResponse(500), FakeResponse(403), requests.Timeout("timeout")])
def test_robots_error_disallows_the_whole_host(monkeypatch, robots):
    web = FakeWeb(monkeypatch, {"https://a.test/robots.txt": robots, "https://a.test/jobs": FakeResponse(text="x")})

    with pytest.raises(crawler.Disallowed):
        crawler.get_text("https://a.test/jobs")

    assert "https://a.test/jobs" not in web.urls()


@pytest.mark.parametrize("status", [403, 429])
def test_403_and_429_raise_blocked(monkeypatch, status):
    FakeWeb(monkeypatch, {"https://a.test/robots.txt": FakeResponse(404), "https://a.test/jobs": FakeResponse(status)})

    with pytest.raises(crawler.Blocked) as exc_info:
        crawler.get_text("https://a.test/jobs")

    assert str(exc_info.value) == f"a.test 차단 (HTTP {status})"


def test_other_errors_hide_full_address(monkeypatch):
    FakeWeb(
        monkeypatch,
        {
            "https://a.test/robots.txt": FakeResponse(404),
            "https://a.test/jobs?token=secret": requests.ConnectionError("https://a.test/jobs?token=secret 실패"),
            "https://a.test/gone?token=secret": FakeResponse(500),
        },
    )

    with pytest.raises(crawler.CrawlError) as conn:
        crawler.get_text("https://a.test/jobs?token=secret")
    with pytest.raises(crawler.CrawlError) as server:
        crawler.get_text("https://a.test/gone?token=secret")

    assert str(conn.value) == "a.test 연결 실패 (ConnectionError)"
    assert str(server.value) == "a.test 오류 (HTTP 500)"


def test_missing_charset_is_guessed_from_content(monkeypatch):
    page = FakeResponse(text="한글", encoding="ISO-8859-1")
    FakeWeb(monkeypatch, {"https://a.test/robots.txt": FakeResponse(404), "https://a.test/p": page})

    crawler.get_text("https://a.test/p")

    assert page.encoding == "utf-8"

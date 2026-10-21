import pytest

from agent import crawler, graph, postings
from agent.postings import Detail

LONG = "주요업무와 자격요건이 담긴 본문. " * 20  # 200자 넘음


def make_job(source: str, job_id: str, **changes) -> dict:
    job = {
        "source": source,
        "id": job_id,
        "company": f"회사{job_id}",
        "title": "백엔드 개발자",
        "experience": "신입",
        "education": "대졸" if source == "saramin" else "",
        "location": "서울 강남구",
        "deadline": "2026-11-01",
        "keywords": "Python" if source == "saramin" else "",
        "url": f"https://{source}.test/{job_id}",
    }
    return job | changes


class Fakes:
    """사이트 모듈, crawler, OCR, 시트를 가짜로 바꾼다. 실제 요청 없음."""

    def __init__(self, monkeypatch, tmp_path, lists, details=None, existing=((), ()), fail_save_ids=()):
        self.lists = lists  # 출처 -> 공고 목록 또는 예외
        self.details = details or {}  # 공고ID -> Detail 또는 예외
        self.images = {}  # 이미지 주소 -> bytes 또는 예외
        self.sizes = {}  # bytes -> (가로, 세로)
        self.ocr_fail = set()
        self.requested = []
        self.ocr_read = []
        self.rows = []
        self.fail_save_ids = set(fail_save_ids)
        self.search_filters = {}

        for source, module in graph.SOURCES.items():
            monkeypatch.setattr(module, "search_url", self._search_url(source))
            monkeypatch.setattr(module, "parse_list", lambda html: self._list(html))
            monkeypatch.setattr(module, "detail_url", lambda job_id, source=source: f"detail:{source}:{job_id}")
            monkeypatch.setattr(module, "parse_detail", lambda html: html)

        def fake_get_text(url):
            self.requested.append(url)
            kind, source, key = url.split(":", 2)
            value = self.lists[source] if kind == "search" else self.details.get(key, Detail(LONG))
            if isinstance(value, Exception):
                raise value
            return (source, value) if kind == "search" else value

        def fake_get_bytes(url):
            self.requested.append(url)
            value = self.images[url]
            if isinstance(value, Exception):
                raise value
            return value

        def fake_read(image):
            if image in self.ocr_fail:
                raise RuntimeError("OCR 모델 오류")
            self.ocr_read.append(image)
            return f"OCR:{image.decode()}"

        def fake_append(row):
            if row[5] in self.fail_save_ids:
                raise ConnectionError("시트 연결 끊김")
            self.rows.append(row)

        monkeypatch.setattr(graph.crawler, "get_text", fake_get_text)
        monkeypatch.setattr(graph.crawler, "get_bytes", fake_get_bytes)
        monkeypatch.setattr(graph.ocr, "read", fake_read)
        monkeypatch.setattr(graph.ocr, "size", lambda image: self.sizes.get(image, (800, 1200)))
        monkeypatch.setattr(graph.postings, "DIR", tmp_path / "postings")
        monkeypatch.setattr(graph.sheets, "existing_keys", lambda: (set(existing[0]), set(existing[1])))
        monkeypatch.setattr(graph.sheets, "append_row", fake_append)
        # 수집은 LLM을 부르지 않는다 (N7)
        monkeypatch.setattr(graph, "init_chat_model", lambda *a, **k: pytest.fail("수집에서 LLM을 부르면 안 됨"))

    def _search_url(self, source):
        def search_url(keyword, filters):
            self.search_filters[source] = (keyword, filters.get("region_code"), filters.get("career"))
            return f"search:{source}:{keyword}"

        return search_url

    @staticmethod
    def _list(value):
        return value[1]


def run(sources=("saramin", "jobkorea"), count=10, career=None, location=None, ocr_ready=True):
    state = {
        "keyword": "백엔드",
        "sources": list(sources),
        "location": location,
        "region_code": "101000" if location else None,
        "job_code": None,
        "career": career,
        "count": count,
        "ocr_ready": ocr_ready,
    }
    return graph.build_graph().invoke(state, {"recursion_limit": graph.recursion_limit(count * len(sources))})


def ids(jobs):
    return [(job["source"], job["id"]) for job in jobs]


def assert_counts_add_up(result):
    # OCR 실패는 줄을 저장한 채 실패 목록에만 남으므로 셈에서 뺀다. 목록 실패는 공고가 없다.
    failed = [f for f in result.get("failed", []) if f["step"] not in ("OCR", "목록")]
    total = len(result.get("saved", [])) + len(result.get("skipped", [])) + len(failed)
    assert sum(result["fetched"].values()) == total


def test_collects_both_sites_and_saves_rows_and_posting_files(monkeypatch, tmp_path):
    fakes = Fakes(
        monkeypatch,
        tmp_path,
        {"saramin": [make_job("saramin", "1")], "jobkorea": [make_job("jobkorea", "2", title="데이터 엔지니어")]},
    )

    result = run()

    assert result["fetched"] == {"saramin": 1, "jobkorea": 1}
    assert ids(result["saved"]) == [("saramin", "1"), ("jobkorea", "2")]
    row = fakes.rows[0]
    header = graph.sheets.HEADER
    assert len(row) == header.index("본문") + 1
    assert row[:6] == ["회사1", "백엔드 개발자", "", "2026-11-01", "https://saramin.test/1", "1"]
    assert row[7:11] == ["신입", "대졸", "Python", False]
    assert row[11 : header.index("출처")] == [""] * 10  # 평가 칸은 비움
    assert row[header.index("출처") :] == ["사람인", "서울 강남구", "글자"]
    assert fakes.rows[1][header.index("출처")] == "잡코리아"
    # 원문은 PC 파일에만, 시트에는 넣지 않는다 (F14)
    assert (tmp_path / "postings" / "saramin_1.txt").read_text(encoding="utf-8") == LONG
    assert (tmp_path / "postings" / "jobkorea_2.txt").exists()
    assert LONG not in str(fakes.rows)
    assert_counts_add_up(result)


def test_one_source_only(monkeypatch, tmp_path):
    fakes = Fakes(monkeypatch, tmp_path, {"saramin": [make_job("saramin", "1")], "jobkorea": AssertionError()})

    result = run(sources=["saramin"])

    assert result["fetched"] == {"saramin": 1}
    assert not any(url.startswith("search:jobkorea") for url in fakes.requested)


def test_duplicate_by_source_id_skips_detail_request(monkeypatch, tmp_path):
    fakes = Fakes(
        monkeypatch,
        tmp_path,
        {"saramin": [make_job("saramin", "1"), make_job("saramin", "2", title="다른 공고")], "jobkorea": []},
        existing=({("saramin", "1"), ("jobkorea", "2")}, set()),
    )
    fakes.lists["jobkorea"] = [make_job("jobkorea", "3", title="또 다른 공고")]

    result = run()

    assert ids(result["skipped"]) == [("saramin", "1")]
    assert ids(result["saved"]) == [("saramin", "2"), ("jobkorea", "3")]  # 같은 ID라도 출처가 다르면 다른 공고
    assert "detail:saramin:1" not in fakes.requested  # 본문을 가져오지 않음 (F8)
    assert_counts_add_up(result)


def test_same_posting_on_both_sites_keeps_the_first(monkeypatch, tmp_path):
    fakes = Fakes(
        monkeypatch,
        tmp_path,
        {
            "saramin": [make_job("saramin", "1", company="(주)가나다", title="백엔드 개발자 [신입]")],
            "jobkorea": [
                make_job("jobkorea", "7", company="(주) 가나다", title="백엔드 개발자 신입"),
                make_job("jobkorea", "8", company="라마바", title="Backend"),
            ],
        },
        existing=(set(), {("라마바", "backend")}),  # 시트에 이미 있는 회사+제목 (대소문자 무시)
    )

    result = run()

    assert ids(result["saved"]) == [("saramin", "1")]
    assert ids(result["skipped"]) == [("jobkorea", "7"), ("jobkorea", "8")]
    assert "detail:jobkorea:7" not in fakes.requested
    assert_counts_add_up(result)


def test_career_and_location_filters(monkeypatch, tmp_path):
    Fakes(
        monkeypatch,
        tmp_path,
        {
            "saramin": [
                make_job("saramin", "1", experience="경력 3년↑"),
                make_job("saramin", "2", experience="경력무관", location="부산"),  # 사람인은 주소로 거름
            ],
            "jobkorea": [
                make_job("jobkorea", "3", experience="신입·경력"),
                make_job("jobkorea", "4", experience="신입", location="부산 해운대구"),
                make_job("jobkorea", "5", experience="경력 5년 이상"),
            ],
        },
    )

    result = run(career="신입", location="서울")

    assert result["fetched"] == {"saramin": 1, "jobkorea": 1}
    assert ids(result["saved"]) == [("saramin", "2"), ("jobkorea", "3")]


def test_count_is_per_site(monkeypatch, tmp_path):
    Fakes(
        monkeypatch,
        tmp_path,
        {
            "saramin": [make_job("saramin", str(i), title=f"s{i}") for i in range(5)],
            "jobkorea": [make_job("jobkorea", str(i), title=f"j{i}") for i in range(5)],
        },
    )

    result = run(count=2)

    assert result["fetched"] == {"saramin": 2, "jobkorea": 2}
    assert len(result["saved"]) == 4


def test_blocked_site_stops_but_other_site_continues(monkeypatch, tmp_path):
    fakes = Fakes(
        monkeypatch,
        tmp_path,
        {"saramin": [make_job("saramin", "1"), make_job("saramin", "2", title="b")], "jobkorea": []},
        details={"1": crawler.Blocked("www.saramin.co.kr 차단 (HTTP 429)")},
    )
    fakes.lists["jobkorea"] = [make_job("jobkorea", "3", title="c")]

    result = run()

    assert result["blocked"] == [{"source": "saramin", "reason": "www.saramin.co.kr 차단 (HTTP 429)"}]
    assert ids(result["saved"]) == [("jobkorea", "3")]
    assert [(f["source"], f["step"]) for f in result["failed"]] == [("saramin", "본문"), ("saramin", "본문")]
    assert "detail:saramin:2" not in fakes.requested  # 막힌 뒤로는 요청하지 않음 (N4)
    assert_counts_add_up(result)


def test_search_blocked_or_empty_stops_only_that_site(monkeypatch, tmp_path):
    Fakes(monkeypatch, tmp_path, {"saramin": crawler.Blocked("www.saramin.co.kr 차단 (HTTP 403)"), "jobkorea": []})

    result = run()

    assert result["fetched"] == {"saramin": 0, "jobkorea": 0}
    assert result["blocked"] == [
        {"source": "saramin", "reason": "www.saramin.co.kr 차단 (HTTP 403)"},
        {"source": "jobkorea", "reason": "사이트 구조가 바뀌었을 수 있음"},  # 0건 (F20)
    ]
    assert result.get("saved", []) == []


def test_search_robots_disallowed_and_connection_error(monkeypatch, tmp_path):
    Fakes(
        monkeypatch,
        tmp_path,
        {"saramin": crawler.Disallowed("금지"), "jobkorea": crawler.CrawlError("www.jobkorea.co.kr 연결 실패")},
    )

    result = run()

    assert result["blocked"] == [{"source": "saramin", "reason": "robots.txt 금지"}]
    assert result["failed"] == [
        {
            "source": "jobkorea",
            "company": "",
            "title": "",
            "step": "목록",
            "error": "CrawlError: www.jobkorea.co.kr 연결 실패",  # 호스트와 이유까지 남김 (2026-10-21 PC 시험)
        },
    ]


def test_detail_failure_does_not_save_row(monkeypatch, tmp_path):
    fakes = Fakes(
        monkeypatch,
        tmp_path,
        {"saramin": [make_job("saramin", "1"), make_job("saramin", "2", title="b")], "jobkorea": []},
        details={"1": crawler.CrawlError("www.saramin.co.kr 연결 실패 (Timeout)")},
    )
    fakes.lists["jobkorea"] = [make_job("jobkorea", "3", title="c")]

    result = run()

    # 저장하지 않아야 다음 실행 때 다시 시도된다
    assert [row[5] for row in fakes.rows] == ["2", "3"]
    assert result["failed"][0] == {
        "source": "saramin",
        "company": "회사1",
        "title": "백엔드 개발자",
        "step": "본문",
        "error": "CrawlError: www.saramin.co.kr 연결 실패 (Timeout)",
    }
    assert not (tmp_path / "postings" / "saramin_1.txt").exists()
    assert_counts_add_up(result)


def test_non_crawler_errors_keep_only_the_name(monkeypatch, tmp_path):
    Fakes(
        monkeypatch,
        tmp_path,
        {"saramin": [make_job("saramin", "1")]},
        details={"1": ValueError("token=secret 파싱 실패")},
    )

    result = run(sources=["saramin"])

    assert result["failed"][0]["error"] == "ValueError"  # 크롤러 밖 예외는 메시지를 버림
    assert "secret" not in str(result["failed"])


def test_save_failure_does_not_stop_others(monkeypatch, tmp_path):
    fakes = Fakes(
        monkeypatch,
        tmp_path,
        {"saramin": [make_job("saramin", "1"), make_job("saramin", "2", title="b")], "jobkorea": []},
        fail_save_ids={"1"},
    )
    fakes.lists["jobkorea"] = [make_job("jobkorea", "3", title="c")]

    result = run()

    assert ids(result["saved"]) == [("saramin", "2"), ("jobkorea", "3")]
    assert [(f["company"], f["step"], f["error"]) for f in result["failed"]] == [("회사1", "저장", "ConnectionError")]
    assert_counts_add_up(result)


def test_ocr_reads_large_images_and_appends_text(monkeypatch, tmp_path):
    images = ["https://img.test/big.png", "https://img.test/icon.png", "https://pds.test/banned.png"]
    fakes = Fakes(
        monkeypatch,
        tmp_path,
        {"saramin": [make_job("saramin", "1")], "jobkorea": []},
        details={"1": Detail("짧은 본문", images)},
    )
    fakes.lists["jobkorea"] = [make_job("jobkorea", "9", title="z")]
    fakes.images = {images[0]: b"big", images[1]: b"icon", images[2]: crawler.Disallowed("금지")}
    fakes.sizes = {b"icon": (120, 40)}  # 300px 미만은 건너뜀 (F12)
    fakes.details["9"] = Detail(LONG, [images[0]])

    result = run()

    assert fakes.ocr_read == [b"big", b"big"]
    content = (tmp_path / "postings" / "saramin_1.txt").read_text(encoding="utf-8")
    assert content == "짧은 본문\n\n--- 이미지 글자 ---\nOCR:big"
    # 본문+OCR이 200자 미만 → 본문 미확보. 1번은 금지 이미지가 있지만 길이 규칙이 먼저다.
    assert [job["body"] for job in result["saved"]] == ["본문 미확보", "글자+이미지"]
    assert fakes.rows[0][-1] == "본문 미확보"


def test_banned_image_marks_partly_unread(monkeypatch, tmp_path):
    fakes = Fakes(
        monkeypatch,
        tmp_path,
        {"saramin": [make_job("saramin", "1")], "jobkorea": []},
        details={"1": Detail(LONG, ["https://pds.test/a.png", "https://img.test/icon.png"])},
    )
    fakes.lists["jobkorea"] = []
    fakes.images = {"https://pds.test/a.png": crawler.Disallowed("금지"), "https://img.test/icon.png": b"icon"}
    fakes.sizes = {b"icon": (299, 800)}

    result = run(sources=["saramin"])

    assert result["saved"][0]["body"] == "이미지 일부 못 읽음"
    assert result.get("failed", []) == []  # 금지는 실패가 아님


def test_small_image_only_is_not_counted_as_unread(monkeypatch, tmp_path):
    fakes = Fakes(
        monkeypatch,
        tmp_path,
        {"saramin": [make_job("saramin", "1")]},
        details={"1": Detail(LONG, ["https://img.test/icon.png"])},
    )
    fakes.images = {"https://img.test/icon.png": b"icon"}
    fakes.sizes = {b"icon": (800, 100)}

    result = run(sources=["saramin"])

    assert result["saved"][0]["body"] == "글자"


def test_ocr_reads_at_most_ten_images(monkeypatch, tmp_path):
    urls = [f"https://img.test/{i}.png" for i in range(12)]
    fakes = Fakes(monkeypatch, tmp_path, {"saramin": [make_job("saramin", "1")]}, details={"1": Detail(LONG, urls)})
    fakes.images = {url: str(i).encode() for i, url in enumerate(urls)}

    run(sources=["saramin"])

    assert len(fakes.ocr_read) == 10
    assert "https://img.test/10.png" not in fakes.requested


def test_ocr_error_skips_only_that_image_and_keeps_row(monkeypatch, tmp_path):
    urls = ["https://img.test/a.png", "https://img.test/b.png"]
    fakes = Fakes(monkeypatch, tmp_path, {"saramin": [make_job("saramin", "1")]}, details={"1": Detail(LONG, urls)})
    fakes.images = {urls[0]: b"a", urls[1]: b"b"}
    fakes.ocr_fail = {b"a"}

    result = run(sources=["saramin"])

    assert fakes.ocr_read == [b"b"]
    assert ids(result["saved"]) == [("saramin", "1")]
    assert result["saved"][0]["body"] == "이미지 일부 못 읽음"
    assert [(f["step"], f["error"]) for f in result["failed"]] == [("OCR", "RuntimeError")]
    assert_counts_add_up(result)


def test_without_ocr_images_are_not_downloaded(monkeypatch, tmp_path):
    fakes = Fakes(
        monkeypatch,
        tmp_path,
        {"saramin": [make_job("saramin", "1")]},
        details={"1": Detail(LONG, ["https://img.test/a.png"])},
    )
    monkeypatch.setattr(graph.ocr, "read", lambda image: pytest.fail("OCR이 없으면 부르지 않음"))

    result = run(sources=["saramin"], ocr_ready=False)

    assert "https://img.test/a.png" not in fakes.requested
    assert result["saved"][0]["body"] == "이미지 일부 못 읽음"


def test_no_jobs_ends_without_reading_sheet(monkeypatch, tmp_path):
    fakes = Fakes(monkeypatch, tmp_path, {"saramin": [], "jobkorea": []})
    monkeypatch.setattr(graph.sheets, "existing_keys", lambda: pytest.fail("공고가 없으면 시트를 읽지 않아야 함"))

    result = run()

    assert result["fetched"] == {"saramin": 0, "jobkorea": 0}
    assert fakes.rows == []


def test_max_count_on_both_sites_does_not_hit_recursion_limit(monkeypatch, tmp_path):
    n = graph.MAX_COUNT
    Fakes(
        monkeypatch,
        tmp_path,
        {
            "saramin": [make_job("saramin", f"s{i}", title=f"s{i}") for i in range(n)],
            "jobkorea": [make_job("jobkorea", f"j{i}", title=f"j{i}") for i in range(n)],
        },
    )

    result = run(count=n)

    assert len(result["saved"]) == 2 * n


def test_recursion_limit_stops_a_run_longer_than_planned(monkeypatch, tmp_path):
    # 공고 수에 맞춘 한도가 브레이크 역할을 하는지 확인한다. 수집의 실제 단계 수는 3 × 공고 수 + 3.
    from langgraph.errors import GraphRecursionError

    Fakes(monkeypatch, tmp_path, {"saramin": [make_job("saramin", str(i), title=str(i)) for i in range(5)]})
    state = {"keyword": "백엔드", "sources": ["saramin"], "count": 5}

    with pytest.raises(GraphRecursionError):
        graph.build_graph().invoke(state, {"recursion_limit": 3 * 5 + 2})


def test_posting_status_constants_match_sheet_values():
    assert {postings.TEXT, postings.TEXT_AND_IMAGE, postings.PARTLY_UNREAD, postings.MISSING} == {
        "글자",
        "글자+이미지",
        "이미지 일부 못 읽음",
        "본문 미확보",
    }

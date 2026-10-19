from agent import saramin

SAMPLE_JOB = {
    "id": "123",
    "url": "https://www.saramin.co.kr/job/123",
    "keyword": "Python, Django",
    "expiration-timestamp": "1793000000",
    "company": {"detail": {"name": "테스트회사"}},
    "position": {
        "title": "백엔드 개발자",
        "experience-level": {"name": "신입"},
        "required-education-level": {"name": "대학교졸업(4년)"},
    },
}


def test_to_row_extracts_fields():
    row = saramin._to_row(SAMPLE_JOB)

    assert row["company"] == "테스트회사"
    assert row["title"] == "백엔드 개발자"
    assert row["experience"] == "신입"
    assert row["education"] == "대학교졸업(4년)"
    assert row["keywords"] == "Python, Django"
    assert row["url"] == "https://www.saramin.co.kr/job/123"
    assert len(row["deadline"]) == len("2026-10-26")


def test_to_row_without_deadline_is_always_open():
    job = {**SAMPLE_JOB, "expiration-timestamp": None}

    assert saramin._to_row(job)["deadline"] == "상시"


def test_fetch_jobs_sends_keyword_and_parses(monkeypatch):
    sent = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"jobs": {"job": [SAMPLE_JOB]}}

    def fake_get(url, params, headers, timeout):
        sent.update(params)
        return FakeResponse()

    monkeypatch.setenv("SARAMIN_API_KEY", "test-key")
    monkeypatch.setattr(saramin.requests, "get", fake_get)

    rows = saramin.fetch_jobs("백엔드", location="101000", count=1)

    assert sent["keywords"] == "백엔드"
    assert sent["loc_mcd"] == "101000"
    assert sent["access-key"] == "test-key"
    assert rows[0]["company"] == "테스트회사"

import pytest
import requests

from agent import saramin

SAMPLE_JOB = {
    "id": "123",
    "url": "https://www.saramin.co.kr/job/123",
    "keyword": "Python, Django",
    "expiration-timestamp": "1793000000",
    "company": {"detail": {"name": "테스트회사"}},
    "position": {
        "title": "백엔드 개발자",
        "experience-level": {"code": "1", "name": "신입"},
        "required-education-level": {"name": "대학교졸업(4년)"},
    },
}


def test_to_row_extracts_fields():
    row = saramin._to_row(SAMPLE_JOB)

    assert row["id"] == "123"
    assert row["company"] == "테스트회사"
    assert row["title"] == "백엔드 개발자"
    assert row["experience"] == "신입"
    assert row["experience_code"] == 1
    assert row["education"] == "대학교졸업(4년)"
    assert row["keywords"] == "Python, Django"
    assert row["url"] == "https://www.saramin.co.kr/job/123"
    assert len(row["deadline"]) == len("2026-10-26")


def test_to_row_without_deadline_is_always_open():
    job = {**SAMPLE_JOB, "expiration-timestamp": None}

    assert saramin._to_row(job)["deadline"] == "상시"


def test_to_row_without_experience_code():
    job = {**SAMPLE_JOB, "position": {"title": "개발자"}}

    assert saramin._to_row(job)["experience_code"] is None


def test_fetch_jobs_sends_keyword_and_parses(monkeypatch):
    sent = {}

    class FakeResponse:
        ok = True

        def json(self):
            return {"jobs": {"job": [SAMPLE_JOB]}}

    def fake_get(url, params, headers, timeout):
        sent.update(params)
        return FakeResponse()

    monkeypatch.setenv("SARAMIN_API_KEY", "test-key")
    monkeypatch.setattr(saramin.requests, "get", fake_get)

    rows = saramin.fetch_jobs("백엔드", region_code="101000", job_code="84", count=110)

    assert sent["keywords"] == "백엔드"
    assert sent["loc_mcd"] == "101000"
    assert sent["job_cd"] == "84"
    assert sent["count"] == 110
    assert sent["access-key"] == "test-key"
    assert rows[0]["company"] == "테스트회사"


def _error_response(status: int, url: str) -> requests.Response:
    resp = requests.Response()
    resp.status_code = status
    resp.reason = "Server Error"
    resp.url = url
    return resp


def test_http_error_does_not_leak_api_key(monkeypatch):
    monkeypatch.setenv("SARAMIN_API_KEY", "secret-key-123")

    def fake_get(url, params, headers, timeout):
        return _error_response(500, f"{url}?access-key={params['access-key']}&keywords=x")

    monkeypatch.setattr(saramin.requests, "get", fake_get)

    with pytest.raises(saramin.SaraminAPIError) as exc_info:
        saramin.fetch_jobs("백엔드")

    error = exc_info.value
    assert "500" in str(error)
    assert "secret-key-123" not in str(error)
    assert error.__context__ is None


def test_network_error_does_not_leak_api_key(monkeypatch):
    monkeypatch.setenv("SARAMIN_API_KEY", "secret-key-123")

    def fake_get(url, params, headers, timeout):
        raise requests.ConnectionError(f"Max retries exceeded with url: /job-search?access-key={params['access-key']}")

    monkeypatch.setattr(saramin.requests, "get", fake_get)

    with pytest.raises(saramin.SaraminAPIError) as exc_info:
        saramin.fetch_jobs("백엔드")

    assert "secret-key-123" not in str(exc_info.value)
    assert exc_info.value.__suppress_context__


def _json_response(data: dict):
    class FakeResponse:
        ok = True

        def json(self):
            return data

    return FakeResponse()


def test_optional_filters_are_not_sent(monkeypatch):
    sent = {}
    monkeypatch.setenv("SARAMIN_API_KEY", "test-key")
    monkeypatch.setattr(
        saramin.requests,
        "get",
        lambda url, params, headers, timeout: sent.update(params) or _json_response({"jobs": {}}),
    )

    assert saramin.fetch_jobs("백엔드") == []
    assert "loc_mcd" not in sent
    assert "job_cd" not in sent


def test_api_error_code_raises(monkeypatch):
    # 하루 호출 한도 초과(코드 4)처럼 jobs 대신 오류 코드가 오는 경우
    monkeypatch.setenv("SARAMIN_API_KEY", "secret-key-123")
    monkeypatch.setattr(
        saramin.requests, "get", lambda url, params, headers, timeout: _json_response({"code": 4, "message": "limit"})
    )

    with pytest.raises(saramin.SaraminAPIError) as exc_info:
        saramin.fetch_jobs("백엔드")

    assert "코드 4" in str(exc_info.value)
    assert "secret-key-123" not in str(exc_info.value)

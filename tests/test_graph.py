import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from agent import graph


def make_job(job_id: str, experience_code: int = 1) -> dict:
    return {
        "id": job_id,
        "company": f"회사{job_id}",
        "title": "백엔드 개발자",
        "experience": "신입",
        "experience_code": experience_code,
        "education": "대졸",
        "keywords": "Python",
        "deadline": "2026-11-01",
        "url": f"https://www.saramin.co.kr/job/{job_id}",
    }


class Fakes:
    def __init__(self, monkeypatch, jobs, existing=(), summaries=None, fail_save_ids=()):
        self.requested = {}
        self.rows = []
        self.fail_save_ids = set(fail_save_ids)
        summaries = summaries or ["신입, 대졸, Python"] * len(jobs)

        def fake_fetch(keyword, region_code, job_code, count):
            self.requested.update(keyword=keyword, region_code=region_code, job_code=job_code, count=count)
            return jobs

        def fake_append(row):
            if row[5] in self.fail_save_ids:
                raise ConnectionError("시트 연결 끊김")
            self.rows.append(row)

        self.llm = FakeListChatModel(responses=summaries)
        monkeypatch.setattr(graph.saramin, "fetch_jobs", fake_fetch)
        monkeypatch.setattr(graph.sheets, "existing_ids", lambda: set(existing))
        monkeypatch.setattr(graph.sheets, "append_row", fake_append)
        monkeypatch.setattr(graph, "init_chat_model", lambda *a, **k: self.llm)


def run(count=10, career=None):
    state = {"keyword": "백엔드", "region_code": "101000", "job_code": "84", "career": career, "count": count}
    return graph.build_graph().invoke(state, {"recursion_limit": graph.recursion_limit(count)})


def assert_counts_add_up(result):
    total = len(result.get("saved", [])) + len(result.get("skipped", [])) + len(result.get("failed", []))
    assert result["fetched"] == total


def test_saves_new_jobs_and_skips_saved_ones(monkeypatch):
    fakes = Fakes(monkeypatch, [make_job("1"), make_job("2"), make_job("3")], existing={"2"})

    result = run()

    assert [job["id"] for job in result["saved"]] == ["1", "3"]
    assert [job["id"] for job in result["skipped"]] == ["2"]
    assert result.get("failed", []) == []
    assert fakes.requested == {"keyword": "백엔드", "region_code": "101000", "job_code": "84", "count": 10}
    row = fakes.rows[0]
    assert row[:6] == [
        "회사1",
        "백엔드 개발자",
        "신입, 대졸, Python",
        "2026-11-01",
        "https://www.saramin.co.kr/job/1",
        "1",
    ]
    assert len(row[6]) == len("2026-10-20 09:00")
    assert_counts_add_up(result)


def test_skipped_jobs_are_not_summarized(monkeypatch):
    fakes = Fakes(monkeypatch, [make_job("1"), make_job("2")], existing={"1"})
    summarized = []

    def counting_init(*args, **kwargs):
        summarized.append(1)
        return fakes.llm

    monkeypatch.setattr(graph, "init_chat_model", counting_init)

    result = run()

    assert len(summarized) == 1  # 이미 저장된 공고는 AI를 부르지 않음 (N2)
    assert len(result["skipped"]) == 1


def test_summary_and_save_failures_do_not_stop_others(monkeypatch):
    fakes = Fakes(monkeypatch, [make_job("1"), make_job("2"), make_job("3")], fail_save_ids={"3"})
    calls = {"n": 0}

    def flaky_init(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("api-key=secret 요청 시간 초과")
        return fakes.llm

    monkeypatch.setattr(graph, "init_chat_model", flaky_init)

    result = run()

    assert [job["id"] for job in result["saved"]] == ["2"]
    assert result["failed"] == [
        {"company": "회사1", "title": "백엔드 개발자", "step": "요약", "error": "TimeoutError"},
        {"company": "회사3", "title": "백엔드 개발자", "step": "저장", "error": "ConnectionError"},
    ]
    assert "secret" not in str(result["failed"])
    assert_counts_add_up(result)


def test_career_filter_requests_max_and_keeps_count(monkeypatch):
    jobs = [make_job("1", 2), make_job("2", 1), make_job("3", 3), make_job("4", 0), make_job("5", 1)]
    fakes = Fakes(monkeypatch, jobs)

    result = run(count=2, career="신입")

    assert fakes.requested["count"] == graph.MAX_COUNT
    assert result["fetched"] == 2
    assert [job["id"] for job in result["saved"]] == ["2", "3"]


def test_fewer_jobs_than_count_after_filter(monkeypatch):
    Fakes(monkeypatch, [make_job("1", 2), make_job("2", 1)])

    result = run(count=5, career="신입")

    assert result["fetched"] == 1
    assert_counts_add_up(result)


def test_no_jobs_ends_normally_with_zero_counts(monkeypatch):
    fakes = Fakes(monkeypatch, [])
    monkeypatch.setattr(graph.sheets, "existing_ids", lambda: pytest.fail("공고가 없으면 시트를 읽지 않아야 함"))

    result = run()

    assert result["fetched"] == 0
    assert fakes.rows == []


def test_max_count_does_not_hit_recursion_limit(monkeypatch):
    jobs = [make_job(str(i)) for i in range(graph.MAX_COUNT)]
    Fakes(monkeypatch, jobs)

    result = run(count=graph.MAX_COUNT)

    assert len(result["saved"]) == graph.MAX_COUNT


def test_recursion_limit_stops_a_run_longer_than_planned(monkeypatch):
    # 공고 수에 맞춘 한도가 브레이크 역할을 하는지 확인한다. 실제 단계 수는 3 × 공고 수 + 3.
    from langgraph.errors import GraphRecursionError

    Fakes(monkeypatch, [make_job(str(i)) for i in range(5)])
    state = {"keyword": "백엔드", "count": 5}

    with pytest.raises(GraphRecursionError):
        graph.build_graph().invoke(state, {"recursion_limit": 3 * 5 + 2})

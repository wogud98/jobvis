import pytest

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
    def __init__(self, monkeypatch, jobs, existing=(), fail_save_ids=()):
        self.requested = {}
        self.rows = []
        self.fail_save_ids = set(fail_save_ids)

        def fake_fetch(keyword, region_code, job_code, count):
            self.requested.update(keyword=keyword, region_code=region_code, job_code=job_code, count=count)
            return jobs

        def fake_append(row):
            if row[5] in self.fail_save_ids:
                raise ConnectionError("시트 연결 끊김")
            self.rows.append(row)

        monkeypatch.setattr(graph.saramin, "fetch_jobs", fake_fetch)
        monkeypatch.setattr(graph.sheets, "existing_ids", lambda: set(existing))
        monkeypatch.setattr(graph.sheets, "append_row", fake_append)
        # 수집은 LLM을 부르지 않는다 (F2)
        monkeypatch.setattr(graph, "init_chat_model", lambda *a, **k: pytest.fail("수집에서 LLM을 부르면 안 됨"))


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
    assert row[:6] == ["회사1", "백엔드 개발자", "", "2026-11-01", "https://www.saramin.co.kr/job/1", "1"]
    assert len(row[6]) == len("2026-10-20 09:00")
    assert row[7:] == ["신입", "대졸", "Python", False]  # 평가용 정보, 평가 체크 해제 (F3)
    assert len(row) == graph.sheets.HEADER.index("평가") + 1
    assert_counts_add_up(result)


def test_save_failure_does_not_stop_others(monkeypatch):
    fakes = Fakes(monkeypatch, [make_job("1"), make_job("2"), make_job("3")], fail_save_ids={"2"})

    result = run()

    assert [job["id"] for job in result["saved"]] == ["1", "3"]
    assert result["failed"] == [
        {"company": "회사2", "title": "백엔드 개발자", "step": "저장", "error": "ConnectionError"},
    ]
    assert [row[5] for row in fakes.rows] == ["1", "3"]
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
    # 공고 수에 맞춘 한도가 브레이크 역할을 하는지 확인한다. 수집의 실제 단계 수는 2 × 공고 수 + 3.
    from langgraph.errors import GraphRecursionError

    Fakes(monkeypatch, [make_job(str(i)) for i in range(5)])
    state = {"keyword": "백엔드", "count": 5}

    with pytest.raises(GraphRecursionError):
        graph.build_graph().invoke(state, {"recursion_limit": 2 * 5 + 2})

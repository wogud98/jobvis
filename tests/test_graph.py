import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from agent import graph

JOB = {
    "company": "테스트회사",
    "title": "백엔드 개발자",
    "experience": "신입",
    "education": "대졸",
    "keywords": "Python",
    "deadline": "2026-11-01",
    "url": "https://www.saramin.co.kr/job/123",
}


@pytest.fixture
def fakes(monkeypatch):
    saved = []
    monkeypatch.setattr(graph.saramin, "fetch_jobs", lambda keyword, location, count: [JOB])
    monkeypatch.setattr(graph, "init_chat_model", lambda *a, **k: FakeListChatModel(responses=["신입, 대졸, Python"]))
    monkeypatch.setattr(graph.sheets, "append_row", saved.append)
    return saved


def test_graph_runs_fetch_summarize_save(fakes):
    result = graph.build_graph().invoke({"keyword": "백엔드"})

    assert result["job"] == JOB
    assert result["requirements"] == "신입, 대졸, Python"
    assert fakes == [["테스트회사", "백엔드 개발자", "신입, 대졸, Python", "2026-11-01", JOB["url"]]]


def test_graph_stops_when_no_jobs(monkeypatch):
    monkeypatch.setattr(graph.saramin, "fetch_jobs", lambda keyword, location, count: [])

    with pytest.raises(SystemExit):
        graph.build_graph().invoke({"keyword": "없는직무"})

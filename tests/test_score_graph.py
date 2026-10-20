import json

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from agent import graph


def make_row(number: int) -> dict:
    return {
        "row": number,
        "company": f"회사{number}",
        "title": "백엔드 개발자",
        "experience": "신입",
        "education": "대졸",
        "keywords": "Java, Spring",
    }


def answer(**changes) -> str:
    data = {
        "summary": "신입, 대졸, Java 필수",
        "skills": 72,
        "experience": 60,
        "culture": None,
        "career": 80,
        "strengths": ["Java 프로젝트", "백엔드 희망"],
        "gaps": ["Spring Boot", "AWS"],
    }
    return json.dumps(data | changes, ensure_ascii=False)


class Fakes:
    def __init__(self, monkeypatch, answers, fail_write_rows=()):
        self.written = []
        self.prompts = []
        self.fail_write_rows = set(fail_write_rows)
        self.llm = FakeListChatModel(responses=answers)

        def fake_write(row_number, summary, values):
            if row_number in self.fail_write_rows:
                raise ConnectionError("token=secret 시트 연결 끊김")
            self.written.append((row_number, summary, values))

        def fake_init(*args, **kwargs):
            return self.llm

        monkeypatch.setattr(graph.sheets, "write_result", fake_write)
        monkeypatch.setattr(graph, "init_chat_model", fake_init)


def run(rows, skipped=()):
    state = {"profile": "Python, Java 가능. 백엔드 희망", "queue": rows, "skipped": list(skipped)}
    return graph.build_score_graph().invoke(state, {"recursion_limit": graph.recursion_limit(len(rows))})


def assert_counts_add_up(result, total):
    assert len(result.get("done", [])) + len(result.get("skipped", [])) + len(result.get("failed", [])) == total


def test_scores_and_writes_each_row(monkeypatch):
    fakes = Fakes(monkeypatch, [answer(), answer(culture=90, career=100)])

    result = run([make_row(2), make_row(5)])

    assert [r["row"] for r in result["done"]] == [2, 5]
    row_number, summary, values = fakes.written[0]
    assert (row_number, summary) == (2, "신입, 대졸, Java 필수")
    assert values[:8] == [False, 71, "★★★★☆", "추천", 72, 60, "-", 80]
    assert values[8:10] == ["Java 프로젝트, 백엔드 희망", "Spring Boot, AWS"]
    assert len(values[10]) == len("2026-10-20 09:00")
    assert len(values) == len(graph.sheets.HEADER) - graph.sheets.HEADER.index("평가")
    # (30×72 + 25×60 + 15×90 + 30×100) / 100 = 80.1 → 80
    assert fakes.written[1][2][1:4] == [80, "★★★★☆", "강력 추천"]


def test_prompt_contains_profile_rubric_and_posting(monkeypatch):
    fakes = Fakes(monkeypatch, [answer()])
    seen = []
    original = fakes.llm.invoke

    def spy(messages, *args, **kwargs):
        seen.append(messages)
        return original(messages, *args, **kwargs)

    monkeypatch.setattr(type(fakes.llm), "invoke", lambda self, m, *a, **k: spy(m, *a, **k))

    run([make_row(2)])

    text = "\n".join(message.content for message in seen[0].to_messages())
    assert "Python, Java 가능. 백엔드 희망" in text
    assert "회사2" in text and "Java, Spring" in text
    assert "culture는 null" in text
    assert '"summary"' in text


def test_bad_answer_llm_error_and_write_failure_do_not_stop_others(monkeypatch):
    fakes = Fakes(monkeypatch, [answer(skills=150), answer(), answer()], fail_write_rows={4})
    calls = {"n": 0}

    def flaky_init(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise TimeoutError("api-key=secret 요청 시간 초과")
        return fakes.llm

    monkeypatch.setattr(graph, "init_chat_model", flaky_init)

    result = run([make_row(2), make_row(3), make_row(4), make_row(5)])

    assert [r["row"] for r in result["done"]] == [5]
    failed = [(f["company"], f["step"]) for f in result["failed"]]
    assert failed == [("회사2", "채점"), ("회사3", "채점"), ("회사4", "저장")]
    assert result["failed"][1]["error"] == "TimeoutError"
    assert "secret" not in str(result["failed"])
    # 형식이 틀리면 시트를 바꾸지 않는다 (F15)
    assert [written[0] for written in fakes.written] == [5]
    assert_counts_add_up(result, 4)


def test_non_json_answer_is_a_scoring_failure(monkeypatch):
    fakes = Fakes(monkeypatch, ["적합도는 70점 정도입니다."])

    result = run([make_row(2)])

    assert result["failed"][0]["step"] == "채점"
    assert fakes.written == []


def test_skipped_rows_are_reported_and_not_scored(monkeypatch):
    Fakes(monkeypatch, [])
    monkeypatch.setattr(graph, "init_chat_model", lambda *a, **k: pytest.fail("대상이 없으면 LLM을 부르지 않음"))

    result = run([], skipped=[make_row(9)])

    assert [r["row"] for r in result["skipped"]] == [9]
    assert_counts_add_up(result, 1)


def test_many_rows_do_not_hit_recursion_limit(monkeypatch):
    rows = [make_row(i) for i in range(2, 112)]
    Fakes(monkeypatch, [answer()] * len(rows))

    result = run(rows)

    assert len(result["done"]) == len(rows)

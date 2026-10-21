"""화면 실행 모듈. 가짜 그래프·시트로 돌린다. 실제 사이트·LLM·시트 없음 (v0.5.2 N5)."""

import threading

import pytest
import requests
from langchain_core.exceptions import ModelNotFoundError

from agent import codes, inbox, ocr, reports, runner, scoring, sheets, user_profile


@pytest.fixture(autouse=True)
def no_job(monkeypatch):
    monkeypatch.setattr(runner, "_job", None)


class FakeGraph:
    """graph.stream 흉내. 노드 갱신을 차례로 내보내고 마지막 State를 values로 준다."""

    def __init__(self, updates, final):
        self.updates, self.final, self.calls = updates, final, []

    def stream(self, state, config, stream_mode):
        self.calls.append((state, config, stream_mode))
        for update in self.updates:
            yield "updates", update
        yield "values", self.final


# ---- 입력 검사 ----


def test_collect_state_from_screen_inputs():
    state = runner.collect_state(" 백엔드 ", "서울", None, "신입", ["saramin"], 5)

    assert state == {
        "keyword": "백엔드",
        "sources": ["saramin"],
        "location": "서울",
        "region_code": codes.to_region_code("서울"),
        "job_code": None,
        "career": "신입",
        "count": 5,
    }


def test_collect_state_all_career_and_default_sources():
    state = runner.collect_state("백엔드", career=runner.CAREER_ALL)

    assert state["career"] is None and state["sources"] == list(runner.SOURCES)
    assert state["location"] is None and state["region_code"] is None


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("",), "키워드를 입력해 주세요"),
        (("   ",), "키워드를 입력해 주세요"),
        (("백엔드", None, None, None, None, 0), "개수는 1~"),
        (("백엔드", None, None, None, None, runner.MAX_COUNT + 1), "개수는 1~"),
        (("백엔드", None, None, None, ["unknown"]), "사이트를 하나 이상"),
    ],
)
def test_collect_state_rejects_bad_input(args, message):
    with pytest.raises(runner.RunError, match=message):
        runner.collect_state(*args)


def test_collect_state_unknown_region_stops_before_request():
    with pytest.raises(codes.CodeNotFoundError):
        runner.collect_state("백엔드", location="없는지역")


def test_keyword_options_put_profile_first_without_duplicates():
    raw = {"skills": {"main": ["Python", "백엔드 개발"]}, "direction": {"jobs": ["백엔드 개발"]}}

    options = runner.keyword_options(raw)

    assert options[:2] == ["백엔드 개발", "Python"]
    assert len(options) == len(set(options)) and set(runner.JOB_NAMES) <= set(options)


def test_keyword_options_without_profile_are_job_names():
    assert runner.keyword_options(None) == runner.JOB_NAMES


# ---- 실행 잠금 ----


def test_start_runs_work_and_keeps_result():
    job = runner.start("collect", lambda job: reports.Summary("끝"), wait=True)

    assert job.finished and job.result.headline == "끝" and not job.error
    assert runner.current() is job and not runner.running()


def test_second_start_while_running_is_refused():
    release = threading.Event()
    first = runner.start("collect", lambda job: reports.Summary(release.wait(5) and "끝"))
    try:
        assert runner.running()
        for kind in runner.KINDS:  # 세 버튼 모두 (F12)
            with pytest.raises(runner.RunError, match="수집을 실행하는 중"):
                runner.start(kind, lambda job: reports.Summary(""))
    finally:
        release.set()
    for _ in range(100):
        if first.finished:
            break
        threading.Event().wait(0.05)
    assert first.finished and first.result.headline == "끝"
    assert (
        runner.start("score", lambda job: reports.Summary("다음"), wait=True).result.headline == "다음"
    )  # 끝나면 다시 실행 가능


def test_error_in_work_becomes_message_without_details():
    def work(job):
        raise KeyError("/home/me/service_account.json")

    job = runner.start("collect", work, wait=True)

    assert job.finished and "인증 정보를 찾지 못했습니다" in job.error
    assert "service_account" not in job.error  # F13
    assert not runner.running()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (runner.RunError("키워드를 입력해 주세요."), "키워드를 입력해 주세요."),
        (requests.ConnectionError("host"), "네트워크 오류입니다"),
        (RuntimeError("API key AIza-secret invalid"), "실행하지 못했습니다 (RuntimeError)"),
        (type("GoogleModelNotFoundError", (ModelNotFoundError,), {})("404 AIza-secret"), "LLM_MODEL"),  # F26
        (type("AnthropicRateLimitError", (Exception,), {})("AIza"), "사용 한도"),
    ],
)
def test_error_text(error, expected):
    text = runner.error_text(error)

    assert expected in text and "AIza" not in text


# ---- 수집 ----


def test_collect_streams_graph_and_reports_progress(monkeypatch):
    graph = FakeGraph(
        [
            {"fetch": {"fetched": {"saramin": 3}}},
            {"dedupe": {"queue": [{}, {}]}},
            {"pick": {"current": {"source": "saramin"}}},
            {"save": None},
            {"pick": {"current": {"source": "saramin"}}},
            {"pick": {"current": None}},
        ],
        {"fetched": {"saramin": 3}, "saved": [{"source": "saramin", "body": "글자"}], "skipped": [], "failed": []},
    )
    monkeypatch.setattr(runner, "build_graph", lambda: graph)
    monkeypatch.setattr(ocr, "available", lambda: True)
    state = runner.collect_state("백엔드", sources=["saramin"], count=3)

    job = runner.start_collect(state, wait=True)

    assert not job.error
    assert (job.done, job.total) == (2, 2)  # F5
    assert job.result.headline == "새 공고 1건을 저장했습니다."  # F24
    assert job.result.details == ["사람인 가져옴 3 / 새로 저장 1 / 건너뜀 0 / 실패 0"]  # 터미널과 같은 글은 자세히에
    sent, config, modes = graph.calls[0]
    assert sent["ocr_ready"] is True and config["recursion_limit"] == runner.recursion_limit(3)
    assert modes == ["updates", "values"]


def test_collect_without_ocr_says_so(monkeypatch):
    monkeypatch.setattr(runner, "build_graph", lambda: FakeGraph([], {"fetched": {}}))
    monkeypatch.setattr(ocr, "available", lambda: False)

    job = runner.start_collect(runner.collect_state("백엔드"), wait=True)

    first = job.result.details[0]
    assert first.startswith("이미지 OCR 없음") and ocr.INSTALL_HINT in first
    assert not job.result.todo and not job.result.problems  # 참고라 자세히에만


def test_collect_progress_grows_total_for_late_duplicates():
    job = runner.Job("collect")
    on_update = runner._collect_progress(job)
    on_update("dedupe", {"queue": [{}]})
    on_update("pick", {"current": {"source": "jobkorea"}})
    on_update("pick", {"current": {"source": "saramin"}})

    assert (job.done, job.total) == (2, 2) and "사람인" in job.stage


# ---- 평가 ----


def rows():
    return [
        {"check": "TRUE", "experience": "신입", "company": "가"},
        {"check": "TRUE", "company": "정보 없음"},
        {"score": "", "experience": "경력 3년", "company": "나"},
        {"score": "", "verdict": scoring.EXCLUDED, "experience": "경력", "company": "다"},
    ]


def test_score_targets_match_terminal_selection():
    assert runner.score_targets(rows(), "checked") == 1
    assert runner.score_targets(rows(), "all") == 2  # 정보 없는 줄·제외 줄 빼고
    assert runner.score_targets([], "all") == 0


def profile():
    return user_profile.Profile.model_validate(
        {"skills": {"main": ["Python"]}, "experience": {"years": 1}, "direction": {"jobs": ["백엔드"]}}
    )


def test_score_runs_graph_on_targets(monkeypatch):
    graph = FakeGraph(
        [{"score_pick": {"current": {"company": "가"}}}, {"score_pick": {"current": None}}],
        {"done": [{}], "skipped": [{}], "failed": [], "excluded": []},
    )
    monkeypatch.setattr(sheets, "read_rows", rows)
    monkeypatch.setattr(runner, "build_score_graph", lambda: graph)

    job = runner.start_score("checked", profile(), wait=True)

    assert not job.error
    assert (job.done, job.total) == (1, 1)  # F9
    assert job.result.headline == "공고 1건을 평가했습니다."
    assert job.result.details[0] == "평가 대상 2 / 완료 1 / 제외 0 / 건너뜀 1 / 실패 0"
    state = graph.calls[0][0]
    assert [row["company"] for row in state["queue"]] == ["가"] and state["years"] == 1


def test_score_sheet_error_is_shown_as_message(monkeypatch):
    def broken():
        raise FileNotFoundError("C:/secret/service_account.json")

    monkeypatch.setattr(sheets, "read_rows", broken)

    job = runner.start_score("all", profile(), wait=True)

    assert "인증 정보를 찾지 못했습니다" in job.error and "secret" not in job.error


def test_load_profile_missing_file(tmp_path):
    with pytest.raises(user_profile.ProfileError):
        runner.load_profile(str(tmp_path / "profile.yaml"))


# ---- 받은함 ----


def test_inbox_count_ignores_wrong_names(monkeypatch, tmp_path):
    monkeypatch.setattr(inbox, "DIR", tmp_path)
    (tmp_path / "saramin_123.png").write_bytes(b"x")
    (tmp_path / "saramin_123_2.png").write_bytes(b"x")
    (tmp_path / "memo.txt").write_bytes(b"x")

    assert runner.inbox_count() == 2


def test_inbox_count_without_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(inbox, "DIR", tmp_path / "없음")

    assert runner.inbox_count() == 0


def test_read_inbox_without_ocr_touches_nothing(monkeypatch):
    monkeypatch.setattr(ocr, "available", lambda: False)
    monkeypatch.setattr(sheets, "read_rows", lambda: pytest.fail("OCR 없으면 시트도 읽지 않음"))

    with pytest.raises(runner.RunError, match="OCR이 설치돼 있지 않습니다"):
        runner.read_inbox()
    job = runner.start_inbox(wait=True)
    assert "OCR이 설치돼 있지 않습니다" in job.error  # F11


def test_start_inbox_reports_result(monkeypatch):
    monkeypatch.setattr(ocr, "available", lambda: True)
    monkeypatch.setattr(runner, "inbox_count", lambda: 1)
    monkeypatch.setattr(sheets, "read_rows", list)
    monkeypatch.setattr(
        inbox, "run", lambda rows: inbox.InboxResult(read=1, skipped=[{"file": "a.png", "reason": "시트에 없는 공고"}])
    )

    job = runner.start_inbox(wait=True)

    assert job.total == 1
    assert job.result.headline == "이미지 1장을 읽어 공고 0건의 본문을 채웠습니다."
    assert job.result.problems == ["이미지 1장을 건너뛰었습니다. 자세히를 확인해 주세요."]
    assert job.result.details == [
        "읽은 이미지 1장 / 본문을 채운 공고 0건 / 건너뜀 1",
        "  건너뜀: a.png (시트에 없는 공고)",
    ]

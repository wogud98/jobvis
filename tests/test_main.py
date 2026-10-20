import pytest

import main
from agent.saramin import SaraminAPIError


def test_names_become_codes():
    args = main.parse_args(["--keyword", "백엔드", "--location", "서울", "--job", "백엔드", "--career", "신입"])

    assert main.to_state(args) == {
        "keyword": "백엔드",
        "region_code": "101000",
        "job_code": "84",
        "career": "신입",
        "count": 10,
    }


@pytest.mark.parametrize("count", ["0", "111"])
def test_count_out_of_range_is_rejected(count):
    with pytest.raises(SystemExit):
        main.parse_args(["--keyword", "백엔드", "--count", count])


def test_unknown_career_is_rejected():
    with pytest.raises(SystemExit):
        main.parse_args(["--keyword", "백엔드", "--career", "무관"])


def test_unknown_name_stops_before_api_call(monkeypatch):
    monkeypatch.setattr(main, "build_graph", lambda: pytest.fail("모르는 이름이면 그래프를 실행하지 않아야 함"))

    with pytest.raises(SystemExit) as exc_info:
        main.main(["--keyword", "백엔드", "--location", "서울특별시"])

    assert "서울특별시" in str(exc_info.value)


def test_saramin_error_is_printed_without_traceback(monkeypatch):
    class FailingGraph:
        def invoke(self, state, config):
            raise SaraminAPIError("사람인 API 오류 (코드 4)")

    monkeypatch.setattr(main, "build_graph", FailingGraph)

    with pytest.raises(SystemExit) as exc_info:
        main.main(["--keyword", "백엔드"])

    assert str(exc_info.value) == "사람인 API 오류 (코드 4)"


def test_report_prints_counts_and_failures(capsys):
    main.print_report(
        {
            "fetched": 4,
            "saved": [{}, {}],
            "skipped": [{}],
            "failed": [{"company": "회사3", "title": "백엔드", "step": "요약", "error": "TimeoutError"}],
        }
    )

    out = capsys.readouterr().out
    assert "가져옴 4 / 새로 저장 2 / 건너뜀 1 / 실패 1" in out
    assert "실패(요약): 회사3 | 백엔드 (TimeoutError)" in out


def test_report_with_no_jobs(capsys):
    main.print_report({"fetched": 0})

    assert "가져옴 0 / 새로 저장 0 / 건너뜀 0 / 실패 0" in capsys.readouterr().out


# ---- v0.3: 평가, 스킬 갭 ----


def test_score_option_values():
    assert main.parse_args(["--score"]).score == "checked"
    assert main.parse_args(["--score", "all"]).score == "all"
    assert main.parse_args(["--keyword", "백엔드", "--score", "all"]).score == "all"
    assert main.parse_args(["--gaps"]).gaps is True
    assert main.parse_args(["--score"]).profile == "profile.md"


@pytest.mark.parametrize(
    "argv",
    [
        [],  # 아무 작업도 없음
        ["--gaps", "--keyword", "백엔드"],
        ["--gaps", "--score"],
        ["--keyword", "백엔드", "--score"],  # 방금 수집한 줄은 체크돼 있지 않음
        ["--score", "some"],
    ],
)
def test_invalid_option_combinations(argv):
    with pytest.raises(SystemExit):
        main.parse_args(argv)


def test_missing_profile_stops_before_collecting(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "build_graph", lambda: pytest.fail("프로필이 없으면 수집도 하지 않아야 함"))
    monkeypatch.setattr(main.sheets, "read_rows", lambda: pytest.fail("프로필이 없으면 시트를 읽지 않아야 함"))
    missing = tmp_path / "profile.md"

    with pytest.raises(SystemExit) as exc_info:
        main.main(["--keyword", "백엔드", "--score", "all", "--profile", str(missing)])

    assert "profile.example.md" in str(exc_info.value)


class Recorder:
    def __init__(self, result):
        self.calls = []
        self.result = result

    def __call__(self):
        return self

    def invoke(self, state, config):
        self.calls.append((state, config))
        return self.result


def test_collect_then_score_all(monkeypatch, tmp_path, capsys):
    profile = tmp_path / "profile.md"
    profile.write_text("Python", encoding="utf-8")
    rows = [
        {"row": 2, "check": "FALSE", "score": "", "experience": "신입", "education": "", "keywords": ""},
        {"row": 3, "check": "FALSE", "score": "70", "experience": "신입", "education": "", "keywords": ""},
        {"row": 4, "check": "FALSE", "score": "", "experience": "", "education": "", "keywords": ""},
    ]
    collect = Recorder({"fetched": 1, "saved": [{}]})
    score = Recorder({"done": [rows[0]], "skipped": [rows[2]]})
    monkeypatch.setattr(main, "build_graph", collect)
    monkeypatch.setattr(main, "build_score_graph", score)
    monkeypatch.setattr(main.sheets, "read_rows", lambda: rows)

    main.main(["--keyword", "백엔드", "--score", "all", "--profile", str(profile)])

    assert len(collect.calls) == 1
    state, config = score.calls[0]
    assert state == {"profile": "Python", "queue": [rows[0]], "skipped": [rows[2]]}
    assert config == {"recursion_limit": main.recursion_limit(1)}
    out = capsys.readouterr().out
    assert "가져옴 1 / 새로 저장 1" in out
    assert "평가 대상 2 / 완료 1 / 건너뜀 1 / 실패 0" in out


def test_score_only_does_not_collect(monkeypatch, tmp_path):
    profile = tmp_path / "profile.md"
    profile.write_text("Python", encoding="utf-8")
    rows = [{"row": 2, "check": "TRUE", "score": "", "experience": "신입", "education": "", "keywords": ""}]
    score = Recorder({"done": rows})
    monkeypatch.setattr(main, "build_graph", lambda: pytest.fail("--score만 쓰면 수집하지 않음"))
    monkeypatch.setattr(main, "build_score_graph", score)
    monkeypatch.setattr(main.sheets, "read_rows", lambda: rows)

    main.main(["--score", "--profile", str(profile)])

    assert score.calls[0][0]["queue"] == rows


def test_gaps_needs_no_profile_and_no_llm(monkeypatch, capsys):
    rows = [{"score": "40", "gaps": "Docker, AWS"}, {"score": "80", "gaps": "docker"}, {"score": "", "gaps": "Git"}]
    monkeypatch.setattr(main.sheets, "read_rows", lambda: rows)
    monkeypatch.setattr(main.user_profile, "load", lambda path: pytest.fail("--gaps는 프로필을 읽지 않음"))
    monkeypatch.setattr(main, "build_score_graph", lambda: pytest.fail("--gaps는 평가하지 않음"))

    main.main(["--gaps"])

    out = capsys.readouterr().out
    assert "공부할 기술 상위 2개 (평가한 공고 2건 기준, 점수 없는 줄 1건 제외)" in out
    assert "1. Docker | 가중 합 0.80 | 공고 2건" in out
    assert "2. AWS | 가중 합 0.60 | 공고 1건" in out


def test_gaps_with_nothing_to_analyze(capsys):
    main.print_gaps([], 0, 3)

    assert "분석할 부족한 점이 없습니다" in capsys.readouterr().out


def test_score_report_prints_failures(capsys):
    main.print_score_report(
        {"done": [{}], "failed": [{"company": "회사3", "title": "백엔드", "step": "채점", "error": "ValidationError"}]}
    )

    out = capsys.readouterr().out
    assert "평가 대상 2 / 완료 1 / 건너뜀 0 / 실패 1" in out
    assert "실패(채점): 회사3 | 백엔드 (ValidationError)" in out

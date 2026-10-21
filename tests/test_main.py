import pytest

import main


class Recorder:
    def __init__(self, result):
        self.calls = []
        self.result = result

    def __call__(self):
        return self

    def invoke(self, state, config):
        self.calls.append((state, config))
        return self.result


def test_names_become_codes_and_both_sources_by_default():
    args = main.parse_args(["--keyword", "백엔드", "--location", "서울", "--job", "백엔드", "--career", "신입"])

    assert main.to_state(args) == {
        "keyword": "백엔드",
        "sources": ["saramin", "jobkorea"],
        "location": "서울",
        "region_code": "101000",
        "job_code": "84",
        "career": "신입",
        "count": 10,
    }


def test_source_option_picks_one_site():
    args = main.parse_args(["--keyword", "백엔드", "--source", "jobkorea", "--count", "30"])

    state = main.to_state(args)
    assert state["sources"] == ["jobkorea"]
    assert state["count"] == 30
    assert state["location"] is None and state["region_code"] is None


@pytest.mark.parametrize("count", ["0", "31"])
def test_count_out_of_range_is_rejected(count):
    with pytest.raises(SystemExit):
        main.parse_args(["--keyword", "백엔드", "--count", count])


@pytest.mark.parametrize("argv", [["--career", "무관"], ["--source", "wanted"]])
def test_unknown_choice_is_rejected(argv):
    with pytest.raises(SystemExit):
        main.parse_args(["--keyword", "백엔드", *argv])


def test_unknown_name_stops_before_requests(monkeypatch):
    monkeypatch.setattr(main, "build_graph", lambda: pytest.fail("모르는 이름이면 그래프를 실행하지 않아야 함"))

    with pytest.raises(SystemExit) as exc_info:
        main.main(["--keyword", "백엔드", "--location", "서울특별시"])

    assert "서울특별시" in str(exc_info.value)


def test_report_prints_counts_per_site_and_failures(capsys):
    main.print_report(
        {
            "fetched": {"saramin": 3, "jobkorea": 2},
            "saved": [
                {"source": "saramin", "body": "글자"},
                {"source": "saramin", "body": "본문 미확보"},
                {"source": "jobkorea", "body": "글자"},
            ],
            "skipped": [{"source": "jobkorea"}],
            "failed": [
                {"source": "saramin", "company": "회사3", "title": "백엔드", "step": "본문", "error": "CrawlError"},
                {"source": "jobkorea", "company": "회사5", "title": "AI", "step": "OCR", "error": "RuntimeError"},
            ],
            "blocked": [{"source": "jobkorea", "reason": "www.jobkorea.co.kr 차단 (HTTP 429)"}],
        }
    )

    out = capsys.readouterr().out
    assert "사람인 가져옴 3 / 새로 저장 2 / 건너뜀 0 / 실패 1" in out
    assert "잡코리아 가져옴 2 / 새로 저장 1 / 건너뜀 1 / 실패 0" in out  # OCR 실패는 줄을 저장했으므로 셈에서 뺌
    assert "잡코리아 수집 멈춤: www.jobkorea.co.kr 차단 (HTTP 429)" in out
    assert "실패(본문): 사람인 | 회사3 | 백엔드 (CrawlError)" in out
    assert "실패(OCR): 잡코리아 | 회사5 | AI (RuntimeError)" in out
    assert "본문 미확보 1건: 시트의 링크로 직접 확인해 주세요" in out


def test_report_with_no_jobs(capsys):
    main.print_report({"fetched": {"saramin": 0}})

    out = capsys.readouterr().out
    assert "사람인 가져옴 0 / 새로 저장 0 / 건너뜀 0 / 실패 0" in out
    assert "본문 미확보" not in out


def test_first_run_prints_personal_use_notice_and_ocr_hint(monkeypatch, tmp_path, capsys):
    collect = Recorder({"fetched": {"saramin": 0}})
    monkeypatch.setattr(main, "build_graph", collect)
    monkeypatch.setattr(main.postings, "DIR", tmp_path / "postings")
    monkeypatch.setattr(main.ocr, "available", lambda: False)

    main.main(["--keyword", "백엔드"])

    out = capsys.readouterr().out
    assert "개인 사용만. 수집한 공고를 공유·공개·판매하지 않음" in out  # N6
    assert "pip install -r requirements-ocr.txt" in out  # F13
    state, config = collect.calls[0]
    assert state["ocr_ready"] is False
    assert config == {"recursion_limit": main.recursion_limit(10 * 2)}  # 사이트당 개수 × 사이트 수


def test_notice_only_on_first_run(monkeypatch, tmp_path, capsys):
    (tmp_path / "postings").mkdir()
    monkeypatch.setattr(main, "build_graph", Recorder({"fetched": {}}))
    monkeypatch.setattr(main.postings, "DIR", tmp_path / "postings")
    monkeypatch.setattr(main.ocr, "available", lambda: True)

    main.main(["--keyword", "백엔드", "--source", "saramin"])

    out = capsys.readouterr().out
    assert "개인 사용만" not in out
    assert "requirements-ocr" not in out


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


def test_collect_then_score_all(monkeypatch, tmp_path, capsys):
    profile = tmp_path / "profile.md"
    profile.write_text("Python", encoding="utf-8")
    rows = [
        {"row": 2, "check": "FALSE", "score": "", "experience": "신입", "education": "", "keywords": ""},
        {"row": 3, "check": "FALSE", "score": "70", "experience": "신입", "education": "", "keywords": ""},
        {"row": 4, "check": "FALSE", "score": "", "experience": "", "education": "", "keywords": ""},
    ]
    collect = Recorder({"fetched": {"saramin": 1}, "saved": [{"source": "saramin", "body": "글자"}]})
    score = Recorder({"done": [rows[0]], "skipped": [rows[2]]})
    monkeypatch.setattr(main, "build_graph", collect)
    monkeypatch.setattr(main, "build_score_graph", score)
    monkeypatch.setattr(main.sheets, "read_rows", lambda: rows)

    monkeypatch.setattr(main.postings, "DIR", tmp_path)
    monkeypatch.setattr(main.ocr, "available", lambda: True)
    main.main(["--keyword", "백엔드", "--score", "all", "--profile", str(profile)])

    assert len(collect.calls) == 1
    state, config = score.calls[0]
    assert state == {"profile": "Python", "queue": [rows[0]], "skipped": [rows[2]]}
    assert config == {"recursion_limit": main.recursion_limit(1)}
    out = capsys.readouterr().out
    assert "사람인 가져옴 1 / 새로 저장 1" in out
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

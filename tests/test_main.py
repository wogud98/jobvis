import pytest

import main

PROFILE = "skills: {main: [Python]}\nexperience: {years: 1}\ndirection: {jobs: [백엔드]}\n"


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
    assert "본문 미확보 1건: 공고 이미지를 data/inbox/나 화면 카드에 넣고 --inbox를 실행하세요" in out


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
    assert main.parse_args(["--score"]).profile == "profile.yaml"  # v0.5 F11
    assert main.parse_args(["--inbox"]).inbox is True


@pytest.mark.parametrize(
    "argv",
    [
        [],  # 아무 작업도 없음
        ["--gaps", "--keyword", "백엔드"],
        ["--gaps", "--score"],
        ["--keyword", "백엔드", "--score"],  # 방금 수집한 줄은 체크돼 있지 않음
        ["--score", "some"],
        ["--inbox", "--score"],  # v0.5 F37
        ["--inbox", "--keyword", "백엔드"],
        ["--inbox", "--gaps"],
    ],
)
def test_invalid_option_combinations(argv):
    with pytest.raises(SystemExit):
        main.parse_args(argv)


def test_missing_profile_stops_before_collecting(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "build_graph", lambda: pytest.fail("프로필이 없으면 수집도 하지 않아야 함"))
    monkeypatch.setattr(main.sheets, "read_rows", lambda: pytest.fail("프로필이 없으면 시트를 읽지 않아야 함"))
    missing = tmp_path / "profile.yaml"

    with pytest.raises(SystemExit) as exc_info:
        main.main(["--keyword", "백엔드", "--score", "all", "--profile", str(missing)])

    assert "profile.example.yaml" in str(exc_info.value)
    assert "streamlit run app.py" in str(exc_info.value)  # v0.5 F16


def test_bad_profile_stops_before_sheet_and_llm(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "build_score_graph", lambda: pytest.fail("프로필이 틀리면 평가하지 않음"))
    monkeypatch.setattr(main.sheets, "read_rows", lambda: pytest.fail("프로필이 틀리면 시트를 읽지 않아야 함"))
    profile = tmp_path / "profile.yaml"
    profile.write_text("skills: {main: []}\nexperience: {years: 2.5}\ndirection: {jobs: [백엔드]}\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        main.main(["--score", "--profile", str(profile)])

    assert "skills.main" in str(exc_info.value) and "experience.years" in str(exc_info.value)  # F13


def test_collect_then_score_all(monkeypatch, tmp_path, capsys):
    profile = tmp_path / "profile.yaml"
    profile.write_text(PROFILE + "hobby: 등산\n", encoding="utf-8")
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
    assert state["queue"] == [rows[0]] and state["skipped"] == [rows[2]]
    assert state["years"] == 1  # 보정과 신입 제외에 쓴다 (v0.5 F26, F36)
    assert state["profile"].startswith("## 기술\n- 주력: Python")  # to_prompt 글 (F22)
    assert config == {"recursion_limit": main.recursion_limit(1)}
    out = capsys.readouterr().out
    assert "모르는 칸(무시함): hobby" in out  # F14
    assert "사람인 가져옴 1 / 새로 저장 1" in out
    assert "평가 대상 2 / 완료 1 / 제외 0 / 건너뜀 1 / 실패 0" in out


def test_score_only_does_not_collect(monkeypatch, tmp_path):
    profile = tmp_path / "profile.yaml"
    profile.write_text(PROFILE, encoding="utf-8")
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
    assert "평가 대상 2 / 완료 1 / 제외 0 / 건너뜀 0 / 실패 1" in out
    assert "실패(채점): 회사3 | 백엔드 (ValidationError)" in out


def test_score_report_counts_excluded(capsys):
    main.print_score_report({"done": [{}], "excluded": [{}, {}]})

    out = capsys.readouterr().out
    assert "평가 대상 3 / 완료 1 / 제외 2 / 건너뜀 0 / 실패 0" in out
    assert "제외 (경력 요구)" in out


def test_report_prints_filled_rows(capsys):
    main.print_report(
        {
            "fetched": {"jobkorea": 1},
            "filled": [{"source": "jobkorea", "company": "회사1", "title": "백엔드"}],
        }
    )

    assert "본문 채움: 잡코리아 공고 본문으로 바꿈 (회사1 | 백엔드)" in capsys.readouterr().out


# ---- v0.5: 받은함 ----


def test_inbox_without_ocr_stops_without_touching_files(monkeypatch):
    monkeypatch.setattr(main.ocr, "available", lambda: False)
    monkeypatch.setattr(main.inbox, "run", lambda rows: pytest.fail("OCR이 없으면 파일을 건드리지 않음"))
    monkeypatch.setattr(main.sheets, "read_rows", lambda: pytest.fail("OCR이 없으면 시트도 읽지 않음"))

    with pytest.raises(SystemExit) as exc_info:
        main.main(["--inbox"])

    assert "requirements-ocr.txt" in str(exc_info.value)  # F44


def test_inbox_prints_report(monkeypatch, capsys):
    result = main.inbox.InboxResult(
        read=3,
        filled=[
            {"source": "saramin", "id": "1", "company": "회사1", "status": "글자+이미지"},
            {"source": "saramin", "id": "2", "company": "회사2", "status": "글자+이미지"},
        ],
        skipped=[{"file": "saramin_999.png", "reason": "시트에 없는 공고"}],
    )
    monkeypatch.setattr(main.ocr, "available", lambda: True)
    monkeypatch.setattr(main.sheets, "read_rows", lambda: [])
    monkeypatch.setattr(main.inbox, "run", lambda rows: result)

    main.main(["--inbox"])

    out = capsys.readouterr().out
    assert "읽은 이미지 3장 / 본문을 채운 공고 2건 (글자+이미지 2) / 건너뜀 1" in out  # F45
    assert "건너뜀: saramin_999.png (시트에 없는 공고)" in out
    assert "python main.py --score" in out

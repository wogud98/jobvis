"""화면 결과 요약: 한 줄, 할 일, 문제, 자세히 (v0.5.2 F24–F26). 터미널 줄은 test_main.py에서 본다."""

from agent import inbox, postings, reports


def saved(source="saramin", body="글자"):
    return {"source": source, "company": "가", "title": "백엔드", "body": body}


def test_collect_summary_hides_log_lines_behind_details():
    result = {
        "fetched": {"saramin": 20, "jobkorea": 12},
        "saved": [saved()] * 15 + [saved("jobkorea", postings.MISSING)] * 2,
        "skipped": [{"source": "saramin"}] * 6 + [{"source": "jobkorea"}] * 8,
        "failed": [],
        "filled": [{"source": "jobkorea", "company": "레드브릭", "title": "FDE"}],
    }

    summary = reports.collect_summary(result)

    assert summary.headline.startswith("새 공고 17건을 저장했습니다.")
    assert "다른 사이트 본문으로 채웠습니다" in summary.headline
    assert summary.todo == ["본문 없는 공고 2건: 카드 '자세히'에서 공고 이미지를 넣으면 더 정확하게 평가됩니다."]
    assert all("--inbox" not in line for line in summary.todo)  # 터미널 명령 대신 화면 할 일 (F25)
    assert summary.problems == []
    assert summary.details == reports.collect(result)  # 터미널과 같은 줄은 자세히에


def test_collect_summary_nothing_new():
    assert reports.collect_summary({"saved": [], "skipped": [{}]}).headline.startswith("새 공고가 없습니다")
    assert reports.collect_summary({}).headline.startswith("가져온 공고가 없습니다")


def test_collect_summary_problems_for_blocked_and_failed_but_not_ocr():
    result = {
        "saved": [saved()],
        "blocked": [{"source": "jobkorea", "reason": "429 요청이 너무 많음"}],
        "failed": [
            {"source": "saramin", "company": "가", "title": "a", "step": "본문", "error": "CrawlError: 500"},
            {"source": "saramin", "company": "나", "title": "b", "step": "OCR", "error": "ValueError"},
        ],
    }

    summary = reports.collect_summary(result)

    assert summary.problems == [
        "잡코리아 수집이 멈췄습니다: 429 요청이 너무 많음",
        "1건을 가져오지 못했습니다. 자세히를 확인해 주세요.",
    ]


def test_score_summary_with_llm_model_error_says_how_to_fix():
    failed = [
        {"source": "", "company": c, "title": "", "step": "채점", "error": "GoogleModelNotFoundError"} for c in "가나"
    ]

    summary = reports.score_summary({"done": [], "failed": failed})

    assert summary.headline == "평가하지 못했습니다."
    assert summary.problems == [f"2건을 평가하지 못했습니다. {reports.llm_hint('GoogleModelNotFoundError')}"]
    assert "LLM_MODEL" in summary.problems[0]  # F26


def test_score_summary_counts():
    summary = reports.score_summary({"done": [{}] * 3, "excluded": [{}], "skipped": [{}], "failed": []})

    assert summary.headline == "공고 3건을 평가했습니다. 신입에게 경력을 요구하는 공고 1건은 제외했습니다."
    assert summary.problems == [] and summary.todo == []
    assert reports.score_summary({}).headline == "평가할 공고가 없습니다."


def test_score_summary_mixed_failures_point_to_details():
    failed = [
        {"source": "", "company": "가", "title": "", "step": "채점", "error": "GoogleRateLimitError"},
        {"source": "", "company": "나", "title": "", "step": "저장", "error": "APIError"},
    ]

    summary = reports.score_summary({"done": [{}], "failed": failed})

    assert summary.problems == ["2건을 평가하지 못했습니다. LLM 사용 한도를 넘었습니다. 잠시 뒤 다시 해 주세요."]


def test_image_score_summary_joins_read_and_score():
    read = inbox.InboxResult(read=2, filled=[{"status": "이미지 읽음"}], skipped=[{"file": "x.png", "reason": "이름"}])

    summary = reports.image_score_summary(read, {"done": [{}], "skipped": [], "failed": [], "excluded": []})

    assert summary.headline == "이미지 2장을 읽어 본문을 채우고 공고 1건을 평가했습니다."
    assert summary.problems == ["이미지 1장을 건너뛰었습니다. 자세히를 확인해 주세요."]
    assert summary.todo == [] and "평가 대상 1 / 완료 1" in " ".join(summary.details)


def test_image_score_summary_when_nothing_read():
    summary = reports.image_score_summary(inbox.InboxResult(), None)

    assert summary.headline.startswith("이미지에서 글자를 읽지 못해 다시 평가하지 않았습니다.")
    assert summary.details == ["읽은 이미지 0장 / 본문을 채운 공고 0건 / 건너뜀 0"]


def test_llm_hint():
    assert "LLM_MODEL" in reports.llm_hint(["GoogleModelNotFoundError", "ModelNotFoundError"])
    assert "GOOGLE_API_KEY" in reports.llm_hint("ModelAuthenticationError")
    assert reports.llm_hint(["ValueError", "Exception"]) == ""


def test_llm_hint_names_the_model(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "google_genai:gemini-2.5-flash")

    hint = reports.llm_hint(["ModelNotFoundError"])

    assert "LLM 모델(google_genai:gemini-2.5-flash)을 찾지 못했습니다" in hint  # v0.5.2 F33
    assert "gemini-flash-lite-latest" in hint


def test_failure_lines_hide_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "AIzaSyFAKE-report-1111")
    result = {
        "saved": [],
        "failed": [{"source": "saramin", "company": "회사", "title": "직무", "step": "본문",
                    "error": "CrawlError: key=AIzaSyFAKE-report-1111"}],
        "blocked": [{"source": "jobkorea", "reason": "AIzaSyFAKE-report-1111 429"}],
    }  # fmt: skip

    summary = reports.collect_summary(result)

    shown = " ".join([*summary.problems, *summary.details])
    assert "AIzaSyFAKE-report-1111" not in shown and "••••" in shown  # v0.6.1 F12

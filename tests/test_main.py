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

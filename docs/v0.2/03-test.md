# v0.2 테스트

2026-10-20 실행. 사람인 API, LLM, 구글 시트는 모두 가짜로 바꿨고 실제 키는 쓰지 않았다.

## 실행한 명령

```bash
ruff check .            # All checks passed!
ruff format --check .   # 25 files already formatted
pytest                  # 45 passed
```

## 요구사항별 확인

| ID | 확인 내용 | 테스트 | 결과 |
| --- | --- | --- | --- |
| F1 | 옵션 5개를 받고, count 0·111과 모르는 경력 값은 거부 | `test_main.py` | 통과 |
| F2 | 서울 → 101000, 백엔드 → 84. 띄어쓰기·대소문자 무시, 괄호 앞부분, 줄임말 | `test_codes.py::test_job_name_to_code` 외 | 통과 |
| F2 | 직무 코드표 260개, 코드 겹침 없음 | `test_job_table_has_whole_it_category` | 통과 |
| F2 | 지역·직무 코드를 `loc_mcd`, `job_cd`로 보냄. 없으면 안 보냄 | `test_saramin.py` | 통과 |
| F3, F4 | 신입은 1·3·0, 경력은 2·3·0, 생략은 전부 | `test_matches_career` | 통과 |
| F5, F6 | 경력 조건이 있으면 110건 요청 후 앞에서 count건. 거른 결과가 적으면 적은 대로 | `test_career_filter_requests_max_and_keeps_count`, `test_fewer_jobs_than_count_after_filter` | 통과 |
| F7 | 새 공고마다 요약해서 저장 | `test_saves_new_jobs_and_skips_saved_ones` | 통과 |
| F8, N2 | 시트에 있는 ID는 건너뛰고 AI도 부르지 않음 | `test_skipped_jobs_are_not_summarized` | 통과 |
| F9 | 공고ID, 저장시각 열. v0.1 제목 줄 교체, 빈 시트에 제목 줄 추가 | `test_sheets.py` | 통과 |
| F10 | 가져옴 = 새로 저장 + 건너뜀 + 실패. 실패는 단계와 예외 이름만 출력 | `assert_counts_add_up`, `test_report_*` | 통과 |
| F10 | 사람인 오류(HTTP, 연결, 코드 4)는 집계 없이 메시지만 출력, 키 노출 없음 | `test_saramin.py`, `test_saramin_error_is_printed_without_traceback` | 통과 |
| F11 | 모르는 이름이면 API 호출 전에 멈추고 비슷한 이름, 전체 목록 출력 | `test_unknown_*` | 통과 |
| N3 | 요약 실패 1건, 저장 실패 1건이 있어도 나머지 저장 | `test_summary_and_save_failures_do_not_stop_others` | 통과 |
| - | 공고 0건이면 시트를 읽지 않고 집계 0으로 끝남 | `test_no_jobs_ends_normally_with_zero_counts` | 통과 |
| - | 110건이 recursion_limit에 걸리지 않음. 한도보다 길게 돌면 멈춤 | `test_max_count_*`, `test_recursion_limit_*` | 통과 |
| - | 시트 연결은 실행당 1번 | `test_connects_once_per_run` | 통과 |

테스트가 실제로 잡는지 확인하려고 `dedupe`를 일부러 고장 내서(중복도 queue에 넣음) 돌려 봤다. 중복 관련 테스트 2개가 실패했고, 되돌린 뒤 다시 45개 통과했다.

## 가짜 서비스로 끝까지 실행

`main.main()`에 가짜 사람인(4건), 가짜 시트(ID 0 저장돼 있음, ID 3 저장 실패), 가짜 LLM을 넣고 `--location 서울 --job 백엔드 --career 신입`으로 실행했다.

```text
가져옴 3 / 새로 저장 1 / 건너뜀 1 / 실패 1
  실패(저장): 회사3 | 백엔드 개발자 (ConnectionError)
```

경력 코드 2(경력) 공고 1건은 걸러졌고, 나머지 3건이 집계에 맞게 나뉘었다.

## 실제 실행

| 확인 항목 | 결과 |
| --- | --- |
| 실제 사람인 키로 지역·직무 조건 검색 | 미확인 (키 없음) |
| 사람인 응답의 `id`, `experience-level.code` 형식 | 미확인. 문서 기준으로 구현함 |
| 실제 Gemini 키로 여러 건 요약, 무료 한도에 걸리는지 | 미확인 |
| 실제 시트에서 v0.1 제목 줄 교체, 공고ID 읽기 | 미확인 |
| 직무 코드표 260개가 사람인 화면과 같은지 | 미확인. 문서 페이지를 읽어 옮김 |

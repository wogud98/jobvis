# v0.3 테스트

2026-10-20 실행. 사람인 API, LLM, 구글 시트는 모두 가짜로 바꿨고 실제 키는 쓰지 않았다.

## 실행한 명령

```bash
ruff check .            # All checks passed!
ruff format --check .   # 36 files already formatted
python -m pytest        # 111 passed
```

`pytest`만 치면 이 환경에서는 다른 파이썬의 pytest가 실행돼 패키지를 못 찾아서 `python -m pytest`로 실행했다.

## 요구사항별 확인

| ID | 확인 내용 | 테스트 | 결과 |
| --- | --- | --- | --- |
| F1 | v0.2 수집 테스트(코드 변환, 경력 거르기, 개수, 중복, 0건, 110건) 그대로 통과 | `test_graph.py`, `test_codes.py`, `test_saramin.py` | 통과 |
| F2 | 수집에서 LLM을 부르면 테스트 실패. 자격요건 칸은 빈칸 | `test_graph.py` 전체 (`init_chat_model`이 불리면 실패) | 통과 |
| F3 | 수집 줄에 경력·학력·키워드와 평가 체크 해제(False)를 저장 | `test_saves_new_jobs_and_skips_saved_ones` | 통과 |
| F4 | 저장 실패 1건이 있어도 나머지 저장, 집계가 맞음 | `test_save_failure_does_not_stop_others` | 통과 |
| F5, F6 | 프로필 읽기, 파일 없음·빈 파일이면 안내와 함께 멈춤. 수집과 시트 읽기 전에 멈춤 | `test_user_profile.py`, `test_missing_profile_stops_before_collecting` | 통과 |
| F7 | 체크한 줄만 고름, 점수가 있어도 다시 평가, 끝나면 체크 해제(False) | `test_select_checked_rows`, `test_scores_and_writes_each_row` | 통과 |
| F8 | 점수 없는 줄만 고름 | `test_select_rows_without_score` | 통과 |
| F9 | 한 번의 LLM 응답에서 요약·점수·강점·부족한 점을 받아 요약은 C열, 결과는 K–U열에 씀. 프롬프트에 프로필·기준표·공고 정보가 들어감 | `test_scores_and_writes_each_row`, `test_prompt_contains_profile_rubric_and_posting`, `test_write_result_*` | 통과 |
| F10, F11 | 네 항목 가중 평균, 문화 null이면 세 항목으로 다시 나눔, 사사오입(2.5 → 3) | `test_overall_*` | 통과 |
| F12 | 판정 경계값 39/40, 59/60, 79/80 | `test_verdict_boundaries` | 통과 |
| F13 | 별점 0–5개 | `test_stars` | 통과 |
| F14 | 강점·부족한 점은 앞 3개만, 빈 항목 제거 | `test_parse_keeps_first_three_items_and_drops_blanks` | 통과 |
| F15 | 항목 누락, 범위 밖 점수, 요약 빈칸, JSON 아님, 빈 응답 → 오류. 그 줄은 시트에 안 씀 | `test_parse_rejects_bad_answers`, `test_bad_answer_*`, `test_non_json_answer_is_a_scoring_failure` | 통과 |
| F16 | 정보 없는 줄은 건너뜀. 대상 = 완료 + 건너뜀 + 실패. 실패는 단계와 예외 이름만, 키 노출 없음 | `test_rows_without_posting_info_are_skipped`, `test_score_report_prints_failures` | 통과 |
| F17–F21 | 가중 합 순위, 대소문자·공백 무시, 점수 없는 줄 제외 수, 상위 10개, 분석할 줄 0개. 프로필·LLM 안 씀 | `test_gaps.py`, `test_gaps_needs_no_profile_and_no_llm` | 통과 |
| N1 | 채점 실패·LLM 예외·쓰기 실패가 섞여도 나머지 계속 | `test_bad_answer_llm_error_and_write_failure_do_not_stop_others` | 통과 |
| N3 | `profile.md`가 `.gitignore`에 있음 | `git check-ignore profile.md` | 확인 |
| - | 시트 제목 줄: v0.1·v0.2 제목 줄을 v0.3으로 바꾸고 체크박스 규칙 요청, 이미 v0.3이면 요청 안 함 | `test_sheets.py` | 통과 |
| - | 옵션 조합: 옵션 없음, `--gaps`와 다른 옵션, `--keyword`와 값 없는 `--score` → 오류 | `test_invalid_option_combinations` | 통과 |
| - | 110줄 평가가 recursion_limit에 안 걸림 | `test_many_rows_do_not_hit_recursion_limit` | 통과 |

테스트가 실제로 잡는지 확인하려고 코드를 일부러 고장 내서 돌려 봤다. 모두 되돌린 뒤 다시 111개 통과했다.

| 고장 낸 곳 | 실패한 테스트 수 |
| --- | --- |
| 반올림을 파이썬 `round`로 바꿈 | 3 |
| 문화 null도 가중 평균에 넣음 | 5 |
| 평가 후 체크를 해제하지 않음 | 1 |

## 가짜 서비스로 끝까지 실행

v0.2 제목 줄과 예전 줄 1개가 있는 가짜 시트, 공고 3건을 주는 가짜 사람인, 응답 3개(정상, 기술 150점, 정상)를 주는 가짜 LLM으로 `main.main()`을 실행했다.

```text
$ python main.py --keyword 백엔드 --score all
  [시트] 체크박스 규칙 요청 {'sheetId': 0, 'startRowIndex': 1, 'startColumnIndex': 10, 'endColumnIndex': 11}
가져옴 3 / 새로 저장 3 / 건너뜀 0 / 실패 0
평가 대상 4 / 완료 2 / 건너뜀 1 / 실패 1
  건너뜀: 경력·학력·키워드가 없는 줄 (v0.3 이전에 저장한 공고)
  실패(채점): 회사2 | 백엔드 개발자 2 (ValidationError)

$ python main.py --gaps
공부할 기술 상위 3개 (평가한 공고 2건 기준, 점수 없는 줄 2건 제외)
  1. AWS | 가중 합 0.88 | 공고 2건
  2. Docker | 가중 합 0.59 | 공고 1건
  3. Spring Boot | 가중 합 0.29 | 공고 1건
```

시트 결과 (C열, K–T열):

| 회사명 | 자격요건 | 평가 | 종합점수 | 별점 | 판정 | 기술 | 경력 | 문화 | 방향 | 부족한점 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 옛회사 | 옛요약 | | | | | | | | | |
| 회사1 | 신입, 대졸, Java·Spring 필수 | FALSE | 71 | ★★★★☆ | 추천 | 72 | 60 | - | 80 | Spring Boot, AWS |
| 회사2 | | FALSE | | | | | | | | |
| 회사3 | 신입, 대졸, Java·Spring 필수 | FALSE | 41 | ★★☆☆☆ | 보통 | 40 | 30 | - | 50 | AWS, Docker |

- 회사1: (30×72 + 25×60 + 30×80) / 85 = 71.29 → 71
- 회사3: (30×40 + 25×30 + 30×50) / 85 = 40.59 → 41
- AWS: (100 − 71)/100 + (100 − 41)/100 = 0.88
- 회사2는 기술 150점이라 검증에서 걸려 시트를 바꾸지 않았고, 점수가 비어 있어 다음 `--score all` 때 다시 평가된다.

## 실제 실행

| 확인 항목 | 결과 |
| --- | --- |
| 실제 Gemini 키로 채점. JSON 형식을 지키는지, 점수가 그럴듯한지 | 미확인 (키 없음) |
| Gemini 무료 구간 요청 한도에 걸리는지 | 미확인 |
| 실제 시트에서 v0.2 제목 줄 교체, K열 체크박스 생성 | 미확인 |
| 체크박스 규칙이 `append_row`로 붙인 줄에도 적용되는지 | 미확인 |
| 실제 시트에서 체크한 칸을 `get_all_values()`가 `TRUE`로 읽는지 | 미확인. gspread 문서 기준으로 구현함 |
| 실제 사람인 키로 수집 | 미확인 (v0.2부터 계속) |

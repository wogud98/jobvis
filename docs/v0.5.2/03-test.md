# v0.5.2 테스트

2026-10-21 실행. 공고 사이트·구글 시트·LLM은 모두 가짜로 바꿨다. 실제 키·사이트는 쓰지 않았다. 파일은 임시 폴더에서만 쓰고 읽었다.

## 실행한 명령

```bash
ruff check .            # All checks passed!
ruff format --check .   # 68 files already formatted
python -m pytest        # 408 passed (v0.5.1 344개 → 408개)
```

Streamlit 1.66.0, pypdf 6.17.0, python-docx 1.2.0. 새 테스트 파일: `tests/test_runner.py`(27개), `tests/test_resume.py`(24개). `tests/test_app.py`에 13개 추가.

## 요구사항별 확인

| ID | 확인 내용 | 테스트 | 결과 |
| --- | --- | --- | --- |
| F1, F4 | 수집 카드 입력 → 터미널과 같은 State, 수집 시작 | `test_collect_button_starts_collect_with_inputs`, `test_collect_state_from_screen_inputs`, `test_collect_state_all_career_and_default_sources` | 통과 |
| F1 | 키워드 없음, 개수 범위 밖, 사이트 없음은 시작하지 않음 | `test_collect_without_keyword_shows_error_and_does_not_start`, `test_collect_state_rejects_bad_input`(5가지) | 통과 |
| F2 | 모르는 지역은 사이트 요청 전에 멈춤 | `test_collect_state_unknown_region_stops_before_request` | 통과 |
| F3 | 키워드 추천: 프로필 희망 직무·주력 기술 먼저, 겹치지 않음, 직무 이름 포함 | `test_keyword_options_put_profile_first_without_duplicates`, `test_keyword_options_without_profile_are_job_names`, `test_run_panel_shows_collect_and_score_cards` | 통과 |
| F5 | 진행 수(처리 수/전체), 결과 요약이 터미널과 같은 글 | `test_collect_streams_graph_and_reports_progress`, `test_collect_progress_grows_total_for_late_duplicates`, `test_running_job_locks_buttons_and_shows_progress`, `test_main.py` 전체 | 통과 |
| F5 | 결과 줄의 글자를 HTML로 그대로 넣지 않음 | `test_finished_job_shows_result_lines_escaped` | 통과 |
| F7 | 평가 대상 수: 체크한 공고 / 점수 없는 공고 전부, 0이면 버튼 잠금 | `test_run_panel_shows_collect_and_score_cards`, `test_score_targets_match_terminal_selection`, `test_score_button_is_disabled_without_targets` | 통과 |
| F8 | 프로필 없으면 평가하지 않고 프로필 탭 안내 | `test_score_without_profile_points_to_profile_tab`, `test_load_profile_missing_file` | 통과 |
| F9 | 평가 진행 수, 결과 요약 | `test_score_runs_graph_on_targets` | 통과 |
| F10 | 받은함 이미지 수(이름 형식 맞는 것만), 버튼, 결과 글 | `test_inbox_count_ignores_wrong_names`, `test_inbox_count_without_folder`, `test_inbox_button_when_ocr_is_ready`, `test_start_inbox_reports_result` | 통과 |
| F11 | OCR 없으면 버튼 대신 안내, 시트도 읽지 않음 | `test_inbox_without_ocr_shows_install_hint`, `test_read_inbox_without_ocr_touches_nothing` | 통과 |
| F12 | 실행 중 세 종류 모두 거절, 끝나면 다시 실행, 버튼 잠금 | `test_second_start_while_running_is_refused`, `test_running_job_locks_buttons_and_shows_progress` | 통과 |
| F13 | 오류는 문구만(경로·키 없음), 화면 꺼지지 않음 | `test_error_in_work_becomes_message_without_details`, `test_error_text`(3가지), `test_score_sheet_error_is_shown_as_message`, `test_failed_job_shows_error` | 통과 |
| F14 | 터미널 명령·출력 그대로 | `tests/test_main.py` (검사 내용 그대로, 가짜 그래프에 `stream`만 붙임) | 통과 |
| F15 | 사용법 첫 줄 | `test_run_panel_shows_collect_and_score_cards` | 통과 |
| F16 | PDF·docx·txt·md 글자 뽑기, 윈도우 한글(cp949), BOM | `test_extract_text_pdf`, `test_extract_word_paragraphs_and_tables`, `test_extract_plain_utf8_and_windows_korean` | 통과 |
| F17 | LLM 한 번, `LLM_MODEL`로 만듦, 응답 → 프로필 모양 | `test_ask_calls_model_once_with_text`, `test_parse_json_in_code_block_and_missing_parts` | 통과 |
| F18 | 채운 값은 입력란에만, 저장을 눌러야 파일에 씀, 저장 뒤 채운 값 지움, 버리기 | `test_resume_fill_values_become_defaults_and_are_saved`, `test_resume_fill_can_be_discarded` | 통과 |
| F19 | 빈 칸만 채움(기본), 목록 칸은 없는 항목만 더함, 덮어쓰기, 찾은 게 없으면 그대로 | `test_merge_fills_empty_form`, `test_merge_keeps_written_fields_and_adds_missing_items`, `test_merge_overwrite_replaces_found_fields_only`, `test_merge_nothing_found_changes_nothing`, `test_merge_years_zero_from_resume_means_new_grad`, 토글 기본값 꺼짐 | 통과 |
| F20 | 채운 칸 배지, 경력 연수 확인 안내 | `test_resume_fill_values_become_defaults_and_are_saved` | 통과 |
| F21 | 스캔(글자 없는) PDF, 빈 파일, 깨진 docx·PDF, 모르는 형식, 10MB 초과, 인코딩 모름은 그 파일만 건너뜀. 형식 틀린 LLM 응답은 오류 | `test_extract_bad_files`(7가지), `test_read_files_skips_bad_ones_and_cuts_text`, `test_parse_rejects_bad_answers`(4가지) | 통과 |
| F22 | 앞 20,000자만 | `test_read_files_skips_bad_ones_and_cuts_text` | 통과 |
| N2 | 오류 메시지에 파일 내용 없음 | `test_extract_bad_files` | 통과 |
| N3 | LLM 전송 안내, 파일 없으면 채우기 버튼 잠금 | `test_resume_section_notes_llm_transfer_and_disables_button_without_files` | 통과 |
| - | 이력서 글 안의 지시는 자료로만 (프롬프트) | `test_prompt_keeps_resume_text_as_data` | 통과 |

`tests/test_app.py`의 `test_profile_tab_saves_valid_profile`은 학력 칸을 `at.selectbox[0]`으로 찾았는데, 공고 탭에 수집 카드 고르기 칸이 생겨 첫 칸이 바뀌었다. 이름("최종 학력")으로 찾도록 고쳤고 검사 내용은 그대로다.

코드를 일부러 고장 내서 테스트가 잡는지 봤다. 모두 되돌린 뒤 다시 408개 통과했다.

| 고장 낸 곳 | 실패한 테스트 수 |
| --- | --- |
| 이력서 합치기에서 "빈 칸만" 규칙을 끔 | 1 |
| 실행 잠금(이미 실행 중 검사)을 끔 | 1 |
| 오류 문구 대신 예외 메시지를 그대로 보임 | 4 |
| 결과 줄 escape를 끔 | 1 |
| 20,000자 자르기를 끔 | 1 |
| 저장 뒤 채운 값을 지우지 않음 | 1 |

## 화면 확인

테스트가 아니라 눈으로 본 확인이다. 가짜 시트 줄 6개, 가짜 수집 그래프(공고 6건, 2초 간격), 가짜 LLM 응답으로 실제 `app.py`를 `streamlit run`(헤드리스, localhost)으로 띄우고 Playwright + 크로미움으로 눌러 봤다. 캡처는 `/mnt/project-files/screens/v0.5.2/`.

| 확인 | 결과 |
| --- | --- |
| 키워드 칸에 목록에 없는 "FDE"를 입력하고 Enter (`accept_new_options`) | 들어감 |
| 수집 누른 뒤 5초: 진행 막대 "수집 중: 사람인 공고 본문을 가져오는 중 (2/6)", 수집 버튼 잠김 | 확인 (`v052-running.png`) |
| 끝난 뒤: 결과 요약 4줄(OCR 없음 안내, 사이트별 수, 본문 미확보), 버튼 다시 켜짐 | 확인 (`v052-done.png`) |
| 받은함 이미지 1장 + OCR 없음 → 설치 안내 | 확인 |
| 프로필 탭에 실제 .docx 파일을 올리고 이력서로 채우기 → 입력란 11칸 채움, 배지, 경력 연수 안내 | 확인 (`v052-profile-filled.png`) |
| 초록 테마(F23): 버튼·차트·키워드·점수 글자 초록, 판정 배지 회녹색이 신뢰 높음 배지와 구별됨 | 확인 (`green-done.png`, `green-profile-filled.png`) |

## 미확인

- 실제 사람인·잡코리아 수집을 화면 버튼으로 돌린 것. 그래프는 터미널과 같지만 실제 사이트로는 안 돌림.
- 실제 LLM(Gemini)으로 이력서를 읽은 결과. 양식이 다른 실제 이력서에서 칸을 얼마나 잘 찾는지, 응답이 형식에 맞는지는 재리 PC에서 확인 필요.
- 한글 PDF 글자 뽑기. 테스트 PDF는 영문 글꼴만 썼다. 한글 글꼴이 들어간 실제 PDF에서 pypdf가 글자를 제대로 뽑는지 확인 필요.
- 실제 구글 시트로 평가·받은함을 화면에서 돌린 것, 끝난 뒤 시트를 다시 읽어 카드가 바뀌는 것(가짜 시트로만 봄).
- 윈도우 PC 모니터에서 초록 테마 글자 대비. 크로미움 캡처로만 봄.
- 윈도우 PC 브라우저(엣지·크롬)에서 진행 막대가 1초마다 바뀌는 것, 수집 중 다른 탭·입력란을 눌러도 끊기지 않는 것.
- 화면 창 두 개에서 동시에 누르는 경우. 잠금은 테스트로 봤지만 실제 창 두 개로는 안 해 봄.

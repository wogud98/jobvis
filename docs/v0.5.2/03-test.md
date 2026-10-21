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
| 테마(F23): 초록은 버튼·차트·고른 키워드·카드 점수에만, 바탕·글자·요약 숫자·판정 배지는 무채색 | 확인 (`point-done.png`, `point-profile-filled.png`) |

## 보완 확인 (F24–F27)

2026-10-21 보완 PR. 재리 PC에서 화면으로 실제 수집(사람인 14건·잡코리아 3건 저장)과 이력서 PDF 채우기를 써 본 뒤 나온 의견을 반영했다.

```bash
ruff check .            # All checks passed!
ruff format --check .   # 70 files already formatted
python -m pytest        # 420 passed (408 → 420)
```

| ID | 확인 내용 | 테스트 | 결과 |
| --- | --- | --- | --- |
| F24 | 결과 한 줄만 기본, 할 일·문제는 있을 때만, 터미널 줄은 접힌 자세히 | `test_finished_job_shows_headline_todo_problems_and_folded_details`, `test_finished_job_without_todo_or_problems_shows_only_headline`, `test_collect_summary_hides_log_lines_behind_details`, `test_collect_summary_nothing_new`, `test_score_summary_counts`, `test_inbox_summary` | 통과 |
| F24 | 수집 멈춤·실패는 문제, OCR 실패는 문제 아님 | `test_collect_summary_problems_for_blocked_and_failed_but_not_ocr` | 통과 |
| F25 | 본문 없는 공고 안내에 `--inbox` 없음 | `test_collect_summary_hides_log_lines_behind_details`, AppTest | 통과 |
| F26 | 모델 없음·키·한도 오류는 고칠 방법, `FileNotFoundError`는 기존 인증 문구 | `test_error_text`(5가지), `test_score_summary_with_llm_model_error_says_how_to_fix`, `test_score_summary_mixed_failures_point_to_details`, `test_llm_hint`, `test_score_sheet_error_is_shown_as_message` | 통과 |
| F27 | pypdf 없으면 설치 방법 | `test_missing_library_says_how_to_install` | 통과 |

`tests/test_runner.py`의 결과 검사는 `job.lines`에서 `job.result.headline`·`details`로 바꿨다. 터미널 줄 검사 내용은 `details`에 그대로 남아 있다. `test_app.py`의 결과 escape 테스트는 한 줄·할 일·문제·자세히를 모두 보는 테스트로 바꿨다(escape 검사 유지).

고장 내기: `ModelNotFound`를 `NotFound`로 넓힘(1개 실패, 파일 없음 오류가 모델 오류로 보임), 자세히 접기를 끔(1개), LLM 고칠 방법을 끔(2개). 모두 되돌린 뒤 420개 통과.

화면 확인(가짜 수집 그래프): 결과 칸이 "새 공고 6건을 저장했습니다." 한 줄 + 노란 "본문 없는 공고 2건" 안내 + 접힌 "자세히"로 보임(`/mnt/project-files/screens/v0.5.2/summary-folded.png`, `summary-open.png`).

재리가 올린 실제 이력서 PDF(한글, 4쪽)를 이 환경의 pypdf 6.17로 읽어 4,955자를 뽑았다. 한글 PDF 글자 뽑기는 이 파일 하나로는 확인됨. 재리 PC의 첫 실패는 pypdf 미설치로 추정(이후 PDF는 읽히고 LLM 모델 404로 바뀜).

## 네오 브루탈리즘 확인 (F28)

CSS와 테마 설정만 바꿔 pytest로는 잡지 못한다. 가짜 시트·가짜 수집 그래프·가짜 LLM으로 실제 `app.py`를 띄워 크로미움으로 캡처했다(`/mnt/project-files/screens/neo-brutalism/postings.png`, `profile.png`). 테두리·그림자, 요약 칸 4색, 버튼 잠김(수집 중), 이력서 채운 배지가 보임.

```bash
ruff check .            # All checks passed!
ruff format --check .   # 통과
python -m pytest        # 420 passed (변경 없음)
```

## 필터 확인 (F29, F30)

```bash
ruff check .            # All checks passed!
ruff format --check .   # 통과
python -m pytest        # 432 passed (420 → 432)
```

| ID | 확인 내용 | 테스트 | 결과 |
| --- | --- | --- | --- |
| F29 | 필터가 빈 채로 시작, 비면 전체, 고르면 거름 | `test_filters_start_empty_meaning_all`, `test_options_and_filters` | 통과 |
| F30 | 경력 글자 → 묶음 10가지(신입·경력 둘 다, 무관, 숫자+년, 기타, 빈 칸), 둘 다인 공고는 두 묶음에 | `test_career_groups`, `test_mixed_career_posting_matches_both_groups` | 통과 |

`test_options_and_filters`는 경력 보기가 글자 그대로에서 묶음으로 바뀌어 기대값을 바꿨고, 빈 필터·묶음 필터·출처와 경력을 함께 고르는 경우를 더했다.

## 보완 2 확인 (F31–F37)

```bash
ruff check .            # All checks passed!
ruff format --check .   # 70 files already formatted
python -m pytest        # 448 passed (432 → 448)
```

| ID | 확인 내용 | 테스트 | 결과 |
| --- | --- | --- | --- |
| F31 | 평가 전 카드에 평가 전 안내, 수집 정보, 원문 앞부분, 원문 없으면 이미지 안내. `Card.info`는 빈 칸 뺌, `preview`는 이미지 글자를 붙이고 자르고, 파일·공고ID 없으면 빈 글자 | `test_unscored_card_shows_collected_info_and_body_preview`, `test_card_info_has_collected_fields_only`, `test_preview_reads_saved_body_and_cuts`, `test_preview_without_saved_body_or_id_is_blank` | 통과 |
| F32 | 처음엔 평가 전까지 3건, 토글을 켜면 2건 | `test_postings_tab_shows_guide_summary_and_scored_cards`, `test_options_and_filters`, `test_unscored_card_shows_dash_and_sheet_text_is_escaped` | 통과 |
| F33 | 모델 없음 안내에 `LLM_MODEL` 이름 | `test_llm_hint_names_the_model` | 통과 |
| F34 | 프롬프트에 추측 금지·애매하면 비움·주소로 지역 정하지 않음 | `test_prompt_forbids_guessing_location_from_address` | 통과 |
| F35 | 빈 칸 이름(필수 먼저), 경력 연수 0을 찾았거나 사용자가 적었으면 빠짐, 화면 "입력 필요" 노란 배지 | `test_missing_lists_blank_fields_required_first`, `test_missing_years_found_zero_is_not_missing`, `test_resume_fill_shows_input_needed_badges` | 통과 |
| F36 | 예전 `tried`를 `can_use`로 읽고 경고 없음, 다시 저장하면 `tried` 없음, 프롬프트 한 줄, 입력란 칸 11개 | `test_old_tried_is_read_into_can_use_without_warning`, `test_to_prompt_has_one_can_use_line`, `test_old_tried_joins_can_use_and_main_is_removed`, `test_every_file_field_has_one_input_in_a_group` | 통과 |
| F37 | 주력에 고른 기술은 다룰 수 있음 보기·값에서 빠지고 나머지 값은 남음, 저장값에 겹침 없음, 이력서 채우기·파일 읽기에서도 겹침 지움 | `test_skill_in_main_cannot_be_picked_in_can_use`, `test_from_form_removes_skills_already_in_main`, `test_taken_and_without_taken`, `test_merge_moves_skill_out_of_can_use_when_resume_puts_it_in_main` | 통과 |

화면: 가짜 시트(6건, 평가 전 1건은 저장 원문 있음)·가짜 LLM(이력서에 지역 없음, 주력에 Git)·예전 `tried`가 있는 `profile.yaml`로 `streamlit run`하고 크로미움으로 캡처(`/mnt/project-files/screens/v0.5.2/fix2-*.png`). 평가 전 카드에 안내·수집 정보·원문 앞부분이 보이고, 프로필 탭에 예전 `tried`(Docker)가 다룰 수 있음에 보이고, 이력서 채우기 뒤 "입력 필요" 배지 5개, 주력에 들어간 Git이 다룰 수 있음에서 빠진 것을 봄.

바꾼 기존 테스트: 평가 전이 기본으로 보이게 되어(F32) 카드 수 기대값을 2 → 3으로, 토글을 켜던 테스트는 켜지 않게, `Filters(..., True)`는 `scored_only` 뜻으로 바꾸고 토글 켠 경우를 더함. `tried` 칸을 쓰던 테스트 3개는 `can_use`로 바꿈(F36). 검사 조건을 약하게 바꾼 것은 없음.

## 평가 줄과 카드 체크 확인 (F38, F39)

```bash
ruff check .            # All checks passed!
ruff format --check .   # 70 files already formatted
python -m pytest        # 457 passed (448 → 457)
```

| ID | 확인 내용 | 테스트 | 결과 |
| --- | --- | --- | --- |
| F38 | 평가 줄 버튼 두 개와 건수, 대상 라디오 없음, 차트 아래·카드 위, 두 버튼이 checked/all로 평가 시작 | `test_run_panel_shows_collect_and_score_cards`, `test_score_bar_sits_right_above_card_list`, `test_score_bar_buttons_start_score` | 통과 |
| F39 | 체크 칸 처음 값 = 시트, 체크·해제하면 시트에 쓰고 건수가 바뀜, 쓰기 실패면 되돌리고 오류(경로 없음), `set_check`는 K열만, `with_checks`·`Card.checked` | `test_card_check_writes_sheet_and_updates_target_count`, `test_card_check_failure_shows_error_and_keeps_sheet_value`, `test_set_check_writes_check_column_only`, `test_card_checked_and_with_checks` | 통과 |

`test_run_panel_shows_collect_and_score_cards`는 라디오를 바꾸던 부분을 버튼 두 개의 건수 확인으로 바꿨다(F38). 화면: 가짜 시트로 `streamlit run` 후 크로미움에서 카드 체크를 눌러 버튼 건수가 1 → 2건으로 바뀌는 것을 봄(`/mnt/project-files/screens/v0.5.2/bar-*.png`).

## 목록 정리 확인 (F40–F44)

```bash
ruff check .            # All checks passed!
ruff format --check .   # 통과
python -m pytest        # 471 passed (457 → 471)
```

| ID | 확인 내용 | 테스트 | 결과 |
| --- | --- | --- | --- |
| F40 | 높은 순·낮은 순, 같은 점수는 줄 순, 평가 전은 아래, 화면 정렬 칸 | `test_sort_lowest_first_keeps_unscored_last`, `test_sort_select_reorders_cards` | 통과 |
| F41 | 23건 → 10·10·3, 범위 밖 쪽 번호, 이전·다음 버튼 잠금, 정렬 바꾸면 1쪽, 10건 이하면 쪽 넘기기 없음 | `test_page_splits_and_clamps`, `test_pages_of_ten_and_filter_change_goes_back_to_first_page`, `test_no_pager_for_ten_or_fewer` | 통과 |
| F42 | 낮은 순이어도 높은 5건, 제목 TOP 5 | `test_chart_shows_top_five_by_score_whatever_the_sort`, `test_score_bar_sits_right_above_card_list` | 통과 |
| F43 | 새 문장 | `test_hero_tagline` | 통과 |
| F44 | AD열만 씀, 예전 29열 시트 제목 늘림, 신뢰·보정 쓰기가 AD를 안 건드림, 뺀 줄은 두 평가 대상에서 빠짐, 화면에서 빼기·관심 없는 공고만 보기·되돌리기, 쓰기 실패 | `test_set_hidden_writes_hidden_column_only`, `test_v05_header_is_extended_with_hidden_column`, `test_write_result_does_not_touch_hidden_column`, `test_hidden_rows_are_never_targets`, `test_hidden_cards_only_in_hidden_view`, `test_hide_card_moves_it_to_hidden_view_and_back`, `test_hide_failure_keeps_card_and_shows_error` | 통과 |

화면: 가짜 시트 20건으로 `streamlit run` 후 크로미움 캡처(`/mnt/project-files/screens/v0.5.2/list-*.png`). TOP 5 막대가 점수 높은 순(처음엔 이름순으로 회사20이 회사3 앞에 와서 `sort` 지정으로 고침), 1–10번째, 쪽 넘기기, 관심 없음 버튼을 봄.

바꾼 기존 테스트: 시트 열 수 29 → 30과 AD열 확인(`test_header_and_keys_line_up`), 차트 제목 "종합점수" → "종합점수 TOP 5"(`test_score_bar_sits_right_above_card_list`).

## 미확인

- 실제 구글 시트에 AD "관심없음" 제목이 붙고 값이 쓰이는지(재리 시트는 29열이라 처음 수집·평가 때 제목 줄이 늘어남). 가짜 시트로만 봄.
- 실제 구글 시트에서 카드 체크가 "평가" 체크박스에 반영되는지, 체크 한 번에 걸리는 시간. 가짜 시트로만 봄.
- 실제 Gemini가 추측 금지 규칙(F34)을 따라 주소를 희망 지역에 넣지 않는지. 재리 PC에서 같은 이력서로 다시 확인 필요.
- 재리 PC의 예전 `profile.yaml`(`tried` 있음)을 화면에서 열고 저장한 결과. 테스트 파일로만 봄.
- 윈도우 엣지·크롬에서 네오 브루탈리즘 CSS(`:has()`, 버튼 눌림 효과)가 같게 보이는지.

- 실제 사람인·잡코리아 수집을 화면 버튼으로 돌린 것. 그래프는 터미널과 같지만 실제 사이트로는 안 돌림.
- 실제 LLM(Gemini)으로 이력서를 읽은 결과. 양식이 다른 실제 이력서에서 칸을 얼마나 잘 찾는지, 응답이 형식에 맞는지는 재리 PC에서 확인 필요.
- 한글 PDF 글자 뽑기는 실제 이력서 PDF 1개로만 확인(보완 확인 참고). 다른 PDF 생성기(한글 HWP 변환 등)는 미확인.
- `gemini-flash-lite-latest`로 바꾼 뒤 재리 PC에서 이력서 채우기·평가가 되는지.
- 실제 구글 시트로 평가·받은함을 화면에서 돌린 것, 끝난 뒤 시트를 다시 읽어 카드가 바뀌는 것(가짜 시트로만 봄).
- 윈도우 PC 모니터에서 테마 색과 글자 대비. 크로미움 캡처로만 봄.
- 윈도우 PC 브라우저(엣지·크롬)에서 진행 막대가 1초마다 바뀌는 것, 수집 중 다른 탭·입력란을 눌러도 끊기지 않는 것.
- 화면 창 두 개에서 동시에 누르는 경우. 잠금은 테스트로 봤지만 실제 창 두 개로는 안 해 봄.

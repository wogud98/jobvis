# v0.5 테스트

2026-10-21 실행. 구글 시트, LLM, OCR은 모두 가짜로 바꿨다. 실제 시트·키·공고 사이트는 쓰지 않았다. 파일은 `tmp_path`에서만 쓰고 읽었다.

## 실행한 명령

```bash
ruff check .            # All checks passed!
ruff format --check .   # 55 files already formatted
python -m pytest        # 328 passed
```

`pytest`만 치면 이 환경에서는 다른 파이썬의 pytest가 실행돼 `python -m pytest`로 실행했다 (v0.3, v0.4와 같음). Streamlit 1.66.0.

화면은 `streamlit.testing.v1.AppTest`(`tests/test_app.py`)로 확인했다. 그 밖에 가짜 시트 줄을 넣은 데모를 `streamlit run`으로 띄워(헤드리스, localhost) 브라우저 화면을 찍어 봤다. 카드·막대 차트·필터·프로필 입력란이 그려지는 것만 눈으로 확인했고, 이 실행은 테스트가 아니다.

## 요구사항별 확인

| ID | 확인 내용 | 테스트 | 결과 |
| --- | --- | --- | --- |
| F1 | 탭 두 개(공고, 프로필) | `test_postings_tab_shows_scored_cards_and_two_tabs` | 통과 |
| F2 | 점수 높은 순, 같으면 줄 순, 평가 전·제외는 아래. 점수 칸에 글자면 평가 전 | `test_cards_sorted_by_score_then_row_and_unscored_last`, `test_score_with_text_is_unscored` | 통과 |
| F3 | 펼친 카드 내용 순서, 빈 칸 "없음" | `test_details_show_blank_as_none` | 통과 |
| F4 | 원문 링크(`st.link_button`) | `app.py` 코드 확인. AppTest로는 링크 버튼을 누르지 않음 | 미확인(PC 브라우저) |
| F5 | 차트는 필터를 지난 점수 있는 공고만, 같은 막대 이름에 번호 | `test_chart_has_scored_cards_only_and_unique_names` | 통과 |
| F6 | 출처·경력 필터, 평가 전 기본 숨김, 출처 빈 줄 "미상", 경력 빈 줄 "(없음)" | `test_options_and_filters`, `test_blank_source_is_unknown_but_saved_as_saramin` | 통과 |
| F7 | 시트는 `st.cache_data`로 한 번 읽고 새로고침 때 비움 | `app.py` 코드 확인 | 테스트 없음 |
| F8 | 화면용 시트 읽기는 제목 줄을 고치지 않음 | `test_read_rows_readonly_does_not_touch_old_header` | 통과 |
| F9 | 오류 문구에 경로·키 없음 | `test_error_message_hides_details`(6가지), `test_sheet_error_shows_message` | 통과 |
| F10 | 빈 시트 안내 | `test_empty_sheet_shows_collect_hint` | 통과 |
| F11, F15 | `profile.yaml` 기본, 예시 파일 읽힘 | `test_example_file_in_repo_is_valid` | 통과 |
| F12 | 필수 칸 누락·형식 오류 9가지 | `test_wrong_required_fields_name_the_field` | 통과 |
| F13 | 프로필 틀리면 시트·LLM 전에 멈춤 | `test_bad_profile_stops_before_sheet_and_llm` | 통과 |
| F14 | 모르는 칸은 경고만 | `test_unknown_fields_are_warnings_only` | 통과 |
| F16 | 파일 없으면 화면·예시 안내, 예전 `profile.md` 있으면 그것도 안내(변환 안 함) | `test_missing_file_points_to_screen_and_example`, `test_missing_file_mentions_old_markdown_profile` | 통과 |
| F17, F19 | 파일 내용으로 입력란 채움, 목록은 한 줄에 하나, 빈 줄 지움 | `test_form_round_trip_from_example_file`, `test_form_lines_become_items_and_blank_lines_are_dropped`, `test_form_defaults_for_missing_or_wrong_values` | 통과 |
| F18 | 경력 슬라이더 0–30 | `app.py` 코드 확인, 데모 화면 | 테스트 없음 |
| F20 | 저장 성공, 필수 칸 없으면 저장 안 함, 저장 실패해도 기존 파일 유지 | `test_profile_tab_saves_valid_profile`, `test_profile_tab_does_not_save_without_required_fields`, `test_form_without_required_fields_is_rejected`, `test_failed_save_keeps_old_file`, `test_save_round_trip_keeps_field_order_and_korean` | 통과 |
| F21 | 깨진 파일이면 화면에서 덮어쓰지 않음 | `test_profile_tab_keeps_broken_file`, `test_read_raw_missing_and_broken` | 통과 |
| F22–F24 | 프롬프트 네 제목, 자격증·학력·지역 위치, 문화 없음 | `test_to_prompt_has_four_sections`, `test_to_prompt_marks_blank_fields_and_missing_culture` | 통과 |
| F25 | `required_years` 0·3·null, 빠짐 → null, 음수·글자 → 실패 | `test_required_years_values`, `test_required_years_missing_is_null`, `test_required_years_negative_or_text_is_rejected` | 통과 |
| F26 | 부족 1·2·3·5년 상한, 낮은 점수는 그대로 | `test_experience_cap_by_short_years`, `test_lower_llm_score_is_kept_without_note` | 통과 |
| F27 | 경력 부족이면 종합 79 | `test_short_experience_caps_total_at_79`, `test_short_experience_caps_total_even_when_experience_score_is_already_low` | 통과 |
| F28 | 신뢰 세 단계 | `test_trust_levels`, `test_trust_medium_for_partly_unread_body` | 통과 |
| F29 | 신뢰 낮음 종합 69, 둘 다면 낮은 상한 | `test_low_trust_caps_total_at_69`, `test_short_experience_and_low_trust_use_lower_cap` | 통과 |
| F30, F31 | 프롬프트에 방향 기준·규칙과 `required_years` | `test_prompt_has_direction_rules_and_required_years` | 통과 |
| F32, F33 | AB·AC 열, 판정에 "(본문 미확보)" 없음, v0.4 제목 줄 늘림 | `test_short_experience_caps_experience_and_total`, `test_no_adjustment_leaves_note_blank`, `test_v04_header_is_extended_without_new_checkbox_rule` | 통과 |
| F34 | 카드에 신뢰·보정, 신뢰 낮음 흐리게. v0.4 판정 "(본문 미확보)"는 신뢰 낮음 | `test_v04_verdict_with_missing_body_means_low_trust` | 통과 |
| F35, F36 | 신입 제외는 LLM 안 부름(호출 0), 경력 있으면 제외 안 함, `--score all`은 제외 줄 안 고름 | `test_newcomer_exclusion`, `test_newcomer_skips_postings_that_require_experience_without_llm`, `test_experienced_profile_is_not_excluded`, `test_select_all_skips_excluded_rows_but_checked_picks_them`, `test_write_result_for_excluded_row_keeps_summary_and_body_summary`, `test_score_report_counts_excluded` | 통과 |
| F37, F39, F40 | 원문에 붙임(파일 없으면 새로), 상태 바뀌면 시트·체크, 상태 같으면 시트 그대로 | `test_run_fills_body_turns_on_check_and_moves_files`, `test_same_status_keeps_sheet_but_updates_file`, `test_partly_unread_becomes_text_and_image`, `test_short_text_stays_missing`, `test_blank_source_row_is_saramin` | 통과 |
| F38 | 이름 형식(번호 있음·없음·대문자, 틀린 이름), 번호순 | `test_parse_name`, `test_scan_groups_by_posting_in_number_order_and_skips_bad_names` | 통과 |
| F41 | done 이동, 다시 실행해도 안 붙음, done 이름 겹치면 번호 | `test_run_twice_does_not_add_text_twice`, `test_done_name_clash_gets_number` | 통과 |
| F42 | 크기·장수 제한 없음 | `inbox.py` 코드 확인(크기 검사·장수 상한 없음) | 테스트 없음 |
| F43 | 시트에 없는 공고·OCR 실패는 받은함에 남김, 모두 실패하면 원문 안 만듦 | `test_unknown_posting_and_ocr_failure_are_skipped_and_left_in_inbox`, `test_all_images_fail_leaves_posting_untouched`, `test_empty_or_missing_inbox` | 통과 |
| F44 | OCR 없으면 파일 안 건드리고 멈춤 | `test_inbox_without_ocr_stops_without_touching_files` | 통과 |
| F45 | 결과 출력 | `test_inbox_prints_report` | 통과 |
| F46 | 시트의 미확보 줄을 다른 사이트 공고로 교체, 새 본문도 미확보면 그대로, 같은 실행 두 사이트(앞 미확보 / 앞 본문 있음 / 앞 실패) | `test_missing_row_in_sheet_is_replaced_by_other_site_posting`, `test_missing_row_stays_when_new_body_is_also_missing`, `test_same_run_second_site_*` 3개, `test_report_prints_filled_rows`, `test_append_row_returns_row_number`, `test_update_cells_writes_named_columns_only` | 통과 |
| F47 | 본문 미확보·일부 못 읽음이고 공고ID 있을 때만 이미지 칸 | `test_upload_box_only_for_missing_or_partly_unread_body` | 통과 |
| F48 | 저장 이름, inbox·done 둘 다 보고 번호 올림 | `test_save_upload_uses_posting_name_and_raises_number` | 통과 |
| F49 | 확장자 아님·10MB 초과 거절, 10MB 정확히는 받음 | `test_save_upload_rejects_bad_files`, `test_save_upload_accepts_exactly_10mb` | 통과 |
| N1 | `profile.yaml`이 `.gitignore`에 있음 | 파일 확인 | 통과 |
| N2 | 프로필 오류에 입력값 없음 | `test_error_does_not_show_profile_content` | 통과 |
| N3 | `streamlit>=1.50`, `PyYAML>=6.0`을 `requirements.txt`에 | 파일 확인 | 통과 |
| N5, N6, N8 | 규칙은 Streamlit 밖 함수, 가짜 LLM·OCR·시트 | 위 테스트 전체 | 통과 |

테스트가 실제로 잡는지 확인하려고 코드를 일부러 고장 내서 돌려 봤다. 모두 되돌린 뒤 다시 328개 통과했다.

| 고장 낸 곳 | 실패한 테스트 수 |
| --- | --- |
| 경력 상한(60/45/30)을 끔 | 7 |
| 신뢰 낮음 상한(69)을 끔 | 3 |
| 신입 제외를 끔 | 3 |
| 이미지 넣는 칸을 본문 상태와 상관없이 보임 | 1 |
| 평가 전 공고 숨김을 끔 | 2 |

## 미확인

- 실제 구글 시트에서 화면 읽기(`read_rows_readonly`), AB·AC 열 늘리기, `update_cells`. 가짜 시트로만 확인함.
- gspread `append_row` 응답의 `updates.updatedRange`에서 줄 번호 읽기. gspread 문서 형식으로 만든 가짜 응답으로만 확인함. 형식이 다르면 F46 같은 실행 교체가 건너뜀으로 끝남(잘못 쓰지는 않음).
- 윈도우 PC 브라우저에서 이미지 끌어다 놓기, 원문 링크 새 탭.
- 사람이 넣은 실제 공고 이미지의 PaddleOCR 결과.
- 실제 LLM이 `required_years`를 일관되게 주는지("3~5년" → 3). 가짜 응답으로만 확인함.
- 보정 상한 숫자(60/45/30, 79, 69)가 실제 공고에서 알맞은지. 써 보며 판단.

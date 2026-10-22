# v0.6.1 테스트

2026-10-22 실행. LLM·사이트는 가짜로 바꿨다. 실제 키·시트는 쓰지 않았다.

## 실행한 명령

```bash
ruff check .            # All checks passed!
ruff format --check .   # 90 files already formatted
python -m pytest        # 581 passed (v0.6 561개 → 581개, 보완 포함)
docker compose config -q  # 통과 (키 환경변수 뺀 뒤)
```

Streamlit 1.66.1.

## 요구사항별 확인

| ID | 확인 내용 | 테스트 | 결과 |
| --- | --- | --- | --- |
| F1 | 어두운 테마 제목 흰색, 밝은 테마 검정, 3.4rem | `test_title_is_white_and_larger_in_dark_theme` | 통과 |
| F2 | 키 칸 제목이 한 줄(큰 제목 아님), 발급 링크, 입력란 이름 숨김 | `test_key_card_is_one_line_title_and_input`, v0.6 키 테스트 3개 | 통과 |
| F3 | 수집 카드에 "요청 간격" 글 없음 | `test_collect_card_has_no_site_interval_note` | 통과 |
| F4 | 체크 글자·버튼 줄바꿈 금지 CSS | `test_css_wraps_many_keywords_and_keeps_card_text` | 통과 |
| F5 | 결과·할 일은 알림, 결과 칸·할 일 칸 없음, 다시 그려도 알림 한 번. 문제 있을 때만 빨간 칸·자세히(escape) | `test_finished_job_without_problems_shows_only_toast_once`, `test_finished_job_shows_problems_and_folded_details`, `test_failed_job_shows_error` | 통과 |
| F6 | 점수 없으면 TOP 5 칸 없음, 있으면 보임 | `test_chart_only_when_scored_postings_exist`, `test_chart_shows_with_scored_posting` | 통과 |
| F7 | 키워드 줄바꿈 CSS | `test_css_wraps_many_keywords_and_keeps_card_text` | 통과 |
| F8 | 띄어쓰기·대소문자만 다른 항목 하나만, 기존 목록과도 비교, 프롬프트 규칙 | `tests/test_resume.py` 새 테스트 3개 | 통과 |
| F9 | 프로필 칸 높이 맞춤 CSS | `test_css_wraps_many_keywords_and_keeps_card_text` | 통과 |
| F10 | 전송 안내가 파일 칸 도움말에 있음 | `test_resume_section_notes_llm_transfer_and_disables_button_without_files` | 통과 |
| F12 | 키가 섞인 오류 글을 가림(두 제공자), 짧은 값은 안 가림, 작업 오류·실패/멈춤 줄에서 가림 | `test_redact_hides_key_in_any_text`, `test_redact_leaves_text_without_key_and_ignores_short_values`, `test_error_text_hides_key_in_unknown_error`, `test_failure_lines_hide_key` | 통과 |
| F13 | compose에 키 환경변수 없음 | `test_compose_does_not_pass_key_as_environment` | 통과 |
| F14 | 삭제 버튼 → 파일·환경에서 지움, 입력 칸 다시 뜸, AI Studio 안내. `.env` 키는 파일 안 건드리고 이번 실행에서만 뺌 | `test_key_card_deletes_key_from_this_pc`, `test_delete_removes_saved_key_and_environment`, `test_delete_key_from_dotenv_only_clears_this_run` | 통과 |

바뀐 결정(F5, F10)에 맞춰 고친 기존 테스트: 결과 칸 테스트 2개를 알림 테스트 2개로 바꿈, 전송 안내 위치를 도움말로 바꿈, 평가 줄 순서 테스트에 점수 있는 공고를 넣음(F6로 점수 없으면 차트가 없어서).

### 보완 (F15–F20)

| ID | 확인 내용 | 테스트 | 결과 |
| --- | --- | --- | --- |
| F15 | 보는 칸 이름 앞 ✓, 굵은 테두리 CSS | `test_postings_tab_shows_guide_summary_and_scored_cards`, `test_sidebar_filter_is_a_card_and_selected_tile_is_marked` | 통과 |
| F16 | 진행 막대 없이 끝난 작업도 한 번 다시 읽고, 같은 작업은 다시 안 읽음 | `test_finished_job_rereads_rows_once_even_without_progress_bar` | 통과 |
| F17 | 키 없으면 키 창 한 번·"🔑 키 넣기", 저장·틀린 키·키 있으면 끝 4자리 버튼·창에서 삭제 | `test_key_dialog_opens_once_when_no_key_and_saves_to_data_folder`, `test_key_dialog_rejects_bad_key_without_saving`, `test_key_button_shows_masked_key_and_no_dialog_when_key_exists`, `test_key_is_a_top_button_not_a_card`, `test_key_card_deletes_key_from_this_pc` | 통과 |
| F18 | 프로필 비면 펼침, 있으면 접힘 | `test_resume_box_is_open_for_empty_profile_and_folded_otherwise` | 통과 |
| F19 | 4rem, 형광 줄 없음 | `test_title_is_white_and_larger_in_dark_theme` | 통과 |
| F20 | 사이드바 바탕·필터 카드 | `test_sidebar_filter_is_a_card_and_selected_tile_is_marked` | 통과 |

### 보완 (F21–F23)

```bash
ruff check .            # All checks passed!
ruff format --check .   # 93 files already formatted
python -m pytest        # 584 passed (581개 → 584개)
```

| ID | 확인 내용 | 테스트 | 결과 |
| --- | --- | --- | --- |
| F21 | `-on` 칸 면·글자 CSS, 밝은 테마 검정·흰색, 두 테마 모두 고른 칸 색이 요약 칸 4색과 다름 | `test_selected_tile_inverts_colors` | 통과 |
| F22 | 어두운 테마 순백 글자·순흑 바탕 없음, 두 테마 색 이름 같음, 배지가 팔레트 변수, config.toml 값이 팔레트와 같음 | `test_dark_theme_avoids_glare_and_badges_follow_theme`, `test_css_follows_theme_and_guide_mentions_theme`(새 색으로 고침) | 통과 |
| F23 | 명세에 `params`·selection 없음, 높은 점수 위, 화면에 vega-lite 차트 하나 | `test_top5_chart_is_static` | 통과 |

### 보완 (F24–F25)

```bash
ruff check .            # All checks passed!
ruff format --check .   # 93 files already formatted
python -m pytest        # 588 passed (584개 → 588개)
```

| ID | 확인 내용 | 테스트 | 결과 |
| --- | --- | --- | --- |
| F24 | 전체 초기화 → 🔄 → 파일 값 복구·파일 그대로, 저장 안 한 입력·이력서 값 버림, 파일 없을 때 오류 없음 | `test_refresh_restores_saved_profile_after_clear_all`, `test_refresh_drops_unsaved_typing_and_resume_fill`, `test_refresh_without_profile_file_keeps_empty_form` | 통과 |
| F25 | 모든 색이 `light-dark(밝은, 어두운)`, 사용법 메뉴 이름 | `test_css_lets_browser_pick_theme`, 색 값 테스트 3개(새 형식으로 고침) | 통과 |

F17로 키 칸 테스트 3개를 창 테스트로 바꿈. 테스트 화면은 기본으로 가짜 키가 있는 상태로 띄움(키가 없으면 키 창이 먼저 떠서 사용법 창 테스트가 달라짐).

F16 재현 시도: 평가를 가짜로 바꾼 화면(한 건 2초, 0초 두 경우)에서 Playwright로 "평가 전 전부 평가"를 눌렀을 때 두 경우 모두 끝나자마자 점수가 보였음. 재리 PC에서 생긴 조건은 재현 못 함.

## 브라우저 확인

작업 환경에서 `streamlit run app.py`(DB 저장, SQLite, 공고 3건·키 없음)를 띄우고 Playwright Chromium으로 봤다.

| 창 | 확인 | 결과 |
| --- | --- | --- |
| 1400px 어두운 | 제목 흰색·크게, 키 칸 2줄·제목과 간격, 수집 카드 제목만, 카드 체크·점수 한 칸 | 확인 |
| 900px 어두운(사이드바 열림) | 카드 "평가" 글자·점수·별점·지원함/관심 없음 버튼이 잘리지 않음, 회사·직무 칸 유지, 평가 줄 버튼 글자 다 보임 | 확인 |
| 1400px 밝은·어두운 프로필 | 다룰 수 있음 키워드 12개가 4줄로 모두 보임, 기술·경력 / 방향·문화 칸 높이 같음, 이력서 칸 제목·파일 칸·버튼 한 줄 | 확인 |
| 1400px 밝은(보완) | 처음 열면 키 창, 오른쪽 위 "🔑 키 넣기"(초록)·사용법·새로고침 한 줄, 제목 4rem·형광 줄 없음, 보는 칸 "✓ 전체 공고"·굵은 테두리, 사이드바 바탕·필터 카드, 프로필 이력서 칸 접힘 | 확인 |
| 1300px 밝은·어두운(보완 3차) | "평가 완료" 눌렀을 때 그 칸만 검정(밝은)·밝은 회색(어두운) 면, 나머지 3칸 색 유지, 어두운 테마 카드·배지·차트 톤, TOP 5 공고 이름이 잘리지 않음 | 확인 |
| 1300px(보완 4차) | 프로필 키워드 19개 → 전체 초기화 0개 → 🔄 새로고침 19개(고치기 전에는 0개 그대로, F5만 복구) | 확인 |
| 1300px(보완 4차) | 열어 둔 채 시스템 테마 밝은 → 어두운 → 밝은, ⋮ 메뉴 Dark → Light, 메뉴 Light로 고른 뒤 시스템 어두운: 요약 칸·바탕 색이 F5 없이 그때마다 맞게 바뀌고, 메뉴에서 고른 테마가 시스템보다 우선 | 확인 |
| 900px | 수집 카드 사이트 칸 키워드가 줄을 바꿔 보임(칸이 좁아 "잡코…"처럼 끝이 줄어듦) | 확인 |

## 미확인

- **F16 원인**: 재리 PC에서 갱신이 안 된 조건을 재현하지 못함. 놓칠 수 있는 길을 막았지만 같은 증상이 다시 나면 조건(시트/DB, 평가 건수, 탭) 확인 필요.
- **알림(F5) 실제 화면**: AppTest로만 확인. 실제 수집을 돌려 브라우저에서 알림이 뜨는 모습은 보지 않음.
- **실제 이력서 여러 개로 중복 합치기(F8)**: 프롬프트 규칙의 효과는 실제 Gemini로 확인 못 함. 코드 합치기는 테스트로 확인.
- **재리 PC Windows 브라우저**: 재리 확인 필요. 어두운 테마 색(F22)이 눈에 편한지는 재리 판단 필요.
- **F25 재리 PC 브라우저 판**: `light-dark()`는 Chrome·Edge 123 이상 필요. 작업 환경 Chromium으로만 확인.
- **F23 끌기·확대 직접 조작**: 명세에 `params`가 없는 것으로 확인. 브라우저에서 휠·끌기를 직접 해 보지는 않음.
- **F12 범위**: 화면·결과 문구만 가림. 터미널(`main.py`)에서 잡지 못한 예외의 traceback, 라이브러리가 남기는 로그는 가리지 않음. 실제 Gemini 오류에 키가 섞이는지는 확인 못 함.
- **Docker 이미지에서 `showErrorDetails=type`**: CI의 Docker 빌드로만 확인(설정 이름은 Streamlit 1.66 코드에서 확인).
- **README F11 Cloud 콘솔 메뉴 이름**: 실제 화면에서 확인 못 함.

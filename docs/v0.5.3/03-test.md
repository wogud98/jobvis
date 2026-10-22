# v0.5.3 테스트

2026-10-22 실행. 구글 시트·LLM은 가짜로 바꿨다. 실제 키·시트는 쓰지 않았다. 파일은 임시 폴더에서만 쓰고 읽었다.

## 실행한 명령

```bash
ruff check .            # All checks passed!
ruff format --check .   # 72 files already formatted
python -m pytest        # 503 passed (v0.5.2 PR #34 뒤 → 503개)
```

Streamlit 1.66.0. 새 테스트: `tests/test_view.py`, `tests/test_sheets.py`, `tests/test_app.py`에 추가.

## 요구사항별 확인

| ID | 확인 내용 | 테스트 | 결과 |
| --- | --- | --- | --- |
| F1, F6 | 점수 막대 3개(문화 "-"는 없음), 70↑·40–69·40↓ 색 | `test_scored_details_show_bars_columns_bullets_chips_and_guide`, `test_scores_strengths_gaps_on_card` | 통과 |
| F2 | 강점·부족한 점 두 칸 글머리표 | `test_scored_details_show_bars_columns_bullets_chips_and_guide` | 통과 |
| F3 | 쉼표·줄바꿈·" · "·" / "로 나눔, 붙은 /·는 그대로, 빈 칸 숨김 | `test_split_items`(7가지), `test_scored_details_show_bars_columns_bullets_chips_and_guide` | 통과 |
| F4 | 내 기술 초록 칩, 대소문자·공백 무시 | `test_stack_chips_mark_my_skills_ignoring_case_and_spaces`, `test_scored_details_show_bars_columns_bullets_chips_and_guide` | 통과 |
| F5 | 접힌 "점수 기준", 0–100·가중 평균 글 | `test_scored_details_show_bars_columns_bullets_chips_and_guide` | 통과 |
| F7 | D-n·D-day·마감 배지, 상시·빈칸은 없음, 지난 공고 흐림 | `test_deadline_badge`, `test_deadline_badges_and_closed_card_is_dimmed` | 통과 |
| F8 | 마감 임박 순: 남은 날 → 날짜 없음 → 지난 공고 | `test_sort_by_deadline_soonest_then_open_then_closed`, `test_deadline_badges_and_closed_card_is_dimmed` | 통과 |
| F9, N3 | 지난번 연 시각 뒤 저장은 NEW, 처음엔 없음, 파일 갱신, 깨진·못 쓰는 파일 무시 | `test_is_new_and_last_seen_file`, `test_last_seen_broken_or_unwritable_is_ignored`, `test_new_badge_uses_last_visit_and_updates_it`, `test_first_visit_has_no_new_badge` | 통과 |
| F10 | 회사명·직무 검색, 대소문자 무시 | `test_search_matches_company_or_title_all_words`, `test_search_filters_by_company_and_title` | 통과 |
| F11 | 지원함 버튼 → AE 칸만 씀, 배지, 취소, "지원한 공고만 보기", 실패 시 그대로 두고 경로 숨긴 오류 | `test_applied_only_and_override`, `test_set_applied_writes_applied_column_only`, `test_v052_header_is_extended_with_applied_column`, `test_apply_button_marks_card_and_applied_filter`, `test_apply_failure_shows_error_without_secret` | 통과 |
| F12 | 점수 있을 때만 카드 머리에 첫 강점 | `test_card_head_shows_first_strength_only_when_scored` | 통과 |
| F13, F14 | 테마별 CSS 변수(어두운 바탕 #16181d), 사용법에 Theme 안내 | `test_css_follows_theme_and_guide_mentions_theme` | 통과 |

## 화면 확인

가짜 시트로 `streamlit run`을 띄우고 Playwright Chromium(`color_scheme` light·dark)으로 열어 봤다. 시스템 설정에 따라 밝은·어두운 테마가 바뀌고, 자세히(막대, 두 칸, 글머리표, 칩), 배지(D-3, NEW, 지원함)가 보이는 것을 눈으로 확인했다. 이때 강점 "Python·LangGraph 프로젝트 경험"이 가운뎃점에서 잘리는 것을 보고 붙은 가운뎃점은 나누지 않도록 고쳤다(F3).

## 미확인

- 실제 구글 시트에 AE "지원" 열이 붙는지, 예전 30열 시트가 늘어나는지
- 윈도우 브라우저에서 시스템 다크 모드·⋮ → Settings → Theme 전환
- 실제 LLM 결과 글(요약·업무·우대)이 글머리표로 자연스럽게 나뉘는지
- 같은 PC에서 여러 브라우저 탭을 열 때 NEW 기준(먼저 연 탭이 파일을 갱신함)

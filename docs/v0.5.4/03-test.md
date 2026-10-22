# v0.5.4 테스트

2026-10-22 실행. 구글 시트·LLM은 가짜로 바꿨다. 실제 키·시트는 쓰지 않았다. 파일은 임시 폴더에서만 쓰고 읽었다.

## 실행한 명령

```bash
ruff check .            # All checks passed!
ruff format --check .   # 73 files already formatted
python -m pytest        # 511 passed (v0.5.3 503개 → 511개)
```

Streamlit 1.66.0.

## 요구사항별 확인

| ID | 확인 내용 | 테스트 | 결과 |
| --- | --- | --- | --- |
| F1 | 검색·정렬·보기 토글 5개가 사이드바에 있음 | `test_filters_live_in_sidebar` | 통과 |
| F2, F3 | 이미지 필요 필터와 요약 칸이 같은 기준(본문 미확보·이미지 일부, 공고 번호 있음) | `test_image_only_keeps_missing_and_partly_unread_with_id`, `test_summary_counts_whole_sheet`, `test_postings_tab_shows_guide_summary_and_scored_cards` | 통과 |
| F4 | 8일 이상 남으면 흰 D-n, 7일 이하 빨강, 지나면 마감 | `test_deadline_badge`, `test_deadline_badges_and_closed_card_is_dimmed` | 통과 |
| F5, F6 | 자세히는 popover, 펼쳐 두기 → 카드 안 고정, 접기 → 되돌림 | `test_pin_keeps_details_open_in_card`, `test_postings_tab_shows_guide_summary_and_scored_cards` | 통과 |
| F7, F8 | 이미지 필요 배지와 도움말, 넣는 순서 안내 | `test_image_badge_and_upload_steps` | 통과 |
| F9 | 처음 열면 사용법 창, 전에 열었으면 안 뜸, 버튼으로 열림, 화면에 사용법 칸 없음 | `test_postings_tab_shows_guide_summary_and_scored_cards`, `test_guide_dialog_opens_on_first_visit_and_by_button`, `test_run_panel_shows_collect_and_score_cards` | 통과 |
| F10 | 신뢰 배지 도움말에 기준과 최대 69점 | `test_trust_badge_has_criteria_tooltip` | 통과 |
| F11, F13 | 어두운 테마 바탕·칸·요약 칸 색 변수 | `test_css_follows_theme_and_guide_mentions_theme` | 통과 |
| F12 | 칸 글 누르면 그 필터만 켜짐, 앞 필터 풀림, 전체 공고는 검색까지 풂, 적용 칸 표시 | `test_summary_text_applies_its_filter_and_marks_tile`, `test_recommended_only_keeps_strong_and_recommended` | 통과 |

## 화면 확인

가짜 시트로 `streamlit run`을 띄우고 Playwright Chromium(`color_scheme` light·dark)으로 열어 봤다.

- 사이드바 필터가 보임.
- 이미지 필요 칸의 글을 누르면 필터가 켜지고 칸에 초록 테두리가 생김.
- 자세히 창이 뜨고, 바깥을 누르면 닫힘.
- 사용법 버튼을 누르면 새 창이 뜸.
- 어두운 테마에서 바탕보다 칸이 밝게 구분되고, 요약 칸이 짙은 톤으로 보임.

이때 요약 칸 글 버튼에 일반 버튼 테두리가 남는 것을 보고 CSS 우선순위를 고쳤다.

## 미확인

- 윈도우 브라우저에서 사이드바 접기·펼치기, 자세히 창 바깥 누르기
- 자세히 창 안에서 이미지 파일을 끌어다 놓을 때 창이 열린 채로 남는지(브라우저에서 파일 끌어다 놓기는 시험하지 못함)
- 처음 연 PC(`data/last_seen.txt` 없음)에서 사용법 창이 한 번만 뜨는지

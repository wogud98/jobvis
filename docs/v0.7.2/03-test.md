# v0.7.2 테스트

2026-10-23 실행.

## 실행한 명령

```bash
ruff check .            # All checks passed!
ruff format --check .   # 107 files already formatted
python -m pytest        # 686 passed (682개 → 686개)
```

작업 환경에서 `streamlit run app.py`(SQLite DB, 가짜 키, 공고 5건)를 띄우고 Chromium(Playwright)으로 1100·1280·1600px, 높이 600·700·900px, 밝은·어두운 테마, "움직임 줄이기"를 확인함.

## 요구사항별 확인

| ID | 확인 내용 | 테스트·명령 | 결과 |
| --- | --- | --- | --- |
| F1 | 사이드바 필터 → 평가 → 공고 초기화 순서 | `test_score_bar_sits_below_filters_in_sidebar`, Chromium | 통과 |
| F2 | 900px 창에서 사이드바 스크롤 없음, 안내 글은 버튼 도움말, 공고 초기화는 버튼 하나 | `test_score_bar_sits_below_filters_in_sidebar`, `test_reset_is_one_button_with_help`, Chromium(사이드바 scrollHeight 900 = clientHeight 900, v0.7.1은 909) | 통과 |
| F3 | 보기 칸 하나(7개), 평가 전 공고만(제외 공고는 뺌), 요약 칸이 보기 칸을 바꿈 | `test_filters_live_in_sidebar`, `test_view_select_shows_unscored_cards_only`, `test_unscored_only_shows_only_cards_before_scoring`, `test_summary_text_applies_its_filter_and_marks_tile`, `test_hide_card_moves_it_to_hidden_view_and_back`, `test_apply_button_marks_card_and_applied_filter` | 통과 |
| F4 | 추천 키워드 버튼 없음, 글자 칸은 그대로 남음 | `test_keyword_text_box_stays_without_suggestion_buttons`, `test_run_panel_shows_collect_and_score_cards` | 통과 |
| F5 | 소개 문장 "채용공고를 모아 나와 비교!" 한 줄 | `test_hero_tagline`, Chromium(1100·1600px 모두 높이 한 줄 25.6px, 넘침 없음) | 통과 |
| F6 | "AI 취업 비서" 없음, 제목 크게·한 줄 | `test_hero_tagline`, `test_title_is_lime_with_dark_edge_and_large`, Chromium(66px·76.8px·83.2px, 셋 다 scrollWidth = clientWidth) | 통과 |
| F7 | Footer 세 줄, ✦ hover 시 이스터에그 | `test_footer_is_three_lines_with_easter_egg`, `test_footer_shows_use_notice_and_version`, Chromium(문장 opacity 0 → hover 1) | 통과 |
| F8 | 자세히를 누르면 카드 윗단으로 움직이고 아래로 열림, 닫을 때는 그대로 | `test_more_button_scrolls_card_up_and_buttons_tint_on_hover`, Chromium(공고 5건 각각 맨 위에서 눌러 봄: 높이 900·700px 모두 5건 아래로 열림, 움직임 줄이기에서도 아래) | 통과 |
| F9 | 보통 버튼·자세히 hover 시 살짝 라임 빛, 지우는 버튼은 빨강 유지 | 같은 테스트, Chromium(지원함·자세히 rgb(246,244,238) → 라임 섞인 색, 어두운 테마도 바뀜, 공고 초기화 hover rgb(229,56,59)) | 통과 |
| F10 | 자세히를 내리면 형광 띠가 글과 같이 올라감 | Chromium(높이 600px 창, 자세히 칸 120px 내림 → 띠가 사라지고 글이 겹치지 않음, `background-attachment: local, local`) | 통과 |
| F11 | 기술 모아보기 두 탭 높이 같음 | `test_stats_tabs_have_same_height_and_filter_title_is_plain`, Chromium(탭 바꿔도 창 크기 그대로) | 통과 |
| F12 | 필터 제목 옆 글 없음 | `test_stats_tabs_have_same_height_and_filter_title_is_plain` | 통과 |
| F13 | 경력 슬라이더 0–10년, 저장된 12년은 그대로 | `test_years_slider_goes_to_ten_unless_saved_value_is_larger` | 통과 |
| N1 | 새 의존성 없음 | `requirements.txt` 그대로 | 통과 |
| N2 | 움직임 줄이기면 바로 이동 | `test_more_button_scrolls_card_up_and_buttons_tint_on_hover`, Chromium(`reduced_motion="reduce"`로 아래로 열림) | 통과 |
| N3 | 두 테마 hover 색·Footer | Chromium 밝은·어두운 | 통과 |

## 구현 중 바뀐 것

- 제목 크기: 처음 5.2rem 고정은 1100px 창에서 "JOBVI / S"로 갈라짐(Chromium 확인). `clamp(3.6rem, 6vw, 5.2rem)` + 줄바꿈 없음으로 바꿈. `02-design.md` D6.
- 재리 추가 의견(03:02–03:05)을 같은 PR에 넣음: 형광 띠 겹침(F10), 모아보기 탭 높이(F11), 필터 옆 글(F12), 경력 10년(F13).
- `runner.keyword_options`와 그 테스트 2개를 지움. 추천 키워드 버튼을 없애 쓰는 곳이 없어짐(F4). 테스트를 약하게 한 것이 아니라 기능 자체를 뺌.

## 미확인

- 재리 PC(Windows)·Docker 이미지, Safari·Firefox에서의 자세히 스크롤·hover 색(`color-mix`는 오래된 브라우저에서 색이 안 바뀔 수 있음).
- 공고가 아주 많은 목록에서 맨 아래 공고: 더 내려갈 곳이 없으면 위로 열릴 수 있음(시험 데이터 5건에서는 모두 아래).
- v0.7 미확인(실제 Gmail 발송 등)은 그대로.

# v0.7.1 테스트

2026-10-23 실행.

## 실행한 명령

```bash
ruff check .            # All checks passed!
ruff format --check .   # 105 files already formatted
python -m pytest        # 682 passed (673개 → 682개)
```

작업 환경에서 `streamlit run app.py`(SQLite DB, 가짜 키, 가짜 메일 설정, 공고 5건)를 띄우고 Chromium(Playwright)으로 1100·1280·1600px, 밝은·어두운 테마, "움직임 줄이기"를 켠 상태를 확인함.

## 요구사항별 확인

| ID | 확인 내용 | 테스트·명령 | 결과 |
| --- | --- | --- | --- |
| F1 | 글자 칸에 치고 다른 곳을 눌러도 남음, 추천 버튼 8개(프로필 직무·주력 기술 먼저), 누르면 칸에 들어가고 버튼은 비워짐, 그 값으로 수집 | `test_keyword_pick_fills_text_box_and_typed_keyword_stays`, `test_keyword_picks_put_profile_jobs_and_main_skills_first`, `test_collect_button_starts_collect_with_inputs`, Chromium("데이터 엔지니어" 입력 → 제목 클릭 → 그대로, "Python" 버튼 → 칸에 Python) | 통과 |
| F2 | 버튼·창 이름 "✉ 공고 메일 보내기", "📊 기술 모아보기" | `test_top_buttons_have_clear_names_and_dialog_titles`, `test_mail_dialog_title_matches_button` | 통과 |
| F3 | 요약 한 줄, 탭 두 개, 위 10개, 막대 시작점 같음 | `test_stats_dialog_has_summary_and_two_tabs`, `test_stack_rank_shows_top_ten`, Chromium(막대 10개 모두 x=204에서 시작) | 통과 |
| F4 | 평가 줄이 사이드바 필터 위, 목록 위에는 없음, 0건이면 한 줄 | `test_score_bar_sits_at_top_of_sidebar`, `test_score_bar_is_one_line_without_targets`, Chromium | 통과 |
| F5 | 사용법에 메일·모아보기 줄, 키 받기 접힌 칸 두 개(발급 주소) | `test_guide_has_mail_stats_and_folded_key_steps`, `test_guide_is_three_basic_steps_and_extras`(10줄 이하) | 통과 |
| F6 | 지우는 버튼 6개 hover 빨강 | `test_css_danger_hover_animations_and_reduced_motion`, Chromium(🗑 공고 초기화: 밝은 rgb(229,56,59)·어두운 rgb(196,60,60), 글자 흰색) | 통과 |
| F7 | "초록은 …" 글 없음, 초록 칩 도움말 | `test_scored_details_show_bars_columns_bullets_chips_and_guide`, `test_stats_dialog_ranks_stack_and_gaps_of_shown_cards`, Chromium(자세히 칩 title "내 프로필에 있는 기술") | 통과 |
| F8 | 탭을 바꾸면 `jv-rise` 0.2초 | `test_css_danger_hover_animations_and_reduced_motion`, Chromium(👤 프로필 누른 직후 `jv-rise` 실행 중) | 통과 |
| F9 | 도넛 `jv-fill`, 막대 `jv-grow`, 카드 hover 들림 | 같은 테스트, Chromium(도넛 animationName `jv-fill`, 기술 모아보기 막대 열자마자 scaleX 0.59 → 끝나면 none, 카드 hover `translate(-2px,-2px)`·그림자 8px) | 통과 |
| F10 | Footer 이용 안내·버전 | `test_footer_shows_use_notice_and_version`, Chromium(밝은·어두운 테마 글자 읽힘) | 통과 |
| F11 | 자세히 열 때 위에서 아래로 펼침, 끝나면 `clip-path` 없음 | Chromium(연 직후 `inset(0 0 51%)`, 0.6초 뒤 `none`) | 통과 |
| F12 | 위 버튼 글자 13.6px, 높이 32px, 두 줄 오른쪽 정렬, 잘림 없음 | Chromium 1100·1280·1600px(다섯 버튼 모두 scrollWidth ≤ clientWidth, 두 줄 유지) | 통과 |
| N1 | 새 의존성 없음 | `requirements.txt` 그대로 | 통과 |
| N2 | 움직임 줄이기면 애니메이션·들림 없음 | `test_css_danger_hover_animations_and_reduced_motion`, Chromium(`reduced_motion="reduce"`: 탭·도넛·자세히 `none`, 카드 hover `none`) | 통과 |
| N3 | 두 테마 빨간 버튼·Footer | `PALETTES` 두 테마에 `danger`, Chromium 밝은·어두운 | 통과 |

## 구현 중 바뀐 것

- 탭 칸 선택자: 설계 초안의 `[data-baseweb="tab-panel"]`은 Streamlit 1.66에 없음. Chromium에서 `[data-testid="stTabPanel"]`을 확인해 바꿈. `02-design.md` 갱신.
- 위 버튼: 처음 1:1 칸에서 1100px 창이 첫 줄을 세 줄로 나눔. 칸을 1:1.25로, 줄바꿈 없음(`wrap=False`)으로 바꿔 1100–1600px에서 두 줄 유지.
- 자세히 항목 점수 막대: 시험 데이터에 항목 점수가 없어 자세히 안 막대는 브라우저로 못 봄. 같은 CSS 규칙(`.jv-bar > div`)을 쓰는 기술 모아보기 막대로 확인.

## 미확인

- 재리 PC(Windows)·Docker 이미지에서의 모양과 애니메이션.
- Safari·Firefox(작업 환경은 Chromium만). `@property`가 없는 오래된 브라우저는 도넛이 채움 효과 없이 바로 보임.
- v0.7 미확인(실제 Gmail 발송 등)은 그대로.

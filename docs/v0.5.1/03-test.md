# v0.5.1 테스트

2026-10-21 실행. 구글 시트는 가짜로 바꿨다. 실제 시트·키는 쓰지 않았다. 파일은 임시 폴더에서만 쓰고 읽었다.

## 실행한 명령

```bash
ruff check .            # All checks passed!
ruff format --check .   # 통과
python -m pytest        # 344 passed (v0.5 328개 → 344개)
```

Streamlit 1.66.0. 화면은 `streamlit.testing.v1.AppTest`(`tests/test_app.py`)로 확인했다. 그 밖에 실제 `app.py`에 가짜 시트 줄 6개와 예시 프로필을 넣어 `streamlit run`(헤드리스, localhost)으로 띄우고 크로미움으로 화면을 찍어 봤다. 이 실행은 테스트가 아니라 눈으로 본 확인이다.

## 요구사항별 확인

| ID | 확인 내용 | 테스트 | 결과 |
| --- | --- | --- | --- |
| F1, F7 | 두 탭 맨 위 "사용법" 토글 | `test_postings_tab_shows_guide_summary_and_scored_cards`, 화면 캡처 | 통과 |
| F2 | 요약 칸 4개 수, 필터와 상관없이 전체. 빈 시트·평가 전만 | `test_summary_counts_whole_sheet`, `test_summary_of_empty_or_unscored_sheet`, AppTest 요약 칸 값 | 통과 |
| F3 | 차트 2 : 필터 1 | 화면 캡처 | 눈으로 확인 |
| F4 | 카드 머리(점수·회사 · 직무·배지)와 "자세히" 펼침 | `test_postings_tab_shows_guide_summary_and_scored_cards` | 통과 |
| F5 | 신뢰 배지 색, 신뢰 낮음 흐리게 | 같은 테스트(`jv-low`), 흐림은 화면 캡처 | 통과, 흐림은 눈으로 확인 |
| F6 | 평가 전 카드 점수 "-" | `test_unscored_card_shows_dash_and_sheet_text_is_escaped` | 통과 |
| F8 | 필수 칸 배지, 입력하면 바로 바뀜 | `test_required_status_badges`, `test_profile_tab_saves_valid_profile` | 통과 |
| F9 | 4묶음, 모든 칸이 한 묶음에 | `test_every_file_field_has_one_input_in_a_group`, 화면 캡처 | 통과 |
| F10, F11 | 고르기 칸, 파일에만 있는 값이 보기에 남고 선택됨 | `test_options_keep_file_values_not_in_suggestions`, `test_profile_tab_shows_file_values_not_in_suggestions`, `test_single_text_in_pick_field_becomes_one_item` | 통과 |
| F12 | 문화 고르기 + 직접 적기, 파일 항목 잃지 않음, 겹치면 한 번 | `test_culture_splits_into_picked_and_own_lines_without_losing_items`, `test_culture_picked_and_typed_same_item_is_saved_once` | 통과 |
| F13 | 학력 나누기·합치기, 형식 다른 글자는 전공 칸에 | `test_split_degree`(5가지), `test_join_degree_round_trip_and_blanks`, AppTest 학력 고르고 저장 | 통과 |
| F14, F15 | 예시 문구, 도움말 | 화면 캡처 | 눈으로 확인 |
| F16 | 저장, 필수 칸 없으면 저장 안 함, 깨진 파일 유지 | `test_profile_tab_saves_valid_profile`, `test_profile_tab_does_not_save_without_required_fields`, `test_profile_tab_keeps_broken_file`, `test_form_without_required_fields_is_rejected` | 통과 |
| F17–F20 | 테마, 글래스 카드, 벤토 배치, 머리 | 화면 캡처 | 눈으로 확인 |
| N1 | 새 의존성 없음 | `requirements.txt` 변경 없음 | 통과 |
| N2 | `profile.yaml` 형식 같음. 예시 파일 왕복이 v0.5 `load`와 같은 Profile | `test_form_round_trip_from_example_file` | 통과 |
| N4 | 규칙은 Streamlit 밖 함수 | `test_profile_form.py`, `test_view.py` | 통과 |
| - | 시트 글자를 HTML로 그대로 넣지 않음 | `test_unscored_card_shows_dash_and_sheet_text_is_escaped` | 통과 |

v0.5의 입력란 테스트 4개(`test_user_profile.py`)는 함수가 `profile_form`으로 옮겨 가서 `test_profile_form.py`로 옮기고, 목록 칸이 줄 글자에서 고르기로 바뀐 만큼 입력 값을 바꿨다. 검사 내용(왕복, 틀린 값, 빈 줄 지움, 필수 칸 없음)은 그대로다.

코드를 일부러 고장 내서 테스트가 잡는지 봤다. 모두 되돌린 뒤 다시 344개 통과했다.

| 고장 낸 곳 | 실패한 테스트 수 |
| --- | --- |
| 파일에만 있는 값을 보기에서 뺌 | 2 |
| 카드 머리 escape를 끔 | 1 |
| 학력 이름 뒤 쉼표 검사를 끔 | 1 |
| "추천 이상"을 평가 완료 수로 셈 | 1 |

## 보완 확인 (F21–F22)

2026-10-21 보완 PR. CSS만 바꿔서 pytest로는 잡지 못한다. 가짜 시트 줄로 실제 `app.py`를 `streamlit run`(헤드리스)으로 띄우고 Playwright + 크로미움으로 확인했다.

| ID | 확인 방법 | 결과 |
| --- | --- | --- |
| F21 | 종합점수 카드와 필터 카드의 화면 높이(`getBoundingClientRect().height`)를 잼 | 둘 다 309.6px, 같음 |
| F22 | 필터 "출처"의 "사람인" 키워드 왼쪽 끝(글자 위, x에서 먼 곳)을 마우스로 누름 | 키워드가 지워짐(남은 수 0) |
| F22 | 프로필 "주력 기술"의 키워드에 마우스를 올림 | 어둡게 바뀌고 취소선 보임(캡처) |

`ruff check .`, `ruff format --check .`, `python -m pytest`(344 passed)도 다시 통과했다.

## 미확인

- 윈도우 PC 브라우저에서 글래스 흐림(`backdrop-filter`)과 글자 대비, 실제 시트 줄로 본 화면.
- 고르기 칸에 목록에 없는 값을 입력해 추가하는 동작(`accept_new_options`). AppTest로는 보기에 있는 값만 넣어 봄.
- 신뢰 낮음 카드 흐림은 CSS라 테스트로는 못 잡고 캡처로만 봄.
- 키워드 눌러 지우기와 높이 맞추기를 윈도우 PC 브라우저(엣지·크롬)에서. `:has()` 선택자는 최근 크롬·엣지에서 지원됨.

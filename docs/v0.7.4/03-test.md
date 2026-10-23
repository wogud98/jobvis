# v0.7.4 테스트

2026-10-23 실행.

## 실행한 명령

```bash
ruff check .            # All checks passed!
ruff format --check .   # 118 files already formatted
python -m pytest        # 706 passed (695개 → 706개)
```

작업 환경에서 `streamlit run app.py`(SQLite DB, 가짜 키, 가짜 공고 5건)를 띄우고 Chromium(Playwright, 1280×860·900×860, 밝은·어두운 테마)으로 기술 모아보기·메일 창을 확인함.

## 요구사항별 확인

| ID | 확인 내용 | 테스트·명령 | 결과 |
| --- | --- | --- | --- |
| F1 | 2건 이상만 막대, 1건은 이름순 칩 묶음(내 기술 초록), 모두 1건이면 막대 없음 | `test_stats_dialog_ranks_only_repeated_skills_and_chips_the_rest`, `test_stats_dialog_lists_every_skill_in_scroll_box`, `test_split_once_keeps_order_of_repeated_and_sorts_single_by_name`, Chromium(막대 1줄 + 칩 15개) | 통과 |
| F2 | 모두 고르기 버튼 글자 둘레 여유 | `test_mail_dialog_is_wider_and_list_stays_one_line`, Chromium 화면 | 통과 |
| F3 | 메일 창 medium(752px), 긴 공고 줄도 한 줄(말줄임) | 같은 테스트, Chromium(일부러 긴 제목을 넣어도 줄 높이 21px, 1280·900px 창 모두) | 통과 |
| F4 | CSV 내려받기, BOM, 쉼표 든 이름, 내려받아도 창 그대로 | `test_stats_csv_opens_in_excel_with_korean`, `test_stats_csv_quotes_names_with_commas`, `test_stats_dialog_saves_csv_and_copies_text`, Chromium(파일 `jobvis-기술모아보기.csv`, 첫 바이트 EF BB BF, 창 열린 채) | 통과 |
| F5 | 전체 복사 글(1건 한 줄, 없음), 누르면 "✓ 복사했습니다" | `test_stats_text_groups_single_postings_in_one_line`, `test_stats_text_without_items_says_none`, `test_stats_dialog_saves_csv_and_copies_text`, `test_stats_dialog_without_postings_has_no_export_buttons`, Chromium(클립보드 글 읽어 확인) | 통과 |
| F6 | 받은함 카드·단어 없음, 버튼 하나, 이미지 넣기 전엔 누를 수 없음, OCR 없으면 안내만 | `test_image_badge_and_upload_steps`, `test_upload_without_ocr_shows_install_hint_only` | 통과 |
| F7 | 저장 → 읽기 → 그 공고만 다시 평가(점수 있고 체크 안 된 공고도, 다른 체크한 공고는 아님) | `test_image_upload_saves_and_rescores_that_posting`, `test_image_score_rescores_only_that_posting`, `test_image_score_summary_joins_read_and_score` | 통과 |
| F8 | 본문 못 채우면 평가 안 함, 다른 공고만 채워져도 평가 안 함, 프로필·키 없으면 저장 안 함, OCR 없으면 아무것도 안 건드림 | `test_image_score_without_text_does_not_rescore`, `test_image_score_other_posting_filled_is_not_this_one`, `test_image_upload_without_profile_saves_nothing`, `test_image_upload_without_key_saves_nothing`, `test_read_inbox_without_ocr_touches_nothing`, `test_image_score_summary_when_nothing_read` | 통과 |
| N1 | 새 의존성 없음 | `requirements.txt` 그대로 | 통과 |
| N2 | 모아보기 LLM 없음, 이미지 평가는 1건만 | 위 테스트(가짜 그래프의 평가 대상 1건) | 통과 |
| N3 | 엑셀·복사 버튼이 두 테마에서 다른 보통 버튼과 같은 모양 | Chromium(밝은 rgb(246,244,238)·어두운 rgb(30,31,36), 두 버튼 바탕·테두리·그림자 같음) | 통과 |
| N4 | `--inbox`·`--score` 그대로 | 기존 `tests/test_main.py`·`test_inbox.py` 통과 | 통과 |

## 구현 중 바뀐 것

- 복사 버튼을 처음엔 마크다운 `<button>`으로 그렸는데 Streamlit 보통 버튼과 바탕색이 달라(Chromium 비교) 진짜 `st.button` + 화면 스크립트로 바꿈(D4).
- 복사 뒤 알림을 처음엔 `st.toast`로 했는데 창이 닫힘(Chromium). 버튼 글자를 "✓ 복사했습니다"로 바꾸는 방식으로 바꿈.
- 메일 줄 말줄임은 체크 칸 글자 칸(`stWidgetLabel`)과 그 위 칸 폭을 함께 제한해야 함(처음 규칙은 글이 칸 밖으로 나감, Chromium).
- 테스트를 지운 것: `test_inbox_without_ocr_shows_install_hint`, `test_inbox_button_when_ocr_is_ready`(받은함 카드 삭제, F6), `test_inbox_count_*` 2개·`test_start_inbox_reports_result`(`runner.inbox_count`·`start_inbox` 삭제), `test_inbox_summary`(`reports.inbox_summary` 삭제). 기능 자체를 뺀 것이고, 같은 경우(OCR 없음, 결과 글)는 새 테스트가 검사함.
- `test_image_upload_saves_to_inbox_and_shows_toast`는 저장 뒤 알림 대신 다시 평가 시작을 검사하는 `test_image_upload_saves_and_rescores_that_posting`으로 바꿈.

## 미확인

- 실제 OCR(PaddleOCR)·Gemini로 이미지로 다시 평가 전체 흐름(작업 환경에 OCR 없음, 가짜 OCR·가짜 그래프로만 확인)
- 재리 PC(Windows)·Docker 이미지 화면, 엑셀에서 CSV 열기(BOM 바이트까지만 확인), Safari·Firefox 클립보드
- 아주 긴 공고 줄은 끝(점수)이 "…"로 가려질 수 있음

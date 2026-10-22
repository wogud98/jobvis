# v0.6.1 테스트

2026-10-22 실행. LLM·사이트는 가짜로 바꿨다. 실제 키·시트는 쓰지 않았다.

## 실행한 명령

```bash
ruff check .            # All checks passed!
ruff format --check .   # 90 files already formatted
python -m pytest        # 570 passed (v0.6 561개 → 570개)
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

바뀐 결정(F5, F10)에 맞춰 고친 기존 테스트: 결과 칸 테스트 2개를 알림 테스트 2개로 바꿈, 전송 안내 위치를 도움말로 바꿈, 평가 줄 순서 테스트에 점수 있는 공고를 넣음(F6로 점수 없으면 차트가 없어서).

## 브라우저 확인

작업 환경에서 `streamlit run app.py`(DB 저장, SQLite, 공고 3건·키 없음)를 띄우고 Playwright Chromium으로 봤다.

| 창 | 확인 | 결과 |
| --- | --- | --- |
| 1400px 어두운 | 제목 흰색·크게, 키 칸 2줄·제목과 간격, 수집 카드 제목만, 카드 체크·점수 한 칸 | 확인 |
| 900px 어두운(사이드바 열림) | 카드 "평가" 글자·점수·별점·지원함/관심 없음 버튼이 잘리지 않음, 회사·직무 칸 유지, 평가 줄 버튼 글자 다 보임 | 확인 |
| 1400px 밝은·어두운 프로필 | 다룰 수 있음 키워드 12개가 4줄로 모두 보임, 기술·경력 / 방향·문화 칸 높이 같음, 이력서 칸 제목·파일 칸·버튼 한 줄 | 확인 |
| 900px | 수집 카드 사이트 칸 키워드가 줄을 바꿔 보임(칸이 좁아 "잡코…"처럼 끝이 줄어듦) | 확인 |

## 미확인

- **알림(F5) 실제 화면**: AppTest로만 확인. 실제 수집을 돌려 브라우저에서 알림이 뜨는 모습은 보지 않음.
- **실제 이력서 여러 개로 중복 합치기(F8)**: 프롬프트 규칙의 효과는 실제 Gemini로 확인 못 함. 코드 합치기는 테스트로 확인.
- **재리 PC Windows 브라우저**: 재리 확인 필요.

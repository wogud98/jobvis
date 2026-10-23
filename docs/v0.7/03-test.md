# v0.7 테스트

2026-10-23 실행. 실제 메일은 보내지 않았다. 작업 환경은 메일 서버(smtp.gmail.com)에 나갈 수 없다.

## 실행한 명령

```bash
ruff check .            # All checks passed!
ruff format --check .   # 102 files already formatted
python -m pytest        # 673 passed (636개 → 673개)
```

작업 환경에서 `streamlit run app.py`(SQLite DB, 가짜 키, 가짜 메일 설정, 공고 5건)를 띄우고 Chromium(Playwright)으로 눌러 봄.

## 요구사항별 확인

| ID | 확인 내용 | 테스트·명령 | 결과 |
| --- | --- | --- | --- |
| F1 | 위 ✉ 메일: 설정 없으면 설정 칸, 있으면 고르기 | `test_mail_without_settings_shows_form_and_saves`, `test_mail_picks_from_shown_cards_and_sends` | 통과 |
| F2 | 지금 목록(관심 없음 뺌)을 회사·직무·점수 체크로, 처음엔 안 고름, 모두 고르기 | `test_mail_picks_from_shown_cards_and_sends`, `test_mail_pick_all_callback_checks_every_shown_card`, Chromium(체크해도 창이 닫히지 않음, "✉ 2건 보내기") | 통과 |
| F3 | 0건·31건이면 보내기 비활성과 이유, 30건은 됨 | `test_mail_pick_all_and_more_than_max_cannot_send`, `test_build_rejects_zero_or_too_many`, `test_build_accepts_max` | 통과 |
| F4 | 보내면 "n건을 보냄 (받는 주소)" 알림, 창 닫힘 | `test_mail_picks_from_shown_cards_and_sends` | 통과 |
| F5 | 제목 `[JOBVIS] 공고 n건 (YYYY-MM-DD)` | `test_build_has_subject_addresses_and_both_bodies` | 통과 |
| F6 | 글자판·HTML 두 판, 회사·직무·점수·판정·마감 D-n·출처·경력·강점/부족한 점 첫 줄, 평가 전·제외 | `test_build_has_subject_addresses_and_both_bodies`, `test_unscored_and_excluded_cards`, `test_deadline_without_date_is_shown_as_is` | 통과 |
| F7 | 시트 글자 escape, `javascript:` 주소는 링크 아님 | `test_sheet_text_is_escaped_and_only_http_links` | 통과 |
| F8 | 설정 칸·앱 비밀번호 링크·2단계 인증 안내, 빈칸 뺀 16자 저장, 받는 주소 비우면 보내는 주소, 비밀번호 비우면 그대로, 시험 메일, 삭제 | `test_mail_without_settings_shows_form_and_saves`, `test_save_mail_strips_spaces_and_defaults_to_sender`, `test_save_mail_keeps_password_when_left_blank`, `test_mail_settings_can_be_deleted`, `test_delete_mail_removes_only_mail_settings` | 통과 |
| F9 | 인증 오류·연결 오류·시간 초과·끊김 → 할 일 문구, 틀린 주소·16자 아님은 저장 전에 막음, 실패하면 창에 남음 | `test_send_errors_become_what_to_do_without_secrets`, `test_save_mail_rejects_bad_values_without_echoing_password`, `test_mail_settings_reject_bad_address_without_saving`, `test_mail_failure_stays_in_dialog_without_secret`, Chromium(네트워크가 막힌 작업 환경에서 보내기 → "메일 서버에 연결하지 못했습니다" 창에 표시) | 통과 |
| F10 | 위 📊 모아 보기 큰 창, "공고 n건 기준"과 켜진 필터 | `test_stats_dialog_ranks_stack_and_gaps_of_shown_cards`, `test_stats_dialog_shows_filters_and_empty_message`, `test_filter_labels_lists_only_what_is_on` | 통과 |
| F11 | 기술 스택 위 15개, 공고 안 중복 한 번, 대소문자·빈칸 합침, 같은 수 이름 순, 내 기술 초록·없는 기술 빨강 | `test_stack_rank_counts_postings_once_and_merges_case_and_spaces`, `test_stack_rank_empty`, `test_stats_dialog_ranks_stack_and_gaps_of_shown_cards`, Chromium | 통과 |
| F12 | 부족한 점 위 10개, `--gaps`와 같은 가중치, 공고 수, 평가 전 뺀 수 | `test_gap_rank_weights_like_gaps_command_and_counts_excluded`, `test_gap_rank_empty`, `test_stats_dialog_ranks_stack_and_gaps_of_shown_cards` | 통과 |
| F13 | 0건이면 두 칸 모두 "모을 공고가 없습니다…" | `test_stats_dialog_shows_filters_and_empty_message` | 통과 |
| N1 | 새 의존성 없음, `smtp.gmail.com:465` SSL로 로그인 | `requirements.txt` 그대로, `test_send_logs_in_with_app_password_and_sends` | 통과 |
| N2 | 비밀번호가 오류 문구·화면에 없음, `redact`가 두 모양 모두 가림, 저장은 `data/settings.env`만 | `test_send_errors_become_what_to_do_without_secrets`, `test_redact_hides_mail_password_in_both_shapes`, `test_mail_without_settings_shows_form_and_saves`, `test_mail_failure_stays_in_dialog_without_secret` | 통과 |
| N3 | 테스트는 가짜 SMTP·가짜 `mail.send`만 씀 | `tests/test_mail.py`의 `FakeSMTP`, `tests/test_app.py`의 `sent` | 통과 |
| N4 | 메일 보내기는 실행 중 잠금(`runner`)을 쓰지 않음 | 코드 확인(`send_mail`은 `runner`를 부르지 않음) | 확인 |
| N5 | 모아 보기는 저장된 칸만 셈, 집계는 `agent/view.py` 함수 | `tests/test_view.py` 모아 보기 테스트 | 통과 |

## 구현 중 바뀐 것

- 위 버튼이 다섯 개가 되어 한 줄이면 1280px 창에서 "🔑 키 ••••", "🔄 새로…"처럼 글자가 잘림. 제목 오른쪽을 두 줄(🔑 · 📖 · 🔄 / ✉ · 📊)로 바꿈. Chromium으로 1100px(최종 비율), 1280·1600px(첫 줄 비율을 조금 바꾸기 전)에서 잘리지 않음을 확인. `02-design.md` "정할 것 확인" 갱신.
- 사용법 창에 "모아 보기·메일" 한 줄 추가(10줄 이하 유지).

## 미확인

- 실제 Gmail 발송(앱 비밀번호 로그인, 받은 메일의 HTML 모양, 휴대폰 메일 앱에서 보기). 재리 계정으로 확인 필요.
- 네이버 메일 등 다른 받는 주소에서 HTML이 깨지지 않는지.
- Windows·Docker 이미지에서 메일 보내기(작업 환경은 Linux, 이미지 빌드는 머지 뒤 CI).
- 다크 테마에서 모아 보기 순위 색.

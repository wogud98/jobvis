# v0.4 테스트

2026-10-21 실행. 사람인·잡코리아 페이지, robots.txt, 이미지, OCR, LLM, 구글 시트는 모두 가짜로 바꿨다. 실제 사이트 요청과 실제 키는 쓰지 않았다. 테스트 HTML(`tests/fixtures/`)은 실제 공고를 저장한 것이 아니라 설계 문서의 선택자 구조로 직접 만든 가짜 공고다 (N5).

## 실행한 명령

```bash
ruff check .            # All checks passed!
ruff format --check .   # 48 files already formatted
python -m pytest        # 188 passed
```

`pytest`만 치면 이 환경에서는 다른 파이썬의 pytest가 실행돼 `python -m pytest`로 실행했다 (v0.3과 같음).

## 요구사항별 확인

| ID | 확인 내용 | 테스트 | 결과 |
| --- | --- | --- | --- |
| F1 | 사람인 API 호출 코드 삭제. 사람인 검색 주소 `/zf_user/search/recruit`, 잡코리아 `/Search/` | `test_search_url_*` (`test_saramin.py`, `test_jobkorea.py`) | 통과 |
| F2 | `--source`로 한 사이트만, 생략하면 둘 다. 모르는 값은 오류 | `test_source_option_picks_one_site`, `test_names_become_codes_and_both_sources_by_default`, `test_unknown_choice_is_rejected`, `test_one_source_only` | 통과 |
| F3 | 사람인은 지역·직무·경력을 주소에, 잡코리아는 검색어만 주소에. 경력은 두 사이트 모두 글자로 한 번 더, 잡코리아 지역은 글자로 거름 | `test_search_url_puts_conditions_in_address`, `test_search_url_has_keyword_only`, `test_career_and_location_filters`, `test_matches_career_by_text`, `test_matches_location` | 통과 |
| F4 | 목록 10칸. 잡코리아 학력·키워드 빈칸. 잡코리아 지역·경력이 한 칸에 섞여도 나눠 읽음(2026-10-21 시험 수집 버그) | `test_parse_list_reads_ten_fields_*`, `test_parse_list_reads_cards_*`, `test_location_and_experience_mixed_in_one_chip_are_split`, `test_split_condition` | 통과 |
| F5 | 연도 없는 날짜 → 가장 가까운 미래, 12월에 본 1월 마감, 상시·채용시, 오늘·내일마감, 없는 날짜. 잡코리아 ISO 날짜 자르기, null → 상시 | `test_parse_deadline`, `test_deadline_null_is_always_open_and_iso_is_cut_to_date` | 통과 |
| F6 | 잡코리아 Next.js 데이터에 없는 카드(광고) 제외. 사람인 공고ID 없는 카드 제외 | `test_parse_list_reads_cards_and_deadlines_from_next_data`, `test_parse_list_reads_ten_fields_and_skips_cards_without_id` | 통과 |
| F7 | `--count` 사이트당, 30까지, 31은 오류. 사이트 2개 × 30건이 recursion_limit에 안 걸림 | `test_count_is_per_site`, `test_count_out_of_range_is_rejected`, `test_max_count_on_both_sites_does_not_hit_recursion_limit` | 통과 |
| F8 | 출처+ID가 시트에 있으면 본문 요청 없이 건너뜀. 같은 ID라도 출처가 다르면 새 공고 | `test_duplicate_by_source_id_skips_detail_request` | 통과 |
| F9 | 회사+제목 정규화(공백·기호 제거, 대소문자 무시)가 같으면 먼저 나온 것만. 시트에 있는 것과도 비교 | `test_same_posting_on_both_sites_keeps_the_first`, `test_normalize_drops_spaces_symbols_and_case` | 통과 |
| F10 | 새 공고만 본문 주소 한 번 요청. 본문 실패면 시트·원문 파일 모두 저장 안 함 | `test_detail_url*`, `test_detail_failure_does_not_save_row` | 통과 |
| F11 | `script`·`style`·`noscript`·숨은 요소(`display:none`, `hidden`) 글자 제거. 본문 위치 없으면 빈 본문 | `test_parse_detail_keeps_visible_text_and_absolute_images`, `test_parse_detail_without_body_area_is_empty` | 통과 |
| F12 | 300px 미만 이미지 건너뜀(못 읽음에 안 셈), 공고당 10장까지, OCR 글자를 본문 뒤에 붙임 | `test_ocr_reads_large_images_and_appends_text`, `test_small_image_only_is_not_counted_as_unread`, `test_ocr_reads_at_most_ten_images` | 통과 |
| F13 | OCR 미설치면 이미지를 받지 않고 설치 안내를 한 번 출력. OCR 예외는 그 이미지만 건너뜀 | `test_without_ocr_images_are_not_downloaded`, `test_first_run_prints_personal_use_notice_and_ocr_hint`, `test_ocr_error_skips_only_that_image_and_keeps_row`, `test_available_follows_installed_package` | 통과 |
| F14 | 원문은 `data/postings/{출처}_{ID}.txt`에만, 시트에는 없음 | `test_collects_both_sites_and_saves_rows_and_posting_files`, `test_save_and_load_in_data_folder` | 통과 |
| F15, F15a | V–X열에 출처·지역·본문 상태. 상태 4가지, 200자 경계(199/200) | `test_collects_both_sites_*`, `test_status`, `test_banned_image_marks_partly_unread` | 통과 |
| F16 | 원문 앞 6,000자만 LLM에. 원문이 있으면 시트 정보 칸을 넣지 않음. 출처 빈 줄은 사람인 파일 | `test_long_posting_is_cut_to_6000_chars`, `test_posting_file_is_used_instead_of_sheet_info`, `test_blank_source_reads_saramin_file` | 통과 |
| F17 | 원문 없음·본문 미확보 → 시트 정보(지역 포함)로 채점, 판정에 "(본문 미확보)" | `test_missing_body_status_uses_sheet_info_even_if_file_exists`, `test_scores_and_writes_each_row` | 통과 |
| F18 | 주요업무·우대사항·기술스택을 Y–AA열에. 빠지거나 null이면 빈 문자열(실패 아님) | `test_posting_file_is_used_instead_of_sheet_info`, `test_null_body_fields_are_blank_not_failures`, `test_write_result_writes_summary_result_and_body_summary_columns_only` | 통과 |
| F19 | 사이트별 가져옴/저장/건너뜀/실패, 실패 단계, 멈춘 이유, 본문 미확보 수 | `test_report_prints_counts_per_site_and_failures`, `test_report_with_no_jobs` | 통과 |
| F20 | 검색 결과 0건이면 "사이트 구조가 바뀌었을 수 있음"으로 그 사이트만 멈춤 | `test_search_blocked_or_empty_stops_only_that_site` | 통과 |
| N1 | `.env.example`에서 사람인 키 삭제. 실패가 섞여도 나머지 계속 | `test_save_failure_does_not_stop_others` 등 | 통과 |
| N2 | robots 금지 주소는 요청 안 함, robots 404는 허용, 500·403·연결 오류는 호스트 전체 금지, 호스트마다 한 번만 읽음 | `test_disallowed_page_is_not_requested`, `test_robots_404_allows_everything`, `test_robots_error_disallows_the_whole_host` | 통과 |
| N3 | User-Agent `JOBVIS/0.4 (personal job search)`, 브라우저 이름 없음 | `test_allowed_page_is_fetched_with_named_user_agent` | 통과 |
| N4 | 같은 호스트 3초 간격(robots.txt 포함, 가짜 시계), 403·429 → 그 사이트 남은 공고 요청 안 함, 다른 사이트는 계속 | `test_waits_three_seconds_between_requests_to_same_host`, `test_403_and_429_raise_blocked`, `test_blocked_site_stops_but_other_site_continues` | 통과 |
| N5 | `data/`가 `.gitignore`에 있음. 테스트 HTML은 직접 만든 가짜 | `test_data_folder_is_git_ignored` | 통과 |
| N6 | 첫 실행(`data/postings/` 없음)에만 개인 사용 안내. README에 같은 문구 | `test_first_run_prints_*`, `test_notice_only_on_first_run` | 통과 |
| N7 | 수집에서 LLM을 부르면 테스트 실패 | `test_graph.py` 전체 (`init_chat_model`이 불리면 실패) | 통과 |
| N8 | `beautifulsoup4`를 `requirements.txt`에, PaddleOCR은 `requirements-ocr.txt`에. 테스트는 PaddleOCR·Pillow 없이 통과 | 파일 확인, CI와 같은 `pytest` | 통과 |
| - | 오류 메시지에 주소 전체(쿼리 속 값)가 남지 않음 | `test_other_errors_hide_full_address` | 통과 |
| - | 시트 제목 줄 v0.3 → v0.4(체크박스 규칙 다시 안 검), 출처 빈 줄은 사람인 | `test_v03_header_is_extended_without_new_checkbox_rule`, `test_existing_keys_reads_ids_and_names_*` | 통과 |

v0.2 API용 테스트(`test_saramin.py`의 API 응답 변환, 숫자 경력 코드 `matches_career`, `SaraminAPIError` 출력)는 F1로 해당 코드를 지워서 크롤링 테스트로 바꿨다.

테스트가 실제로 잡는지 확인하려고 코드를 일부러 고장 내서 돌려 봤다. 모두 되돌린 뒤 다시 188개 통과했다.

| 고장 낸 곳 | 실패한 테스트 수 |
| --- | --- |
| 잡코리아 지역·경력 나누기를 끔 | 7 |
| robots.txt를 무시하고 모두 허용 | 4 |
| 원문 6,000자 자르기를 끔 | 1 |
| 같은 호스트 3초 대기를 끔 | 1 |
| 사이트 간 중복(회사+제목) 거르기를 끔 | 1 |

## 가짜 인터넷으로 끝까지 실행

실제 `crawler.py`와 실제 파서에 가짜 `requests.get`(테스트 HTML을 돌려줌, 사람인 두 번째 본문부터 429)과 가짜 시트를 붙여 `main.main(["--keyword", "백엔드"])`를 실행했다. 대기 시간만 0으로 바꿨다.

```text
개인 사용만. 수집한 공고를 공유·공개·판매하지 않음 (사이트 약관)
이미지 OCR 없음: 글자 본문만 저장합니다. 이미지 OCR을 쓰려면 `pip install -r requirements-ocr.txt`
사람인 가져옴 3 / 새로 저장 1 / 건너뜀 0 / 실패 2
잡코리아 가져옴 3 / 새로 저장 3 / 건너뜀 0 / 실패 0
  사람인 수집 멈춤: www.saramin.co.kr 차단 (HTTP 429)
  실패(본문): 사람인 | 라마바데이터 | 데이터 엔지니어 (Blocked)
  실패(본문): 사람인 | 사아자AI | AI 엔지니어 (Blocked)
본문 미확보 4건: 시트의 링크로 직접 확인해 주세요
```

- 요청 순서: 호스트마다 robots.txt → 검색 → 본문. 429 뒤 사람인 본문은 더 요청하지 않음.
- 시트 줄 V–X: `['사람인', '서울 강남구', '본문 미확보']`, `['잡코리아', '경기 성남시', '본문 미확보']` 등. 가짜 본문이 200자보다 짧아 모두 "본문 미확보"가 맞음.
- 원문 파일 4개(`saramin_1001.txt`, `jobkorea_2001.txt` …)가 `data/postings/`에 생김.

## 미확인

- **실제 사이트 수집.** 이 환경(클라우드)에서는 두 사이트가 막혀 있어 실행하지 못했다. 재리 PC(DESKTOP-OF0CMDB)에서 `python main.py --keyword FDE --count 5`로 확인해야 한다. 확인할 것: 선택자가 실제 화면과 맞는지, 잡코리아 지역·경력 나누기, 잡코리아 마감일(Next.js 데이터) 짝 맞추기, 광고 카드 제외, 사람인 `loc_mcd`·`cat_kewd`·`exp_cd`·`sort=RD`가 먹는지.
- **PaddleOCR.** 설치하지 않고 가짜로만 확인했다. `ocr.read()`(3.x `predict()`·`rec_texts`)와 `ocr.size()`(Pillow)는 실행해 보지 못했다. 버전도 고정하지 못했다(`>=3.0`).
- **실제 구글 시트.** v0.3 → v0.4 제목 줄 바꾸기와 Y–AA열 쓰기는 가짜 시트로만 확인했다.
- **실제 LLM.** 본문으로 채점했을 때 세 칸(주요업무·우대사항·기술스택)을 잘 채우는지 확인하지 못했다.
- 사람인 API 공고ID와 크롤링 `rec_idx`가 같은지(출처 빈 줄을 사람인으로 볼 때 중복 판단).

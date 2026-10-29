# v0.7.6 테스트

2026-10-27 실행.

## 실행한 명령

```bash
ruff check .            # All checks passed!
ruff format --check .   # 122 files already formatted
python -m pytest        # 733 passed (725개 → 733개)
```

## 요구사항별 확인

| ID | 확인 내용 | 테스트 | 결과 |
| --- | --- | --- | --- |
| F1 | 이미 있는 공고(ID·회사+제목)는 개수에 안 들어가고 새 공고 3건을 채움, 본문 요청 안 함 | `test_existing_postings_do_not_use_up_count`, `test_same_name_posting_is_also_skipped_before_counting`, 기존 `test_duplicate_by_source_id_skips_detail_request`·본문 채우기 테스트 | 통과 |
| F2 | 모자라면 다음 쪽, 최대 3쪽, 채우면 더 안 읽음, 지역으로 걸러진 잡코리아도 다음 쪽 | `test_existing_postings_do_not_use_up_count`, `test_reads_at_most_max_pages`, `test_first_page_filtered_by_location_reads_next_page`, `test_search_url_next_page`(두 사이트) | 통과 |
| F3 | 빈 쪽·같은 공고만 오는 쪽에서 멈춤 | `test_stops_when_next_page_is_empty_or_repeats` | 통과 |
| F4 | 가져옴 = 새로 저장 + 건너뜀 + 실패 | 위 테스트의 `assert_counts_add_up` | 통과 |
| F5 | 다음 쪽 연결 오류는 실패 "목록" + 첫 쪽 공고 저장, robots 금지는 멈춤만 | `test_next_page_error_keeps_first_page_postings` | 통과 |
| N1 | 쪽마다 같은 crawler 규칙 | 코드 확인(`crawler.get_text` 한 곳) | 통과 |
| N2 | 새 의존성 없음, 옵션 그대로 | `requirements.txt` 그대로, 기존 `test_runner.py`·`test_main.py` 통과 | 통과 |

## 미확인

- 실제 사람인 `recruitPage`, 잡코리아 `Page_No` 응답(작업 환경에서 두 사이트 접속 불가, 프록시 거부). 칸이 무시되면 같은 공고가 와서 F3대로 첫 쪽만 쓰고 멈춤
- 실제 robots.txt가 다음 쪽 주소를 허용하는지. 금지면 첫 쪽만 씀
- 재리 PC 실제 수집에서 두 번째 수집 때 새 공고가 채워지는지

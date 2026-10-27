# v0.7.5 테스트

2026-10-27 실행.

## 실행한 명령

```bash
ruff check .            # All checks passed!
ruff format --check .   # 122 files already formatted
python -m pytest        # 725 passed
```

## 요구사항별 확인

| ID | 확인 내용 | 테스트·명령 | 결과 |
| --- | --- | --- | --- |
| F1 | 사이드바 출처·지역·경력 순서, 처음 빔, 있는 묶음만 정해진 순서, 고르면 거름, 다른 필터와 함께 | `test_region_filter_in_sidebar`, `test_region_filter_lists_only_found_groups_in_order` | 통과 |
| F2 | "외 1"·긴 이름·"경기 광주시"·전국·해외·빈 칸 묶기 | `test_region_group` (13가지) | 통과 |
| F3 | 켜진 필터 이름에 "지역 서울·경기" | `test_filter_labels_include_regions` | 통과 |
| N1 | 새 의존성 없음 | `requirements.txt` 그대로 | 통과 |
| N2 | 수집·`--location` 그대로 | 기존 `test_runner.py`·`test_graph.py`·`test_main.py` 통과 | 통과 |

## 미확인

- 실제 사람인·잡코리아에서 받은 지역 표기 전부(테스트는 고정 HTML·가짜 줄 기준). 못 묶는 표기는 "기타"로 보임
- 재리 PC 브라우저 화면(사이드바 높이, 밝은·어두운 테마)

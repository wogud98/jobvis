# v0.7.7 테스트

2026-11-06 실행.

## 실행한 명령

```bash
ruff check .            # All checks passed!
ruff format --check .   # 126 files already formatted
python -m pytest        # 750 passed (733개 → 750개)
```

## 요구사항별 확인

| ID | 확인 내용 | 테스트 | 결과 |
| --- | --- | --- | --- |
| F1 | 950×6744 이미지가 높이 1600 이하 조각 여러 개로 나뉘어 읽힘, 조각이 80px씩 겹치고 끝까지 덮음, 짧은 이미지는 한 조각 | `test_read_long_image_reads_pieces_not_whole`, `test_pieces_cover_long_image_with_overlap`, `test_pieces_short_image_is_one_piece` | 통과 |
| F2 | 가로 2560 이미지가 1280으로 비율대로 줄어 한 조각, 작은 이미지는 그대로 | `test_read_wide_image_is_shrunk_first`, `test_read_small_image_unchanged` | 통과 |
| F3 | 경계에서 두 번 읽힌 줄 한 번만, 빈 조각·빈 결과, 빈 줄 빼기 그대로 | `test_join_lines_drops_lines_read_twice_at_overlap`, `test_read_empty_result`, `test_read_small_image_unchanged` | 통과 |
| F4 | 남은 표시를 보면 "지난 수집 작업(시작 시각)이 끝나지 않고 멈췄습니다"+메모리·다시 실행 안내, 화면 위 경고로 보이고 같은 창에서 다시 그려도 유지, 모르는 종류는 "지난 작업" | `test_mark_left_by_killed_app_is_told_once`, `test_interrupted_collect_is_shown_and_stays_in_session`, `test_unknown_kind_mark_still_told` | 통과 |
| F5 | 실행 중에만 표시 있음·실행 중엔 알리지 않음, 정상·오류 끝은 표시 지움, 한 번 알리면 지움, 깨진 표시는 무시, 표시 없으면 알림 없음 | `test_running_mark_exists_only_while_job_runs`, `test_error_end_also_removes_mark`, `test_broken_mark_is_ignored`, `test_no_interrupted_notice_without_mark` | 통과 |
| N1 | 새 의존성 없음 | `requirements*.txt` 그대로 | 통과 |
| N2 | 표시 파일을 못 써도 작업은 끝까지 | `test_mark_write_failure_does_not_stop_job` | 통과 |
| N3 | PaddleOCR 없이 가짜 모델로 시험, 표시 파일은 임시 폴더(`tests/conftest.py`) | 위 테스트 전부 | 통과 |

## 미확인

- 실제 PaddleOCR로 긴 이미지를 읽을 때 메모리가 실제로 줄어드는지(작업 환경에 PaddleOCR 없음). 재리 PC에서 새 ocr 이미지로 "백엔드" 30개 수집해 개수가 차고 앱 재시작이 없는지 확인 필요
- 조각으로 나눴을 때 실제 OCR 글자 품질(경계 줄이 빠지거나 두 번 남는지)
- 실제 Docker에서 앱이 강제 종료된 뒤 다시 연 화면에 알림이 뜨는지(가짜 표시 파일로만 확인)

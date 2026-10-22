# v0.5.5 테스트

2026-10-22 실행. 프로필 파일은 임시 폴더에서만 쓰고 읽었다. 외부 API 호출 없음.

## 실행한 명령

```bash
ruff check .            # All checks passed!
ruff format --check .   # 78 files already formatted
python -m pytest        # 515 passed (v0.5.4 511개 → 515개)
```

작업 전 main(PR #37 머지 뒤)에서 `python -m pytest`는 1 failed, 510 passed였다. 실패는 `test_css_follows_theme_and_guide_mentions_theme`(어두운 칸 색 #2a2f38 확인)로, 사용자가 고른 #323B4B로 맞췄다.

## 요구사항별 확인

| ID | 확인 내용 | 테스트 | 결과 |
| --- | --- | --- | --- |
| F1, F3 | ↺로 그 칸만 비움, 다른 칸·파일 그대로 | `test_clear_one_field_empties_only_that_field_and_keeps_file` | 통과 |
| F1 | 비운 뒤 적은 글도 다시 ↺로 비움 | `test_clear_again_after_typing_empties_text` | 통과 |
| F2, F3 | 전체 초기화는 확인 창, 취소면 그대로, 비우기면 모든 칸·필수 배지 바뀜, 파일 그대로 | `test_clear_all_asks_first_then_empties_every_field` | 통과 |
| F3 | 비운 뒤 저장하면 파일에 반영, 저장 뒤 화면 값 유지 | `test_saving_after_clear_writes_cleared_value` | 통과 |
| 기존 | 프로필 저장·이력서 채우기·기술 칸 겹침 막기 | `tests/test_app.py` 기존 프로필 테스트 | 통과 |

## 화면 확인

가짜 시트로 `streamlit run`을 띄우고 Playwright Chromium(어두운 테마)으로 프로필 탭을 열어 봤다. ↺가 칸 오른쪽 위에 작게 보이고, 누르면 주력 기술이 비고 필수 배지가 ✗로 바뀌었다. 전체 초기화를 누르면 확인 창이 떴다. 처음엔 ↺에 일반 버튼 테두리가 남아 CSS를 고쳤다.

## 미확인

- 윈도우 브라우저에서 ↺·확인 창 동작

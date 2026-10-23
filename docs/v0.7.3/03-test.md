# v0.7.3 테스트

2026-10-23 실행.

## 실행한 명령

```bash
ruff check .            # All checks passed!
ruff format --check .   # 115 files already formatted
python -m pytest        # 695 passed (686개 → 695개)
python main.py --help   # 명령줄 옵션 그대로
```

작업 환경에서 `streamlit run app.py`(SQLite DB, 가짜 키, 가짜 공고 5건)를 띄우고 Chromium(Playwright, 1280×860)으로 기술 모아보기를 열어 확인함.

## 요구사항별 확인

| ID | 확인 내용 | 테스트·명령 | 결과 |
| --- | --- | --- | --- |
| F1 | 두 탭 모두 전부 보임, 요약 "N개 중"도 전부 기준, 칸 높이 그대로 칸 안 스크롤 | `test_stats_dialog_lists_every_skill_in_scroll_box`(13줄), `test_stack_rank_shows_all_and_merges_same_words`, `test_top_none_keeps_all`, Chromium(기술 16줄, 칸 scrollHeight 510 > clientHeight 400) | 통과 |
| F2 | 같은 말은 대표 이름 한 줄로, 다른 기술은 따로 | `test_dictionary_loads_and_maps_aliases_to_main_name`, `test_different_skills_stay_apart`, `test_same_words_in_dictionary_merge_under_main_name` | 통과 |
| F3 | 프로필 쿠버네티스·js → 공고 Kubernetes·JavaScript가 내 기술, Java는 아님. 자세히 칩도 같음 | `test_stack_rank_shows_all_and_merges_same_words`, `test_stack_chips_mark_same_words_as_mine` | 통과 |
| F4 | `--gaps`도 같은 함수로 합침, 출력 개수 10 그대로 | `test_same_words_in_dictionary_merge_under_main_name`, `test_keeps_only_top_n` | 통과 |
| N1 | 새 의존성 없음 | `requirements.txt` 그대로 | 통과 |
| N2 | 한 이름이 두 묶음이면 거부, SQL·MySQL·Java·JavaScript 따로 | `test_name_in_two_groups_is_refused`, `test_different_skills_stay_apart` | 통과 |
| N3 | LLM 안 부름. 이미 저장된 기술스택 칸으로 바로 합침 | 위 테스트 모두 가짜 데이터, 외부 호출 없음 | 통과 |

## 구현 중 바뀐 것

- 기존 테스트 3개의 시험 이름을 바꿈: "처음 나온 모양으로 보인다" 규칙을 검사하던 이름(Python·AWS·docker)이 사전에 들어가 대표 이름으로 보이게 됨. 사전에 없는 이름(Kotlin·Jenkins)으로 같은 규칙을 그대로 검사하고, 사전 이름은 새 테스트로 따로 검사함. 검사를 약하게 한 것이 아님.
- `test_stack_rank_shows_top_ten`(10개 상수 검사)을 `test_stats_dialog_lists_every_skill_in_scroll_box`로 바꿈. 요구사항이 "위 10개"에서 "전부"로 바뀜(F1).
- `--gaps` 이름 비교가 앞뒤 공백만 무시하던 것에서 띄어쓰기 전부 무시로 바뀜(D2, 화면과 같게).

## 미확인

- 재리 PC(Windows)·Docker 이미지에서 화면 확인
- 실제 수집 공고에서 사전이 얼마나 합치는지(가짜 데이터로만 확인). 사전에 없는 새 이름은 따로 보임

# v0.6 테스트

2026-10-22 실행. 구글 시트·LLM은 가짜로 바꿨다. 실제 키·시트는 쓰지 않았다. DB 테스트는 SQLite 메모리 DB로 했다(N1).

## 실행한 명령

```bash
ruff check .            # All checks passed!
ruff format --check .   # 88 files already formatted
python -m pytest        # 561 passed (v0.5.5 515개 → 561개)
```

Streamlit 1.66.1, SQLAlchemy 2.1.6, psycopg 3.3.6.

## 요구사항별 확인

| ID | 확인 내용 | 테스트 | 결과 |
| --- | --- | --- | --- |
| F4 | 키가 없으면 맨 위 입력 칸, 저장하면 `data/settings.env`에 쓰고 칸이 접힘, 키가 있으면 "바꾸기"만 | `test_key_card_shows_when_no_key_and_saves_to_data_folder`, `test_key_card_is_folded_when_key_exists`, `test_save_writes_file_and_sets_environment`, `test_load_fills_only_missing_or_blank_values` | 통과 |
| F5 | 화면에 끝 4자리만, 틀린 키는 저장 안 하고 문구에 키 없음 | `test_masked_shows_last_four_only`, `test_short_key_is_fully_hidden`, `test_bad_key_is_rejected_without_echoing_it`, `test_key_card_rejects_bad_key_without_saving` | 통과 |
| F6 | `JOBVIS_STORAGE`로 고름, 틀린 값은 안내, 두 백엔드 함수 모양 같음, DB면 "저장된 공고"·DB 오류 문구(비밀번호 안 보임) | `tests/test_store.py` 전체, `test_error_message_for_db_hides_address`, `test_error_message_for_wrong_storage_setting`, `test_summary_says_saved_postings_for_db` | 통과 |
| F7 | DB에 시트 열과 같은 칸 저장, 체크는 "TRUE"/"FALSE", 평가 결과가 시트와 같은 칸에, 수집 칸은 안 건드림, 중복 막기 규칙 같음 | `tests/test_db.py` 전체 | 통과 |
| F8 | 표를 손으로 만들지 않아도 첫 연결 때 생김 | `test_engine_creates_table_on_first_connect` | 통과 |
| F9 | 설정이 없으면 시트, 기존 시트 테스트 515개 그대로 통과 | `test_default_is_sheet`, 기존 테스트 | 통과 |
| F10 | `JOBVIS_OCR=off`면 OCR 없음으로 동작 | `test_off_setting_hides_installed_ocr` | 통과 |
| F3 | 프로필 경로가 `JOBVIS_PROFILE`을 따름 | `test_default_path_follows_environment` | 통과 |

## Docker 확인

이 작업 환경에서 Docker로 실제로 띄워 봤다. 다만 작업 환경 네트워크가 `deb.debian.org`와 OCR 모델 저장소를 막아서, 시험용으로 Dockerfile 두 줄을 바꿔 빌드했다.

- `apt-get install libgomp1 libgl1 libglib2.0-0` 대신 작업 환경의 같은 라이브러리 파일을 복사해 넣음
- `python scripts/warm_ocr.py`(모델 받기)는 실패해도 넘어가게 함 → 모델 없는 이미지

그 밖은 저장소의 `Dockerfile`, `docker-compose.yml`, `.dockerignore` 그대로다.

| 확인 | 결과 |
| --- | --- |
| `docker compose config -q` | 통과 |
| 이미지 빌드 시간 | 4분 11초 (pip 설치 포함) |
| 이미지 크기 | 2.53GB (압축 564MB), OCR 모델 없이 |
| `docker compose up -d --wait` | app·db 모두 healthy, 포트는 `127.0.0.1:8501`만 열림, db는 밖으로 안 열림 |
| `/_stcore/health` | 200 |
| 화면(Playwright Chromium) | 키 입력 칸이 뜸 → 가짜 키 저장 → "키를 저장함 (••••2468)", 칸이 "🔑 LLM 키 ••••2468 · 바꾸기"로 접힘, 화면에 키 전체가 안 보임 |
| 컨테이너 안에서 `store`로 Postgres에 줄 추가·평가 결과·지원 표시 | `store.kind()`가 `db`, 읽은 값이 시트와 같은 글자("80", "TRUE") |
| 화면에서 그 줄 | "저장된 공고" 칸과 카드가 보임, 오류 없음 |
| `docker compose down` → `up` 뒤 | 줄과 키(`settings.env`, 권한 600)가 그대로 남음 |
| 메모리 (빈 화면, OCR 안 씀) | app 194MiB, db 22MiB |
| `docker compose down -v` | 볼륨까지 지워짐 |

## 미확인

- **OCR 모델 내려받기와 OCR 실제 동작**: 작업 환경에서 모델 저장소가 막혀 확인 못 함. 새 CI 워크플로(`.github/workflows/docker.yml`)가 GitHub Actions에서 빌드·모델 받기·`ocr._model()`까지 확인한다. 이 PR에서 그 결과를 본다.
- **Dockerfile의 apt 설치**: 위처럼 작업 환경에서는 바꿔 빌드함. CI 워크플로가 원래 Dockerfile로 확인한다.
- **OCR 쓸 때 메모리**: 모델이 없어 재지 못함.
- **실제 Gemini 키로 평가·이력서 채우기, 실제 사이트 수집**: 가짜 키만 씀.
- **Windows Docker Desktop**: 재리 PC에서 확인 필요. Mac은 범위 밖(미확인).
- **기존 시트 사용자 동작**: 시트 방식은 기존 테스트로만 확인. 재리 PC `.env`로 화면을 띄워 확인 필요.

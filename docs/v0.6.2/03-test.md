# v0.6.2 테스트

2026-10-22 실행. Docker는 작업 환경에서 띄운 dockerd로 확인했다. Windows `.bat`은 작업 환경에서 돌릴 수 없다.

## 실행한 명령

```bash
ruff check .            # All checks passed!
ruff format --check .   # 98 files already formatted
python -m pytest        # 621 passed (612개 → 621개)
docker compose config   # 저장소 compose: build target ocr, name jobvis
docker compose -f start/compose.yml config -q   # 통과
JOBVIS_TAG=ocr docker compose -f start/compose.yml config   # image ghcr.io/wogud98/jobvis:ocr
docker build --target base -t jobvis:base2 .    # 통과 (작업 환경용 CA만 더한 복사본으로)
sh scripts/check_image.sh jobvis:base2          # 비밀 파일 없음
sh scripts/check_image.sh jobvis:bad            # .env, service_account.json을 넣은 이미지 → 실패(EXIT 1)
```

## 요구사항별 확인

| ID | 확인 내용 | 테스트·명령 | 결과 |
| --- | --- | --- | --- |
| F1, F2, F4 | 시작 파일 순서(Docker 확인 → OCR 묻기 → 포트 → 받기 → 켜기 → 브라우저), 실패 4곳에서 안내 후 `pause`, CRLF·UTF-8(BOM 없음)·`chcp 65001` | `test_start_bat_steps_and_failures`, `test_bat_files_use_crlf_and_utf8` | 통과 |
| F3 | 끄기 파일이 `down`(볼륨 남김) | 파일 확인 | 확인 |
| F4 | 키를 다루지 않음(키 이름·`set /p` 없음) | `test_bat_files_never_touch_keys` | 통과 |
| F5, F6 | 답을 `jobvis.env`의 `JOBVIS_TAG`로 남김, 다시 열면 5초 동안 바꿀 기회, 묻는 크기가 화면 안내와 같음 | `test_start_bat_steps_and_failures` | 통과 |
| F7 | 기본 이미지면 "`JOBVIS 시작.bat`을 다시 열고 OCR 포함을 고르세요", 그 밖에는 pip 안내 | `test_install_hint_points_to_start_file_on_base_image`, 기본 이미지에서 `ocr.available()` 거짓·문구 확인 | 통과 |
| F8 | OCR 이미지 = v0.6 이미지 | Docker CI(`docker compose build`, OCR 모델 확인) | CI에서 확인 |
| F9 | main push·`v*` 태그에서 두 이미지 올림 | `publish.yml` | 머지 뒤 첫 실행에서 확인 |
| F10 | 저장소 compose는 `target: ocr`로 빌드, 두 compose가 `name: jobvis`·같은 볼륨·같은 DB 설정 | `test_repo_compose_still_builds_ocr_image`, `test_start_compose_shares_data_with_repo_compose` | 통과 |
| F11 | README 시작하기를 시작 파일 기준으로, 직접 빌드는 아래로 | 문서 확인 | 확인 |
| N3 | 기본 이미지에 `paddleocr` 없음 | 작업 환경 `docker run jobvis:base2`, Docker CI | 통과 |
| N4 | 이미지 `/app`에 비밀 파일 없음, 있으면 실패 | `scripts/check_image.sh` 정상·나쁜 이미지 | 통과 |

## 크기 (N2)

PR #52 Docker CI(GitHub Actions)에서 잰 값. 받는 크기는 `docker save | gzip -1` 크기로 어림함(레지스트리 층 압축과 비슷함).

| 이미지 | 풀린 크기 | 받는 크기(압축 어림) |
| --- | --- | --- |
| 기본(base) | 730MB | 257MB |
| OCR 포함 | 2.23GB | 819MB |

OCR을 고르면 약 560MB를 더 받음 → 질문 문구·화면 안내 "약 560MB". 처음 넣은 "약 350MB"는 작업 환경 근사값(시스템 라이브러리·모델 빠짐)이라 CI 값으로 고침. 기본 이미지는 받는 크기가 OCR 포함의 약 3분의 1.

## 미확인

- **Windows에서 `.bat` 실행**: 더블클릭, 한국어 출력, `choice` 5초, 포트 확인, `--wait`, 브라우저 열기. 재리 PC 확인 필요.
- **GHCR 올리기·받기**: `publish.yml`은 main 머지 뒤 처음 돈다. 그 뒤 재리가 패키지를 공개로 바꿔야 로그인 없이 받음(한 번 공개하면 되돌릴 수 없음).
- **기존 사용자 볼륨 이어짐**: `name: jobvis`를 넣음. 저장소 폴더 이름이 `jobvis`면 전과 같은 볼륨(`jobvis_jobvis-data`). 폴더 이름이 다른 PC는 새 볼륨이 생김(재리 PC 두 대 모두 폴더 이름 `jobvis`).

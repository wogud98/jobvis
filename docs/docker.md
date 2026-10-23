# Docker로 쓰기

README의 [빠른 시작](../README.md#docker-코드-없이-쓰기)에서 옮겨 온 자세한 내용입니다.

## 시작 파일로 쓰기

1. 시작 파일 묶음(`JOBVIS 시작.bat`, `JOBVIS 끄기.bat`, `compose.yml`)을 한 폴더에 풉니다. 저장소의 [`start/`](../start/) 폴더와 같습니다.
2. Docker Desktop을 켜고 **`JOBVIS 시작.bat`** 을 더블클릭합니다.
3. 처음 한 번 "OCR도 받을까요"에 답합니다. 공고 본문이 이미지일 때 글자를 읽는 기능이고 약 560MB를 더 받습니다. 다음부터는 시작할 때 5초 안에 Y를 누르면 바꿀 수 있습니다.
4. 이미지를 받고(처음 몇 분) 화면이 준비되면 브라우저가 http://localhost:8501 을 엽니다.
5. 처음 열면 뜨는 키 창(또는 오른쪽 위 **🔑 키 넣기**)에 Gemini API 키를 붙여넣고 저장합니다.
6. 👤 프로필 탭에서 프로필을 채우고 저장 → 📋 공고 탭에서 수집 → 평가.
7. 끌 때는 **`JOBVIS 끄기.bat`**. 키·프로필·공고·점수는 남습니다.

## 직접 빌드하기 (저장소를 받은 사람)

`git clone https://github.com/wogud98/jobvis.git` → `cd jobvis` → `docker compose up -d` (처음엔 이미지를 만드느라 몇 분 걸립니다. OCR 포함 약 2.5GB). 시작 파일과 같은 데이터(볼륨)를 씁니다. 아래 명령은 저장소 폴더에서 씁니다.

| 하고 싶은 일 | 명령 |
| --- | --- |
| 끄기 (데이터는 남음) | `docker compose down` |
| 다시 켜기 | `docker compose up -d` |
| 코드를 새로 받은 뒤 | `git pull` → `docker compose up -d --build` |
| 공고만 지우고 다시 모으기 (프로필·키는 남음) | 화면 사이드바의 **🗑 공고 초기화** (지원한 공고는 남길 수 있음) |
| 내 데이터까지 모두 지우기 | `docker compose -p jobvis down -v` (어느 폴더에서나) |
| OCR 끄기 (OCR이 안 도는 PC) | `JOBVIS_OCR=off docker compose up -d` (PowerShell: `$env:JOBVIS_OCR="off"; docker compose up -d`) |

## 데이터 위치

- Docker 볼륨 `jobvis-data`: 키·메일 설정(`settings.env`), `profile.yaml`, 공고 원문, 받은함
- Docker 볼륨 `jobvis-db`: 공고·점수
- 모두 내 PC 안에만 있습니다. 평가와 이력서 채우기 때 공고·프로필 글이 Gemini로 전송됩니다.
- 화면은 이 PC에서만 열립니다(`127.0.0.1`). 같은 와이파이의 다른 PC는 들어올 수 없습니다.

## 키 지키기

- 키는 화면에서 넣어 볼륨 안 `settings.env`(권한 600)에만 둡니다. compose 환경변수로 넘기지 않습니다(`docker inspect`에 보이지 않게).
- 화면·결과 문구에 키와 같은 글자가 섞이면 `••••`로 가립니다. 예상 못 한 오류는 종류만 보입니다(`docker compose logs app`에서 자세히).
- [Google Cloud 콘솔 → API 및 서비스 → 사용자 인증 정보](https://console.cloud.google.com/apis/credentials)에서 키를 열어 *API 제한사항*을 **Generative Language API**만 허용으로 바꾸고, 결제를 연결했다면 [예산 알림](https://console.cloud.google.com/billing/budgets)을 걸어 둡니다. 키가 새도 피해가 이 안에서 멈춥니다.
- PC를 넘기거나 키가 샜다고 의심되면: 오른쪽 위 **🔑 키** 버튼 → **🗑 이 PC에서 키 삭제**로 이 PC의 키를 지우고, [AI Studio](https://aistudio.google.com/apikey)에서 그 키를 삭제한 뒤 새로 발급합니다. 화면의 삭제 버튼은 Google의 키를 없애지 않습니다.
- Gmail 앱 비밀번호도 같습니다. ✉ 공고 메일 보내기 → 설정의 **🗑 이 PC에서 메일 설정 삭제**와 [Google 앱 비밀번호](https://myaccount.google.com/apppasswords) 화면에서 삭제합니다.

## 알려진 제한

- Windows·Intel PC를 기준으로 만들었습니다. **Mac(Apple Silicon)은 아직 확인하지 않았습니다.** 안 되면 OCR을 꺼 보세요.

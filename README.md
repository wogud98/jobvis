# JOBVIS

자비스에서 영감받은 AI 취업 비서입니다.
조건(키워드·지역·직무·경력)에 맞는 사람인·잡코리아 채용공고를 공개 페이지에서 모아 구글 시트(또는 Docker로 실행하면 내 PC의 DB)에 저장하고, 내 프로필과 비교해 LLM(기본 Gemini)으로 적합도를 평가합니다.
평가가 쌓이면 부족한 기술을 모아 무엇을 공부해야 할지 보여줍니다. 결과는 PC 브라우저 화면(Streamlit)에서 점수순 카드로 봅니다.

> **개인 사용만.** 수집한 공고를 공유·공개·판매하지 않습니다. 두 사이트 약관은 동의 없는 복제·제3자 제공·영리 이용을 금지합니다.

- 수집: `사이트별 공고 가져오기 → 중복 거르기 → (꺼내기 → 상세 본문 → 저장) 반복`. LLM을 부르지 않습니다. 본문 원문은 PC의 `data/postings/`에만 저장합니다.
- 평가: `(꺼내기 → (신입 제외 | LLM 채점) → 시트에 결과 쓰기) 반복`. 저장해 둔 원문(앞 6,000자)으로 채점하고, 원문이 없으면 시트 정보로 채점해 신뢰 "낮음"으로 적습니다. 기술·경력·문화·커리어 방향 점수, 종합점수, 별점, 판정, 강점, 부족한 점, 신뢰, 보정 내용을 씁니다.
- 화면: `streamlit run app.py`. 공고 탭의 수집·평가·받은함 버튼으로 터미널과 같은 작업을 실행하고(한 번에 하나), 요약 칸·점수순 카드·막대 차트·필터로 결과를 봅니다. 프로필 탭에서 추천 목록을 골라 입력하거나, 이력서·포트폴리오 파일(PDF·Word·txt·md)을 올려 빈 칸을 채운 뒤 저장합니다. 이력서 글자는 LLM 제공자로 전송되고 파일은 저장하지 않습니다. 탭마다 "사용법" 토글이 있습니다.
- 받은함: 이미지뿐이라 본문을 못 읽은 공고는 사람이 저장한 이미지를 `data/inbox/`(또는 화면 카드)에 넣고 `--inbox`로 읽습니다.
- 스킬 갭: 시트의 부족한 점을 점수로 가중해 순위를 냅니다. LLM을 부르지 않습니다.

## 반 사람용 시작하기 (Docker)

Docker만 있으면 됩니다. 구글 시트·서비스 계정 설정은 필요 없고, 결과는 내 PC 안의 DB(Postgres)에 저장됩니다.

1. 코드를 받습니다: `git clone https://github.com/wogud98/jobvis.git` → `cd jobvis`
2. `docker compose up -d` (처음엔 이미지를 만드느라 몇 분 걸립니다. OCR 포함 약 2.5GB)
3. 브라우저에서 http://localhost:8501 을 엽니다.
4. 처음 열면 뜨는 키 창(또는 오른쪽 위 **🔑 키 넣기**)에 **Gemini API 키**를 붙여넣고 저장합니다. 키는 https://aistudio.google.com/apikey 에서 무료로 발급합니다(구글 로그인 → Create API key).
5. 👤 프로필 탭에서 이력서로 프로필을 채우고 저장 → 📋 공고 탭에서 수집 → 평가.

| 하고 싶은 일 | 명령 |
| --- | --- |
| 끄기 (데이터는 남음) | `docker compose down` |
| 다시 켜기 | `docker compose up -d` |
| 코드를 새로 받은 뒤 | `git pull` → `docker compose up -d --build` |
| 내 데이터까지 모두 지우기 | `docker compose down -v` |
| OCR 끄기 (OCR이 안 도는 PC) | `JOBVIS_OCR=off docker compose up -d` (PowerShell: `$env:JOBVIS_OCR="off"; docker compose up -d`) |

- 데이터가 남는 곳: Docker 볼륨 `jobvis-data`(키 `settings.env`, `profile.yaml`, 공고 원문, 받은함)와 `jobvis-db`(공고·점수). 모두 내 PC 안에만 있습니다. 평가와 이력서 채우기 때 공고·프로필 글이 Gemini로 전송됩니다.
- **키 지키기** (v0.6.1)
  - 키는 화면에서 넣어 볼륨 안 `settings.env`(권한 600)에만 둡니다. compose 환경변수로 넘기지 않습니다(`docker inspect`에 보이지 않게).
  - 화면·결과 문구에 키와 같은 글자가 섞이면 `••••`로 가립니다. 예상 못 한 오류는 종류만 보입니다(`docker compose logs app`에서 자세히).
  - **꼭 하세요:** [Google Cloud 콘솔 → API 및 서비스 → 사용자 인증 정보](https://console.cloud.google.com/apis/credentials)에서 키를 열어 *API 제한사항*을 **Generative Language API**만 허용으로 바꾸고, 결제를 연결했다면 [예산 알림](https://console.cloud.google.com/billing/budgets)을 걸어 둡니다. 키가 새도 피해가 이 안에서 멈춥니다.
  - PC를 넘기거나 키가 샜다고 의심되면: 오른쪽 위 **🔑 키** 버튼 → **🗑 이 PC에서 키 삭제**로 이 PC의 키를 지우고, [AI Studio](https://aistudio.google.com/apikey)에서 그 키를 삭제한 뒤 새로 발급합니다. 화면의 삭제 버튼은 Google의 키를 없애지 않습니다.
- 화면은 이 PC에서만 열립니다(`127.0.0.1`). 같은 와이파이의 다른 PC는 들어올 수 없습니다.
- Windows·Intel PC에서 쓰는 것을 기준으로 만들었습니다. **Mac(Apple Silicon)은 아직 확인하지 않았습니다.** 안 되면 OCR을 꺼 보세요.
- 개인 사용만: 각자 자기 PC에서 자기 용도로 씁니다. 수집한 공고를 공유·공개하지 않습니다.

## 준비물 (Docker 없이 파이썬으로 실행할 때)

1. **Gemini API 키 (무료)**: https://aistudio.google.com/apikey 에서 구글 계정으로 로그인 → Create API key. `.env`의 `GOOGLE_API_KEY`에 넣습니다.
2. **구글 서비스 계정**
   - https://console.cloud.google.com 에서 프로젝트 생성 → "Google Sheets API" 사용 설정
   - 사용자 인증 정보 → 서비스 계정 만들기 → 키 추가(JSON) → 받은 파일을 `service_account.json`으로 이 폴더에 저장
   - 구글 시트를 하나 만들고, JSON 안의 `client_email` 주소에 시트를 **편집자로 공유**

## 실행

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-ocr.txt  # 선택: 공고 이미지 글자 읽기(PaddleOCR, 약 1GB). 없으면 글자 본문만 저장
cp .env.example .env              # 열어서 키와 시트 ID 입력
streamlit run app.py              # 화면에서 프로필 입력 → 수집 → 평가 (터미널 명령도 그대로 됨)
# 또는 cp profile.example.yaml profile.yaml 후 직접 입력
```

프로필(`profile.yaml`)은 개인정보라 커밋되지 않습니다. 필수 칸은 주력 기술, 경력 연수, 희망 직무입니다.

| 하고 싶은 일 | 명령 |
| --- | --- |
| 공고 수집 (두 사이트) | `python main.py --keyword 백엔드 --location 서울 --job 백엔드 --career 신입 --count 10` |
| 한 사이트만 수집 | `python main.py --keyword 백엔드 --source jobkorea` |
| 시트에서 체크한 공고만 평가 | `python main.py --score` |
| 점수 없는 공고 전부 평가 | `python main.py --score all` |
| 수집하고 바로 평가 | `python main.py --keyword 백엔드 --score all` |
| 공부할 기술 순위 | `python main.py --gaps` |
| 화면에서 수집·평가·결과 보기, 프로필 입력 | `streamlit run app.py` |
| 넣어 둔 공고 이미지 읽기 | `python main.py --inbox` (이미지 이름: `saramin_공고ID.png`, 여러 장이면 `saramin_공고ID_2.png`) |

| 옵션 | 값 |
| --- | --- |
| `--keyword` | 검색어. 수집할 때 필요 |
| `--source` | `saramin` 또는 `jobkorea`. 빼면 둘 다 |
| `--location` | 지역 이름 (서울, 경기, 부산 …). 빼면 전국. 잡코리아는 지역 글자로 거름 |
| `--job` | 직무 이름. 사람인 IT개발·데이터 이름 그대로 (백엔드, 프론트엔드, Python …). 잡코리아에는 쓰지 않음 |
| `--career` | `신입` 또는 `경력`. 빼면 거르지 않음. 공고의 경력 글자로 거름 |
| `--count` | 사이트당 가져올 공고 수 1–30, 기본 10 |
| `--score` | 값 없이 쓰면 "평가" 열을 체크한 줄, `all`이면 점수 없는 줄 전부 |
| `--profile` | 프로필 파일. 기본 `profile.yaml` |
| `--gaps` | 스킬 갭 분석. 다른 옵션과 함께 쓰지 않음 |
| `--inbox` | `data/inbox/`의 공고 이미지를 OCR로 읽어 본문 채우기. OCR 설치 필요. 다른 옵션과 함께 쓰지 않음 |

모르는 이름을 넣으면 비슷한 이름과 쓸 수 있는 이름 목록을 보여주고 멈춥니다. 수집이 끝나면 사이트별 `가져옴 / 새로 저장 / 건너뜀 / 실패`와 본문을 못 읽은 공고 수, 평가가 끝나면 `평가 대상 / 완료 / 제외 / 건너뜀 / 실패`를 출력합니다.

### 점수 계산

LLM은 항목별 점수(0–100)만 매기고, 나머지는 코드가 계산합니다.

- 종합점수: 기술 30, 경력 25, 문화 15, 커리어 방향 30 가중 평균. 공고에 문화 근거가 없으면 문화를 빼고 다시 나눕니다.
- 별점: 종합점수 ÷ 20 (예: 71점 → ★★★★☆)
- 판정: 80 이상 강력 추천, 60–79 추천, 40–59 보통, 40 미만 비추천
- 보정: 공고가 요구하는 경력보다 1년 부족하면 경력점수 최대 60, 2년 45, 3년 이상 30이고 종합은 최대 79. 본문 없이 채점한 공고(신뢰 낮음)는 종합 최대 69. 깎은 내용은 "보정" 열에 남습니다.
- 신입 제외: 프로필 경력 연수가 0이고 공고 경력 칸에 "신입"·"무관"이 없으면 LLM을 부르지 않고 "제외 (경력 요구)"로 적습니다.

가중치와 기준은 [ai-job-search](https://github.com/MadsLorentzen/ai-job-search)(MIT)를 참고했습니다.

## 모델 바꾸기

`.env`의 `LLM_MODEL` 한 줄만 바꾸면 됩니다.

| 모델 | `LLM_MODEL` 값 | 필요한 키 |
| --- | --- | --- |
| Gemini (기본, 무료 구간) | `google_genai:gemini-flash-lite-latest` (`gemini-2.5-flash`는 새 키에서 404가 날 수 있음) | `GOOGLE_API_KEY` |
| Claude (유료) | `anthropic:claude-sonnet-5-5` | `ANTHROPIC_API_KEY` + `pip install langchain-anthropic` |

## 구조

| 파일 | 역할 |
| --- | --- |
| `main.py` | 실행 옵션을 받고 수집·평가·스킬 갭·받은함을 실행, 결과 출력 |
| `app.py` | Streamlit 화면 (공고 탭, 프로필 탭). 그리기와 버튼만 |
| `agent/runner.py` | 수집·평가·받은함 실행 (터미널과 화면이 같이 씀), 화면용 작업 스레드·잠금·진행 상황 |
| `agent/reports.py` | 실행 결과 요약 글 (터미널 출력, 화면 결과 칸) |
| `agent/resume.py` | 이력서·포트폴리오 글자 뽑기, LLM으로 프로필 칸 찾기, 입력란에 합치기 |
| `agent/view.py` | 화면 카드·정렬·필터·차트 자료·요약 칸·오류 문구 |
| `agent/profile_form.py` | 프로필 탭 입력란, 추천 목록, 파일 값 ↔ 입력란 값 |
| `.streamlit/config.toml` | 화면 테마 (네오 브루탈리즘, 초록 포인트) |
| `agent/inbox.py` | 받은함 이미지 OCR, 화면에서 넣은 이미지 저장 |
| `agent/codes.py` | 지역·직무 이름 → 사람인 코드, 경력·지역 글자 거르기 |
| `agent/graph.py` | LangGraph 흐름 두 개(수집, 평가)와 채점 프롬프트 |
| `agent/scoring.py` | LLM 응답 검증, 종합점수·별점·판정 계산, 점수 보정·신뢰·신입 제외, 평가할 줄 고르기 |
| `agent/gaps.py` | 부족한 점 가중 집계 |
| `agent/user_profile.py` | 프로필(`profile.yaml`) 검사·저장, LLM에 넘길 글 만들기 |
| `agent/saramin.py` | 사람인 검색 결과·상세 본문 읽기 |
| `agent/jobkorea.py` | 잡코리아 검색 결과·상세 본문 읽기 |
| `agent/crawler.py` | 요청 규칙: robots.txt 확인, 이름 밝힌 User-Agent, 3초 간격, 403·429면 멈춤 |
| `agent/ocr.py` | 공고 이미지 글자 읽기 (PaddleOCR, 선택 설치) |
| `agent/postings.py` | 본문 글자 뽑기, 원문 파일 저장·읽기, 본문 상태 |
| `agent/sheets.py` | 구글 시트 저장, 줄 읽기, 평가 결과 쓰기 |
| `agent/store.py` | 시트와 DB 중 어디에 저장할지 고름 (`JOBVIS_STORAGE`, 기본 `sheet`) |
| `agent/db.py` | DB(Postgres) 저장. 시트와 같은 칸을 같은 함수로 |
| `agent/settings.py` | 화면에서 넣은 LLM 키를 `data/settings.env`에 저장·읽기 |
| `Dockerfile`, `docker-compose.yml` | 반 배포용 이미지(OCR 포함)와 실행 설정 (앱 + Postgres) |

## 개발 문서

요구사항, UML 설계, 테스트, 회고는 [docs/](docs/)에 버전별로 정리합니다.

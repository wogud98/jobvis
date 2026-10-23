# 개발자용 안내

README의 [빠른 시작](../README.md#빠른-시작)에서 옮겨 온 자세한 내용입니다. 파이썬으로 직접 실행하거나 코드를 고칠 때 봅니다.

## 구글 시트 준비

파이썬으로 실행하면 결과를 구글 시트에 저장합니다(기본 `JOBVIS_STORAGE=sheet`).

1. https://console.cloud.google.com 에서 프로젝트를 만들고 "Google Sheets API"를 사용 설정합니다.
2. 사용자 인증 정보 → 서비스 계정 만들기 → 키 추가(JSON) → 받은 파일을 `service_account.json`으로 저장소 폴더에 둡니다.
3. 구글 시트를 하나 만들고, JSON 안의 `client_email` 주소에 시트를 **편집자로 공유**합니다.
4. `.env`의 `GOOGLE_SHEET_ID`에 시트 주소의 `/d/`와 `/edit` 사이 글자를 넣습니다.

`service_account.json`, `.env`, `profile.yaml`은 커밋되지 않습니다(`.gitignore`).

## 설치와 실행

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-ocr.txt  # 선택: 공고 이미지 글자 읽기(PaddleOCR, 약 1GB). 없으면 글자 본문만 저장
cp .env.example .env                 # 키와 시트 ID 입력
streamlit run app.py                 # 화면에서 프로필 입력 → 수집 → 평가
# 또는 cp profile.example.yaml profile.yaml 후 직접 입력
```

프로필(`profile.yaml`)의 필수 칸은 주력 기술, 경력 연수, 희망 직무입니다.

## 명령줄 실행 (`main.py`)

화면과 같은 작업을 터미널에서 합니다.

| 하고 싶은 일 | 명령 |
| --- | --- |
| 공고 수집 (두 사이트) | `python main.py --keyword 백엔드 --location 서울,경기 --job 백엔드 --career 신입 --count 10` |
| 한 사이트만 수집 | `python main.py --keyword 백엔드 --source jobkorea` |
| 시트에서 체크한 공고만 평가 | `python main.py --score` |
| 점수 없는 공고 전부 평가 | `python main.py --score all` |
| 수집하고 바로 평가 | `python main.py --keyword 백엔드 --score all` |
| 공부할 기술 순위 | `python main.py --gaps` |
| 넣어 둔 공고 이미지 읽기 | `python main.py --inbox` (이미지 이름: `saramin_공고ID.png`, 여러 장이면 `saramin_공고ID_2.png`) |

| 옵션 | 값 |
| --- | --- |
| `--keyword` | 검색어. 수집할 때 필요 |
| `--source` | `saramin` 또는 `jobkorea`. 빼면 둘 다 |
| `--location` | 지역 이름 (서울, 경기, 부산 …). 여러 개는 쉼표로 (`서울,경기`). 빼면 전국. 잡코리아는 지역 글자로 거름 |
| `--job` | 직무 이름. 사람인 IT개발·데이터 이름 그대로 (백엔드, 프론트엔드, Python …). 잡코리아에는 쓰지 않음 |
| `--career` | `신입` 또는 `경력`. 빼면 거르지 않음. 공고의 경력 글자로 거름 |
| `--count` | 사이트당 가져올 공고 수 1–30, 기본 10 |
| `--score` | 값 없이 쓰면 "평가" 열을 체크한 줄, `all`이면 점수 없는 줄 전부 |
| `--profile` | 프로필 파일. 기본 `profile.yaml` |
| `--gaps` | 스킬 갭 분석. 다른 옵션과 함께 쓰지 않음 |
| `--inbox` | `data/inbox/`의 공고 이미지를 OCR로 읽어 본문 채우기. OCR 설치 필요. 다른 옵션과 함께 쓰지 않음 |

모르는 이름을 넣으면 비슷한 이름과 쓸 수 있는 이름 목록을 보여주고 멈춥니다. 수집이 끝나면 사이트별 `가져옴 / 새로 저장 / 건너뜀 / 실패`와 본문을 못 읽은 공고 수, 평가가 끝나면 `평가 대상 / 완료 / 제외 / 건너뜀 / 실패`를 출력합니다.

## 동작 흐름

- 수집: `사이트별 공고 가져오기 → 중복 거르기 → (꺼내기 → 상세 본문 → 저장) 반복`. LLM을 부르지 않습니다. 본문 원문은 PC의 `data/postings/`에만 저장합니다.
- 평가: `(꺼내기 → (신입 제외 | LLM 채점) → 시트에 결과 쓰기) 반복`. 저장해 둔 원문(앞 6,000자)으로 채점하고, 원문이 없으면 시트 정보로 채점해 신뢰 "낮음"으로 적습니다.
- 받은함: 이미지뿐이라 본문을 못 읽은 공고는 사람이 저장한 이미지를 `data/inbox/`(또는 화면 카드)에 넣고 읽습니다.
- 스킬 갭: 부족한 점을 점수로 가중해 순위를 냅니다. LLM을 부르지 않습니다.

## 점수 계산

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

## 파일 구조

| 파일 | 역할 |
| --- | --- |
| `main.py` | 실행 옵션을 받고 수집·평가·스킬 갭·받은함을 실행, 결과 출력 |
| `app.py` | Streamlit 화면 (공고 탭, 프로필 탭, 메일·기술 모아보기 창). 그리기와 버튼만 |
| `agent/runner.py` | 수집·평가·받은함 실행 (터미널과 화면이 같이 씀), 화면용 작업 스레드·잠금·진행 상황 |
| `agent/graph.py` | LangGraph 흐름 두 개(수집, 평가)와 채점 프롬프트 |
| `agent/scoring.py` | LLM 응답 검증, 종합점수·별점·판정 계산, 점수 보정·신뢰·신입 제외, 평가할 줄 고르기 |
| `agent/gaps.py` | 부족한 점 가중 집계 |
| `agent/skills.py`, `agent/skill_aliases.yaml` | 같은 기술의 다른 이름 묶기(같은 말 사전). 기술 모아보기·내 기술 판단에 씀 |
| `agent/reports.py` | 실행 결과 요약 글 (터미널 출력, 화면 알림) |
| `agent/view.py` | 화면 카드·정렬·필터·차트 자료·요약 칸·기술 모아보기 집계·오류 문구 |
| `agent/mail.py` | 고른 공고 메일 만들기, Gmail(SMTP)로 보내기 |
| `agent/resume.py` | 이력서·포트폴리오 글자 뽑기, LLM으로 프로필 칸 찾기, 입력란에 합치기 |
| `agent/profile_form.py` | 프로필 탭 입력란, 추천 목록, 파일 값 ↔ 입력란 값 |
| `agent/user_profile.py` | 프로필(`profile.yaml`) 검사·저장, LLM에 넘길 글 만들기 |
| `agent/settings.py` | 화면에서 넣은 LLM 키·메일 설정을 `data/settings.env`에 저장·읽기, 화면 글에서 키 가리기 |
| `agent/saramin.py`, `agent/jobkorea.py` | 사이트별 검색 결과·상세 본문 읽기 |
| `agent/crawler.py` | 요청 규칙: robots.txt 확인, 이름 밝힌 User-Agent, 3초 간격, 403·429면 멈춤 |
| `agent/codes.py` | 지역·직무 이름 → 사람인 코드, 경력·지역 글자 거르기 |
| `agent/postings.py` | 본문 글자 뽑기, 원문 파일 저장·읽기, 본문 상태 |
| `agent/inbox.py`, `agent/ocr.py` | 받은함 이미지 저장·읽기, 이미지 글자 읽기 (PaddleOCR, 선택 설치) |
| `agent/store.py` | 시트와 DB 중 어디에 저장할지 고름 (`JOBVIS_STORAGE`, 기본 `sheet`) |
| `agent/sheets.py`, `agent/db.py` | 구글 시트·DB(Postgres) 저장. 같은 칸을 같은 함수로 |
| `.streamlit/config.toml` | 화면 테마 (밝은·어두운) |
| `Dockerfile`, `docker-compose.yml` | 이미지(OCR 포함)와 직접 빌드할 때의 실행 설정 (앱 + Postgres) |
| `start/` | 코드 없이 쓰는 시작 파일 (`JOBVIS 시작.bat`, `JOBVIS 끄기.bat`, `compose.yml`) |

## 테스트와 개발 규칙

```bash
pip install -r requirements-dev.txt
ruff check . && ruff format --check .
pytest   # 외부 API를 부르지 않음. 키 없이 통과
```

PR마다 CI가 같은 검사와 비밀정보 검사(gitleaks)를 합니다. 작업 규칙은 [CLAUDE.md](../CLAUDE.md)와 [harness.md](harness.md), 버전별 요구사항·설계·테스트·회고는 [docs/](README.md)에 있습니다.

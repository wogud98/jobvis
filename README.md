# JOBVIS

자비스에서 영감받은 AI 취업 비서입니다.
조건(키워드·지역·직무·경력)에 맞는 사람인·잡코리아 채용공고를 공개 페이지에서 모아 구글 시트에 저장하고, 내 프로필과 비교해 LLM(기본 Gemini)으로 적합도를 평가합니다.
평가가 쌓이면 부족한 기술을 모아 무엇을 공부해야 할지 보여줍니다.

> **개인 사용만.** 수집한 공고를 공유·공개·판매하지 않습니다. 두 사이트 약관은 동의 없는 복제·제3자 제공·영리 이용을 금지합니다.

- 수집: `사이트별 공고 가져오기 → 중복 거르기 → (꺼내기 → 상세 본문 → 저장) 반복`. LLM을 부르지 않습니다. 본문 원문은 PC의 `data/postings/`에만 저장합니다.
- 평가: `(꺼내기 → LLM 채점 → 시트에 결과 쓰기) 반복`. 저장해 둔 원문(앞 6,000자)으로 채점하고, 원문이 없으면 시트 정보로 채점해 판정 옆에 "(본문 미확보)"를 붙입니다. 기술·경력·문화·커리어 방향 점수, 종합점수, 별점, 판정, 강점, 부족한 점을 씁니다.
- 스킬 갭: 시트의 부족한 점을 점수로 가중해 순위를 냅니다. LLM을 부르지 않습니다.

## 준비물

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
cp profile.example.md profile.md  # 열어서 내 기술·경험·희망 방향 입력 (평가할 때 필요)
```

| 하고 싶은 일 | 명령 |
| --- | --- |
| 공고 수집 (두 사이트) | `python main.py --keyword 백엔드 --location 서울 --job 백엔드 --career 신입 --count 10` |
| 한 사이트만 수집 | `python main.py --keyword 백엔드 --source jobkorea` |
| 시트에서 체크한 공고만 평가 | `python main.py --score` |
| 점수 없는 공고 전부 평가 | `python main.py --score all` |
| 수집하고 바로 평가 | `python main.py --keyword 백엔드 --score all` |
| 공부할 기술 순위 | `python main.py --gaps` |

| 옵션 | 값 |
| --- | --- |
| `--keyword` | 검색어. 수집할 때 필요 |
| `--source` | `saramin` 또는 `jobkorea`. 빼면 둘 다 |
| `--location` | 지역 이름 (서울, 경기, 부산 …). 빼면 전국. 잡코리아는 지역 글자로 거름 |
| `--job` | 직무 이름. 사람인 IT개발·데이터 이름 그대로 (백엔드, 프론트엔드, Python …). 잡코리아에는 쓰지 않음 |
| `--career` | `신입` 또는 `경력`. 빼면 거르지 않음. 공고의 경력 글자로 거름 |
| `--count` | 사이트당 가져올 공고 수 1–30, 기본 10 |
| `--score` | 값 없이 쓰면 "평가" 열을 체크한 줄, `all`이면 점수 없는 줄 전부 |
| `--profile` | 프로필 파일. 기본 `profile.md` |
| `--gaps` | 스킬 갭 분석. 다른 옵션과 함께 쓰지 않음 |

모르는 이름을 넣으면 비슷한 이름과 쓸 수 있는 이름 목록을 보여주고 멈춥니다. 수집이 끝나면 사이트별 `가져옴 / 새로 저장 / 건너뜀 / 실패`와 본문을 못 읽은 공고 수, 평가가 끝나면 `평가 대상 / 완료 / 건너뜀 / 실패`를 출력합니다.

### 점수 계산

LLM은 항목별 점수(0–100)만 매기고, 나머지는 코드가 계산합니다.

- 종합점수: 기술 30, 경력 25, 문화 15, 커리어 방향 30 가중 평균. 공고에 문화 근거가 없으면 문화를 빼고 다시 나눕니다.
- 별점: 종합점수 ÷ 20 (예: 71점 → ★★★★☆)
- 판정: 80 이상 강력 추천, 60–79 추천, 40–59 보통, 40 미만 비추천

가중치와 기준은 [ai-job-search](https://github.com/MadsLorentzen/ai-job-search)(MIT)를 참고했습니다.

## 모델 바꾸기

`.env`의 `LLM_MODEL` 한 줄만 바꾸면 됩니다.

| 모델 | `LLM_MODEL` 값 | 필요한 키 |
| --- | --- | --- |
| Gemini (기본, 무료 구간) | `google_genai:gemini-2.5-flash` | `GOOGLE_API_KEY` |
| Claude (유료) | `anthropic:claude-sonnet-5-5` | `ANTHROPIC_API_KEY` + `pip install langchain-anthropic` |

## 구조

| 파일 | 역할 |
| --- | --- |
| `main.py` | 실행 옵션을 받고 수집·평가·스킬 갭을 실행, 결과 출력 |
| `agent/codes.py` | 지역·직무 이름 → 사람인 코드, 경력·지역 글자 거르기 |
| `agent/graph.py` | LangGraph 흐름 두 개(수집, 평가)와 채점 프롬프트 |
| `agent/scoring.py` | LLM 응답 검증, 종합점수·별점·판정 계산, 평가할 줄 고르기 |
| `agent/gaps.py` | 부족한 점 가중 집계 |
| `agent/user_profile.py` | 프로필 파일 읽기 |
| `agent/saramin.py` | 사람인 검색 결과·상세 본문 읽기 |
| `agent/jobkorea.py` | 잡코리아 검색 결과·상세 본문 읽기 |
| `agent/crawler.py` | 요청 규칙: robots.txt 확인, 이름 밝힌 User-Agent, 3초 간격, 403·429면 멈춤 |
| `agent/ocr.py` | 공고 이미지 글자 읽기 (PaddleOCR, 선택 설치) |
| `agent/postings.py` | 본문 글자 뽑기, 원문 파일 저장·읽기, 본문 상태 |
| `agent/sheets.py` | 구글 시트 저장, 줄 읽기, 평가 결과 쓰기 |

## 개발 문서

요구사항, UML 설계, 테스트, 회고는 [docs/](docs/)에 버전별로 정리합니다.

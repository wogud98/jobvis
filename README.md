# JOBVIS

자비스에서 영감받은 AI 취업 비서입니다.
키워드로 사람인 채용공고를 가져와 LLM(기본 Gemini)으로 자격요건을 요약하고, 구글 시트에 한 줄로 저장합니다.
LangGraph로 `공고 가져오기 → 요약(LLM) → 시트 저장` 흐름을 만들었습니다.

## 준비물

1. **사람인 API 키**: https://oapi.saramin.co.kr 에서 회원가입 후 API 이용 신청 (승인까지 시간이 걸릴 수 있음).
2. **Gemini API 키 (무료)**: https://aistudio.google.com/apikey 에서 구글 계정으로 로그인 → Create API key. `.env`의 `GOOGLE_API_KEY`에 넣습니다.
3. **구글 서비스 계정**
   - https://console.cloud.google.com 에서 프로젝트 생성 → "Google Sheets API" 사용 설정
   - 사용자 인증 정보 → 서비스 계정 만들기 → 키 추가(JSON) → 받은 파일을 `service_account.json`으로 이 폴더에 저장
   - 구글 시트를 하나 만들고, JSON 안의 `client_email` 주소에 시트를 **편집자로 공유**

## 실행

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    # 열어서 키와 시트 ID 입력
python main.py --keyword "백엔드 신입" --location 101000
```

`--location`은 사람인 지역 코드입니다(101000 = 서울). 빼면 전국에서 찾습니다.

## 모델 바꾸기

`.env`의 `LLM_MODEL` 한 줄만 바꾸면 됩니다.

| 모델 | `LLM_MODEL` 값 | 필요한 키 |
| --- | --- | --- |
| Gemini (기본, 무료 구간) | `google_genai:gemini-2.5-flash` | `GOOGLE_API_KEY` |
| Claude (유료) | `anthropic:claude-sonnet-5-5` | `ANTHROPIC_API_KEY` + `pip install langchain-anthropic` |

## 구조

| 파일 | 역할 |
| --- | --- |
| `main.py` | 실행 시 키워드·지역을 받음 |
| `agent/graph.py` | LangGraph 흐름과 LLM 요약 |
| `agent/saramin.py` | 사람인 API 호출 |
| `agent/sheets.py` | 구글 시트 저장 |

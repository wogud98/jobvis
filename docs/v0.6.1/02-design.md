# v0.6.1 설계

모듈 구조, 호출 순서, 저장 칸은 v0.6과 같다. 그래서 UML은 [v0.6 설계](../v0.6/02-design.md)를 그대로 쓴다. 바뀌는 곳은 `app.py`(화면·CSS·키 삭제), `agent/resume.py`(합치기), `agent/settings.py`(`delete_key`, `redact` 함수 추가), `runner.error_text`·`reports`(가리기 호출), `docker-compose.yml`·`Dockerfile`이다. 새 모듈과 State 필드는 없다.

## 결정

| ID | 결정 | 이유 |
| --- | --- | --- |
| D1 | 제목 색은 테마 색표에 `title`을 더해 밝은 `#111111`, 어두운 `#ffffff` (F1) | 밝은 바탕에서 흰 글자는 안 보임 |
| D2 | 키 칸은 `key-card` 컨테이너, 폼 안 `st.columns([5, 1])`에 입력란(이름 숨김)과 저장 (F2) | 카드 하나 높이를 3줄 → 2줄 |
| D3 | 카드는 `[체크+점수, 회사·직무, 버튼]` 세 칸. CSS로 체크 칸 4.6rem·버튼 칸 7rem 고정, 가운데 칸만 줄어듦, 카드 안 칸 줄바꿈 금지 (F4) | 네 칸일 때 좁은 창에서 가운데 칸이 없어지고 글자가 잘림 |
| D4 | 결과는 `st.toast`. 같은 작업(`label-started`)은 `session_state`에 기록해 한 번만 (F5) | 작업이 끝난 뒤 화면을 다시 그릴 때마다 알림이 또 뜨지 않게 |
| D5 | 고르기 칸은 키워드 목록 칸에 `flex-wrap: wrap`, 바깥 칸 `max-height` 해제 (F7) | Streamlit 1.66은 한 줄 + 가로 스크롤이라 마우스 휠로 못 움직임 |
| D6 | `resume._same()`: 띄어쓰기를 하나로 줄이고 소문자로 바꾼 글자로 비교. 채울 때 목록 칸 모두 거침 (F8) | 글자가 아예 다른 중복("…네트워크" vs "…과정")은 프롬프트 규칙으로만 줄임 |
| D7 | 프로필 칸 높이는 칸을 감싼 `stLayoutWrapper`가 늘어나게 하고 칸 `height: 100%` (F9) | 칸 자체가 아니라 감싼 칸이 내용 높이로 멈춰 있었음 |
| D8 | `settings.redact(text)`: 지금 환경의 `GOOGLE_API_KEY`·`ANTHROPIC_API_KEY` 값(8자 이상)을 `••••`로 바꿈. `runner.error_text`(작업·버튼 오류 전부), `reports`의 실패·멈춤 줄에서 부름 (F12) | 오류 글이 화면으로 나가는 길목이 이 둘. 짧은 값은 흔한 글자까지 가려서 건너뜀 |
| D9 | Docker CMD에 `--client.showErrorDetails=type` (F12) | 잡지 못한 예외의 메시지·경로가 화면에 안 나감. 로그에는 남음 |
| D10 | `settings.delete_key()`: `dotenv.unset_key`로 `data/settings.env`에서 지우고 `os.environ`에서 뺌. 파일에서 지웠는지 돌려줘 화면 안내를 고름 (F14) | `.env`는 사용자 파일이라 고치지 않음 |

## 보완 결정 (F15–F20)

| ID | 결정 | 이유 |
| --- | --- | --- |
| D11 | `reload_after_job()`: 화면을 그릴 때마다 마지막 작업이 끝났고 아직 다시 읽지 않았으면(`session_state["reloaded_job"]`이 `label-started`와 다르면) `reload_rows()`. 진행 막대가 끝을 볼 때도 같은 표시를 남겨 두 번 읽지 않음 (F16) | 진행 막대는 그 회차에 작업이 돌고 있을 때만 그려진다. 재현은 못 했지만 작업이 그 사이에 끝나면 다시 읽기를 놓칠 수 있는 길이 이것뿐 |
| D12 | 키는 `@st.dialog` 창. 저장은 폼 버튼 콜백(`save_key`)에서 하고, 저장 뒤 창 안에서 `st.rerun()`으로 닫음. 오류·삭제 안내가 남아 있으면 다음 회차에 창을 다시 띄움 (F17) | 창 안 버튼은 창 부분만 다시 그리므로 콜백이어야 저장이 확실함 |
| D13 | 창은 한 번에 하나라, 키가 없으면 키 창이 먼저, 키를 넣은 뒤 사용법 창 (F17) | 처음 쓰는 사람이 키부터 넣게 |
| D14 | 이력서 칸은 `st.expander(expanded=프로필 비었음 or 채운 값 있음)` (F18) | 막지 않고 접어서 글을 줄임 |
| D15 | 사이드바 `background: var(--jv-paper)`, 필터는 `box-filter` 컨테이너(카드 CSS 그대로) (F20) | 메인 카드와 같은 규칙을 그대로 씀 |

CSS는 v0.5.1 N5처럼 key로 붙는 `st-key-*` 클래스와 `data-testid`에만 건다. Streamlit 판을 올리면 F4·F7·F9 모양을 다시 확인한다.

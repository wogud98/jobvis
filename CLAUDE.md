# JOBVIS 작업 규칙

AI 코딩 에이전트(Claude Code 등)와 사람이 이 저장소에서 작업할 때 따르는 규칙입니다.
JOBVIS는 사람인 채용공고를 수집해 LLM으로 요약하고 구글 시트에 저장하는 Python + LangGraph 프로젝트입니다.

## 개발 과정

기능은 버전 단위로 만들고, 버전마다 이 순서를 지킵니다. 문서는 `docs/vX.Y/`에 둡니다.

1. `01-requirements.md`가 없거나 사용자가 확정하지 않았으면 코드를 쓰지 않는다.
2. `02-design.md`에 UML(Mermaid)과 설계 결정을 먼저 쓴다. 코드 구조가 바뀌면 UML도 같은 PR에서 고친다.
3. 구현한다. 요구사항 ID(F1, N1 …)를 커밋 메시지나 PR 설명에 적는다.
4. `03-test.md`에 테스트 결과를 남긴다. 실제 API로 확인하지 못한 것은 "미확인"으로 쓴다.
5. `04-retrospective.md`에 바뀐 결정과 배운 점을 남긴다.

방향과 결정 사항은 `docs/roadmap.md`가 기준이다. 결정을 바꾸려면 사용자에게 먼저 묻는다.

## 명령

```bash
pip install -r requirements-dev.txt   # 처음 한 번
ruff check . && ruff format --check .  # 린트, 포맷 검사
pytest                                 # 테스트 (외부 API 호출 없음)
python main.py --keyword "백엔드 신입"  # 실제 실행 (.env 필요)
```

## 완료 기준

PR을 올리기 전에 모두 통과해야 한다. CI(`.github/workflows/ci.yml`)도 같은 검사를 한다.

- `ruff check .`, `ruff format --check .`, `pytest` 통과
- 새 기능에는 테스트가 있다
- 바뀐 구조가 `docs/`의 UML에 반영돼 있다

## 코드 규칙

- 노드 함수는 `agent/graph.py`에 두고, State를 받아 바뀐 칸만 딕셔너리로 돌려준다.
- 외부 서비스 호출은 노드 밖 모듈(`saramin.py`, `sheets.py` 등)에 둔다. 테스트에서 이 모듈을 가짜로 바꾼다.
- LLM은 `init_chat_model(LLM_MODEL)`로만 만든다. 특정 제공자 클래스를 직접 import하지 않는다.
- 테스트는 실제 API를 부르지 않는다. 키가 없어도 `pytest`가 통과해야 한다.
- 사용자에게 보이는 문구와 문서는 한국어로 쓴다.

## 하지 말 것

- `.env`, `service_account.json`, API 키를 커밋하지 않는다.
- 테스트를 지우거나 건너뛰어서 통과시키지 않는다.
- 요구사항에 없는 기능을 추가하지 않는다. 필요해 보이면 `docs/roadmap.md`의 다음 버전 후보로 적고 사용자에게 묻는다.

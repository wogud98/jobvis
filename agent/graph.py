"""LangGraph 흐름 두 개.

수집: 공고 가져오기 -> 중복 거르기 -> (꺼내기 -> 저장) 반복. LLM을 부르지 않는다.
평가: (꺼내기 -> LLM 채점 -> 시트에 결과 쓰기) 반복.
"""

import operator
import os
from datetime import datetime
from typing import Annotated, TypedDict

from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph

from agent import codes, saramin, scoring, sheets

MAX_COUNT = 110  # 사람인 API 한 번 요청 한도


class State(TypedDict, total=False):
    keyword: str
    region_code: str | None
    job_code: str | None
    career: str | None
    count: int
    fetched: int
    queue: list[dict]
    current: dict | None
    # 노드가 돌려준 목록을 덮어쓰지 않고 이어 붙인다.
    saved: Annotated[list[dict], operator.add]
    skipped: Annotated[list[dict], operator.add]
    failed: Annotated[list[dict], operator.add]


def fetch(state: State) -> State:
    career = state.get("career")
    # 사람인 API에는 경력 조건이 없어서, 경력으로 거를 때는 최대한 받아 와서 거른다.
    request_count = MAX_COUNT if career else state["count"]
    jobs = saramin.fetch_jobs(state["keyword"], state.get("region_code"), state.get("job_code"), request_count)
    jobs = [job for job in jobs if codes.matches_career(job["experience_code"], career)][: state["count"]]
    return {"fetched": len(jobs), "queue": jobs}


def dedupe(state: State) -> State:
    if not state["queue"]:
        return {}
    saved_ids = sheets.existing_ids()
    new = [job for job in state["queue"] if job["id"] not in saved_ids]
    skipped = [job for job in state["queue"] if job["id"] in saved_ids]
    return {"queue": new, "skipped": skipped}


def pick(state: State) -> State:
    queue = state["queue"]
    if not queue:
        return {"current": None}
    return {"current": queue[0], "queue": queue[1:]}


def _failure(job: dict, step: str, error: Exception) -> dict:
    # 예외 메시지에는 키나 인증정보가 섞일 수 있어 예외 이름만 남긴다.
    return {"company": job["company"], "title": job["title"], "step": step, "error": type(error).__name__}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def save(state: State) -> State:
    job = state["current"]
    # 자격요건 칸은 비워 두고(F2) 평가에 쓸 경력·학력·키워드를 함께 저장한다(F3). 평가 칸은 체크 해제 상태.
    row = [
        job["company"],
        job["title"],
        "",
        job["deadline"],
        job["url"],
        job["id"],
        _now(),
        job["experience"],
        job["education"],
        job["keywords"],
        False,
    ]
    try:
        sheets.append_row(row)
    except Exception as e:  # 한 건이 실패해도 나머지는 계속 처리한다 (N1)
        return {"failed": [_failure(job, "저장", e)]}
    return {"saved": [job]}


def _after_pick(state: State) -> str:
    return "save" if state["current"] else END


def recursion_limit(count: int) -> int:
    # 공고(줄)마다 수집은 pick, save 2단계, 평가는 score_pick, score, write 3단계. 큰 쪽 기준 + 여유
    return count * 3 + 10


def build_graph():
    graph = StateGraph(State)
    graph.add_node("fetch", fetch)
    graph.add_node("dedupe", dedupe)
    graph.add_node("pick", pick)
    graph.add_node("save", save)
    graph.add_edge(START, "fetch")
    graph.add_edge("fetch", "dedupe")
    graph.add_edge("dedupe", "pick")
    graph.add_conditional_edges("pick", _after_pick, ["save", END])
    graph.add_edge("save", "pick")
    return graph.compile()


# ---- 평가 ----


class ScoreState(TypedDict, total=False):
    profile: str
    queue: list[dict]
    current: dict | None
    evaluation: scoring.Evaluation | None
    done: Annotated[list[dict], operator.add]
    skipped: Annotated[list[dict], operator.add]
    failed: Annotated[list[dict], operator.add]


# 기준표는 요구사항 F10 표와 같다. 템플릿이라 JSON의 중괄호는 두 번 쓴다.
SCORE_SYSTEM_PROMPT = """너는 채용공고와 지원자 프로필을 비교해 적합도를 채점하는 도우미야.

항목별 0-100 정수 점수 기준:
- skills(기술)
  80-100 필수 요건이 주력 기술 / 60-79 대부분 맞고 배울 수 있는 빈칸 1-2개
  40-59 일부만 맞고 공부가 꽤 필요 / 0-39 거의 맞지 않음
- experience(경력)
  80-100 같은 분야·같은 종류의 일을 해 봄 / 60-79 관련 경험이 있고 옮겨 쓸 수 있음
  40-59 인접 경험, 설득이 필요함 / 0-39 관련 없음
- culture(문화)
  80-100 일하는 방식이 선호와 잘 맞음 / 60-79 대체로 맞음
  40-59 맞지 않는 부분이 있음 / 0-39 크게 맞지 않음
- career(커리어 방향)
  80-100 희망 방향과 거의 같음 / 60-79 대체로 맞지만 일부만 겹침
  40-59 할 수는 있지만 거리가 있음 / 0-39 방향과 반대

규칙:
- 공고 정보에 없는 내용은 지어내지 마. 문화에 대한 근거가 공고에 없으면 culture는 null로 해.
- summary는 자격요건을 한국어 한 줄(60자 이내)로 요약해.
- strengths와 gaps는 각각 최대 3개. gaps는 공부할 대상이 드러나게 짧은 기술 이름으로 써 (예: Docker, AWS, Spring Boot).
- 아래 형식의 JSON만 출력해. 다른 말은 쓰지 마.

{{"summary": "...", "skills": 0, "experience": 0, "culture": null, "career": 0,
 "strengths": ["..."], "gaps": ["..."]}}"""

score_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SCORE_SYSTEM_PROMPT),
        (
            "human",
            "# 지원자 프로필\n{profile}\n\n# 채용공고\n회사: {company}\n직무: {title}\n경력: {experience}\n"
            "학력: {education}\n키워드: {keywords}",
        ),
    ]
)


def score_pick(state: ScoreState) -> ScoreState:
    queue = state["queue"]
    if not queue:
        return {"current": None}
    return {"current": queue[0], "queue": queue[1:]}


def score(state: ScoreState) -> ScoreState:
    row = state["current"]
    try:
        # "제공자:모델" 형식. 예) google_genai:gemini-2.5-flash, anthropic:claude-sonnet-5-5
        # Gemini 2.5는 생각 토큰도 출력 한도를 쓰므로 JSON이 잘리지 않게 넉넉히 둔다.
        llm = init_chat_model(os.getenv("LLM_MODEL", "google_genai:gemini-2.5-flash"), max_tokens=2048)
        answer = (score_prompt | llm).invoke({"profile": state["profile"], **row})
        evaluation = scoring.parse(answer.text)
    except Exception as e:  # LLM 오류나 형식 오류여도 나머지 줄은 계속 처리한다 (F15)
        return {"evaluation": None, "failed": [_failure(row, "채점", e)]}
    return {"evaluation": evaluation}


def write(state: ScoreState) -> ScoreState:
    row, evaluation = state["current"], state["evaluation"]
    total = scoring.overall(evaluation)
    values = [
        False,  # 평가 끝나면 체크 해제 (F7)
        total,
        scoring.stars(total),
        scoring.verdict(total),
        evaluation.skills,
        evaluation.experience,
        "-" if evaluation.culture is None else evaluation.culture,
        evaluation.career,
        ", ".join(evaluation.strengths),
        ", ".join(evaluation.gaps),
        _now(),
    ]
    try:
        sheets.write_result(row["row"], evaluation.summary, values)
    except Exception as e:  # 한 줄이 실패해도 나머지는 계속 처리한다
        return {"failed": [_failure(row, "저장", e)]}
    return {"done": [row]}


def _after_score_pick(state: ScoreState) -> str:
    return "score" if state["current"] else END


def _after_score(state: ScoreState) -> str:
    return "write" if state["evaluation"] is not None else "score_pick"


def build_score_graph():
    graph = StateGraph(ScoreState)
    graph.add_node("score_pick", score_pick)
    graph.add_node("score", score)
    graph.add_node("write", write)
    graph.add_edge(START, "score_pick")
    graph.add_conditional_edges("score_pick", _after_score_pick, ["score", END])
    graph.add_conditional_edges("score", _after_score, ["write", "score_pick"])
    graph.add_edge("write", "score_pick")
    return graph.compile()

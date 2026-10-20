"""LangGraph 흐름: 공고 가져오기 -> 중복 거르기 -> (꺼내기 -> 요약 -> 저장) 반복."""

import operator
import os
from datetime import datetime
from typing import Annotated, TypedDict

from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph

from agent import codes, saramin, sheets

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
    requirements: str | None
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


SYSTEM_PROMPT = (
    "너는 채용공고를 정리하는 도우미야. 주어진 정보로 자격요건을 한국어 한 줄(60자 이내)로 요약해. "
    "없는 내용은 지어내지 마."
)

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("human", "직무: {title}\n경력: {experience}\n학력: {education}\n키워드: {keywords}"),
    ]
)


def _failure(job: dict, step: str, error: Exception) -> dict:
    # 예외 메시지에는 키나 인증정보가 섞일 수 있어 예외 이름만 남긴다.
    return {"company": job["company"], "title": job["title"], "step": step, "error": type(error).__name__}


def summarize(state: State) -> State:
    job = state["current"]
    try:
        # "제공자:모델" 형식. 예) google_genai:gemini-2.5-flash, anthropic:claude-sonnet-5-5
        llm = init_chat_model(os.getenv("LLM_MODEL", "google_genai:gemini-2.5-flash"), max_tokens=1024)
        answer = (prompt | llm).invoke(job)
    except Exception as e:  # 한 건이 실패해도 나머지는 계속 처리한다 (N3)
        return {"requirements": None, "failed": [_failure(job, "요약", e)]}
    return {"requirements": answer.text.strip()}


def save(state: State) -> State:
    job = state["current"]
    saved_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    row = [job["company"], job["title"], state["requirements"], job["deadline"], job["url"], job["id"], saved_at]
    try:
        sheets.append_row(row)
    except Exception as e:  # 한 건이 실패해도 나머지는 계속 처리한다 (N3)
        return {"failed": [_failure(job, "저장", e)]}
    return {"saved": [job]}


def _after_pick(state: State) -> str:
    return "summarize" if state["current"] else END


def _after_summarize(state: State) -> str:
    return "save" if state["requirements"] is not None else "pick"


def recursion_limit(count: int) -> int:
    # fetch, dedupe 2단계 + 공고마다 pick, summarize, save 3단계 + 여유
    return count * 3 + 10


def build_graph():
    graph = StateGraph(State)
    graph.add_node("fetch", fetch)
    graph.add_node("dedupe", dedupe)
    graph.add_node("pick", pick)
    graph.add_node("summarize", summarize)
    graph.add_node("save", save)
    graph.add_edge(START, "fetch")
    graph.add_edge("fetch", "dedupe")
    graph.add_edge("dedupe", "pick")
    graph.add_conditional_edges("pick", _after_pick, ["summarize", END])
    graph.add_conditional_edges("summarize", _after_summarize, ["save", "pick"])
    graph.add_edge("save", "pick")
    return graph.compile()

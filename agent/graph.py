"""LangGraph 흐름: 공고 가져오기 -> 자격요건 요약(LLM) -> 시트 저장."""

import os
from typing import TypedDict

from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph

from agent import saramin, sheets


class State(TypedDict, total=False):
    keyword: str
    location: str | None
    job: dict
    requirements: str


def fetch(state: State) -> State:
    jobs = saramin.fetch_jobs(state["keyword"], state.get("location"), count=1)
    if not jobs:
        raise SystemExit(f"'{state['keyword']}' 키워드로 찾은 공고가 없어요.")
    return {"job": jobs[0]}


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


def summarize(state: State) -> State:
    # "제공자:모델" 형식. 예) google_genai:gemini-2.5-flash, anthropic:claude-sonnet-5-5
    llm = init_chat_model(os.getenv("LLM_MODEL", "google_genai:gemini-2.5-flash"), max_tokens=1024)
    answer = (prompt | llm).invoke(state["job"])
    return {"requirements": answer.text.strip()}


def save(state: State) -> State:
    job = state["job"]
    sheets.append_row([job["company"], job["title"], state["requirements"], job["deadline"], job["url"]])
    return {}


def build_graph():
    graph = StateGraph(State)
    graph.add_node("fetch", fetch)
    graph.add_node("summarize", summarize)
    graph.add_node("save", save)
    graph.add_edge(START, "fetch")
    graph.add_edge("fetch", "summarize")
    graph.add_edge("summarize", "save")
    graph.add_edge("save", END)
    return graph.compile()

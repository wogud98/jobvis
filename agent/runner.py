"""수집·평가·받은함 실행. 터미널(main.py)과 화면(app.py)이 같은 함수를 부른다 (v0.5.2 F4, F7, F10, F14).

화면에서는 버튼을 누르면 별도 스레드에서 돌린다. Streamlit은 다른 입력란을 누를 때마다 화면 코드를 처음부터 다시 실행해
화면 코드 안에서 돌리면 수집이 중간에 끊긴다. 진행 상황은 Job에 적고 화면이 1초마다 읽어 그린다 (F5, F9).
한 번에 하나만 실행한다 (F12). 화면 서버는 한 프로세스라 창을 두 개 열어도 이 모듈의 잠금 하나를 같이 쓴다.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from agent import codes, inbox, ocr, profile_form, reports, scoring, settings, store, user_profile, view
from agent.graph import MAX_COUNT, SOURCES, build_graph, build_score_graph, recursion_limit

KINDS = {"collect": "수집", "score": "평가", "inbox": "받은함 읽기"}
CAREER_ALL = "전체"


class RunError(Exception):
    """실행 전에 막힌 이유 (입력 틀림, 프로필 없음, OCR 없음, 이미 실행 중). 화면에 그대로 보인다."""


@dataclass
class Job:
    kind: str
    started: str = field(default_factory=lambda: f"{datetime.now():%H:%M:%S}")
    done: int = 0
    total: int = 0
    stage: str = "준비 중"
    result: reports.Summary | None = None  # 끝난 뒤 결과 (F24)
    error: str = ""
    finished: bool = False

    @property
    def label(self) -> str:
        return KINDS[self.kind]


_lock = threading.Lock()
_job: Job | None = None


def current() -> Job | None:
    """지금 또는 마지막으로 실행한 작업. 없으면 None."""
    return _job


def running() -> bool:
    return _job is not None and not _job.finished


def error_text(error: Exception) -> str:
    """실행 중 오류를 화면 문구로. 키·경로는 보이지 않는다 (F13, v0.6.1 F12)."""
    return settings.redact(_error_text(error))


def _error_text(error: Exception) -> str:
    if isinstance(error, (RunError, codes.CodeNotFoundError, user_profile.ProfileError)):
        return str(error)
    hint = reports.llm_hint([cls.__name__ for cls in type(error).__mro__])  # LLM 모델·키 오류 (F26)
    if hint:
        return hint
    message = view.error_message(error)
    if message.startswith(("시트를 읽지 못했습니다", "DB를 읽지 못했습니다")):  # 저장과 상관없는 오류
        return f"실행하지 못했습니다 ({type(error).__name__}). 터미널 로그를 확인해 주세요."
    return message


def start(kind: str, work: Callable[[Job], reports.Summary], *, wait: bool = False) -> Job:
    """work를 별도 스레드에서 실행한다. 이미 실행 중이면 RunError (F12). wait=True면 끝날 때까지 기다린다(테스트용)."""
    global _job
    with _lock:
        if running():
            raise RunError(f"{_job.label}을 실행하는 중입니다. 끝난 뒤 다시 눌러 주세요.")
        job = Job(kind)
        _job = job

    def target() -> None:
        try:
            job.result = work(job)
        except Exception as e:  # 화면이 꺼지지 않게 모든 오류를 문구로 남긴다 (F13)
            job.error = error_text(e)
        finally:
            job.finished = True

    thread = threading.Thread(target=target, name=f"jobvis-{kind}", daemon=True)
    thread.start()
    if wait:
        thread.join()
    return job


# ---- 수집 ----

REGION_NAMES = list(codes.REGIONS)  # 지역 추천 검색어 (F2)
JOB_NAMES = list(codes.JOBS)  # 직무 추천 검색어 (F2)
SOURCE_NAMES = {module.NAME: code for code, module in SOURCES.items()}  # 화면 이름 → 코드


def keyword_options(profile: dict | None) -> list[str]:
    """키워드 추천 검색어: 프로필 희망 직무·주력 기술을 앞에, 그 뒤 직무 이름 (F3)."""
    values = profile_form.to_form(profile)
    return list(dict.fromkeys(values[("direction", "jobs")] + values[("skills", "main")] + JOB_NAMES))


def collect_state(
    keyword: str,
    location: str | None = None,
    job: str | None = None,
    career: str | None = None,
    sources: list[str] | None = None,
    count: int = 10,
) -> dict:
    """입력을 수집 그래프 State로. 모르는 지역·직무 이름이면 사이트에 요청하기 전에 멈춘다 (v0.2 F11)."""
    keyword = (keyword or "").strip()
    if not keyword:
        raise RunError("키워드를 입력해 주세요.")
    if not 1 <= count <= MAX_COUNT:
        raise RunError(f"개수는 1~{MAX_COUNT} 사이로 입력해 주세요.")
    sources = [source for source in (sources or list(SOURCES)) if source in SOURCES]
    if not sources:
        raise RunError("사이트를 하나 이상 골라 주세요.")
    location = (location or "").strip() or None
    job = (job or "").strip() or None
    return {
        "keyword": keyword,
        "sources": sources,
        "location": location,
        "region_code": codes.to_region_code(location) if location else None,
        "job_code": codes.to_job_code(job) if job else None,
        "career": career if career in codes.CAREERS else None,
        "count": count,
    }


def _stream(graph, state: dict, limit: int, on_update: Callable[[str, dict], None] | None) -> dict:
    """그래프를 돌리며 노드마다 on_update(노드 이름, 바뀐 칸)를 부르고 마지막 State를 돌려준다."""
    final = state
    for mode, chunk in graph.stream(state, {"recursion_limit": limit}, stream_mode=["updates", "values"]):
        if mode == "values":
            final = chunk
        elif on_update:
            for node, update in chunk.items():
                on_update(node, update or {})
    return final


def collect(state: dict, on_update: Callable[[str, dict], None] | None = None) -> dict:
    state = state | {"ocr_ready": ocr.available()}
    limit = recursion_limit(state["count"] * len(state["sources"]))
    return _stream(build_graph(), state, limit, on_update)


def _collect_progress(job: Job) -> Callable[[str, dict], None]:
    def on_update(node: str, update: dict) -> None:
        if node == "fetch":
            job.stage = "공고 목록을 가져왔습니다"
        elif node == "dedupe":
            job.total = len(update.get("queue", []))
            job.stage = "새 공고의 본문을 가져오는 중"
        elif node == "pick" and update.get("current"):
            job.done += 1
            job.total = max(job.total, job.done)  # 같은 실행 중복(backup)을 나중에 처리하면 늘어난다
            job.stage = f"{SOURCES[update['current']['source']].NAME} 공고 본문을 가져오는 중"

    return on_update


def start_collect(state: dict, *, wait: bool = False) -> Job:
    def work(job: Job) -> reports.Summary:
        job.stage = "공고 목록을 가져오는 중"
        summary = reports.collect_summary(collect(state, _collect_progress(job)))
        if not ocr.available():  # 할 일이 아니라 참고라 자세히에만
            summary.details.insert(0, f"이미지 OCR 없음: 글자 본문만 저장했습니다. {ocr.INSTALL_HINT}")
        return summary

    return start("collect", work, wait=wait)


# ---- 평가 ----


def score_targets(rows: list[dict], mode: str) -> int:
    """평가 버튼 옆에 미리 보일 대상 수 (F7)."""
    return len(scoring.select_targets(rows, mode)[0])


def load_profile(path: str = user_profile.DEFAULT) -> user_profile.Profile:
    """저장된 프로필. 없거나 틀리면 ProfileError (F8)."""
    profile, _ = user_profile.load(path)
    return profile


def score(mode: str, profile: user_profile.Profile, on_update: Callable[[str, dict], None] | None = None) -> dict:
    targets, skipped = scoring.select_targets(store.read_rows(), mode)
    state = {
        "profile": user_profile.to_prompt(profile),
        "years": profile.experience.years,
        "queue": targets,
        "skipped": skipped,
    }
    if on_update:
        on_update("targets", {"queue": targets})
    return _stream(build_score_graph(), state, recursion_limit(len(targets)), on_update)


def _score_progress(job: Job) -> Callable[[str, dict], None]:
    def on_update(node: str, update: dict) -> None:
        if node == "targets":
            job.total = len(update["queue"])
            job.stage = "평가하는 중"
        elif node == "score_pick" and update.get("current"):
            job.done += 1
            job.stage = f"{update['current'].get('company', '')} 공고를 평가하는 중"

    return on_update


def start_score(mode: str, profile: user_profile.Profile, *, wait: bool = False) -> Job:
    def work(job: Job) -> reports.Summary:
        job.stage = "공고를 읽는 중"
        return reports.score_summary(score(mode, profile, _score_progress(job)))

    return start("score", work, wait=wait)


# ---- 받은함 ----


def inbox_count() -> int:
    """받은함에 있는 이미지 수 (이름 형식이 맞는 것만, F10)."""
    groups, _ = inbox.scan()
    return sum(len(files) for files in groups.values())


def read_inbox() -> inbox.InboxResult:
    if not ocr.available():  # 아무 파일도 건드리지 않는다 (v0.5 F44, v0.5.2 F11)
        raise RunError(f"OCR이 설치돼 있지 않습니다. {ocr.INSTALL_HINT}")
    return inbox.run(store.read_rows())


def start_inbox(*, wait: bool = False) -> Job:
    def work(job: Job) -> reports.Summary:
        job.stage = "이미지를 읽는 중 (한 장에 10초 넘게 걸릴 수 있음)"
        job.total = inbox_count()
        return reports.inbox_summary(read_inbox())

    return start("inbox", work, wait=wait)

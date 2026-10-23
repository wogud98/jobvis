"""실행 결과를 사람이 읽는 줄로 만든다. 터미널(main.py)은 줄을 모두 출력한다 (v0.5.2 F14).

화면(app.py)은 Summary로 결과 한 줄, 할 일, 문제만 보이고 줄 전체는 접어 둔다 (v0.5.2 F24).
"""

from dataclasses import dataclass, field

from agent import inbox, postings, scoring
from agent.graph import SOURCES, llm_model
from agent.settings import redact

# 예외 이름 일부 → 고칠 방법. LangChain 모델 오류 이름(ModelNotFoundError 등)과 제공자별 이름이 모두 걸린다 (F26)
LLM_HINTS = (
    (
        "ModelNotFound",  # FileNotFoundError와 섞이지 않게
        "LLM 모델({model})을 찾지 못했습니다. .env의 LLM_MODEL을 google_genai:gemini-flash-lite-latest 등으로 고치고"
        " 화면을 다시 켜 주세요.",
    ),
    ("Authentication", "LLM API 키가 맞지 않습니다. .env의 GOOGLE_API_KEY를 확인해 주세요."),
    ("PermissionDenied", "LLM API 키에 권한이 없습니다. .env의 GOOGLE_API_KEY를 확인해 주세요."),
    ("RateLimit", "LLM 사용 한도를 넘었습니다. 잠시 뒤 다시 해 주세요."),
)


def llm_hint(names: list[str] | str) -> str:
    """예외 이름(들)에 맞는 고칠 방법. 모르는 오류면 빈 글자."""
    names = [names] if isinstance(names, str) else names
    for part, hint in LLM_HINTS:
        if any(part in name for name in names):
            return hint.format(model=llm_model())  # 실제로 쓴 모델 이름 (F33). 키는 넣지 않는다
    return ""


@dataclass
class Summary:
    """화면에 보일 결과. headline은 항상, todo(할 일)와 problems(문제)는 있을 때만, details는 접어 둔다 (F24)."""

    headline: str
    todo: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)


def _failure_problem(failed: list[dict], what: str) -> list[str]:
    if not failed:
        return []
    hints = list(dict.fromkeys(llm_hint(job["error"]) for job in failed if llm_hint(job["error"])))
    return [
        f"{len(failed)}건을 {what} 못했습니다." + (f" {hints[0]}" if len(hints) == 1 else " 자세히를 확인해 주세요.")
    ]


def _failures(failed: list[dict]) -> list[str]:
    lines = []
    for job in failed:
        site = SOURCES[job["source"]].NAME if job.get("source") else ""
        # 목록 실패는 회사·제목이 빈칸이라 사이트 이름만 남는다.
        where = " | ".join(part for part in (site, job["company"], job["title"]) if part)
        lines.append(redact(f"  실패({job['step']}): {where} ({job['error']})"))  # v0.6.1 F12
    return lines


def collect(result: dict) -> list[str]:
    """수집 결과 요약 (v0.4 F19, v0.5 F46). 터미널과 화면이 같은 글을 쓴다 (v0.5.2 F5, F14)."""
    lines = []
    saved, skipped, failed = result.get("saved", []), result.get("skipped", []), result.get("failed", [])
    for source, fetched in result.get("fetched", {}).items():
        mine = [len([job for job in jobs if job.get("source") == source]) for jobs in (saved, skipped)]
        # OCR 실패는 줄을 저장했으므로 실패 수에 넣지 않고 아래 줄로만 알린다.
        lost = len([job for job in failed if job.get("source") == source and job["step"] != "OCR"])
        name = SOURCES[source].NAME
        lines.append(f"{name} 가져옴 {fetched} / 새로 저장 {mine[0]} / 건너뜀 {mine[1]} / 실패 {lost}")
    for stop in result.get("blocked", []):
        lines.append(redact(f"  {SOURCES[stop['source']].NAME} 수집 멈춤: {stop['reason']}"))
    lines += _failures(failed)
    for job in result.get("filled", []):
        # 사이트별 "새로 저장"·"건너뜀"에는 넣지 않고 따로 알린다 (v0.5 F46)
        lines.append(f"본문 채움: {SOURCES[job['source']].NAME} 공고 본문으로 바꿈 ({job['company']} | {job['title']})")
    missing = [job for job in saved if job.get("body") == postings.MISSING]
    if missing:
        lines.append(f"본문 미확보 {len(missing)}건: 공고 이미지를 data/inbox/나 화면 카드에 넣고 --inbox를 실행하세요")
    return lines


def score(result: dict) -> list[str]:
    """평가 결과 요약 (v0.5 F36, v0.5.2 F9)."""
    lines = []
    done, skipped, failed = result.get("done", []), result.get("skipped", []), result.get("failed", [])
    excluded = result.get("excluded", [])
    total = len(done) + len(excluded) + len(skipped) + len(failed)
    lines.append(
        f"평가 대상 {total} / 완료 {len(done)} / 제외 {len(excluded)} / 건너뜀 {len(skipped)} / 실패 {len(failed)}"
    )
    if excluded:
        lines.append(f"  제외: 신입인데 경력을 요구하는 공고 ({scoring.EXCLUDED}, v0.5 F36)")
    if skipped:
        lines.append("  건너뜀: 경력·학력·키워드가 없는 줄 (v0.3 이전에 저장한 공고)")
    lines += _failures(failed)
    return lines


def inbox_result(result: inbox.InboxResult) -> list[str]:
    """받은함 결과 요약 (v0.5 F45, v0.5.2 F10)."""
    lines = []
    counts: dict[str, int] = {}
    for item in result.filled:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    detail = ", ".join(f"{status} {count}" for status, count in counts.items())
    filled = f"본문을 채운 공고 {len(result.filled)}건" + (f" ({detail})" if detail else "")
    lines.append(f"읽은 이미지 {result.read}장 / {filled} / 건너뜀 {len(result.skipped)}")
    for item in result.skipped:
        lines.append(f"  건너뜀: {item['file']} ({item['reason']})")
    if result.filled:
        lines.append("다음: python main.py --score 로 체크된 공고를 다시 평가하세요")
    return lines


def collect_summary(result: dict) -> Summary:
    """수집 결과 화면용 (F24, F25)."""
    saved, skipped = result.get("saved", []), result.get("skipped", [])
    filled = result.get("filled", [])
    if saved:
        headline = f"새 공고 {len(saved)}건을 저장했습니다."
    elif skipped:
        headline = "새 공고가 없습니다. 가져온 공고는 모두 이미 저장돼 있습니다."
    else:
        headline = "가져온 공고가 없습니다. 키워드나 조건을 바꿔 보세요."
    if filled:
        headline += f" 본문 없던 공고 {len(filled)}건은 다른 사이트 본문으로 채웠습니다."
    todo = []
    missing = [job for job in saved if job.get("body") == postings.MISSING]
    if missing:  # 터미널 명령 대신 화면에서 할 일로 (F25)
        todo.append(f"본문 없는 공고 {len(missing)}건: 카드 '자세히'에서 공고 이미지를 넣으면 더 정확하게 평가됩니다.")
    problems = [
        redact(f"{SOURCES[stop['source']].NAME} 수집이 멈췄습니다: {stop['reason']}")
        for stop in result.get("blocked", [])
    ]
    problems += _failure_problem([job for job in result.get("failed", []) if job["step"] != "OCR"], "가져오지")
    return Summary(headline, todo, problems, collect(result))


def score_summary(result: dict) -> Summary:
    """평가 결과 화면용 (F24)."""
    done, excluded, failed = result.get("done", []), result.get("excluded", []), result.get("failed", [])
    if done or excluded:
        headline = f"공고 {len(done)}건을 평가했습니다." + (
            f" 신입에게 경력을 요구하는 공고 {len(excluded)}건은 제외했습니다." if excluded else ""
        )
    elif failed:
        headline = "평가하지 못했습니다."
    else:
        headline = "평가할 공고가 없습니다."
    return Summary(headline, [], _failure_problem(failed, "평가하지"), score(result))


def image_score_summary(read: inbox.InboxResult, scored: dict | None) -> Summary:
    """이미지로 다시 평가 결과 화면용 (v0.7.4 F7, F8). 본문을 못 채웠으면 평가하지 않았다고 알린다."""
    problems = [f"이미지 {len(read.skipped)}장을 건너뛰었습니다. 자세히를 확인해 주세요."] if read.skipped else []
    details = [line for line in inbox_result(read) if not line.startswith("다음:")]  # 터미널 안내는 화면에 안 보임
    if scored is None:
        headline = "이미지에서 글자를 읽지 못해 다시 평가하지 않았습니다. 공고 본문이 보이는 이미지인지 확인해 주세요."
        return Summary(headline, [], problems, details)
    summary = score_summary(scored)
    headline = f"이미지 {read.read}장을 읽어 본문을 채우고 " + summary.headline
    return Summary(headline, [], problems + summary.problems, details + score(scored))

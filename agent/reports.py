"""실행 결과를 사람이 읽는 줄로 만든다. 터미널(main.py)은 출력하고 화면(app.py)은 그린다 (v0.5.2 F14)."""

from agent import inbox, postings, scoring
from agent.graph import SOURCES


def _failures(failed: list[dict]) -> list[str]:
    lines = []
    for job in failed:
        site = SOURCES[job["source"]].NAME if job.get("source") else ""
        # 목록 실패는 회사·제목이 빈칸이라 사이트 이름만 남는다.
        where = " | ".join(part for part in (site, job["company"], job["title"]) if part)
        lines.append(f"  실패({job['step']}): {where} ({job['error']})")
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
        lines.append(f"  {SOURCES[stop['source']].NAME} 수집 멈춤: {stop['reason']}")
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

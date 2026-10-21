"""실행 예.

수집:            python main.py --keyword 백엔드 --location 서울 --job 백엔드 --career 신입 --count 10
한 사이트만:     python main.py --keyword 백엔드 --source jobkorea
체크한 줄 평가:  python main.py --score
점수 없는 줄 평가: python main.py --score all
수집 후 평가:    python main.py --keyword 백엔드 --score all
스킬 갭 분석:    python main.py --gaps
받은함 이미지 OCR: python main.py --inbox
화면:            streamlit run app.py
"""

import argparse

from dotenv import load_dotenv

from agent import codes, gaps, inbox, ocr, postings, scoring, sheets, user_profile
from agent.graph import MAX_COUNT, SOURCES, build_graph, build_score_graph, recursion_limit

GAPS_TOP = 10  # 스킬 갭 출력 개수 (F20)
NOTICE = "개인 사용만. 수집한 공고를 공유·공개·판매하지 않음 (사이트 약관)"  # v0.4 N6


def _count(value: str) -> int:
    count = int(value)
    if not 1 <= count <= MAX_COUNT:
        raise argparse.ArgumentTypeError(f"1~{MAX_COUNT} 사이로 입력해 주세요")
    return count


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="사람인·잡코리아 공고를 수집하고 내 프로필과 비교해 적합도를 평가")
    parser.add_argument("--keyword", help="검색어 (예: 백엔드). 수집할 때 필요")
    parser.add_argument("--location", help="지역 이름 (예: 서울, 경기)")
    parser.add_argument("--job", help="직무 이름 (예: 백엔드, 프론트엔드, Python)")
    parser.add_argument("--career", choices=codes.CAREERS, help="신입 또는 경력. 생략하면 거르지 않음")
    parser.add_argument("--source", choices=list(SOURCES), help="한 사이트만 수집 (saramin, jobkorea). 생략하면 둘 다")
    parser.add_argument("--count", type=_count, default=10, help=f"사이트당 가져올 공고 수 (1~{MAX_COUNT}, 기본 10)")
    parser.add_argument(
        "--score",
        nargs="?",
        const="checked",
        choices=["checked", "all"],
        help="값 없이 쓰면 '평가' 열을 체크한 줄만, all이면 점수 없는 줄 전부 평가",
    )
    parser.add_argument("--profile", default=user_profile.DEFAULT, help=f"내 프로필 파일 (기본 {user_profile.DEFAULT})")
    parser.add_argument("--gaps", action="store_true", help="시트의 부족한 점을 모아 공부할 기술 순위 출력")
    parser.add_argument("--inbox", action="store_true", help="data/inbox/에 넣은 공고 이미지를 OCR로 읽어 본문 채우기")
    args = parser.parse_args(argv)

    if not (args.keyword or args.score or args.gaps or args.inbox):
        parser.error("--keyword, --score, --gaps, --inbox 중 하나는 필요합니다")
    if args.gaps and (args.keyword or args.score):
        parser.error("--gaps는 다른 작업과 함께 쓸 수 없습니다")
    if args.inbox and (args.keyword or args.score or args.gaps):
        parser.error("--inbox는 다른 작업과 함께 쓸 수 없습니다")
    if args.keyword and args.score == "checked":
        parser.error("방금 수집한 공고는 체크돼 있지 않습니다. 수집과 함께 평가하려면 --score all을 쓰세요")
    return args


def to_state(args: argparse.Namespace) -> dict:
    # 모르는 이름이면 사이트에 요청하기 전에 여기서 멈춘다 (v0.2 F11).
    region_code = codes.to_region_code(args.location) if args.location else None
    return {
        "keyword": args.keyword,
        "sources": [args.source] if args.source else list(SOURCES),
        "location": args.location,
        "region_code": region_code,
        "job_code": codes.to_job_code(args.job) if args.job else None,
        "career": args.career,
        "count": args.count,
    }


def _print_failures(failed: list[dict]) -> None:
    for job in failed:
        site = SOURCES[job["source"]].NAME if job.get("source") else ""
        # 목록 실패는 회사·제목이 빈칸이라 사이트 이름만 남는다.
        where = " | ".join(part for part in (site, job["company"], job["title"]) if part)
        print(f"  실패({job['step']}): {where} ({job['error']})")


def print_report(result: dict) -> None:
    saved, skipped, failed = result.get("saved", []), result.get("skipped", []), result.get("failed", [])
    for source, fetched in result.get("fetched", {}).items():
        mine = [len([job for job in jobs if job.get("source") == source]) for jobs in (saved, skipped)]
        # OCR 실패는 줄을 저장했으므로 실패 수에 넣지 않고 아래 줄로만 알린다.
        lost = len([job for job in failed if job.get("source") == source and job["step"] != "OCR"])
        name = SOURCES[source].NAME
        print(f"{name} 가져옴 {fetched} / 새로 저장 {mine[0]} / 건너뜀 {mine[1]} / 실패 {lost}")
    for stop in result.get("blocked", []):
        print(f"  {SOURCES[stop['source']].NAME} 수집 멈춤: {stop['reason']}")
    _print_failures(failed)
    for job in result.get("filled", []):
        # 사이트별 "새로 저장"·"건너뜀"에는 넣지 않고 따로 알린다 (v0.5 F46)
        print(f"본문 채움: {SOURCES[job['source']].NAME} 공고 본문으로 바꿈 ({job['company']} | {job['title']})")
    missing = [job for job in saved if job.get("body") == postings.MISSING]
    if missing:
        print(f"본문 미확보 {len(missing)}건: 공고 이미지를 data/inbox/나 화면 카드에 넣고 --inbox를 실행하세요")


def print_score_report(result: dict) -> None:
    done, skipped, failed = result.get("done", []), result.get("skipped", []), result.get("failed", [])
    excluded = result.get("excluded", [])
    total = len(done) + len(excluded) + len(skipped) + len(failed)
    print(f"평가 대상 {total} / 완료 {len(done)} / 제외 {len(excluded)} / 건너뜀 {len(skipped)} / 실패 {len(failed)}")
    if excluded:
        print(f"  제외: 신입인데 경력을 요구하는 공고 ({scoring.EXCLUDED}, v0.5 F36)")
    if skipped:
        print("  건너뜀: 경력·학력·키워드가 없는 줄 (v0.3 이전에 저장한 공고)")
    _print_failures(failed)


def print_gaps(top: list[tuple[str, float, int]], used: int, excluded: int) -> None:
    if not top:
        print(f"분석할 부족한 점이 없습니다. 먼저 --score로 평가해 주세요. (점수 없는 줄 {excluded}건)")
        return
    print(f"공부할 기술 상위 {len(top)}개 (평가한 공고 {used}건 기준, 점수 없는 줄 {excluded}건 제외)")
    for rank, (name, weight, count) in enumerate(top, start=1):
        print(f"  {rank}. {name} | 가중 합 {weight:.2f} | 공고 {count}건")


def run_collect(state: dict) -> None:
    if not postings.DIR.exists():
        print(NOTICE)  # 첫 실행 안내 (N6)
    state["ocr_ready"] = ocr.available()
    if not state["ocr_ready"]:
        print(f"이미지 OCR 없음: 글자 본문만 저장합니다. {ocr.INSTALL_HINT}")
    limit = recursion_limit(state["count"] * len(state["sources"]))
    print_report(build_graph().invoke(state, {"recursion_limit": limit}))


def print_inbox_report(result: inbox.InboxResult) -> None:
    counts: dict[str, int] = {}
    for item in result.filled:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    detail = ", ".join(f"{status} {count}" for status, count in counts.items())
    filled = f"본문을 채운 공고 {len(result.filled)}건" + (f" ({detail})" if detail else "")
    print(f"읽은 이미지 {result.read}장 / {filled} / 건너뜀 {len(result.skipped)}")
    for item in result.skipped:
        print(f"  건너뜀: {item['file']} ({item['reason']})")
    if result.filled:
        print("다음: python main.py --score 로 체크된 공고를 다시 평가하세요")


def run_inbox() -> None:
    if not ocr.available():  # 아무 파일도 건드리지 않고 멈춘다 (F44)
        raise SystemExit(f"OCR이 설치돼 있지 않습니다. {ocr.INSTALL_HINT}")
    print_inbox_report(inbox.run(sheets.read_rows()))


def run_score(mode: str, profile: user_profile.Profile) -> None:
    targets, skipped = scoring.select_targets(sheets.read_rows(), mode)
    state = {
        "profile": user_profile.to_prompt(profile),
        "years": profile.experience.years,
        "queue": targets,
        "skipped": skipped,
    }
    result = build_score_graph().invoke(state, {"recursion_limit": recursion_limit(len(targets))})
    print_score_report(result)


def run_gaps() -> None:
    print_gaps(*gaps.analyze(sheets.read_rows(), GAPS_TOP))


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    load_dotenv()
    if args.gaps:
        run_gaps()
        return
    if args.inbox:
        run_inbox()
        return

    try:
        state = to_state(args) if args.keyword else None
        # 평가를 하려면 프로필이 있어야 한다. 없거나 틀리면 사이트 요청과 LLM 호출 전에 멈춘다 (v0.5 F13, F16).
        profile = None
        if args.score:
            profile, warnings = user_profile.load(args.profile)
            for warning in warnings:
                print(warning)  # 모르는 칸은 경고만 (F14)
    except (codes.CodeNotFoundError, user_profile.ProfileError) as e:
        raise SystemExit(str(e)) from None

    if state:
        run_collect(state)
    if args.score:
        run_score(args.score, profile)


if __name__ == "__main__":
    main()

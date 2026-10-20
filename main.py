"""실행 예.

수집:            python main.py --keyword 백엔드 --location 서울 --job 백엔드 --career 신입 --count 10
체크한 줄 평가:  python main.py --score
점수 없는 줄 평가: python main.py --score all
수집 후 평가:    python main.py --keyword 백엔드 --score all
스킬 갭 분석:    python main.py --gaps
"""

import argparse

from dotenv import load_dotenv

from agent import codes, gaps, scoring, sheets, user_profile
from agent.graph import MAX_COUNT, build_graph, build_score_graph, recursion_limit
from agent.saramin import SaraminAPIError

GAPS_TOP = 10  # 스킬 갭 출력 개수 (F20)


def _count(value: str) -> int:
    count = int(value)
    if not 1 <= count <= MAX_COUNT:
        raise argparse.ArgumentTypeError(f"1~{MAX_COUNT} 사이로 입력해 주세요")
    return count


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="사람인 공고를 수집하고 내 프로필과 비교해 적합도를 평가")
    parser.add_argument("--keyword", help="검색어 (예: 백엔드). 수집할 때 필요")
    parser.add_argument("--location", help="지역 이름 (예: 서울, 경기)")
    parser.add_argument("--job", help="직무 이름 (예: 백엔드, 프론트엔드, Python)")
    parser.add_argument("--career", choices=codes.CAREERS, help="신입 또는 경력. 생략하면 거르지 않음")
    parser.add_argument("--count", type=_count, default=10, help=f"가져올 공고 수 (1~{MAX_COUNT}, 기본 10)")
    parser.add_argument(
        "--score",
        nargs="?",
        const="checked",
        choices=["checked", "all"],
        help="값 없이 쓰면 '평가' 열을 체크한 줄만, all이면 점수 없는 줄 전부 평가",
    )
    parser.add_argument("--profile", default="profile.md", help="내 프로필 파일 (기본 profile.md)")
    parser.add_argument("--gaps", action="store_true", help="시트의 부족한 점을 모아 공부할 기술 순위 출력")
    args = parser.parse_args(argv)

    if not (args.keyword or args.score or args.gaps):
        parser.error("--keyword, --score, --gaps 중 하나는 필요합니다")
    if args.gaps and (args.keyword or args.score):
        parser.error("--gaps는 다른 작업과 함께 쓸 수 없습니다")
    if args.keyword and args.score == "checked":
        parser.error("방금 수집한 공고는 체크돼 있지 않습니다. 수집과 함께 평가하려면 --score all을 쓰세요")
    return args


def to_state(args: argparse.Namespace) -> dict:
    # 모르는 이름이면 사람인 API를 부르기 전에 여기서 멈춘다 (v0.2 F11).
    return {
        "keyword": args.keyword,
        "region_code": codes.to_region_code(args.location) if args.location else None,
        "job_code": codes.to_job_code(args.job) if args.job else None,
        "career": args.career,
        "count": args.count,
    }


def _print_failures(failed: list[dict]) -> None:
    for job in failed:
        print(f"  실패({job['step']}): {job['company']} | {job['title']} ({job['error']})")


def print_report(result: dict) -> None:
    saved, skipped, failed = result.get("saved", []), result.get("skipped", []), result.get("failed", [])
    print(f"가져옴 {result.get('fetched', 0)} / 새로 저장 {len(saved)} / 건너뜀 {len(skipped)} / 실패 {len(failed)}")
    _print_failures(failed)


def print_score_report(result: dict) -> None:
    done, skipped, failed = result.get("done", []), result.get("skipped", []), result.get("failed", [])
    total = len(done) + len(skipped) + len(failed)
    print(f"평가 대상 {total} / 완료 {len(done)} / 건너뜀 {len(skipped)} / 실패 {len(failed)}")
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
    try:
        result = build_graph().invoke(state, {"recursion_limit": recursion_limit(state["count"])})
    except SaraminAPIError as e:
        raise SystemExit(str(e)) from None
    print_report(result)


def run_score(mode: str, profile: str) -> None:
    targets, skipped = scoring.select_targets(sheets.read_rows(), mode)
    state = {"profile": profile, "queue": targets, "skipped": skipped}
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

    try:
        state = to_state(args) if args.keyword else None
        # 평가를 하려면 프로필이 있어야 한다. 없으면 사람인 API와 LLM을 부르기 전에 멈춘다 (F6).
        profile = user_profile.load(args.profile) if args.score else None
    except (codes.CodeNotFoundError, user_profile.ProfileError) as e:
        raise SystemExit(str(e)) from None

    if state:
        run_collect(state)
    if args.score:
        run_score(args.score, profile)


if __name__ == "__main__":
    main()

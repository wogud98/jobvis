"""실행 예: python main.py --keyword 백엔드 --location 서울 --job 백엔드 --career 신입 --count 10"""

import argparse

from dotenv import load_dotenv

from agent import codes
from agent.graph import MAX_COUNT, build_graph, recursion_limit
from agent.saramin import SaraminAPIError


def _count(value: str) -> int:
    count = int(value)
    if not 1 <= count <= MAX_COUNT:
        raise argparse.ArgumentTypeError(f"1~{MAX_COUNT} 사이로 입력해 주세요")
    return count


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="사람인 공고를 요약해 구글 시트에 저장")
    parser.add_argument("--keyword", required=True, help="검색어 (예: 백엔드)")
    parser.add_argument("--location", help="지역 이름 (예: 서울, 경기)")
    parser.add_argument("--job", help="직무 이름 (예: 백엔드, 프론트엔드, Python)")
    parser.add_argument("--career", choices=codes.CAREERS, help="신입 또는 경력. 생략하면 거르지 않음")
    parser.add_argument("--count", type=_count, default=10, help=f"가져올 공고 수 (1~{MAX_COUNT}, 기본 10)")
    return parser.parse_args(argv)


def to_state(args: argparse.Namespace) -> dict:
    # 모르는 이름이면 사람인 API를 부르기 전에 여기서 멈춘다 (F11).
    return {
        "keyword": args.keyword,
        "region_code": codes.to_region_code(args.location) if args.location else None,
        "job_code": codes.to_job_code(args.job) if args.job else None,
        "career": args.career,
        "count": args.count,
    }


def print_report(result: dict) -> None:
    saved, skipped, failed = result.get("saved", []), result.get("skipped", []), result.get("failed", [])
    print(f"가져옴 {result.get('fetched', 0)} / 새로 저장 {len(saved)} / 건너뜀 {len(skipped)} / 실패 {len(failed)}")
    for job in failed:
        print(f"  실패({job['step']}): {job['company']} | {job['title']} ({job['error']})")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    try:
        state = to_state(args)
    except codes.CodeNotFoundError as e:
        raise SystemExit(str(e)) from None

    load_dotenv()
    try:
        result = build_graph().invoke(state, {"recursion_limit": recursion_limit(args.count)})
    except SaraminAPIError as e:
        raise SystemExit(str(e)) from None
    print_report(result)


if __name__ == "__main__":
    main()

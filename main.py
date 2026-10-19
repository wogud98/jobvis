"""실행 예: python main.py --keyword "백엔드 신입" --location 101000"""
import argparse

from dotenv import load_dotenv

from agent.graph import build_graph


def main() -> None:
    parser = argparse.ArgumentParser(description="사람인 공고 1건을 구글 시트에 저장")
    parser.add_argument("--keyword", required=True, help="검색 키워드 (예: 백엔드 신입)")
    parser.add_argument("--location", help="사람인 지역 코드 (예: 101000 = 서울)")
    args = parser.parse_args()

    load_dotenv()
    result = build_graph().invoke({"keyword": args.keyword, "location": args.location})
    job = result["job"]
    print(f"저장 완료: {job['company']} | {job['title']} | {result['requirements']}")


if __name__ == "__main__":
    main()

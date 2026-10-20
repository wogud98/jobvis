"""시트에 쌓인 부족한 점을 점수로 가중해 모은다 (스킬 갭 분석). LLM을 부르지 않는다."""


def _score(row: dict) -> int | None:
    try:
        return int(row.get("score", "").strip())
    except ValueError:
        return None  # 비었거나 사람이 숫자가 아닌 값을 넣은 줄


def analyze(rows: list[dict], top: int = 10) -> tuple[list[tuple[str, float, int]], int, int]:
    """(상위 기술 목록 [(이름, 가중 합, 공고 수)], 분석한 줄 수, 뺀 줄 수)를 돌려준다."""
    names: dict[str, str] = {}
    weights: dict[str, float] = {}
    counts: dict[str, int] = {}
    used = excluded = 0
    for row in rows:
        score = _score(row)
        if score is None:
            excluded += 1  # 점수 없는 줄은 뺀다 (F21)
            continue
        used += 1
        seen_in_row = set()
        for gap in row.get("gaps", "").split(","):
            key = gap.strip().casefold()  # 대소문자·앞뒤 공백만 다른 이름은 같은 기술 (F19)
            if not key or key in seen_in_row:
                continue
            seen_in_row.add(key)
            names.setdefault(key, gap.strip())
            weights[key] = weights.get(key, 0) + (100 - score) / 100  # 점수가 낮을수록 크게 (F18)
            counts[key] = counts.get(key, 0) + 1
    ranked = sorted(weights, key=lambda key: (-weights[key], -counts[key], names[key]))
    return [(names[key], weights[key], counts[key]) for key in ranked[:top]], used, excluded

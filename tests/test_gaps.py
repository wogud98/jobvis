from agent import gaps


def row(score, gap_text):
    return {"score": score, "gaps": gap_text}


def test_weights_low_scores_more():
    rows = [row("90", "Docker"), row("40", "AWS"), row("80", "Docker")]

    top, used, excluded = gaps.analyze(rows)

    # AWS 0.6, Docker 0.1 + 0.2 = 0.3
    assert [(name, round(weight, 2), count) for name, weight, count in top] == [("AWS", 0.6, 1), ("Docker", 0.3, 2)]
    assert (used, excluded) == (3, 0)


def test_same_skill_ignores_case_and_spaces():
    rows = [row("50", "kotlin, Jenkins"), row("50", " Kotlin ,jenkins ")]

    top, _, _ = gaps.analyze(rows)

    # 사전에 없는 이름은 처음 나온 모양 그대로
    assert [(name, count) for name, _, count in top] == [("Jenkins", 2), ("kotlin", 2)]


def test_same_words_in_dictionary_merge_under_main_name():
    rows = [row("50", "k8s, LLM Agent"), row("50", "쿠버네티스, Agentic AI"), row("50", "MySQL, SQL")]

    top, _, _ = gaps.analyze(rows)

    # 같은 말은 대표 이름으로 합치고, SQL·MySQL처럼 다른 것은 따로 (v0.7.3 F2)
    ranked = [(name, count) for name, _, count in top]
    assert ranked == [("AI 에이전트", 2), ("Kubernetes", 2), ("MySQL", 1), ("SQL", 1)]


def test_top_none_keeps_all():
    rows = [row("50", ", ".join(f"skill{n}" for n in range(15)))]

    assert len(gaps.analyze(rows, top=None)[0]) == 15  # v0.7.3 F1


def test_rows_without_score_are_excluded():
    rows = [row("", "Docker"), row("높음", "Git"), row("60", "Kotlin")]

    top, used, excluded = gaps.analyze(rows)

    assert [name for name, _, _ in top] == ["Kotlin"]
    assert (used, excluded) == (1, 2)


def test_keeps_only_top_n():
    rows = [row("0", ", ".join(f"skill{i}" for i in range(15)))]

    top, _, _ = gaps.analyze(rows, top=10)

    assert len(top) == 10


def test_no_rows_to_analyze():
    assert gaps.analyze([]) == ([], 0, 0)
    assert gaps.analyze([row("", "Docker")]) == ([], 0, 1)


def test_scored_row_without_gaps_counts_as_used():
    top, used, _ = gaps.analyze([row("95", "")])

    assert top == []
    assert used == 1

"""같은 말 사전 (v0.7.3 F2, N2)."""

import pytest

from agent import skills


def test_dictionary_loads_and_maps_aliases_to_main_name():
    assert len(skills.ALIASES) >= 60
    assert skills.display("llm agent") == "AI 에이전트"
    assert skills.display("K8S") == "Kubernetes"
    assert skills.key("Agentic AI") == skills.key("AI Agent") == skills.key("AI 에이전트")


def test_different_skills_stay_apart():
    assert skills.key("SQL") != skills.key("MySQL")  # 재리 결정: 현행 유지
    assert skills.key("Java") != skills.key("JavaScript")
    assert skills.key("C") != skills.key("C++") != skills.key("C#")


def test_unknown_names_only_ignore_case_and_spaces():
    assert skills.key("Spring  Batch") == skills.key("springbatch")
    assert skills.display("Spring Batch") == "Spring Batch"
    assert skills.key("") == ""


def test_name_in_two_groups_is_refused(tmp_path):
    path = tmp_path / "aliases.yaml"
    path.write_text("Kubernetes: [k8s]\nKafka: [K8S]\n", encoding="utf-8")

    with pytest.raises(ValueError, match="두 묶음"):
        skills.load(path)


def test_empty_dictionary_file(tmp_path):
    path = tmp_path / "aliases.yaml"
    path.write_text("# 비어 있음\n", encoding="utf-8")

    assert skills.load(path) == {}

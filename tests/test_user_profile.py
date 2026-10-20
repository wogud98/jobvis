from pathlib import Path

import pytest

from agent import user_profile


def test_load_reads_text(tmp_path):
    path = tmp_path / "profile.md"
    path.write_text("# 보유 기술\nPython\n", encoding="utf-8")

    assert user_profile.load(str(path)) == "# 보유 기술\nPython"


def test_missing_file(tmp_path):
    path = tmp_path / "profile.md"

    with pytest.raises(user_profile.ProfileError) as exc_info:
        user_profile.load(str(path))

    assert str(path) in str(exc_info.value)
    assert "profile.example.md" in str(exc_info.value)


def test_blank_file(tmp_path):
    path = tmp_path / "profile.md"
    path.write_text("  \n\n", encoding="utf-8")

    with pytest.raises(user_profile.ProfileError, match="비어 있습니다"):
        user_profile.load(str(path))


def test_example_file_in_repo_is_usable():
    assert "보유 기술" in user_profile.load(str(Path(__file__).parent.parent / "profile.example.md"))

import pytest

from agent import postings

LONG = "가" * postings.MIN_TEXT


@pytest.mark.parametrize(
    ("text", "ocr_texts", "unread", "expected"),
    [
        (LONG, [], 0, "글자"),
        (LONG, ["이미지 글자"], 0, "글자+이미지"),
        (LONG, ["이미지 글자"], 1, "이미지 일부 못 읽음"),
        (LONG, [], 2, "이미지 일부 못 읽음"),
        ("가" * 150, ["나" * 50], 0, "글자+이미지"),  # 본문 + OCR을 합쳐 200자 (F15a)
        ("가" * 150, ["나" * 49], 0, "본문 미확보"),
        ("", [], 3, "본문 미확보"),  # 이미지뿐인 공고에서 이미지를 못 읽음
        ("   \n  ", [], 0, "본문 미확보"),
    ],
)
def test_status(text, ocr_texts, unread, expected):
    assert postings.status(text, ocr_texts, unread) == expected


def test_compose_adds_ocr_after_mark_only_when_present():
    assert postings.compose("본문", []) == "본문"
    assert postings.compose("본문", ["", "  "]) == "본문"
    assert postings.compose("본문", ["첫 장", "둘째 장"]) == "본문\n\n--- 이미지 글자 ---\n첫 장\n둘째 장"


def test_save_and_load_in_data_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(postings, "DIR", tmp_path / "data" / "postings")

    assert postings.load("saramin", "1") is None
    postings.save("saramin", "1", "본문 글자")

    assert (tmp_path / "data" / "postings" / "saramin_1.txt").read_text(encoding="utf-8") == "본문 글자"
    assert postings.load("saramin", "1") == "본문 글자"
    assert postings.load("jobkorea", "1") is None


def test_data_folder_is_git_ignored():
    from pathlib import Path

    assert "data/" in Path(".gitignore").read_text(encoding="utf-8").split()

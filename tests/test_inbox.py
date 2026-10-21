import pytest

from agent import inbox, postings

LONG = "주요업무와 자격요건이 담긴 이미지 글자. " * 20  # 200자 넘음


@pytest.fixture
def folders(monkeypatch, tmp_path):
    """받은함과 원문 폴더는 임시 폴더에서만 쓴다."""
    monkeypatch.setattr(inbox, "DIR", tmp_path / "inbox")
    monkeypatch.setattr(inbox, "DONE", tmp_path / "inbox" / "done")
    monkeypatch.setattr(postings, "DIR", tmp_path / "postings")
    (tmp_path / "inbox").mkdir()
    return tmp_path


class FakeSheet:
    def __init__(self, monkeypatch):
        self.updated = []
        monkeypatch.setattr(inbox.sheets, "update_cells", lambda row, changes: self.updated.append((row, changes)))


class FakeOcr:
    """bytes를 글자로 바꾼다. b"fail"이면 예외."""

    def __init__(self, monkeypatch):
        self.read = []

        def read(image: bytes) -> str:
            if image == b"fail":
                raise RuntimeError("OCR 모델 오류")
            self.read.append(image)
            return image.decode()

        monkeypatch.setattr(inbox.ocr, "read", read)


def put(folders, name: str, data: bytes = b"text") -> None:
    (folders / "inbox" / name).write_bytes(data)


def sheet_row(number=5, source="사람인", job_id="1", body="본문 미확보") -> dict:
    return {"row": number, "source": source, "id": job_id, "company": f"회사{job_id}", "body": body}


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("saramin_123.png", ("saramin", "123", 1)),
        ("saramin_123_2.jpg", ("saramin", "123", 2)),
        ("JOBKOREA_48_10.WEBP", ("jobkorea", "48", 10)),
        ("wanted_1.png", None),
        ("saramin-123.png", None),
        ("saramin_.png", None),
        ("공고.png", None),
    ],
)
def test_parse_name(name, expected):
    assert inbox.parse_name(name) == expected


def test_scan_groups_by_posting_in_number_order_and_skips_bad_names(folders):
    for name in [
        "saramin_1_10.png",
        "saramin_1_2.png",
        "saramin_1.png",
        "jobkorea_7.jpeg",
        "memo.txt",
        "saramin_1.gif",
    ]:
        put(folders, name)
    (folders / "inbox" / "done").mkdir()  # 폴더는 무시

    groups, skipped = inbox.scan()

    assert {key: [f.name for f in files] for key, files in groups.items()} == {
        ("jobkorea", "7"): ["jobkorea_7.jpeg"],
        ("saramin", "1"): ["saramin_1.png", "saramin_1_2.png", "saramin_1_10.png"],  # 이름 문자열순이 아니라 번호순
    }
    assert skipped == [
        {"file": "memo.txt", "reason": "이름 형식"},
        {"file": "saramin_1.gif", "reason": "모르는 확장자"},
    ]


def test_run_fills_body_turns_on_check_and_moves_files(folders, monkeypatch):
    sheet, ocr = FakeSheet(monkeypatch), FakeOcr(monkeypatch)
    put(folders, "saramin_1_2.png", LONG[100:].encode())
    put(folders, "saramin_1.png", LONG[:100].encode())

    result = inbox.run([sheet_row()])

    assert ocr.read == [LONG[:100].encode(), LONG[100:].encode()]  # 번호순
    content = postings.load("saramin", "1")
    assert postings.split(content) == ("", [f"{LONG[:100]}\n{LONG[100:]}"])  # 원문 파일이 없으면 새로 만든다
    assert sheet.updated == [(5, {"본문": "글자+이미지", "평가": True})]  # F39, F40
    assert result.read == 2
    assert result.filled == [{"source": "saramin", "id": "1", "company": "회사1", "status": "글자+이미지"}]
    assert sorted(p.name for p in (folders / "inbox" / "done").iterdir()) == ["saramin_1.png", "saramin_1_2.png"]
    assert [p.name for p in (folders / "inbox").iterdir()] == ["done"]


def test_run_twice_does_not_add_text_twice(folders, monkeypatch):
    FakeSheet(monkeypatch)
    FakeOcr(monkeypatch)
    postings.save("saramin", "1", "글자 본문")
    put(folders, "saramin_1.png", LONG.encode())

    inbox.run([sheet_row()])
    second = inbox.run([sheet_row(body="글자+이미지")])

    assert postings.load("saramin", "1") == postings.compose("글자 본문", [LONG])
    assert second.read == 0 and second.filled == []


def test_same_status_keeps_sheet_but_updates_file(folders, monkeypatch):
    sheet, _ = FakeSheet(monkeypatch), FakeOcr(monkeypatch)
    postings.save("saramin", "1", postings.compose(LONG, ["예전 이미지 글자"]))
    put(folders, "saramin_1.png", b"new")

    result = inbox.run([sheet_row(body="글자+이미지")])

    assert sheet.updated == []  # 상태가 같으면 시트는 그대로
    assert postings.load("saramin", "1").endswith("예전 이미지 글자\nnew")
    assert result.filled[0]["status"] == "글자+이미지"


def test_partly_unread_becomes_text_and_image(folders, monkeypatch):
    sheet, _ = FakeSheet(monkeypatch), FakeOcr(monkeypatch)
    postings.save("jobkorea", "7", LONG)
    put(folders, "jobkorea_7.png", b"more")

    inbox.run([sheet_row(source="잡코리아", job_id="7", body="이미지 일부 못 읽음")])

    # 사람이 이미지를 넣었으니 못 읽은 이미지는 0으로 본다 (v0.5 설계)
    assert sheet.updated == [(5, {"본문": "글자+이미지", "평가": True})]


def test_short_text_stays_missing(folders, monkeypatch):
    sheet, _ = FakeSheet(monkeypatch), FakeOcr(monkeypatch)
    put(folders, "saramin_1.png", b"short")

    result = inbox.run([sheet_row()])

    assert sheet.updated == []
    assert result.filled[0]["status"] == "본문 미확보"


def test_blank_source_row_is_saramin(folders, monkeypatch):
    sheet, _ = FakeSheet(monkeypatch), FakeOcr(monkeypatch)
    put(folders, "saramin_1.png", LONG.encode())

    inbox.run([sheet_row(source="")])

    assert len(sheet.updated) == 1


def test_unknown_posting_and_ocr_failure_are_skipped_and_left_in_inbox(folders, monkeypatch):
    sheet, _ = FakeSheet(monkeypatch), FakeOcr(monkeypatch)
    put(folders, "saramin_999.png")
    put(folders, "saramin_1.png", LONG.encode())
    put(folders, "saramin_1_2.png", b"fail")

    result = inbox.run([sheet_row()])

    assert result.skipped == [
        {"file": "saramin_1_2.png", "reason": "OCR 실패(RuntimeError)"},
        {"file": "saramin_999.png", "reason": "시트에 없는 공고"},
    ]
    left = sorted(p.name for p in (folders / "inbox").iterdir() if p.is_file())
    assert left == ["saramin_1_2.png", "saramin_999.png"]  # 다음 실행 때 다시 읽는다 (F43)
    assert result.read == 1 and len(sheet.updated) == 1


def test_all_images_fail_leaves_posting_untouched(folders, monkeypatch):
    sheet, _ = FakeSheet(monkeypatch), FakeOcr(monkeypatch)
    put(folders, "saramin_1.png", b"fail")

    result = inbox.run([sheet_row()])

    assert postings.load("saramin", "1") is None
    assert sheet.updated == [] and result.filled == []


def test_done_name_clash_gets_number(folders, monkeypatch):
    FakeSheet(monkeypatch)
    FakeOcr(monkeypatch)
    (folders / "inbox" / "done").mkdir()
    (folders / "inbox" / "done" / "saramin_1.png").write_bytes(b"old")
    put(folders, "saramin_1.png", LONG.encode())

    inbox.run([sheet_row()])

    names = sorted(p.name for p in (folders / "inbox" / "done").iterdir())
    assert names == ["saramin_1.png", "saramin_1_2.png"]
    assert (folders / "inbox" / "done" / "saramin_1.png").read_bytes() == b"old"


def test_empty_or_missing_inbox(folders, monkeypatch):
    FakeSheet(monkeypatch)
    FakeOcr(monkeypatch)
    (folders / "inbox").rmdir()

    result = inbox.run([sheet_row()])

    assert (result.read, result.filled, result.skipped) == (0, [], [])


# ---- 화면에서 넣기 (F47–F49) ----


def test_save_upload_uses_posting_name_and_raises_number(folders):
    first = inbox.save_upload("saramin", "1", "캡처.PNG", b"a")
    (folders / "inbox" / "done").mkdir()
    (folders / "inbox" / "done" / "saramin_1_2.png").write_bytes(b"old")  # 이미 처리한 이미지
    second = inbox.save_upload("saramin", "1", "다른 캡처.png", b"b")

    assert first.name == "saramin_1.png"
    assert second.name == "saramin_1_3.png"  # inbox와 done 둘 다 보고 번호를 올린다
    assert inbox.parse_name(second.name) == ("saramin", "1", 3)
    assert second.read_bytes() == b"b"


@pytest.mark.parametrize(
    ("name", "size", "reason"),
    [("공고.gif", 10, "png, jpg, jpeg, webp"), ("공고.png", inbox.MAX_UPLOAD + 1, "10MB")],
)
def test_save_upload_rejects_bad_files(folders, name, size, reason):
    with pytest.raises(inbox.UploadError, match=reason):
        inbox.save_upload("saramin", "1", name, b"x" * size)

    assert list((folders / "inbox").iterdir()) == []


def test_save_upload_accepts_exactly_10mb(folders):
    assert inbox.save_upload("jobkorea", "7", "a.webp", b"x" * inbox.MAX_UPLOAD).name == "jobkorea_7.webp"

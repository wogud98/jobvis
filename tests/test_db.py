"""DB 저장(agent/db.py)을 SQLite 메모리 DB로 검사한다. Postgres 서버 없음 (v0.6 N1)."""

import pytest
import sqlalchemy as sa

from agent import db, sheets, store


@pytest.fixture
def memory(monkeypatch):
    """한 테스트 동안 같은 메모리 DB를 쓰도록 연결 하나를 나눠 쓴다."""
    engine = sa.create_engine("sqlite://", poolclass=sa.pool.StaticPool, connect_args={"check_same_thread": False})
    db.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", lambda: engine)
    return engine


def collected(**changes) -> list:
    row = dict.fromkeys(sheets.KEYS, "")
    row |= {"company": "(주)가나다", "title": "백엔드", "id": "123", "saved_at": "2026-10-22 09:00", "source": "사람인"}
    row |= changes
    return [row[key] for key in sheets.KEYS[: sheets.HEADER.index("본문") + 1]]  # graph가 붙이는 길이 (A–X)


def test_empty_table_reads_nothing(memory):
    assert db.read_rows() == []
    assert db.existing_keys() == (set(), set(), {})


def test_append_returns_row_number_and_reads_same_shape_as_sheet(memory):
    first = db.append_row(collected())
    second = db.append_row(collected(id="124", title="프론트엔드", check=False))

    rows = db.read_rows()

    assert (first, second) == (1, 2)
    assert [row["row"] for row in rows] == [1, 2]
    assert set(rows[0]) == set(sheets.KEYS) | {"row"}  # 시트 줄과 같은 키
    assert rows[0]["company"] == "(주)가나다" and rows[0]["applied"] == ""  # 안 쓴 칸은 빈칸
    assert rows[1]["check"] == "FALSE"  # 시트가 돌려주는 글자와 같음 (D4)


def test_short_row_fills_rest_with_blank(memory):
    db.append_row(["회사", "직무", "요약", "마감", "url"])

    row = db.read_rows()[0]

    assert row["title"] == "직무" and row["id"] == "" and row["body"] == ""


def test_update_cells_and_set_marks_write_only_named_columns(memory):
    number = db.append_row(collected(body="본문 미확보"))

    db.update_cells(number, {"본문": "OCR 완료", "평가": True})
    db.set_hidden(number, True)
    db.set_applied(number, False)
    db.set_check(number, False)

    row = db.read_rows()[0]
    assert (row["body"], row["check"], row["hidden"], row["applied"]) == ("OCR 완료", "FALSE", "TRUE", "FALSE")
    assert row["company"] == "(주)가나다"  # 다른 칸은 그대로


def test_write_result_fills_same_columns_as_sheet(memory):
    number = db.append_row(collected(location="서울", body="본문 있음"))
    values = [False, 71, "★★★★☆", "추천", 72, 60, "-", 80, "강점", "Docker", "2026-10-20 09:00"]

    db.write_result(number, "신입, Java 필수", values, ["API 개발", "AWS 경험", "Java"], ["높음", "경력 75→60"])

    row = db.read_rows()[0]
    assert row["requirements"] == "신입, Java 필수"
    assert [row[key] for key in sheets.KEYS[sheets.CHECK_COLUMN : sheets.SCORED_AT_COLUMN]] == [
        "FALSE", "71", "★★★★☆", "추천", "72", "60", "-", "80", "강점", "Docker", "2026-10-20 09:00",
    ]  # fmt: skip
    assert (row["duties"], row["preferred"], row["stack"]) == ("API 개발", "AWS 경험", "Java")
    assert (row["trust"], row["adjust"]) == ("높음", "경력 75→60")
    assert (row["source"], row["location"], row["body"]) == ("사람인", "서울", "본문 있음")  # 수집 칸은 그대로
    assert (row["hidden"], row["applied"]) == ("", "")  # 신뢰·보정 뒤 칸도 그대로


def test_write_result_for_excluded_row_keeps_summary_and_body_summary(memory):
    number = db.append_row(collected(requirements="요약"))
    db.update_cells(number, {"주요업무": "업무"})  # 앞서 평가할 때 채운 본문 요약

    db.write_result(number, None, [False, "", "", "제외 (경력 요구)", "", "", "", "", "", "", "시각"], None, ["", ""])

    row = db.read_rows()[0]
    assert (row["requirements"], row["duties"], row["verdict"]) == ("요약", "업무", "제외 (경력 요구)")


def test_existing_keys_uses_same_rules_as_sheet(memory):
    db.append_row(collected())
    db.append_row(collected(company="마바사", title="FDE", id="88", source="잡코리아", body="본문 미확보"))

    ids, names, missing = db.existing_keys()

    assert ids == {("saramin", "123"), ("jobkorea", "88")}
    assert names == {("가나다", "백엔드"), ("마바사", "fde")}
    assert missing == {("마바사", "fde"): {"row": 2, "source": "jobkorea", "id": "88"}}


def test_store_routes_to_db_when_storage_is_db(memory, monkeypatch):
    monkeypatch.setenv("JOBVIS_STORAGE", "db")
    monkeypatch.setattr(sheets, "_sheet", lambda: pytest.fail("DB를 고르면 시트를 열지 않음"))

    number = store.append_row(collected())
    store.set_check(number, True)

    assert store.read_rows_readonly()[0]["check"] == "TRUE"


def test_engine_needs_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db.engine.cache_clear()

    with pytest.raises(KeyError):
        db.engine()


def test_engine_creates_table_on_first_connect(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'jobvis.db'}")
    db.engine.cache_clear()
    try:
        db.append_row(collected())  # 표를 손으로 만들지 않아도 됨 (F8)
        assert len(db.read_rows()) == 1
    finally:
        db.engine().dispose()
        db.engine.cache_clear()

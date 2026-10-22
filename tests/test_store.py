"""저장 방식 고르기(agent/store.py) (v0.6 F6, F9, D1, D2)."""

import inspect

import pytest

from agent import db, sheets, store

PUBLIC = [
    "existing_keys",
    "append_row",
    "read_rows",
    "read_rows_readonly",
    "update_cells",
    "set_check",
    "set_hidden",
    "set_applied",
    "write_result",
]


def test_default_is_sheet(monkeypatch):
    monkeypatch.delenv("JOBVIS_STORAGE", raising=False)

    assert store.kind() == "sheet" and store.backend() is sheets and store.place() == "시트"  # F9


@pytest.mark.parametrize("value", ["db", " DB "])
def test_db_is_chosen_by_setting(monkeypatch, value):
    monkeypatch.setenv("JOBVIS_STORAGE", value)

    assert store.kind() == "db" and store.backend() is db and store.place() == "DB"


def test_blank_setting_means_sheet(monkeypatch):
    monkeypatch.setenv("JOBVIS_STORAGE", "")

    assert store.kind() == "sheet"


def test_wrong_setting_is_explained(monkeypatch):
    monkeypatch.setenv("JOBVIS_STORAGE", "excel")

    with pytest.raises(store.StorageError, match="sheet 또는 db"):
        store.read_rows()


@pytest.mark.parametrize("name", PUBLIC)
def test_both_backends_have_same_functions(name):
    sheet_fn, db_fn = getattr(sheets, name), getattr(db, name)

    assert list(inspect.signature(sheet_fn).parameters) == list(inspect.signature(db_fn).parameters)


def test_store_looks_up_function_at_call_time(monkeypatch):
    """테스트가 sheets 함수를 바꿔 끼우면 store도 그걸 쓴다."""
    monkeypatch.delenv("JOBVIS_STORAGE", raising=False)
    monkeypatch.setattr(sheets, "read_rows", lambda: [{"row": 2}])

    assert store.read_rows() == [{"row": 2}]

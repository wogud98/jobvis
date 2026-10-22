"""결과를 구글 시트와 DB 중 어디에 저장할지 고르고, 그쪽 함수로 넘긴다 (v0.6 F6, F9, D1, D2).

`JOBVIS_STORAGE`가 없으면 지금처럼 시트를 쓴다. Docker compose는 `db`로 넣는다.
함수는 부를 때마다 고른 모듈에서 찾는다. 그래서 테스트가 sheets 함수를 바꿔 끼워도 그대로 쓰인다.
"""

import os

from agent import sheets

KINDS = ("sheet", "db")


class StorageError(ValueError):
    """JOBVIS_STORAGE 값이 틀림. 화면·터미널에 그대로 보여준다."""


def kind() -> str:
    value = os.getenv("JOBVIS_STORAGE", "").strip().lower() or "sheet"
    if value not in KINDS:
        raise StorageError(f"JOBVIS_STORAGE는 sheet 또는 db만 쓸 수 있습니다 (지금: {value}).")
    return value


def place() -> str:
    """화면 문구에 넣을 저장 위치 이름 (D12)."""
    return "DB" if kind() == "db" else "시트"


def backend():
    if kind() == "db":
        from agent import db  # 시트만 쓰는 사람은 DB 연결 코드를 불러오지 않는다

        return db
    return sheets


def existing_keys() -> tuple[set[tuple[str, str]], set[tuple[str, str]], dict[tuple[str, str], dict]]:
    return backend().existing_keys()


def append_row(values: list) -> int | None:
    return backend().append_row(values)


def read_rows() -> list[dict]:
    return backend().read_rows()


def read_rows_readonly() -> list[dict]:
    return backend().read_rows_readonly()


def update_cells(row_number: int, changes: dict) -> None:
    backend().update_cells(row_number, changes)


def set_check(row_number: int, checked: bool) -> None:
    backend().set_check(row_number, checked)


def set_hidden(row_number: int, hidden: bool) -> None:
    backend().set_hidden(row_number, hidden)


def set_applied(row_number: int, applied: bool) -> None:
    backend().set_applied(row_number, applied)


def write_result(row_number: int, summary: str | None, values: list, extra: list | None, tail: list) -> None:
    backend().write_result(row_number, summary, values, extra, tail)


def delete_rows(keep_applied: bool) -> list[dict]:
    """DB 공고 초기화 (v0.6.1 F30). 시트는 사람이 직접 고치는 곳이라 지우지 않는다."""
    if kind() != "db":
        raise StorageError("공고 초기화는 DB 저장에서만 쓸 수 있습니다.")
    return backend().delete_rows(keep_applied)

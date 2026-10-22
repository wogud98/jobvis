"""DB(Postgres)에 공고를 저장한다. 시트와 같은 칸을 같은 함수로 다룬다 (v0.6 F6–F8, D3–D5).

표는 시트 열과 같은 `postings` 하나다. 칸은 모두 글자로, 체크는 시트처럼 "TRUE"/"FALSE"로 적는다.
그래서 화면·평가 코드는 시트에서 읽은 줄과 똑같이 다룬다.
"""

import functools
import os

import sqlalchemy as sa

from agent import sheets

metadata = sa.MetaData()
TABLE = sa.Table(
    "postings",
    metadata,
    sa.Column("row", sa.Integer, primary_key=True, autoincrement=True),  # 시트 줄 번호 자리
    *[sa.Column(key, sa.Text, nullable=False, server_default="") for key in sheets.KEYS],
)
_KEY_OF = dict(zip(sheets.HEADER, sheets.KEYS, strict=True))  # 시트 열 이름 → 칸 이름


@functools.cache
def engine() -> sa.Engine:
    # 처음 연결할 때 표를 만든다. 이미 있으면 그대로 둔다 (F8)
    connection = sa.create_engine(os.environ["DATABASE_URL"])
    metadata.create_all(connection)
    return connection


def text(value) -> str:
    """시트가 돌려주는 글자와 같게 바꾼다 (D4)."""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return "" if value is None else str(value)


def _set(row_number: int, values: dict) -> None:
    if not values:
        return
    with engine().begin() as connection:
        connection.execute(TABLE.update().where(TABLE.c.row == row_number).values(values))


def _named(names: list[str], values: list) -> dict:
    return {_KEY_OF[name]: text(value) for name, value in zip(names, values, strict=False)}


def append_row(values: list) -> int:
    """새 줄 번호를 돌려준다."""
    data = {key: text(value) for key, value in zip(sheets.KEYS, values, strict=False)}
    with engine().begin() as connection:
        return connection.execute(TABLE.insert().values(data)).inserted_primary_key[0]


def read_rows() -> list[dict]:
    """sheets.read_rows와 같은 모양. 번호 순(시트의 위에서 아래)으로 돌려준다."""
    with engine().connect() as connection:
        found = connection.execute(sa.select(TABLE).order_by(TABLE.c.row)).mappings().all()
    return [{key: row[key] for key in sheets.KEYS} | {"row": row["row"]} for row in found]


def read_rows_readonly() -> list[dict]:
    """화면용. DB는 제목 줄을 고칠 일이 없어 read_rows와 같다."""
    return read_rows()


def existing_keys() -> tuple[set[tuple[str, str]], set[tuple[str, str]], dict[tuple[str, str], dict]]:
    return sheets.collect_keys(read_rows())


def update_cells(row_number: int, changes: dict) -> None:
    """시트 열 이름으로 받은 칸들만 쓴다."""
    _set(row_number, {_KEY_OF[name]: text(value) for name, value in changes.items()})


def set_check(row_number: int, checked: bool) -> None:
    update_cells(row_number, {"평가": bool(checked)})


def set_hidden(row_number: int, hidden: bool) -> None:
    update_cells(row_number, {"관심없음": bool(hidden)})


def set_applied(row_number: int, applied: bool) -> None:
    update_cells(row_number, {"지원": bool(applied)})


def write_result(row_number: int, summary: str | None, values: list, extra: list | None, tail: list) -> None:
    """sheets.write_result와 같은 칸에 쓴다. 수집 칸(출처·지역·본문)은 건드리지 않는다."""
    header = sheets.HEADER
    data = _named(header[sheets.CHECK_COLUMN : sheets.SCORED_AT_COLUMN], values)
    if summary is not None:
        data["requirements"] = text(summary)
    if extra is not None:
        data |= _named(header[sheets.DUTIES_COLUMN - 1 : sheets.TRUST_COLUMN - 1], extra)
    data |= _named(header[sheets.TRUST_COLUMN - 1 :], tail)
    _set(row_number, data)


def delete_rows(keep_applied: bool) -> list[dict]:
    """공고 줄을 지우고 지운 줄을 돌려준다. keep_applied면 "지원"을 체크한 줄은 남긴다 (v0.6.1 F30)."""
    condition = sa.func.upper(sa.func.trim(TABLE.c.applied)) != "TRUE" if keep_applied else sa.true()
    with engine().begin() as connection:
        found = connection.execute(sa.select(TABLE).where(condition)).mappings().all()
        connection.execute(TABLE.delete().where(condition))
    return [{key: row[key] for key in sheets.KEYS} | {"row": row["row"]} for row in found]

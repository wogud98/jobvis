"""구글 시트에 공고를 저장하고, 저장된 줄을 읽고, 평가 결과를 쓴다."""

import functools
import os
import re

import gspread

from agent import postings

HEADER = [
    "회사명",
    "직무",
    "자격요건",
    "마감일",
    "링크",
    "공고ID",
    "저장시각",
    "경력",
    "학력",
    "키워드",
    "평가",
    "종합점수",
    "별점",
    "판정",
    "기술점수",
    "경력점수",
    "문화점수",
    "방향점수",
    "강점",
    "부족한점",
    "평가시각",
    "출처",
    "지역",
    "본문",
    "주요업무",
    "우대사항",
    "기술스택",
    "신뢰",
    "보정",
    "관심없음",
    "지원",
]
# read_rows()가 돌려주는 dict의 키. HEADER와 순서가 같다.
KEYS = [
    "company",
    "title",
    "requirements",
    "deadline",
    "url",
    "id",
    "saved_at",
    "experience",
    "education",
    "keywords",
    "check",
    "score",
    "stars",
    "verdict",
    "skills",
    "experience_score",
    "culture",
    "career",
    "strengths",
    "gaps",
    "scored_at",
    "source",
    "location",
    "body",
    "duties",
    "preferred",
    "stack",
    "trust",
    "adjust",
    "hidden",
    "applied",
]
V01_HEADER = HEADER[:5]
V02_HEADER = HEADER[:7]
V03_HEADER = HEADER[:21]
V04_HEADER = HEADER[:27]
V05_HEADER = HEADER[:29]  # v0.5–v0.5.2 F39까지. "관심없음"은 v0.5.2 F44
V052_HEADER = HEADER[:30]  # v0.5.2 F44까지. "지원"은 v0.5.3 F11
CHECK_COLUMN = HEADER.index("평가")  # 0부터 (시트 API 범위용)
SCORED_AT_COLUMN = HEADER.index("평가시각") + 1  # gspread 열 번호는 1부터
DUTIES_COLUMN = HEADER.index("주요업무") + 1
TRUST_COLUMN = HEADER.index("신뢰") + 1
# 시트에는 사이트 이름으로 적는다. 출처 칸이 빈 줄은 v0.3까지의 사람인 API 줄이다.
SOURCE_NAMES = {"saramin": "사람인", "jobkorea": "잡코리아"}
_SOURCE_CODES = {name: code for code, name in SOURCE_NAMES.items()} | {"": "saramin"}


def _add_checkboxes(sheet: gspread.Worksheet) -> None:
    # "평가" 열 2행부터 끝까지 체크박스 규칙을 건다 (끝 행을 비우면 열 전체).
    rule = {
        "range": {
            "sheetId": sheet.id,
            "startRowIndex": 1,
            "startColumnIndex": CHECK_COLUMN,
            "endColumnIndex": CHECK_COLUMN + 1,
        },
        "rule": {"condition": {"type": "BOOLEAN"}, "showCustomUi": True},
    }
    sheet.spreadsheet.batch_update({"requests": [{"setDataValidation": rule}]})


def _open() -> gspread.Worksheet:
    client = gspread.service_account(filename=os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"])
    return client.open_by_key(os.environ["GOOGLE_SHEET_ID"]).sheet1


@functools.cache
def _sheet() -> gspread.Worksheet:
    # 실행 한 번에 한 번만 인증하고 연결을 재사용한다.
    sheet = _open()
    first_row = sheet.row_values(1)
    if first_row in (V01_HEADER, V02_HEADER):
        sheet.update([HEADER], "A1")  # 예전 제목 줄 뒤에 새 열 이름을 붙인다
        _add_checkboxes(sheet)
    elif first_row in (V03_HEADER, V04_HEADER, V05_HEADER, V052_HEADER):
        sheet.update([HEADER], "A1")  # 체크박스 규칙은 v0.3에서 이미 걸었다
    elif first_row != HEADER:
        sheet.insert_row(HEADER, 1)
        _add_checkboxes(sheet)
    return sheet


# 사이트마다 "(주)회사", "㈜회사", "회사(주)", "주식회사 회사"처럼 다르게 적는다 (2026-10-21 PC 수집)
_LEGAL_FORM = re.compile(r"[(（]\s*[주유사재]\s*[)）]|[㈜㈝㈔㈕]|주식회사|유한회사|사단법인|재단법인")


def normalize(text: str) -> str:
    """사이트 간 같은 공고를 알아보려고 공백·기호를 지운다 (F9)."""
    return "".join(ch for ch in text if ch.isalnum()).casefold()


def normalize_company(name: str) -> str:
    """회사명은 법인 표기를 먼저 지우고 normalize한다 (F9)."""
    return normalize(_LEGAL_FORM.sub("", name))


def source_code(name: str) -> str:
    return _SOURCE_CODES.get(name.strip(), name.strip())


def existing_keys() -> tuple[set[tuple[str, str]], set[tuple[str, str]], dict[tuple[str, str], dict]]:
    """(출처, 공고ID) 쌍, (회사명, 제목) 정규화 쌍, 본문 미확보 줄. 출처 칸이 빈 줄은 사람인으로 본다.

    본문 미확보 줄은 {(회사, 제목): {"row", "source", "id"}}. 다른 사이트 본문으로 채울 때 쓴다 (v0.5 F46).
    """
    return collect_keys(read_rows())


def collect_keys(
    rows: list[dict],
) -> tuple[set[tuple[str, str]], set[tuple[str, str]], dict[tuple[str, str], dict]]:
    """existing_keys의 계산 부분. 시트와 DB가 함께 쓴다 (v0.6 D1)."""
    ids, names, missing = set(), set(), {}
    for row in rows:
        if row["id"]:
            ids.add((source_code(row["source"]), row["id"]))
        if row["company"] or row["title"]:
            name = (normalize_company(row["company"]), normalize(row["title"]))
            names.add(name)
            if row["body"] == postings.MISSING and row["id"]:
                missing.setdefault(name, {"row": row["row"], "source": source_code(row["source"]), "id": row["id"]})
    return ids, names, missing


_ROW_NUMBER = re.compile(r"![A-Z]+(\d+)")


def append_row(values: list) -> int | None:
    """붙인 줄 번호를 돌려준다. 응답에서 못 읽으면 None."""
    response = _sheet().append_row(values)
    updated = response.get("updates", {}).get("updatedRange", "") if isinstance(response, dict) else ""
    found = _ROW_NUMBER.search(updated)
    return int(found.group(1)) if found else None


def _rows(values: list[list]) -> list[dict]:
    rows = []
    for number, row in enumerate(values[1:], start=2):
        if not any(row):
            continue
        row = [str(v) for v in row] + [""] * (len(KEYS) - len(row))
        rows.append(dict(zip(KEYS, row, strict=False)) | {"row": number})
    return rows


def read_rows() -> list[dict]:
    """제목 줄을 뺀 모든 줄. 각 줄은 KEYS를 키로 하고, 시트 줄 번호를 "row"에 담는다."""
    return _rows(_sheet().get_all_values())


def read_rows_readonly() -> list[dict]:
    """화면용. read_rows와 같지만 제목 줄을 고치거나 체크박스 규칙을 걸지 않는다 (v0.5 F8).

    예전 제목 줄이어도 열 위치로 읽고, 모자란 칸은 빈칸이다.
    """
    return _rows(_open().get_all_values())


def update_cells(row_number: int, changes: dict) -> None:
    """제목 이름으로 열을 찾아 그 칸들만 한 번의 요청으로 쓴다. 받은함(F39, F40)과 본문 채우기(F46)가 쓴다."""
    data = [
        {"range": gspread.utils.rowcol_to_a1(row_number, HEADER.index(name) + 1), "values": [[value]]}
        for name, value in changes.items()
    ]
    _sheet().batch_update(data)


def set_check(row_number: int, checked: bool) -> None:
    """화면 카드의 체크 칸을 "평가" 열 체크박스에 쓴다 (v0.5.2 F39). 다른 칸은 건드리지 않는다."""
    update_cells(row_number, {"평가": bool(checked)})


def set_hidden(row_number: int, hidden: bool) -> None:
    """화면 카드의 "관심 없음"을 "관심없음" 열에 쓴다 (v0.5.2 F44). 줄은 지우지 않는다(다시 수집되지 않게)."""
    update_cells(row_number, {"관심없음": bool(hidden)})


def set_applied(row_number: int, applied: bool) -> None:
    """화면 카드의 "지원함"을 "지원" 열에 쓴다 (v0.5.3 F11)."""
    update_cells(row_number, {"지원": bool(applied)})


def _span(row_number: int, first: int, last: int) -> str:
    return f"{gspread.utils.rowcol_to_a1(row_number, first)}:{gspread.utils.rowcol_to_a1(row_number, last)}"


def write_result(row_number: int, summary: str | None, values: list, extra: list | None, tail: list) -> None:
    """요약은 "자격요건" 칸에, 평가 결과는 "평가"부터 "평가시각"까지, 본문 요약은 "주요업무"부터 "기술스택"까지,
    신뢰·보정은 마지막 두 칸에.

    한 번의 요청으로 쓰고, 그 사이 수집 칸(출처·지역·본문)은 건드리지 않는다.
    summary와 extra가 None이면(신입 제외 줄) 그 칸은 그대로 둔다.
    """
    data = [{"range": _span(row_number, CHECK_COLUMN + 1, SCORED_AT_COLUMN), "values": [values]}]
    if summary is not None:
        data.insert(0, {"range": f"C{row_number}", "values": [[summary]]})
    if extra is not None:
        data.append({"range": _span(row_number, DUTIES_COLUMN, TRUST_COLUMN - 1), "values": [extra]})
    data.append({"range": _span(row_number, TRUST_COLUMN, TRUST_COLUMN + len(tail) - 1), "values": [tail]})
    _sheet().batch_update(data)

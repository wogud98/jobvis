"""구글 시트에 공고를 저장하고, 저장된 줄을 읽고, 평가 결과를 쓴다."""

import functools
import os
import re

import gspread

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
]
V01_HEADER = HEADER[:5]
V02_HEADER = HEADER[:7]
V03_HEADER = HEADER[:21]
CHECK_COLUMN = HEADER.index("평가")  # 0부터 (시트 API 범위용)
SCORED_AT_COLUMN = HEADER.index("평가시각") + 1  # gspread 열 번호는 1부터
DUTIES_COLUMN = HEADER.index("주요업무") + 1
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


@functools.cache
def _sheet() -> gspread.Worksheet:
    # 실행 한 번에 한 번만 인증하고 연결을 재사용한다.
    client = gspread.service_account(filename=os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"])
    sheet = client.open_by_key(os.environ["GOOGLE_SHEET_ID"]).sheet1
    first_row = sheet.row_values(1)
    if first_row in (V01_HEADER, V02_HEADER):
        sheet.update([HEADER], "A1")  # 예전 제목 줄 뒤에 새 열 이름을 붙인다
        _add_checkboxes(sheet)
    elif first_row == V03_HEADER:
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


def existing_keys() -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """(출처, 공고ID) 쌍과 (회사명, 제목) 정규화 쌍. 출처 칸이 빈 줄은 사람인으로 본다."""
    ids, names = set(), set()
    for row in read_rows():
        if row["id"]:
            ids.add((source_code(row["source"]), row["id"]))
        if row["company"] or row["title"]:
            names.add((normalize_company(row["company"]), normalize(row["title"])))
    return ids, names


def append_row(values: list) -> None:
    _sheet().append_row(values)


def read_rows() -> list[dict]:
    """제목 줄을 뺀 모든 줄. 각 줄은 KEYS를 키로 하고, 시트 줄 번호를 "row"에 담는다."""
    rows = []
    for number, values in enumerate(_sheet().get_all_values()[1:], start=2):
        if not any(values):
            continue
        values = [str(v) for v in values] + [""] * (len(KEYS) - len(values))
        rows.append(dict(zip(KEYS, values, strict=False)) | {"row": number})
    return rows


def write_result(row_number: int, summary: str, values: list, extra: list) -> None:
    """요약은 "자격요건" 칸에, 평가 결과는 "평가"부터 "평가시각"까지, 본문 요약은 "주요업무"부터 "기술스택"까지.

    한 번의 요청으로 쓰고, 그 사이 수집 칸(출처·지역·본문)은 건드리지 않는다.
    """
    first = gspread.utils.rowcol_to_a1(row_number, CHECK_COLUMN + 1)
    last = gspread.utils.rowcol_to_a1(row_number, SCORED_AT_COLUMN)
    extra_first = gspread.utils.rowcol_to_a1(row_number, DUTIES_COLUMN)
    extra_last = gspread.utils.rowcol_to_a1(row_number, len(HEADER))
    _sheet().batch_update(
        [
            {"range": f"C{row_number}", "values": [[summary]]},
            {"range": f"{first}:{last}", "values": [values]},
            {"range": f"{extra_first}:{extra_last}", "values": [extra]},
        ]
    )

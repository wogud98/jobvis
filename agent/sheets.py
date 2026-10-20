"""구글 시트에 공고를 저장하고, 저장된 줄을 읽고, 평가 결과를 쓴다."""

import functools
import os

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
]
V01_HEADER = HEADER[:5]
V02_HEADER = HEADER[:7]
ID_COLUMN = HEADER.index("공고ID") + 1  # gspread 열 번호는 1부터
CHECK_COLUMN = HEADER.index("평가")  # 0부터 (시트 API 범위용)


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
    elif first_row != HEADER:
        sheet.insert_row(HEADER, 1)
        _add_checkboxes(sheet)
    return sheet


def existing_ids() -> set[str]:
    # 숫자로 읽힐 수 있어 문자열로 맞춘다.
    return {str(value) for value in _sheet().col_values(ID_COLUMN)[1:] if value}


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


def write_result(row_number: int, summary: str, values: list) -> None:
    """요약은 "자격요건" 칸에, 평가 결과는 "평가"부터 "평가시각"까지 한 번의 요청으로 쓴다."""
    first = gspread.utils.rowcol_to_a1(row_number, CHECK_COLUMN + 1)
    last = gspread.utils.rowcol_to_a1(row_number, len(HEADER))
    _sheet().batch_update(
        [
            {"range": f"C{row_number}", "values": [[summary]]},
            {"range": f"{first}:{last}", "values": [values]},
        ]
    )

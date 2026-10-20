"""구글 시트에 한 줄씩 저장하고, 이미 저장한 공고 ID를 읽는다."""

import functools
import os

import gspread

HEADER = ["회사명", "직무", "자격요건", "마감일", "링크", "공고ID", "저장시각"]
V01_HEADER = HEADER[:5]
ID_COLUMN = HEADER.index("공고ID") + 1  # gspread 열 번호는 1부터


@functools.cache
def _sheet() -> gspread.Worksheet:
    # 실행 한 번에 한 번만 인증하고 연결을 재사용한다.
    client = gspread.service_account(filename=os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"])
    sheet = client.open_by_key(os.environ["GOOGLE_SHEET_ID"]).sheet1
    first_row = sheet.row_values(1)
    if first_row == V01_HEADER:
        sheet.update([HEADER], "A1")  # v0.1 제목 줄 뒤에 새 열 이름을 붙인다
    elif first_row != HEADER:
        sheet.insert_row(HEADER, 1)
    return sheet


def existing_ids() -> set[str]:
    # 숫자로 읽힐 수 있어 문자열로 맞춘다.
    return {str(value) for value in _sheet().col_values(ID_COLUMN)[1:] if value}


def append_row(values: list[str]) -> None:
    _sheet().append_row(values)

"""구글 시트에 한 줄씩 저장한다."""

import os

import gspread

HEADER = ["회사명", "직무", "자격요건", "마감일", "링크"]


def append_row(values: list[str]) -> None:
    client = gspread.service_account(filename=os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"])
    sheet = client.open_by_key(os.environ["GOOGLE_SHEET_ID"]).sheet1
    if sheet.row_values(1) != HEADER:
        sheet.insert_row(HEADER, 1)
    sheet.append_row(values)

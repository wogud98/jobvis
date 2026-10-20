import pytest

from agent import sheets


class FakeWorksheet:
    def __init__(self, rows):
        self.rows = [list(row) for row in rows]

    def row_values(self, index):
        return self.rows[index - 1] if len(self.rows) >= index else []

    def col_values(self, index):
        return [row[index - 1] if len(row) >= index else "" for row in self.rows]

    def update(self, values, range_name):
        assert range_name == "A1"
        self.rows[0] = values[0]

    def insert_row(self, values, index):
        self.rows.insert(index - 1, values)

    def append_row(self, values):
        self.rows.append(values)


@pytest.fixture
def worksheet(monkeypatch):
    def use(rows):
        sheet = FakeWorksheet(rows)

        class FakeClient:
            def open_by_key(self, key):
                return type("Spreadsheet", (), {"sheet1": sheet})()

        connections = []
        monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
        monkeypatch.setenv("GOOGLE_SHEET_ID", "sheet-id")
        monkeypatch.setattr(sheets.gspread, "service_account", lambda filename: connections.append(1) or FakeClient())
        sheets._sheet.cache_clear()
        return sheet, connections

    yield use
    sheets._sheet.cache_clear()


def test_v01_header_is_replaced_with_new_header(worksheet):
    sheet, _ = worksheet([sheets.V01_HEADER, ["회사", "직무", "요약", "2026-11-01", "url"]])

    sheets.existing_ids()

    assert sheet.rows[0] == sheets.HEADER
    assert len(sheet.rows) == 2


def test_header_is_inserted_into_empty_sheet(worksheet):
    sheet, _ = worksheet([])

    sheets.append_row(["회사", "직무", "요약", "2026-11-01", "url", "1", "2026-10-20 09:00"])

    assert sheet.rows[0] == sheets.HEADER
    assert sheet.rows[1][5] == "1"


def test_existing_ids_skips_header_and_v01_rows(worksheet):
    worksheet(
        [
            sheets.HEADER,
            ["회사", "직무", "요약", "마감", "url"],  # v0.1 줄: ID 없음
            ["회사", "직무", "요약", "마감", "url", "123", "2026-10-20 09:00"],
        ]
    )

    assert sheets.existing_ids() == {"123"}


def test_connects_once_per_run(worksheet):
    _, connections = worksheet([sheets.HEADER])

    sheets.existing_ids()
    sheets.append_row(["a"] * 7)
    sheets.append_row(["b"] * 7)

    assert len(connections) == 1

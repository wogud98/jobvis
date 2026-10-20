import pytest

from agent import sheets


class FakeSpreadsheet:
    def __init__(self):
        self.requests = []

    def batch_update(self, body):
        self.requests.extend(body["requests"])


class FakeWorksheet:
    id = 0

    def __init__(self, rows):
        self.rows = [list(row) for row in rows]
        self.spreadsheet = FakeSpreadsheet()
        self.updates = []

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

    def get_all_values(self):
        return [list(row) for row in self.rows]

    def batch_update(self, data):
        self.updates.extend(data)


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


CHECKBOX_RULE = {
    "setDataValidation": {
        "range": {"sheetId": 0, "startRowIndex": 1, "startColumnIndex": 10, "endColumnIndex": 11},
        "rule": {"condition": {"type": "BOOLEAN"}, "showCustomUi": True},
    }
}


def test_v02_header_is_extended_and_checkboxes_added(worksheet):
    old_row = ["회사", "직무", "요약", "2026-11-01", "url", "1", "2026-10-20 09:00"]
    sheet, _ = worksheet([sheets.V02_HEADER, old_row])

    sheets.existing_ids()

    assert sheet.rows[0] == sheets.HEADER
    assert sheet.rows[1] == old_row  # 예전 줄은 그대로
    assert sheet.spreadsheet.requests == [CHECKBOX_RULE]  # "평가"는 K열(0부터 10)


def test_checkboxes_added_only_when_header_changes(worksheet):
    sheet, _ = worksheet([sheets.HEADER])

    sheets.existing_ids()

    assert sheet.spreadsheet.requests == []


def test_new_sheet_gets_checkboxes(worksheet):
    sheet, _ = worksheet([])

    sheets.existing_ids()

    assert sheet.spreadsheet.requests == [CHECKBOX_RULE]


def test_read_rows_pads_short_rows_and_keeps_row_numbers(worksheet):
    worksheet(
        [
            sheets.HEADER,
            ["회사1", "직무1", "", "마감", "url", "1", "시각"],  # v0.2 줄: 뒤 칸 없음
            [""] * 7,  # 빈 줄은 건너뜀
            ["회사2", "직무2", "", "마감", "url", "2", "시각", "신입", "대졸", "Python", "TRUE"],
        ]
    )

    rows = sheets.read_rows()

    assert [row["row"] for row in rows] == [2, 4]
    assert rows[0]["company"] == "회사1"
    assert rows[0]["experience"] == ""
    assert rows[0]["scored_at"] == ""
    assert rows[1]["check"] == "TRUE"
    assert rows[1]["keywords"] == "Python"
    assert set(rows[1]) == set(sheets.KEYS) | {"row"}


def test_write_result_writes_summary_and_result_columns_only(worksheet):
    sheet, _ = worksheet([sheets.HEADER])
    values = [False, 71, "★★★★☆", "추천", 72, 60, "-", 80, "강점", "Docker", "2026-10-20 09:00"]

    sheets.write_result(5, "신입, Java 필수", values)

    assert sheet.updates == [
        {"range": "C5", "values": [["신입, Java 필수"]]},
        {"range": "K5:U5", "values": [values]},
    ]


def test_header_and_keys_line_up():
    assert len(sheets.HEADER) == len(sheets.KEYS) == 21
    assert sheets.HEADER[sheets.KEYS.index("gaps")] == "부족한점"
    assert sheets.HEADER[sheets.KEYS.index("check")] == "평가"

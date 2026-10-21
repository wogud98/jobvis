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
        number = len(self.rows)
        return {"updates": {"updatedRange": f"'시트1'!A{number}:AC{number}"}}  # gspread 응답 모양

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

    sheets.existing_keys()

    assert sheet.rows[0] == sheets.HEADER
    assert len(sheet.rows) == 2


def test_header_is_inserted_into_empty_sheet(worksheet):
    sheet, _ = worksheet([])

    sheets.append_row(["회사", "직무", "요약", "2026-11-01", "url", "1", "2026-10-20 09:00"])

    assert sheet.rows[0] == sheets.HEADER
    assert sheet.rows[1][5] == "1"


def test_existing_keys_reads_ids_and_names_and_treats_blank_source_as_saramin(worksheet):
    blank = [""] * 10  # L–U 평가 칸
    worksheet(
        [
            sheets.HEADER,
            ["회사", "직무", "요약", "마감", "url"],  # v0.1 줄: ID 없음
            ["(주)가나다", "백엔드 개발자 [신입]", "요약", "마감", "url", "123", "시각"],  # v0.3까지: 출처 없음
            ["라마바", "AI Engineer", "", "마감", "url", "77", "시각", "신입", "", "", "FALSE", *blank, "잡코리아"],
            ["마바사", "FDE", "", "마감", "url", "88", "시각", "신입", "", "", "FALSE", *blank, "", "", "본문 미확보"],
        ]
    )

    ids, names, missing = sheets.existing_keys()

    assert ids == {("saramin", "123"), ("jobkorea", "77"), ("saramin", "88")}
    # 공백·기호를 지우고 소문자로 비교 (F9). 회사명의 "(주)"는 통째로 지운다.
    assert names == {("회사", "직무"), ("가나다", "백엔드개발자신입"), ("라마바", "aiengineer"), ("마바사", "fde")}
    # 본문 미확보 줄은 다른 사이트 본문으로 채울 수 있게 줄 번호와 함께 (v0.5 F46)
    assert missing == {("마바사", "fde"): {"row": 5, "source": "saramin", "id": "88"}}


def test_normalize_drops_spaces_symbols_and_case():
    assert sheets.normalize("(주) 가나다 · Backend!") == sheets.normalize("(주)가나다backend")


@pytest.mark.parametrize(
    "name",
    [
        "(주)에스투더블유",
        "㈜에스투더블유",
        "에스투더블유(주)",
        "주식회사 에스투더블유",
        "( 주 ) 에스투더블유",
        "에스투더블유",
    ],
)
def test_normalize_company_drops_legal_form(name):
    # 2026-10-21 PC 수집: 사람인 "(주)에스투더블유"와 잡코리아 "㈜에스투더블유"를 다른 회사로 봄
    assert sheets.normalize_company(name) == "에스투더블유"


def test_normalize_company_keeps_other_letters():
    assert sheets.normalize_company("(유)한빛") == sheets.normalize_company("유한회사 한빛") == "한빛"
    assert sheets.normalize_company("주원테크") == "주원테크"  # 회사명 속 "주"는 남긴다
    assert sheets.normalize_company("") == ""


def test_normalize_keeps_legal_form_letters_in_title():
    # 제목에는 법인 표기 제거를 쓰지 않는다
    assert sheets.normalize("주식회사 소개 담당") == "주식회사소개담당"


def test_v03_header_is_extended_without_new_checkbox_rule(worksheet):
    old_row = ["회사", "직무", "요약", "2026-11-01", "url", "1", "시각", "신입", "대졸", "Python", "TRUE"]
    sheet, _ = worksheet([sheets.V03_HEADER, old_row])

    sheets.existing_keys()

    assert sheet.rows[0] == sheets.HEADER
    assert sheet.rows[1] == old_row
    assert sheet.spreadsheet.requests == []  # v0.3에서 이미 걸었음


def test_connects_once_per_run(worksheet):
    _, connections = worksheet([sheets.HEADER])

    sheets.existing_keys()
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

    sheets.existing_keys()

    assert sheet.rows[0] == sheets.HEADER
    assert sheet.rows[1] == old_row  # 예전 줄은 그대로
    assert sheet.spreadsheet.requests == [CHECKBOX_RULE]  # "평가"는 K열(0부터 10)


def test_checkboxes_added_only_when_header_changes(worksheet):
    sheet, _ = worksheet([sheets.HEADER])

    sheets.existing_keys()

    assert sheet.spreadsheet.requests == []


def test_new_sheet_gets_checkboxes(worksheet):
    sheet, _ = worksheet([])

    sheets.existing_keys()

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


def test_write_result_writes_summary_result_and_body_summary_columns_only(worksheet):
    sheet, _ = worksheet([sheets.HEADER])
    values = [False, 71, "★★★★☆", "추천", 72, 60, "-", 80, "강점", "Docker", "2026-10-20 09:00"]
    extra = ["API 개발", "AWS 경험", "Java, Spring"]

    sheets.write_result(5, "신입, Java 필수", values, extra, ["높음", "경력 75→60 (3년 요구, 2년)"])

    # 수집 칸인 V–X(출처·지역·본문)는 건드리지 않는다
    assert sheet.updates == [
        {"range": "C5", "values": [["신입, Java 필수"]]},
        {"range": "K5:U5", "values": [values]},
        {"range": "Y5:AA5", "values": [extra]},
        {"range": "AB5:AC5", "values": [["높음", "경력 75→60 (3년 요구, 2년)"]]},
    ]


def test_write_result_for_excluded_row_keeps_summary_and_body_summary(worksheet):
    sheet, _ = worksheet([sheets.HEADER])
    values = [False, "", "", "제외 (경력 요구)", "", "", "", "", "", "", "2026-10-21 09:00"]

    sheets.write_result(5, None, values, None, ["", ""])

    assert sheet.updates == [
        {"range": "K5:U5", "values": [values]},
        {"range": "AB5:AC5", "values": [["", ""]]},
    ]


def test_v04_header_is_extended_without_new_checkbox_rule(worksheet):
    sheet, _ = worksheet([sheets.V04_HEADER])

    sheets.read_rows()

    assert sheet.rows[0] == sheets.HEADER
    assert sheet.spreadsheet.requests == []


def test_append_row_returns_row_number(worksheet):
    worksheet([sheets.HEADER, ["a"] * 7])

    assert sheets.append_row(["b"] * 7) == 3


def test_append_row_without_range_in_response_returns_none(worksheet, monkeypatch):
    sheet, _ = worksheet([sheets.HEADER])
    monkeypatch.setattr(sheet, "append_row", lambda values: None)

    assert sheets.append_row(["b"] * 7) is None


def test_update_cells_writes_named_columns_only(worksheet):
    sheet, _ = worksheet([sheets.HEADER])

    sheets.update_cells(7, {"본문": "글자+이미지", "평가": True, "출처": "잡코리아"})

    assert sheet.updates == [
        {"range": "X7", "values": [["글자+이미지"]]},
        {"range": "K7", "values": [[True]]},
        {"range": "V7", "values": [["잡코리아"]]},
    ]


def test_read_rows_readonly_does_not_touch_old_header(worksheet):
    old_row = ["회사", "직무", "요약", "2026-11-01", "url", "1", "시각"]
    sheet, _ = worksheet([sheets.V02_HEADER, old_row])

    rows = sheets.read_rows_readonly()

    assert sheet.rows[0] == sheets.V02_HEADER  # 화면은 시트에 쓰지 않는다 (v0.5 F8)
    assert sheet.spreadsheet.requests == []
    assert rows[0]["company"] == "회사" and rows[0]["trust"] == ""


def test_header_and_keys_line_up():
    assert len(sheets.HEADER) == len(sheets.KEYS) == 29
    assert sheets.HEADER[sheets.KEYS.index("gaps")] == "부족한점"
    assert sheets.HEADER[sheets.KEYS.index("check")] == "평가"
    assert sheets.HEADER[21:27] == ["출처", "지역", "본문", "주요업무", "우대사항", "기술스택"]  # V–AA
    assert sheets.HEADER[27:] == ["신뢰", "보정"]  # AB–AC (v0.5 F32)
    assert sheets.HEADER[sheets.KEYS.index("body")] == "본문"


@pytest.mark.parametrize(("checked", "value"), [(True, True), (False, False), (1, True)])
def test_set_check_writes_check_column_only(worksheet, checked, value):
    sheet, _ = worksheet([sheets.HEADER])

    sheets.set_check(5, checked)

    assert sheet.updates == [{"range": "K5", "values": [[value]]}]  # "평가" 체크박스 (v0.5.2 F39)

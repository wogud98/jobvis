"""Streamlit 화면을 가짜 시트로 띄워 본다. 실제 시트·브라우저 없음 (v0.5 N5)."""

from pathlib import Path

import pytest
import streamlit as st
import yaml
from streamlit.testing.v1 import AppTest

from agent import sheets

APP = str(Path(__file__).parent.parent / "app.py")


def make_row(number: int, **changes) -> dict:
    row = dict.fromkeys(sheets.KEYS, "")
    row |= {"row": number, "company": f"회사{number}", "title": "백엔드", "id": str(number), "source": "사람인"}
    return row | changes


@pytest.fixture
def app(monkeypatch, tmp_path):
    """작업 폴더를 임시 폴더로 바꿔 profile.yaml과 data/inbox/가 저장소에 생기지 않게 한다."""
    monkeypatch.chdir(tmp_path)

    def run(rows=None, error=None):
        def fake_read():
            if error:
                raise error
            return rows or []

        monkeypatch.setattr(sheets, "read_rows_readonly", fake_read)
        monkeypatch.setattr(sheets, "_sheet", lambda: pytest.fail("화면은 쓰기용 시트 연결을 쓰지 않음"))
        at = AppTest.from_file(APP, default_timeout=30)
        at.run()
        return at

    yield run
    st.cache_data.clear()  # 다음 테스트가 앞 테스트의 시트 줄을 읽지 않게


def test_postings_tab_shows_guide_summary_and_scored_cards(app):
    rows = [
        make_row(2, score="80", verdict="강력 추천", trust="높음", body="글자"),
        make_row(3, score="60", verdict="추천", trust="낮음", body="본문 미확보"),
        make_row(4),  # 평가 전: 기본으로 숨김
    ]

    at = app(rows)

    assert not at.exception
    assert [tab.label for tab in at.tabs] == ["📋 공고", "👤 프로필"]
    assert at.expander[0].label == "📖 사용법"  # F1
    assert [(m.label, m.value) for m in at.metric] == [
        ("전체 공고", "3"),
        ("평가 완료", "2"),
        ("추천 이상", "2"),
        ("본문 미확보", "1"),
    ]  # 필터와 상관없이 전체 (F2)
    heads = [m.value for m in at.markdown if "회사" in m.value]
    assert len(heads) == 2
    assert heads[0].startswith("**회사2 · 백엔드**") and "신뢰 높음" in heads[0]
    assert "jv-low" in heads[1]  # 신뢰 낮음 배지 색 (F5)
    assert [e.label for e in at.expander].count("자세히") == 2  # F4


def test_unscored_card_shows_dash_and_sheet_text_is_escaped(app):
    at = app([make_row(2, company="<b>회사</b>")])
    at.toggle[0].set_value(True).run()

    assert any('<div class="jv-score">-</div>' in m.value for m in at.markdown)  # F6
    head = next(m.value for m in at.markdown if "회사" in m.value)
    assert "&lt;b&gt;회사&lt;/b&gt;" in head and "<b>회사</b>" not in head  # 시트 글자를 HTML로 그대로 넣지 않음


def test_sheet_error_shows_message(app):
    at = app(error=KeyError("GOOGLE_SHEET_ID"))

    assert not at.exception
    assert "인증 정보를 찾지 못했습니다" in at.error[0].value


def test_empty_sheet_shows_collect_hint(app):
    at = app([])

    assert "공고 없음" in at.info[0].value


def badges(at) -> str:
    return next(m.value for m in at.markdown if "jv-badge" in m.value and "<style>" not in m.value)


def test_profile_tab_saves_valid_profile(app, tmp_path):
    at = app([])
    assert badges(at).count("✗") == 2  # 필수 칸 배지 (F8)
    next(m for m in at.multiselect if m.label.startswith("주력 기술")).set_value(["Python", "SQL"])
    next(m for m in at.multiselect if m.label.startswith("희망 직무")).set_value(["백엔드 개발"])
    at.slider[0].set_value(2)
    at.selectbox[0].set_value("석사")
    at.run()
    assert "✗" not in badges(at)  # 입력하는 동안 바뀜
    at.button(key="profile-save").click().run()

    assert not at.exception
    saved = yaml.safe_load((tmp_path / "profile.yaml").read_text(encoding="utf-8"))
    assert saved["skills"]["main"] == ["Python", "SQL"]
    assert saved["experience"]["years"] == 2
    assert saved["experience"]["degree"] == "석사"
    assert saved["direction"]["jobs"] == ["백엔드 개발"]
    assert any("저장함" in message.value for message in at.success)


def test_profile_tab_shows_file_values_not_in_suggestions(app, tmp_path):
    text = "skills: {main: [VB6]}\nexperience: {years: 2}\ndirection: {jobs: [국방 M&S]}\nculture: [몰입]\n"
    (tmp_path / "profile.yaml").write_text(text, encoding="utf-8")

    at = app([])

    main_skills = next(m for m in at.multiselect if m.label.startswith("주력 기술"))
    assert main_skills.value == ["VB6"] and "VB6" in main_skills.options  # F11
    assert next(a for a in at.text_area if a.label.startswith("직접 적기")).value == "몰입"  # F12
    at.button(key="profile-save").click().run()
    assert yaml.safe_load((tmp_path / "profile.yaml").read_text(encoding="utf-8"))["culture"] == ["몰입"]


def test_profile_tab_does_not_save_without_required_fields(app, tmp_path):
    at = app([])
    at.button(key="profile-save").click().run()

    assert not (tmp_path / "profile.yaml").exists()
    assert "skills.main" in at.error[0].value  # v0.5 F20


def test_profile_tab_keeps_broken_file(app, tmp_path):
    (tmp_path / "profile.yaml").write_text("skills: [Python\n", encoding="utf-8")

    at = app([])

    assert "화면에서 저장하지 않습니다" in at.error[0].value
    assert (tmp_path / "profile.yaml").read_text(encoding="utf-8") == "skills: [Python\n"  # F21

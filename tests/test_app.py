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


def test_postings_tab_shows_scored_cards_and_two_tabs(app):
    rows = [
        make_row(2, score="80", verdict="강력 추천", trust="높음", body="글자"),
        make_row(3, score="60", verdict="추천", trust="낮음", body="본문 미확보"),
        make_row(4),  # 평가 전: 기본으로 숨김
    ]

    at = app(rows)

    assert not at.exception
    assert [tab.label for tab in at.tabs] == ["공고", "프로필"]
    titles = [expander.label for expander in at.expander]
    assert len(titles) == 2
    assert titles[0].startswith("80 | ") and "회사2 · 백엔드" in titles[0]
    assert titles[1].startswith(":gray[")  # 신뢰 낮음은 흐리게 (F34)


def test_sheet_error_shows_message(app):
    at = app(error=KeyError("GOOGLE_SHEET_ID"))

    assert not at.exception
    assert "인증 정보를 찾지 못했습니다" in at.error[0].value


def test_empty_sheet_shows_collect_hint(app):
    at = app([])

    assert "공고 없음" in at.info[0].value


def test_profile_tab_saves_valid_profile(app, tmp_path):
    at = app([])
    main_skills = next(area for area in at.text_area if area.label.startswith("주력 기술"))
    jobs = next(area for area in at.text_area if area.label.startswith("희망 직무"))
    main_skills.input("Python\nSQL")
    jobs.input("백엔드")
    at.slider[0].set_value(2)
    at.button(key="FormSubmitter:profile-저장").click()
    at.run()

    assert not at.exception
    saved = yaml.safe_load((tmp_path / "profile.yaml").read_text(encoding="utf-8"))
    assert saved["skills"]["main"] == ["Python", "SQL"]
    assert saved["experience"]["years"] == 2
    assert any("저장함" in message.value for message in at.success)


def test_profile_tab_does_not_save_without_required_fields(app, tmp_path):
    at = app([])
    at.button(key="FormSubmitter:profile-저장").click()
    at.run()

    assert not (tmp_path / "profile.yaml").exists()
    assert "skills.main" in at.error[0].value  # F20


def test_profile_tab_keeps_broken_file(app, tmp_path):
    (tmp_path / "profile.yaml").write_text("skills: [Python\n", encoding="utf-8")

    at = app([])

    assert "화면에서 저장하지 않습니다" in at.error[0].value
    assert (tmp_path / "profile.yaml").read_text(encoding="utf-8") == "skills: [Python\n"  # F21

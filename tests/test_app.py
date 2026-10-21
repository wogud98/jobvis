"""Streamlit 화면을 가짜 시트로 띄워 본다. 실제 시트·브라우저 없음 (v0.5 N5)."""

from pathlib import Path

import pytest
import streamlit as st
import yaml
from streamlit.testing.v1 import AppTest

from agent import ocr, postings, profile_form, runner, sheets

APP = str(Path(__file__).parent.parent / "app.py")


def make_row(number: int, **changes) -> dict:
    row = dict.fromkeys(sheets.KEYS, "")
    row |= {"row": number, "company": f"회사{number}", "title": "백엔드", "id": str(number), "source": "사람인"}
    return row | changes


@pytest.fixture(autouse=True)
def no_job(monkeypatch):
    """실행 기록(runner._job)은 모듈 전역이라 테스트마다 비운다."""
    monkeypatch.setattr(runner, "_job", None)


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
        make_row(4),  # 평가 전도 기본으로 보임 (v0.5.2 F32)
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
    assert len(heads) == 3
    assert heads[0].startswith("**회사2 · 백엔드**") and "신뢰 높음" in heads[0]
    assert "jv-low" in heads[1]  # 신뢰 낮음 배지 색 (F5)
    assert "평가 전" in heads[2]  # 점수 순, 평가 전은 뒤
    assert [e.label for e in at.expander].count("자세히") == 3  # F4

    at.toggle[0].set_value(True).run()  # 평가된 공고만 보기 (F32)
    assert sum("회사" in m.value for m in at.markdown) == 2


def test_filters_start_empty_meaning_all(app):
    rows = [make_row(n, score="70", experience=e) for n, e in ((2, "신입"), (3, "경력 3년↑"), (4, "경력무관"))]
    at = app(rows)

    source, career = (next(m for m in at.multiselect if m.label == name) for name in ("출처", "경력"))
    assert source.value == [] and career.value == []  # 처음엔 아무것도 안 고름 (v0.5.2 F29)
    assert career.options == ["신입", "경력", "무관"]  # 묶음 (F30)
    assert sum("회사" in m.value for m in at.markdown) == 3  # 비어 있어도 전체가 보임
    career.set_value(["경력"]).run()
    assert sum("회사" in m.value for m in at.markdown) == 1


def test_unscored_card_shows_dash_and_sheet_text_is_escaped(app):
    at = app([make_row(2, company="<b>회사</b>")])  # 평가 전도 기본으로 보임 (F32)

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
    next(s for s in at.selectbox if s.label == "최종 학력").set_value("석사")
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


# ---- v0.5.2 화면에서 실행 ----


def scorable(number: int, **changes) -> dict:
    return make_row(number, experience="신입", **changes)


def test_run_panel_shows_collect_and_score_cards(app):
    at = app([scorable(2), scorable(3, check="TRUE"), scorable(4, score="70")])

    assert not at.exception
    assert at.button(key="run-collect").label == "🔎 수집"  # F1
    assert at.button(key="run-score").label == "🧮 평가 (대상 1건)"  # 체크한 공고 (F7)
    next(r for r in at.radio if r.label == "대상").set_value("점수 없는 공고 전부").run()
    assert at.button(key="run-score").label == "🧮 평가 (대상 2건)"  # --score all (F7)
    keyword = next(s for s in at.selectbox if s.label == "키워드 *")
    assert set(runner.JOB_NAMES) <= set(keyword.options)  # 직무 이름이 추천 검색어 (F3)
    assert any("**수집** 카드에 키워드를 넣고" in m.value for m in at.markdown)  # 사용법 (F15)


def test_score_button_is_disabled_without_targets(app):
    at = app([scorable(2, score="70")])

    assert at.button(key="run-score").disabled


def test_collect_without_keyword_shows_error_and_does_not_start(app, monkeypatch):
    monkeypatch.setattr(runner, "start_collect", lambda state: pytest.fail("키워드 없이 실행하지 않음"))
    at = app([])
    at.button(key="run-collect").click().run()

    assert "키워드를 입력해 주세요" in at.error[0].value


def test_collect_button_starts_collect_with_inputs(app, monkeypatch):
    started = []
    monkeypatch.setattr(runner, "start_collect", lambda state: started.append(state))
    at = app([])
    next(s for s in at.selectbox if s.label == "키워드 *").set_value(runner.JOB_NAMES[0])
    next(s for s in at.selectbox if s.label == "지역").set_value("서울")
    next(r for r in at.radio if r.label == "경력").set_value("신입")
    next(m for m in at.multiselect if m.label == "사이트").set_value(["잡코리아"])
    next(n for n in at.number_input if n.label == "사이트당 개수").set_value(5)
    at.button(key="run-collect").click().run()

    assert not at.exception
    assert started == [
        {
            "keyword": runner.JOB_NAMES[0],
            "sources": ["jobkorea"],
            "location": "서울",
            "region_code": runner.codes.to_region_code("서울"),
            "job_code": None,
            "career": "신입",
            "count": 5,
        }
    ]  # F1, F4


def test_score_without_profile_points_to_profile_tab(app, monkeypatch):
    monkeypatch.setattr(runner, "start_score", lambda *args: pytest.fail("프로필 없이 평가하지 않음"))
    at = app([scorable(2, check="TRUE")])
    at.button(key="run-score").click().run()

    assert "프로필 탭에서" in at.error[0].value  # F8


def test_running_job_locks_buttons_and_shows_progress(app):
    runner._job = runner.Job("collect", done=2, total=8, stage="사람인 공고 본문을 가져오는 중")
    at = app([])

    assert not at.exception
    assert at.button(key="run-collect").disabled  # F12
    text = at.get("progress")[0].proto.text
    assert "수집 중" in text and "(2/8)" in text  # F5


def test_finished_job_shows_headline_todo_problems_and_folded_details(app):
    summary = runner.reports.Summary(
        "새 공고 <b>17</b>건을 저장했습니다.",
        todo=["본문 없는 공고 2건: 카드 '자세히'에서 이미지를 넣어 주세요."],
        problems=["잡코리아 수집이 멈췄습니다: 429"],
        details=["사람인 가져옴 20 / 새로 저장 14 / 건너뜀 6 / 실패 0"],
    )
    runner._job = runner.Job("collect", result=summary, finished=True)
    at = app([])

    assert at.success[0].value.startswith("새 공고 &lt;b&gt;17&lt;/b&gt;건을 저장했습니다.")  # 한 줄, escape (F24)
    assert "수집 결과" in at.success[0].value and "가져옴" not in at.success[0].value  # 로그는 기본으로 안 보임
    assert "본문 없는 공고 2건" in at.warning[0].value  # 할 일 (F25)
    assert "--inbox" not in at.warning[0].value
    assert "수집이 멈췄습니다" in at.error[0].value  # 문제
    details = next(e for e in at.expander if e.label == "자세히" and "가져옴" in e.children[0].value)
    assert "사람인 가져옴 20" in details.children[0].value


def test_finished_job_without_todo_or_problems_shows_only_headline(app):
    runner._job = runner.Job("score", result=runner.reports.Summary("공고 3건을 평가했습니다."), finished=True)
    at = app([])

    assert "공고 3건을 평가했습니다." in at.success[0].value
    assert not at.warning and not at.error


def test_failed_job_shows_error(app):
    runner._job = runner.Job("score", error="시트를 읽지 못했습니다", finished=True)
    at = app([])

    assert "평가 결과" in at.error[0].value and "시트를 읽지 못했습니다" in at.error[0].value  # F13


def test_inbox_without_ocr_shows_install_hint(app, monkeypatch):
    monkeypatch.setattr(runner, "inbox_count", lambda: 2)
    monkeypatch.setattr(ocr, "available", lambda: False)
    at = app([])

    assert any("이미지 2장" in m.value for m in at.markdown)  # F10
    assert ocr.INSTALL_HINT in at.info[0].value  # F11
    with pytest.raises(KeyError):
        at.button(key="run-inbox")


def test_inbox_button_when_ocr_is_ready(app, monkeypatch):
    started = []
    monkeypatch.setattr(runner, "inbox_count", lambda: 1)
    monkeypatch.setattr(ocr, "available", lambda: True)
    monkeypatch.setattr(runner, "start_inbox", lambda: started.append(True))
    at = app([])
    at.button(key="run-inbox").click().run()

    assert started == [True]


# ---- v0.5.2 이력서로 채우기 ----


def test_resume_fill_values_become_defaults_and_are_saved(app, tmp_path):
    values = profile_form.to_form(None)
    values[("skills", "main")] = ["Python", "LangGraph"]
    values[("direction", "jobs")] = ["백엔드 개발"]
    values[("experience", "years")] = 3
    at = app([])
    at.session_state["profile_fill"] = {"values": values, "filled": ["주력 기술", "경력 연수", "희망 직무"]}
    at.run()

    assert not at.exception
    main_skills = next(m for m in at.multiselect if m.label.startswith("주력 기술"))
    assert main_skills.value == ["Python", "LangGraph"]  # 입력란에만 채움 (F18)
    assert not (tmp_path / "profile.yaml").exists()
    filled = next(m.value for m in at.markdown if "이력서에서 채움" in m.value)
    assert 'jv-badge jv-verdict">경력 연수<' in filled and "주력 기술" in filled  # F20
    assert "LLM이 계산한 값" in at.warning[0].value
    at.button(key="profile-save").click().run()

    saved = yaml.safe_load((tmp_path / "profile.yaml").read_text(encoding="utf-8"))
    assert saved["skills"]["main"] == ["Python", "LangGraph"] and saved["experience"]["years"] == 3
    assert "profile_fill" not in at.session_state  # 저장하면 채운 값을 버림


def test_resume_fill_can_be_discarded(app, tmp_path):
    values = profile_form.to_form(None)
    values[("skills", "main")] = ["Python"]
    at = app([])
    at.session_state["profile_fill"] = {"values": values, "filled": ["주력 기술"]}
    at.run()
    at.button(key="resume-discard").click().run()

    assert next(m for m in at.multiselect if m.label.startswith("주력 기술")).value == []
    assert not (tmp_path / "profile.yaml").exists()


def test_resume_section_notes_llm_transfer_and_disables_button_without_files(app):
    at = app([])

    assert any("LLM 제공자" in c.value for c in at.caption)  # N3
    assert at.button(key="resume-fill").disabled
    assert next(t for t in at.toggle if t.label == "이미 적은 칸도 바꾸기").value is False  # F19 기본


# ---- v0.5.2 보완: 평가 전 카드, 입력 필요, 기술 칸 ----


def test_unscored_card_shows_collected_info_and_body_preview(app, tmp_path, monkeypatch):
    monkeypatch.setattr(postings, "DIR", tmp_path / "postings")
    postings.save("saramin", "2", postings.compose("자격요건 Python 3년", []))
    at = app([make_row(2, location="서울", experience="신입", keywords="Python"), make_row(3, body="본문 미확보")])

    assert not at.exception
    assert any("아직 평가 전입니다" in i.value for i in at.info)  # v0.5.2 F31
    info = next(m.value for m in at.markdown if "지역" in m.value and "jv-badge" not in m.value)
    assert "서울" in info and "Python" in info
    assert any(t.value == "자격요건 Python 3년" for t in at.text)  # 원문 앞부분
    assert any("본문이 없습니다" in w.value for w in at.warning)  # 본문 없는 카드는 이미지 넣기 안내


def test_resume_fill_shows_input_needed_badges(app):
    values = profile_form.to_form(None)
    values[("skills", "main")] = ["Python"]
    at = app([])
    at.session_state["profile_fill"] = {
        "values": values,
        "filled": ["주력 기술"],
        "missing": ["희망 직무", "희망 지역"],
    }
    at.run()

    needed = next(m.value for m in at.markdown if "이력서에 없어 비워 둠" in m.value)
    assert 'jv-mid">입력 필요 · 희망 직무<' in needed and "입력 필요 · 희망 지역" in needed  # F35


def skill(at, name):
    return next(m for m in at.multiselect if m.label.startswith(name))


def test_skill_in_main_cannot_be_picked_in_can_use(app, tmp_path):
    text = (
        "skills: {main: [Python], can_use: [Git], tried: [Docker]}\n"
        "experience: {years: 1}\ndirection: {jobs: [백엔드 개발]}\n"
    )
    (tmp_path / "profile.yaml").write_text(text, encoding="utf-8")
    at = app([])

    assert "써 본 적 있음" not in [m.label for m in at.multiselect]  # 칸 하나로 (v0.5.2 F36)
    assert skill(at, "다룰 수 있음").value == ["Git", "Docker"]  # 예전 tried도 보임
    assert "Python" not in skill(at, "다룰 수 있음").options  # 주력에 고른 것은 보기에서 빠짐 (F37)

    skill(at, "다룰 수 있음").select("Java").run()
    skill(at, "주력 기술").select("Git").run()  # 다룰 수 있음에 있던 것을 주력으로

    assert skill(at, "다룰 수 있음").value == ["Docker", "Java"]  # 겹친 것만 빠지고 고른 값은 남음
    assert "Git" not in skill(at, "다룰 수 있음").options
    at.button(key="profile-save").click().run()
    saved = yaml.safe_load((tmp_path / "profile.yaml").read_text(encoding="utf-8"))
    assert saved["skills"] == {"main": ["Python", "Git"], "can_use": ["Docker", "Java"], "certificates": []}

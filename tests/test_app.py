"""Streamlit 화면을 가짜 시트로 띄워 본다. 실제 시트·브라우저 없음 (v0.5 N5)."""

from datetime import date, timedelta
from pathlib import Path

import pytest
import streamlit as st
import yaml
from streamlit.testing.v1 import AppTest

from agent import db, ocr, postings, profile_form, resume, runner, sheets

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
    # 키가 있는 사람 기준. 키 없는 화면은 no_key로 본다 (키가 없으면 키 창이 먼저 뜬다, v0.6.1 F17)
    monkeypatch.setenv("LLM_MODEL", "google_genai:gemini-flash-lite-latest")
    monkeypatch.setenv("GOOGLE_API_KEY", "AIzaSyFAKE-fixture-0000")

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
    assert len(at.get("dialog")) == 1  # 처음 연 화면은 사용법 창 (v0.5.4 F9)
    assert [(m.label, m.value) for m in at.metric] == [
        ("✓ 전체 공고", "3"),  # 지금 보고 있는 칸 (v0.6.1 F15)
        ("평가 완료", "2"),
        ("추천 이상", "2"),
        ("이미지 필요", "1"),
    ]  # 필터와 상관없이 전체 (F2)
    heads = [m.value for m in at.markdown if m.value.startswith("**회사")]  # 사용법 창 글 빼고
    assert len(heads) == 3
    assert heads[0].startswith("**회사2 · 백엔드**") and "신뢰 높음" in heads[0]
    assert "jv-low" in heads[1]  # 신뢰 낮음 배지 색 (F5)
    assert "평가 전" in heads[2]  # 점수 순, 평가 전은 뒤
    assert len(at.get("popover")) == 3  # 자세히 (F4, v0.5.4 F5)

    at.selectbox(key="view").set_value("평가된 공고").run()  # 평가된 공고만 보기 (F32, v0.7.2 F3)
    assert sum("회사" in m.value for m in at.markdown) == 2


def test_filters_start_empty_meaning_all(app):
    rows = [make_row(n, score="70", experience=e) for n, e in ((2, "신입"), (3, "경력 3년↑"), (4, "경력무관"))]
    at = app(rows)

    source, career = (next(m for m in at.multiselect if m.label == name) for name in ("출처", "경력"))
    assert source.value == [] and career.value == []  # 처음엔 아무것도 안 고름 (v0.5.2 F29)
    assert career.options == ["신입", "경력", "무관"]  # 묶음 (F30)
    assert sum(m.value.startswith("**회사") for m in at.markdown) == 3  # 비어 있어도 전체가 보임
    career.set_value(["경력"]).run()
    assert sum(m.value.startswith("**회사") for m in at.markdown) == 1


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
    assert at.button(key="run-score").label == "🧮 체크한 공고 평가 (1건)"  # 체크한 공고 (F7)
    assert at.button(key="run-score-all").label == "평가 전 전부 평가 (2건)"  # --score all (F7)
    assert not [r for r in at.radio if r.label == "대상"]  # 수집 옆 평가 카드 없음 (v0.5.2 F38)
    assert at.text_input(key="collect-keyword").label == "키워드 *"  # Enter 없이 남는 글자 칸 (v0.7.1 F1)
    assert at.text_input(key="collect-keyword").placeholder == "예: 백엔드 신입"
    assert any("수집 카드에 키워드를 넣고" in m.value for m in at.markdown)  # 사용법 창 (F15, v0.5.4 F9)


def test_score_bar_is_one_line_without_targets(app):
    at = app([scorable(2, score="70")])  # 체크한 공고 0건, 평가 전 0건

    assert not at.exception
    keys = [b.key for b in at.button]
    assert "run-score" not in keys and "run-score-all" not in keys  # 누를 수 없는 버튼 대신 (v0.6.2 F17)
    assert any("평가할 공고가 없습니다" in m.value for m in at.markdown)


def test_score_button_is_disabled_when_only_one_kind_has_targets(app):
    at = app([scorable(2, score="70"), scorable(3)])  # 체크 0건, 평가 전 1건

    assert at.button(key="run-score").disabled and not at.button(key="run-score-all").disabled
    assert not any("평가할 공고가 없습니다" in m.value for m in at.markdown)


def test_collect_without_keyword_shows_error_and_does_not_start(app, monkeypatch):
    monkeypatch.setattr(runner, "start_collect", lambda state: pytest.fail("키워드 없이 실행하지 않음"))
    at = app([])
    at.button(key="run-collect").click().run()

    assert "키워드를 입력해 주세요" in at.error[0].value


def test_collect_button_starts_collect_with_inputs(app, monkeypatch):
    started = []
    monkeypatch.setattr(runner, "start_collect", lambda state: started.append(state))
    at = app([])
    at.text_input(key="collect-keyword").input(runner.JOB_NAMES[0])
    next(m for m in at.multiselect if m.label == "지역").set_value(["서울", "경기"])
    next(r for r in at.radio if r.label == "경력").set_value("신입")
    next(m for m in at.multiselect if m.label == "사이트").set_value(["잡코리아"])
    next(n for n in at.number_input if n.label == "사이트당 개수").set_value(5)
    at.button(key="run-collect").click().run()

    assert not at.exception
    assert started == [
        {
            "keyword": runner.JOB_NAMES[0],
            "sources": ["jobkorea"],
            "locations": ["서울", "경기"],
            "region_codes": ["101000", "102000"],
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


def test_finished_job_shows_problems_and_folded_details(app):
    summary = runner.reports.Summary(
        "새 공고 <b>17</b>건을 저장했습니다.",
        todo=["본문 없는 공고 2건: 카드 '자세히'에서 이미지를 넣어 주세요."],
        problems=["잡코리아 수집이 <b>멈췄습니다</b>: 429"],
        details=["사람인 가져옴 20 / 새로 저장 14 / 건너뜀 6 / 실패 0"],
    )
    runner._job = runner.Job("collect", result=summary, finished=True)
    at = app([])

    assert "새 공고 <b>17</b>건을 저장했습니다." in at.toast[0].value  # 결과 한 줄은 잠깐 뜨는 알림 (v0.6.1 F5)
    assert "본문 없는 공고 2건" in at.toast[0].value  # 할 일도 알림에
    assert not at.success and not at.warning  # 화면에 남는 결과 칸 없음
    assert "&lt;b&gt;멈췄습니다&lt;/b&gt;" in at.error[0].value  # 문제는 남김, escape
    details = next(e for e in at.expander if e.label == "자세히" and "가져옴" in e.children[0].value)
    assert "사람인 가져옴 20" in details.children[0].value  # 문제가 있을 때만 자세히


def test_finished_job_without_problems_shows_only_toast_once(app):
    summary = runner.reports.Summary(
        "새 공고 18건을 저장했습니다.",
        todo=["본문 없는 공고 1건: 카드 '자세히'에서 공고 이미지를 넣으면 더 정확하게 평가됩니다."],
        details=["사람인 가져옴 20 / 새로 저장 18 / 건너뜀 2 / 실패 0"],
    )
    runner._job = runner.Job("collect", result=summary, finished=True, started="03:11:45")
    at = app([])

    assert "새 공고 18건을 저장했습니다." in at.toast[0].value  # v0.6.1 F5
    assert not at.success and not at.warning and not at.error
    assert not any("가져옴" in e.children[0].value for e in at.expander if e.label == "자세히")  # 자세히 없음
    at.run()
    assert not at.toast  # 다시 그려도 알림은 한 번만


def test_failed_job_shows_error(app):
    runner._job = runner.Job("score", error="시트를 읽지 못했습니다", finished=True)
    at = app([])

    assert "평가 결과" in at.error[0].value and "시트를 읽지 못했습니다" in at.error[0].value  # F13


def test_upload_without_ocr_shows_install_hint_only(app, monkeypatch):
    monkeypatch.setattr(ocr, "available", lambda: False)
    at = app([scorable(2, body="본문 미확보")])

    assert any(ocr.INSTALL_HINT in i.value for i in at.info)  # v0.5.2 F11
    assert not [u for u in at.get("file_uploader") if u.key == "upload-2"]
    assert not [b for b in at.button if b.key == "save-2"]
    assert not any("받은함" in m.value for m in at.markdown)  # 받은함 카드·단어 없음 (v0.7.4 F6)


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

    uploader = at.get("file_uploader")[0]
    assert "LLM 제공자" in uploader.proto.help  # N3, 도움말로 옮김 (v0.6.1 F10)
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


# ---- v0.5.2 평가 줄과 카드 체크 ----


def test_card_check_writes_sheet_and_updates_target_count(app, monkeypatch):
    written = []
    monkeypatch.setattr(sheets, "set_check", lambda row, checked: written.append((row, checked)))
    at = app([scorable(2), scorable(3, check="TRUE")])
    assert [c.value for c in at.checkbox if c.key.startswith("check-")] == [False, True]  # 시트 체크 그대로

    at.checkbox(key="check-2").check().run()

    assert written == [(2, True)]  # 시트 "평가" 칸에 바로 씀 (F39)
    assert at.button(key="run-score").label == "🧮 체크한 공고 평가 (2건)"  # 시트를 다시 읽지 않고 맞춤
    at.checkbox(key="check-3").uncheck().run()
    assert written[-1] == (3, False)
    assert at.button(key="run-score").label == "🧮 체크한 공고 평가 (1건)"


def test_card_check_failure_shows_error_and_keeps_sheet_value(app, monkeypatch):
    def broken(row, checked):
        raise FileNotFoundError("C:/secret/service_account.json")

    monkeypatch.setattr(sheets, "set_check", broken)
    at = app([scorable(2)])

    at.checkbox(key="check-2").check().run()

    assert not at.exception
    assert "체크를 시트에 쓰지 못했습니다" in at.error[0].value and "secret" not in at.error[0].value
    assert at.checkbox(key="check-2").value is False  # 되돌림
    assert at.button(key="run-score").label == "🧮 체크한 공고 평가 (0건)"


@pytest.mark.parametrize(("key", "mode"), [("run-score", "checked"), ("run-score-all", "all")])
def test_score_bar_buttons_start_score(app, monkeypatch, tmp_path, key, mode):
    started = []
    monkeypatch.setattr(runner, "start_score", lambda mode, profile: started.append(mode))
    text = "skills: {main: [Python]}\nexperience: {years: 0}\ndirection: {jobs: [백엔드 개발]}\n"
    (tmp_path / "profile.yaml").write_text(text, encoding="utf-8")
    at = app([scorable(2, check="TRUE"), scorable(3)])

    at.button(key=key).click().run()

    assert started == [mode]  # F38


def test_score_bar_sits_below_filters_in_sidebar(app):
    at = app([scorable(2), make_row(3, score="70", verdict="추천", trust="높음", body="글자")])

    texts = [m.value for m in at.sidebar.markdown]
    bar = next(i for i, v in enumerate(texts) if v.startswith("**평가**"))
    filters = next(i for i, v in enumerate(texts) if v.startswith("#### 필터"))
    assert filters < bar  # 사이드바 필터 아래 (v0.7.1 F4, v0.7.2 F1)
    assert texts[bar] == "**평가**"  # 안내 글은 버튼 도움말로 (v0.7.2 F2)
    assert at.sidebar.button(key="run-score").help == "카드의 평가 칸을 체크하고 누릅니다"
    assert not any(v.startswith("**평가**") for v in (m.value for m in at.main.markdown))
    assert at.sidebar.button(key="run-score-all").label == "평가 전 전부 평가 (1건)"


# ---- v0.5.2 정렬·페이지·TOP 5·소개 문장 ----


def names(at) -> list[str]:
    return [m.value.split("**")[1].split(" · ")[0] for m in at.markdown if m.value.startswith("**회사")]


def test_sort_select_reorders_cards(app):
    at = app([scorable(2, score="60"), scorable(3, score="90"), scorable(4)])

    assert names(at) == ["회사3", "회사2", "회사4"]
    next(s for s in at.selectbox if s.label == "정렬").set_value("점수 낮은 순").run()

    assert names(at) == ["회사2", "회사3", "회사4"]  # 평가 전은 아래 (F40)


def test_pages_of_ten_and_filter_change_goes_back_to_first_page(app):
    rows = [scorable(n, score=str(100 - n)) for n in range(2, 25)]  # 23건
    at = app(rows)

    assert len(names(at)) == 10 and names(at)[0] == "회사2"  # F41
    assert any("1–10번째" in c.value for c in at.caption)
    assert at.button(key="page-back").disabled
    at.button(key="page-forward").click().run()
    assert names(at)[0] == "회사12"
    at.button(key="page-forward").click().run()
    assert len(names(at)) == 3 and at.button(key="page-forward").disabled

    next(s for s in at.selectbox if s.label == "정렬").set_value("점수 낮은 순").run()
    assert names(at)[0] == "회사24"  # 정렬을 바꾸면 1쪽


def test_no_pager_for_ten_or_fewer(app):
    at = app([scorable(n, score="70") for n in range(2, 12)])

    assert len(names(at)) == 10
    assert not [b for b in at.button if b.key in ("page-back", "page-forward")]


def test_hero_tagline(app):
    at = app([])

    hero = next(m.value for m in at.markdown if "jv-hero" in m.value and "<h1>" in m.value)
    assert "<p>채용공고를 모아 나와 비교!</p>" in hero and "AI 취업 비서" not in hero  # v0.7.2 F5, F6


# ---- v0.5.2 관심 없는 공고 빼기 ----


def test_hide_card_moves_it_to_hidden_view_and_back(app, monkeypatch):
    written = []
    monkeypatch.setattr(sheets, "set_hidden", lambda row, hidden: written.append((row, hidden)))
    at = app([scorable(2, score="80"), scorable(3)])
    assert names(at) == ["회사2", "회사3"]
    assert at.button(key="run-score-all").label == "평가 전 전부 평가 (1건)"

    at.button(key="hide-3").click().run()

    assert written == [(3, True)]  # 시트 "관심없음" 칸에 씀 (F44)
    assert names(at) == ["회사2"]
    assert any("평가할 공고가 없습니다" in m.value for m in at.markdown)  # 평가 대상에서도 빠짐 (v0.6.2 F17)
    at.selectbox(key="view").set_value("관심 없음").run()
    assert names(at) == ["회사3"] and at.button(key="hide-3").label == "되돌리기"

    at.button(key="hide-3").click().run()
    assert written[-1] == (3, False) and names(at) == []
    at.selectbox(key="view").set_value("전체").run()
    assert names(at) == ["회사2", "회사3"]


def test_hide_failure_keeps_card_and_shows_error(app, monkeypatch):
    def broken(row, hidden):
        raise KeyError("GOOGLE_SHEET_ID")

    monkeypatch.setattr(sheets, "set_hidden", broken)
    at = app([scorable(2)])

    at.button(key="hide-2").click().run()

    assert not at.exception
    assert names(at) == ["회사2"]
    assert any("관심 없음을 시트에 쓰지 못했습니다" in e.value for e in at.error)


# ---- v0.5.3 자세히 개편·마감·NEW·검색·지원함·다크 모드 ----


def scored(number: int, **changes) -> dict:
    values = {
        "score": "75", "verdict": "추천", "skills": "85", "experience_score": "60", "culture": "-",
        "career": "30", "strengths": "Python 경험, 신입 지원 가능", "gaps": "Kubernetes 없음",
        "requirements": "백엔드 API 개발, 사내 서비스 운영", "duties": "", "preferred": "AWS 경험",
        "stack": "Python, Django, Kubernetes",
    }  # fmt: skip
    return scorable(number, **(values | changes))


def test_scored_details_show_bars_columns_bullets_chips_and_guide(app, tmp_path):
    text = "skills: {main: [python]}\nexperience: {years: 0}\ndirection: {jobs: [백엔드 개발]}\n"
    (tmp_path / "profile.yaml").write_text(text, encoding="utf-8")
    at = app([scored(2)])

    texts = [m.value for m in at.markdown]
    bars = next(v for v in texts if v.startswith("<div class='jv-bar-row'>"))
    assert bars.count("jv-bar-row") == 3 and "문화" not in bars  # 문화 "-"는 그리지 않음 (F6)
    assert "jv-high" in bars and "jv-mid" in bars and "jv-low" in bars  # 85·60·30 (F1)
    assert "**✅ 강점**\n\n- Python 경험\n- 신입 지원 가능" in texts  # 두 칸 (F2)
    assert "**⚠️ 부족한 점**\n\n- Kubernetes 없음" in texts
    assert "**요약**\n\n- 백엔드 API 개발\n- 사내 서비스 운영" in texts  # 글머리표 (F3)
    assert not any(v.startswith("**주요업무**") for v in texts)  # 빈 칸은 숨김
    chips = next(v for v in texts if v.startswith("**기술스택**"))
    assert "jv-chip jv-mine' title='내 프로필에 있는 기술'>Python<" in chips  # 대소문자 무시 (F4, v0.7.1 F7)
    assert "jv-chip'>Django<" in chips and "초록은" not in chips  # 설명 글 대신 도움말 (v0.7.1 F7)
    assert "점수 기준" in [e.label for e in at.expander]  # F5
    assert any("0–100점" in v and "가중 평균" in v for v in texts)


def test_card_head_shows_first_strength_only_when_scored(app):
    at = app([scored(2), scorable(3, strengths="남은 글자")])

    heads = [m.value for m in at.markdown if m.value.startswith("**회사")]
    assert "💪 Python 경험" in heads[0] and "신입 지원 가능" not in heads[0]  # F12
    assert "💪" not in heads[1]


def test_deadline_badges_and_closed_card_is_dimmed(app):
    today = date.today()
    soon = (today + timedelta(days=3)).isoformat()
    past = (today - timedelta(days=1)).isoformat()
    far = (today + timedelta(days=30)).isoformat()
    at = app([scored(2, deadline=soon), scored(3, deadline=past), scored(4, deadline=far)])

    heads = {v.split("**")[1].split(" · ")[0]: v for v in (m.value for m in at.markdown) if v.startswith("**회사")}
    assert 'jv-low">D-3<' in heads["회사2"]  # F7
    assert 'jv-closed">마감<' in heads["회사3"]
    assert 'jv-plain">D-30<' in heads["회사4"]  # 7일 넘으면 흰 배지 (v0.5.4 F4)
    keys = [c.key for c in at.get("flex_container") if getattr(c, "key", None)]
    assert any(k == "box-dim-card-3" for k in keys) and not any(k == "box-dim-card-2" for k in keys)

    next(s for s in at.selectbox if s.label == "정렬").set_value("마감 임박 순").run()
    assert names(at) == ["회사2", "회사4", "회사3"]  # 다가오는 마감 → 지난 마감 (F8)


def test_new_badge_uses_last_visit_and_updates_it(app, tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "last_seen.txt").write_text("2026-10-21 12:00", encoding="utf-8")
    at = app([scored(2, saved_at="2026-10-21 13:00"), scored(3, saved_at="2026-10-21 11:00")])

    heads = [m.value for m in at.markdown if m.value.startswith("**회사")]
    assert 'jv-new">NEW<' in heads[0] and "NEW" not in heads[1]  # F9
    assert (tmp_path / "data" / "last_seen.txt").read_text(encoding="utf-8") != "2026-10-21 12:00"


def test_first_visit_has_no_new_badge(app):  # 처음 열면 사용법 창도 뜬다 (v0.5.4 F9)
    at = app([scored(2, saved_at="2026-10-21 13:00")])

    assert not any("NEW" in m.value for m in at.markdown if m.value.startswith("**회사"))


def test_search_filters_by_company_and_title(app):
    at = app([scored(2), scored(3, title="데이터 엔지니어"), scored(4, company="회사카카오")])

    at.text_input(key="search").set_value("데이터").run()
    assert names(at) == ["회사3"]  # F10
    at.text_input(key="search").set_value("카카오").run()
    assert names(at) == ["회사카카오"]


def test_apply_button_marks_card_and_applied_filter(app, monkeypatch):
    written = []
    monkeypatch.setattr(sheets, "set_applied", lambda row, applied: written.append((row, applied)))
    at = app([scored(2), scored(3, score="60")])

    at.button(key="apply-3").click().run()

    assert written == [(3, True)]  # 시트 "지원" 칸 (F11)
    assert at.button(key="apply-3").label == "✓ 지원함"
    head = next(m.value for m in at.markdown if m.value.startswith("**회사3"))
    assert 'jv-high">지원함<' in head
    at.selectbox(key="view").set_value("지원한 공고").run()
    assert names(at) == ["회사3"]

    at.button(key="apply-3").click().run()
    assert written[-1] == (3, False) and names(at) == []


def test_apply_failure_shows_error_without_secret(app, monkeypatch):
    def broken(row, applied):
        raise FileNotFoundError("C:/secret/service_account.json")

    monkeypatch.setattr(sheets, "set_applied", broken)
    at = app([scored(2)])

    at.button(key="apply-2").click().run()

    assert not at.exception
    assert at.button(key="apply-2").label == "지원함"
    error = next(e.value for e in at.error if "지원함을 시트에 쓰지 못했습니다" in e.value)
    assert "secret" not in error


def test_css_follows_theme_and_guide_mentions_theme(app):
    import app as screen  # 저장소 app.py

    css = screen.css()  # 두 테마 색을 light-dark(밝은, 어두운)로 함께 넣음 (v0.6.1 F25)
    assert "--jv-paper: light-dark(#f3efe7, #17181c);" in css and "--jv-card: light-dark(#fffdf8, #212329);" in css
    assert "/*VARS*/" not in css
    assert "--jv-tile0: light-dark(#ffd23f, #5a4a1c);" in css  # v0.5.4 F11, v0.6.1 F22, F26
    assert "--jv-tile-text: light-dark(#141414, #ece8df);" in css
    at = app([])
    assert any("⋮ → Light·Dark" in m.value for m in at.markdown)


# ---- v0.5.4 사이드바 필터·요약 칸·자세히 창·이미지 안내·사용법 창 ----


def test_filters_live_in_sidebar(app):
    at = app([scored(2)])

    assert not at.sidebar.toggle  # 토글 다섯 개는 보기 칸 하나로 (v0.7.2 F3)
    assert [w.label for w in at.sidebar.text_input] == ["검색"]
    assert [w.label for w in at.sidebar.selectbox] == ["정렬", "보기"]
    assert at.selectbox(key="view").options == [
        "전체", "평가된 공고", "평가 전 공고", "추천 이상", "지원한 공고", "이미지 필요", "관심 없음",
    ]  # fmt: skip


def test_summary_text_applies_its_filter_and_marks_tile(app):
    rows = [scored(2, score="85", verdict="강력 추천"), scored(3, score="50", verdict="보통"),
            scorable(4, body="본문 미확보")]  # fmt: skip
    at = app(rows)
    assert at.button(key="tile-1").label == "점수가 있는 공고 →"
    assert "box-summary-0-on" in [c.key for c in at.get("flex_container") if getattr(c, "key", None)]

    at.button(key="tile-2").click().run()  # 추천 이상 (F12)
    assert names(at) == ["회사2"] and at.selectbox(key="view").value == "추천 이상"
    assert "box-summary-2-on" in [c.key for c in at.get("flex_container") if getattr(c, "key", None)]

    at.button(key="tile-3").click().run()  # 이미지 필요만, 앞 필터는 풀림 (F3)
    assert names(at) == ["회사4"] and at.selectbox(key="view").value == "이미지 필요"

    at.text_input(key="search").set_value("회사").run()
    at.button(key="tile-0").click().run()  # 전체 공고: 모두 풂
    assert names(at) == ["회사2", "회사3", "회사4"] and at.text_input(key="search").value == ""


def test_image_badge_and_upload_steps(app, monkeypatch):
    monkeypatch.setattr(ocr, "available", lambda: True)
    at = app([scorable(2, body="본문 미확보"), scorable(3)])

    heads = {v.split("**")[1].split(" · ")[0]: v for v in (m.value for m in at.markdown) if v.startswith("**회사")}
    assert "📷 이미지 필요" in heads["회사2"] and 'title="사이트가 본문을' in heads["회사2"]  # F7
    assert "📷 이미지 필요" not in heads["회사3"]
    assert any("③ 여기에 끌어다 놓기 → ④ 🖼 이미지로 다시 평가" in c.value for c in at.caption)  # v0.7.4 F6
    assert at.button(key="save-2").disabled  # 이미지를 넣기 전에는 누를 수 없음


def test_trust_badge_has_criteria_tooltip(app):
    at = app([scored(2, trust="높음")])

    head = next(m.value for m in at.markdown if m.value.startswith("**회사2"))
    assert "신뢰 높음" in head and "낮음: 원문 없이 제목 등만 보고 매김(종합 최대 69점)" in head  # F10


def test_pin_keeps_details_open_in_card(app):
    at = app([scored(2), scored(3)])
    assert [p.key for p in at.get("popover")] == ["more-2", "more-3"]  # 자세히는 떠오르는 창 (F5)

    at.button(key="pin-2").click().run()

    assert [p.key for p in at.get("popover")] == ["more-3"]  # F6
    assert at.button(key="unpin-2").label == "접기"
    assert any(v.startswith("<div class='jv-bar-row'>") for v in (m.value for m in at.markdown))
    at.button(key="unpin-2").click().run()
    assert [p.key for p in at.get("popover")] == ["more-2", "more-3"]


def test_guide_dialog_opens_on_first_visit_and_by_button(app, tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "last_seen.txt").write_text("2026-10-21 12:00", encoding="utf-8")
    at = app([])
    assert not at.get("dialog")  # 전에 연 적 있으면 자동으로 띄우지 않음 (F9)
    assert not any("1. **프로필**" in m.value for m in at.markdown)  # 화면에 사용법 접기 칸도 없음

    at.button(key="guide").click().run()

    assert len(at.get("dialog")) == 1 and any("1. **프로필**" in m.value for m in at.markdown)


# ---- v0.5.5 프로필 칸 비우기·전체 초기화 ----

PROFILE_TEXT = (
    "skills: {main: [Python], certificates: [SQLD]}\n"
    "experience: {years: 2, training: [SSAFY 수료]}\n"
    "direction: {jobs: [백엔드 개발], goals: 에이전트 개발}\n"
)


def text_field(at, label):
    return next(t for t in at.text_input if t.label.startswith(label))


def test_clear_one_field_empties_only_that_field_and_keeps_file(app, tmp_path):
    (tmp_path / "profile.yaml").write_text(PROFILE_TEXT, encoding="utf-8")
    at = app([])
    assert skill(at, "주력 기술").value == ["Python"]

    at.button(key="clear-skills.main").click().run()

    assert skill(at, "주력 기술").value == []  # F1
    assert skill(at, "자격증").value == ["SQLD"] and text_field(at, "하고 싶은 일").value == "에이전트 개발"
    assert (tmp_path / "profile.yaml").read_text(encoding="utf-8") == PROFILE_TEXT  # 파일은 그대로


def test_clear_again_after_typing_empties_text(app, tmp_path):
    (tmp_path / "profile.yaml").write_text(PROFILE_TEXT, encoding="utf-8")
    at = app([])
    at.button(key="clear-direction.goals").click().run()
    text_field(at, "하고 싶은 일").set_value("새로 적은 글").run()

    at.button(key="clear-direction.goals").click().run()

    assert text_field(at, "하고 싶은 일").value == ""  # 빈 칸을 다시 비워도 새로 그린다 (F1)
    assert next(s for s in at.slider if s.label.startswith("경력 연수")).value == 2


def test_clear_all_asks_first_then_empties_every_field(app, tmp_path):
    (tmp_path / "profile.yaml").write_text(PROFILE_TEXT, encoding="utf-8")
    at = app([])

    at.button(key="profile-clear-all").click().run()
    assert len(at.get("dialog")) == 1  # 바로 비우지 않고 묻는다 (F2)
    at.button(key="clear-all-no").click().run()
    assert skill(at, "주력 기술").value == ["Python"]  # 취소하면 그대로

    at.button(key="profile-clear-all").click().run()
    at.button(key="clear-all-yes").click().run()

    assert skill(at, "주력 기술").value == [] and skill(at, "자격증").value == []
    assert next(s for s in at.slider if s.label.startswith("경력 연수")).value == 0
    assert text_field(at, "하고 싶은 일").value == ""
    assert badges(at).count("✗") == 2  # 필수 칸 배지도 바뀜
    assert (tmp_path / "profile.yaml").read_text(encoding="utf-8") == PROFILE_TEXT


def test_saving_after_clear_writes_cleared_value(app, tmp_path):
    (tmp_path / "profile.yaml").write_text(PROFILE_TEXT, encoding="utf-8")
    at = app([])
    at.button(key="clear-skills.certificates").click().run()

    at.button(key="profile-save").click().run()

    saved = yaml.safe_load((tmp_path / "profile.yaml").read_text(encoding="utf-8"))
    assert not saved["skills"]["certificates"] and saved["skills"]["main"] == ["Python"]  # 저장해야 파일에 반영
    assert skill(at, "자격증").value == [] and skill(at, "주력 기술").value == ["Python"]


@pytest.fixture
def no_key(monkeypatch):
    for name in ("GOOGLE_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LLM_MODEL", "google_genai:gemini-flash-lite-latest")


def key_box(at):
    return next(t for t in at.text_input if t.label == "GOOGLE_API_KEY")


def test_key_dialog_opens_once_when_no_key_and_saves_to_data_folder(app, no_key, tmp_path):
    at = app()

    assert len(at.get("dialog")) == 1  # 키가 없으면 처음 한 번 키 창 (v0.6.1 F17)
    assert any("LLM 키를 넣어 주세요" in m.value for m in at.markdown)  # v0.6 F4
    assert at.button(key="key-open").label == "🔑 키 넣기"
    key_box(at).input("AIzaSyFAKE-app-key-5678")
    at.button[[b.label for b in at.button].index("저장")].click()
    at.run()

    saved = (tmp_path / "data" / "settings.env").read_text(encoding="utf-8")
    assert "AIzaSyFAKE-app-key-5678" in saved
    assert not any("LLM 키를 넣어 주세요" in m.value for m in at.markdown)  # 키 창이 닫히고 사용법 창이 뜸
    assert any("1. **프로필**" in m.value for m in at.markdown)
    shown = " ".join([t.value for t in at.toast] + [b.label for b in at.button])
    assert "••••5678" in shown and "AIzaSyFAKE" not in shown  # 끝 4자리만 (F5)


def test_key_dialog_rejects_bad_key_without_saving(app, no_key, tmp_path):
    at = app()
    key_box(at).input("abc def")
    at.button[[b.label for b in at.button].index("저장")].click()
    at.run()

    assert any("빈칸" in e.value for e in at.error)  # 창이 다시 떠서 이유를 보인다
    assert not (tmp_path / "data" / "settings.env").exists()


def test_key_button_shows_masked_key_and_no_dialog_when_key_exists(app, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "AIzaSyFAKE-existing-4321")

    at = app()

    assert not any("LLM 키를 넣어 주세요" in m.value for m in at.markdown)
    assert at.button(key="key-open").label == "🔑 키 ••••4321"  # v0.6.1 F17
    assert len(at.get("dialog")) == 1 and any("1. **프로필**" in m.value for m in at.markdown)  # 사용법 창

    at.button(key="key-open").click().run()
    assert any("••••4321" in m.value for m in at.markdown) and at.button(key="key-delete")


# ---- v0.6.1 화면 다듬기 ----


def test_chart_only_when_scored_postings_exist(app):
    at = app([scorable(2)])

    assert not any("종합점수 TOP" in m.value for m in at.markdown)  # 점수 없으면 칸 없음 (v0.6.1 F6)
    assert not any("점수 있는 공고가 없습니다" in c.value for c in at.caption)


def test_chart_shows_with_scored_posting(app):
    at = app([scorable(2), make_row(3, score="70", verdict="추천", trust="높음", body="글자")])

    assert any(m.value == "**종합점수 TOP 5**" for m in at.markdown)  # v0.6.1 F6


def test_collect_card_has_no_site_interval_note(app):
    at = app([])

    assert any(m.value.startswith("**수집**") for m in at.markdown)
    assert not any("요청 간격" in m.value for m in at.markdown)  # v0.6.1 F3


def test_key_is_a_top_button_not_a_card(app, no_key):
    at = app()

    assert not [c for c in at.get("flex_container") if getattr(c, "key", None) == "key-card"]  # v0.6.1 F17
    caption = next(c.value for c in at.caption if "aistudio.google.com/apikey" in c.value)
    assert "끝 4자리" in caption
    assert "COLLAPSED" in str(key_box(at).label_visibility)  # 입력란과 저장 버튼 한 줄


def test_title_is_lime_with_dark_edge_and_large():
    import app as screen

    assert "--jv-title: light-dark(#c8f53a, #c8f53a);" in screen.css()  # 라임 제목 (v0.6.1 F26, F1을 바꿈)
    assert "-webkit-text-stroke: 2px var(--jv-title-edge)" in screen.CSS  # 검정 테두리로 두 테마 모두 읽힘
    assert "white-space: nowrap; font-size: clamp(3.6rem, 6vw, 5.2rem);" in screen.CSS  # 한 줄, 더 크게 (v0.7.2 F6)
    assert "font-weight: 900; color: var(--jv-title)" in screen.CSS  # F19
    assert "--jv-highlight) 58%" not in screen.CSS  # 제목 뒤 형광 줄 없음 (F19)


def test_css_wraps_many_keywords_and_keeps_card_text():
    import app as screen

    assert "flex-wrap: wrap" in screen.CSS and "[data-tag]" in screen.CSS  # v0.6.1 F7
    assert 'st-key-check-"] label' in screen.CSS and "white-space: nowrap" in screen.CSS  # F4
    assert 'st-key-box-profile-"]) { flex: 1 1 auto; }' in screen.CSS  # F9


def test_key_card_deletes_key_from_this_pc(app, no_key, tmp_path):
    at = app()
    key_box(at).input("AIzaSyFAKE-app-key-7777")
    at.button[[b.label for b in at.button].index("저장")].click()
    at.run()
    at.button(key="key-open").click().run()

    at.button(key="key-delete").click().run()  # v0.6.1 F14

    assert "AIzaSyFAKE" not in (tmp_path / "data" / "settings.env").read_text(encoding="utf-8")
    assert any("LLM 키를 넣어 주세요" in m.value for m in at.markdown)  # 다시 입력 칸
    assert any("Google AI Studio" in i.value for i in at.info)  # 키 자체는 Google에서 지워야 함을 안내


def test_compose_does_not_pass_key_as_environment():
    compose = (Path(__file__).parent.parent / "docker-compose.yml").read_text(encoding="utf-8")

    assert "GOOGLE_API_KEY" not in compose and "ANTHROPIC_API_KEY" not in compose  # v0.6.1 F13


# ---- v0.6.1 보완 (PC 피드백 2차) ----


def test_finished_job_rereads_rows_once_even_without_progress_bar(app, monkeypatch):
    reads = []
    at = app([scorable(2)])
    monkeypatch.setattr(sheets, "read_rows_readonly", lambda: reads.append(1) or [make_row(2, score="77")])
    runner._job = runner.Job("score", result=runner.reports.Summary("공고 1건을 평가했습니다."), finished=True)

    at.run()  # 진행 막대를 거치지 않고 끝난 작업 (v0.6.1 F16)
    assert len(reads) == 1 and any("77" in m.value for m in at.markdown)
    at.run()
    assert len(reads) == 1  # 같은 작업은 한 번만 다시 읽음


def test_resume_box_is_open_for_empty_profile_and_folded_otherwise(app, tmp_path):
    at = app([])
    box = next(e for e in at.expander if e.label == "📄 이력서·포트폴리오로 채우기")
    assert box.proto.expanded  # 프로필이 비어 있으면 펼침 (v0.6.1 F18)

    (tmp_path / "profile.yaml").write_text(PROFILE_TEXT, encoding="utf-8")
    at.run()
    box = next(e for e in at.expander if e.label == "📄 이력서·포트폴리오로 채우기")
    assert not box.proto.expanded  # 채워져 있으면 접음


def test_sidebar_filter_is_a_card_and_selected_tile_is_marked():
    import app as screen

    assert 'section[data-testid="stSidebar"] div[class*="st-key-box"] { padding: 12px 14px; }' in screen.CSS  # v0.7.2
    assert "background: var(--jv-paper); }" in screen.CSS
    assert '[class*="-on"] { border-width: 5px !important;' in screen.CSS  # 초록 대신 굵은 테두리 (F15)


# ---- v0.6.1 보완 3차: 고른 칸 색, 어두운 테마, 고정 차트 ----


def test_selected_tile_inverts_colors():
    import app as screen

    assert 'div[class*="st-key-box-summary"][class*="-on"] { background: var(--jv-sel) !important; }' in screen.CSS
    assert '[class*="-on"] * { color: var(--jv-sel-text) !important; }' in screen.CSS  # v0.6.1 F21
    assert "--jv-sel: light-dark(#141414, #ece8df);" in screen.css()
    assert "--jv-sel-text: light-dark(#fffdf8, #17181c);" in screen.css()
    # 고른 칸 면 색은 요약 칸 4색과 겹치지 않는다
    for theme in ("light", "dark"):
        palette = screen.PALETTES[theme]
        assert palette["sel"] not in {palette[f"tile{i}"] for i in range(4)}


def test_dark_theme_avoids_glare_and_badges_follow_theme():
    import app as screen

    dark = screen.PALETTES["dark"]
    assert dark["text"] != "#ffffff" and dark["paper"] != "#000000"  # 순백 글자·순흑 바탕 피함 (v0.6.1 F22)
    assert set(dark) == set(screen.PALETTES["light"])  # 두 테마가 같은 이름을 모두 채움
    assert ".jv-high { background: var(--jv-high); color: var(--jv-badge-text); }" in screen.CSS
    assert "#8ce99a" not in screen.CSS  # 배지 색도 테마를 따름
    config = (Path(screen.__file__).parent / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    for theme in ("light", "dark"):  # config.toml과 PALETTES가 같은 색 (v0.6.1 F22, F26)
        palette = screen.PALETTES[theme]
        section = config.split(f"[theme.{theme}]")[1].split("[theme.")[0]
        assert f'backgroundColor = "{palette["paper"]}"' in section
        assert f'borderColor = "{palette["ink"]}"' in section and f'textColor = "{palette["text"]}"' in section


def test_top5_chart_is_static(app):
    import app as screen

    spec = screen.chart_spec([("회사1", 80), ("회사2", 60)])
    assert "params" not in spec and "selection" not in str(spec)  # 확대·끌기 없음 (v0.6.1 F23)
    assert spec["encoding"]["y"]["sort"] == "-x"  # 높은 점수가 위 (F42)
    assert [v["종합점수"] for v in spec["data"]["values"]] == [80, 60]
    at = app([scorable(2), make_row(3, score="70", verdict="추천", trust="높음", body="글자")])
    assert not at.exception
    [chart] = at.get("vega_lite_chart")  # st.bar_chart(늘 확대·끌기 됨) 대신 명세 차트
    assert '"params"' not in chart.proto.spec and screen.ACCENT in chart.proto.spec


# ---- v0.6.1 보완 4차: 새로고침으로 프로필 되돌리기, 테마 바로 적용 ----


def test_refresh_restores_saved_profile_after_clear_all(app, tmp_path):
    (tmp_path / "profile.yaml").write_text(PROFILE_TEXT, encoding="utf-8")
    at = app([])
    at.button(key="profile-clear-all").click().run()
    at.button(key="clear-all-yes").click().run()
    assert skill(at, "주력 기술").value == []

    next(b for b in at.button if b.label == "🔄 새로고침").click().run()

    assert skill(at, "주력 기술").value == ["Python"]  # 저장된 값으로 (v0.6.1 F24)
    assert text_field(at, "하고 싶은 일").value != ""
    assert (tmp_path / "profile.yaml").read_text(encoding="utf-8") == PROFILE_TEXT


def test_refresh_drops_unsaved_typing_and_resume_fill(app, tmp_path):
    import app as screen

    (tmp_path / "profile.yaml").write_text(PROFILE_TEXT, encoding="utf-8")
    at = app([])
    saved = text_field(at, "하고 싶은 일").value
    text_field(at, "하고 싶은 일").input("저장 안 한 글").run()
    at.session_state[screen.FILL] = {"values": screen.profile_form.to_form(None), "filled": []}
    at.run()
    assert text_field(at, "하고 싶은 일").value == ""

    next(b for b in at.button if b.label == "🔄 새로고침").click().run()

    assert text_field(at, "하고 싶은 일").value == saved  # 입력·이력서 값 모두 버림 (F24)
    assert screen.FILL not in at.session_state


def test_refresh_without_profile_file_keeps_empty_form(app):
    at = app([])

    next(b for b in at.button if b.label == "🔄 새로고침").click().run()

    assert not at.exception
    assert skill(at, "주력 기술").value == []


def test_css_lets_browser_pick_theme():
    import app as screen

    css = screen.css()
    names = screen.PALETTES["light"]
    assert css.count("light-dark(") == len(names)  # 모든 색이 두 테마 값을 함께 가짐 (v0.6.1 F25)
    assert all(f"--jv-{name}: light-dark(" in css for name in names)


# ---- v0.6.1 보완 5차: 피그마 테마 ----


def test_figma_theme_background_font_and_buttons():
    import app as screen

    css = screen.css()
    assert "--jv-lime: light-dark(#c8f53a, #b6e22e);" in css  # v0.6.1 F26
    assert "radial-gradient(var(--jv-dot)" in screen.CSS  # 점 무늬 바탕
    assert "family=Black+Han+Sans" in screen.CSS  # 제목 글꼴, 없으면 기본 글꼴
    assert 'button[data-testid="stBaseButton-primary"]' in screen.CSS and "var(--jv-lime-text)" in screen.CSS
    assert "repeating-linear-gradient(135deg, var(--jv-lime)" in screen.CSS  # 자세히 창 사선 띠


def test_score_ring_fills_by_score_and_card_gets_tone(app):
    at = app([scorable(2), scored(3), make_row(4, score="35", verdict="비추천", trust="높음", body="글자")])

    texts = [m.value for m in at.markdown]
    assert any('<div class="jv-score" style="--p:35">35</div>' in t for t in texts)  # 도넛 원 채움 (F26)
    assert any('<div class="jv-score">-</div>' in t for t in texts)  # 평가 전은 빈 원
    heads = {t.split("**")[1].split(" · ")[0]: t for t in texts if t.startswith("**회사")}
    assert heads["회사2"].endswith("<span class='jv-tone-none'></span>")
    assert heads["회사4"].endswith("<span class='jv-tone-low'></span>")  # 40 아래는 코랄 띠
    assert ":has(.jv-tone-low) { border-left: 10px solid var(--jv-tile3)" in __import__("app").CSS


# ---- v0.6.1 보완 6차: 앱 칸 밖 창도 같은 테마 ----


def test_popups_follow_app_theme(app):
    import app as screen

    assert ":root { color-scheme: light dark;" in screen.CSS  # 스크립트가 못 돌면 컴퓨터 설정 (v0.6.1 F27)
    assert "getComputedStyle(app).colorScheme" in screen.SCHEME_SYNC
    assert "document.documentElement.style.colorScheme = scheme" in screen.SCHEME_SYNC
    at = app([])
    assert any("jvSchemeSync" in str(h.proto) for h in at.get("html"))  # 화면마다 넣음


def test_summary_tiles_keep_same_height():
    import app as screen

    assert ':has(> div[class*="st-key-box-summary-"]) { flex: 1 1 auto; }' in screen.CSS  # v0.6.1 F28
    assert 'div[class*="st-key-box-summary-"] { height: 100%; }' in screen.CSS


# ---- 지역 여러 개 (v0.6.1 F29) ----


def test_collect_regions_start_from_profile(app, tmp_path):
    (tmp_path / "profile.yaml").write_text(
        PROFILE_TEXT.replace("goals: 에이전트 개발", "goals: 에이전트 개발, locations: [경기, 재택·원격]"),
        encoding="utf-8",
    )
    at = app([])

    regions = next(m for m in at.multiselect if m.label == "지역")
    assert regions.value == ["경기"]  # 프로필 희망 지역. 사이트 지역에 없는 "재택·원격"은 뺌


def test_collect_regions_empty_without_profile(app):
    at = app([])

    assert next(m for m in at.multiselect if m.label == "지역").value == []  # 비우면 전체


# ---- DB 공고 초기화 (v0.6.1 F30) ----


def test_reset_hidden_in_sheet_mode(app, monkeypatch):
    monkeypatch.delenv("JOBVIS_STORAGE", raising=False)
    at = app([make_row(2)])

    assert not [b for b in at.button if b.key == "reset-open"]


def db_app(app, monkeypatch, rows):
    monkeypatch.setenv("JOBVIS_STORAGE", "db")
    monkeypatch.setattr(db, "read_rows_readonly", lambda: rows)
    return app(rows)


def test_reset_asks_with_counts_then_removes(app, monkeypatch):
    calls = []

    def fake_reset(keep):
        calls.append(keep)
        return runner.ResetResult(rows=1, files=2, kept=1)

    monkeypatch.setattr(runner, "reset_postings", fake_reset)
    at = db_app(app, monkeypatch, [make_row(2), make_row(3, applied="TRUE")])

    at.button(key="reset-open").click().run()
    assert len(at.get("dialog")) == 1 and not calls  # 바로 지우지 않고 묻는다
    assert "1건" in at.checkbox(key="reset-keep").label  # 지원한 공고 수
    assert any("**1건**" in m.value for m in at.markdown)  # 지울 공고 수 (지원한 공고 남김)
    at.button(key="reset-no").click().run()
    assert not calls  # 취소

    at.button(key="reset-open").click().run()
    at.checkbox(key="reset-keep").uncheck()
    at.button(key="reset-yes").click().run()

    assert calls == [False]
    assert any("공고 1건 지움, 지원한 공고 1건 남김" in t.value for t in at.toast)


def test_reset_error_stays_in_dialog(app, monkeypatch):
    def fail(keep):
        raise runner.RunError("수집을 실행하는 중입니다. 끝난 뒤 다시 눌러 주세요.")

    monkeypatch.setattr(runner, "reset_postings", fail)
    at = db_app(app, monkeypatch, [make_row(2)])

    at.button(key="reset-open").click().run()
    at.button(key="reset-yes").click().run()

    assert any("실행하는 중" in e.value for e in at.error)
    assert not at.toast


def test_reset_button_disabled_when_only_applied_kept(app, monkeypatch):
    monkeypatch.setattr(runner, "reset_postings", lambda keep: pytest.fail("지울 공고가 없으면 누를 수 없음"))
    at = db_app(app, monkeypatch, [make_row(2, applied="TRUE")])

    at.button(key="reset-open").click().run()

    assert at.button(key="reset-yes").disabled


# ---- v0.6.2 보완: 사용법·오류 문구·펼쳐 두기·원문 링크·평가 줄·아이콘 ----


def test_guide_is_three_basic_steps_and_extras():
    import app as screen

    lines = [line for line in screen.GUIDE.strip().splitlines() if line]
    assert [line.split(" · ")[0] for line in lines if line[0].isdigit()] == [
        "1. **프로필**", "2. **수집**", "3. **평가**",
    ]  # v0.6.2 F13  # fmt: skip
    assert "**추가**" in screen.GUIDE and "**이미지 넣기**" in screen.GUIDE and "**공고 보기**" in screen.GUIDE
    assert len(lines) <= 10  # 짧게


def test_score_without_profile_file_shows_only_what_to_do(app, monkeypatch):
    monkeypatch.setattr(runner, "start_score", lambda *args: pytest.fail("프로필 없이 평가하지 않음"))
    at = app([scorable(2, check="TRUE")])
    at.button(key="run-score").click().run()

    message = at.error[0].value
    assert message.startswith("프로필 입력이 필요합니다.")  # v0.6.2 F14
    assert "profile" not in message and "streamlit" not in message  # 경로·명령 같은 개발자 글 없음


def test_score_with_broken_profile_points_to_profile_tab(app, monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "start_score", lambda *args: pytest.fail("틀린 프로필로 평가하지 않음"))
    (tmp_path / "profile.yaml").write_text("skills: {}\nexperience: {}\ndirection: {}\n", encoding="utf-8")
    at = app([scorable(2, check="TRUE")])
    at.button(key="run-score").click().run()

    assert at.error[0].value.startswith("프로필에 고칠 칸이 있습니다.")
    assert "skills.main" not in at.error[0].value


def test_score_without_key_asks_for_key_and_opens_key_dialog(app, no_key, monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "start_score", lambda *args: pytest.fail("키 없이 평가하지 않음"))
    (tmp_path / "profile.yaml").write_text(PROFILE_TEXT, encoding="utf-8")
    at = app([scorable(2, check="TRUE")])  # 처음 한 번 뜨는 키 창
    at.button(key="run-score").click().run()

    assert not at.get("dialog")
    assert at.error[0].value.startswith("제미나이 API 키 입력이 필요합니다.")  # v0.6.2 F14
    at.button(key="key-ask-score").click().run()
    assert len(at.get("dialog")) == 1 and any("LLM 키를 넣어 주세요" in m.value for m in at.markdown)


def test_resume_fill_without_key_does_not_call_llm(app, no_key, monkeypatch):
    monkeypatch.setattr(resume, "ask", lambda text: pytest.fail("키 없이 LLM을 부르지 않음"))
    at = app([])
    uploader = next(u for u in at.get("file_uploader") if u.key == "resume-files")
    uploader.set_value(("이력서.txt", "Python 백엔드 2년".encode(), "text/plain")).run()
    at.button(key="resume-fill").click().run()

    assert [e.value for e in at.error] == [
        "제미나이 API 키 입력이 필요합니다. 위 🔑 키 넣기를 누르거나 아래 버튼을 눌러 주세요."
    ]  # pydantic 오류 글 대신 (v0.6.2 F14)
    at.button(key="key-ask-resume").click().run()
    assert len(at.get("dialog")) == 1


def test_key_label_follows_model(monkeypatch):
    from agent import settings

    monkeypatch.setenv("LLM_MODEL", "anthropic:claude-haiku-4-5")
    assert settings.key_label() == "Claude API 키"
    monkeypatch.setenv("LLM_MODEL", "google_genai:gemini-flash-lite-latest")
    assert settings.key_label() == "제미나이 API 키"


def test_card_heading_links_to_original_in_new_tab(app):
    at = app([scored(2, url="https://www.saramin.co.kr/x?a=1&b=2"), scored(3, url="javascript:alert(1)")])

    heads = [m.value for m in at.markdown if "· 백엔드**" in m.value and "jv-badge" in m.value]
    linked = next(h for h in heads if "회사2" in h)
    assert linked.startswith('<a class="jv-head" href="https://www.saramin.co.kr/x?a=1&amp;b=2" target="_blank"')
    assert 'rel="noopener noreferrer"' in linked and "**회사2 · 백엔드**" in linked  # v0.6.2 F16
    plain = next(h for h in heads if "회사3" in h)
    assert plain.startswith("**회사3 · 백엔드**") and "<a " not in plain  # http(s)만 링크


def test_pinned_details_are_a_fragment():
    import app as screen

    # 펼쳐 두기·접기는 자세히 칸만 다시 그린다. 화면 전체를 다시 그리면 맨 위로 튐 (v0.6.2 F15)
    assert screen.show_more.__qualname__ == "show_more"
    source = Path(screen.__file__).read_text(encoding="utf-8")
    assert "@st.fragment\ndef show_more(" in source


IMAGE_PROFILE = "skills: {main: [Python]}\nexperience: {years: 0}\ndirection: {jobs: [백엔드 개발]}\n"


def upload_image(app, monkeypatch, tmp_path, profile=IMAGE_PROFILE):
    monkeypatch.setattr(ocr, "available", lambda: True)
    started = []
    monkeypatch.setattr(runner, "start_image_score", lambda *args: started.append(args))
    if profile:
        (tmp_path / "profile.yaml").write_text(profile, encoding="utf-8")
    at = app([scorable(2, body="본문 미확보", source="사람인")])
    uploader = next(u for u in at.get("file_uploader") if u.key == "upload-2")
    uploader.set_value(("공고.png", b"\x89PNG fake", "image/png")).run()
    at.button(key="save-2").click().run()
    return at, started


def test_image_upload_saves_and_rescores_that_posting(app, monkeypatch, tmp_path):
    at, started = upload_image(app, monkeypatch, tmp_path)

    assert not at.exception
    assert [p.name for p in (tmp_path / "data" / "inbox").iterdir()] == ["saramin_2.png"]
    # 버튼 하나로 저장 → 읽기 → 그 공고만 다시 평가 (v0.7.4 F7, F8)
    assert [(source, job_id, profile.experience.years) for source, job_id, profile in started] == [("saramin", "2", 0)]


def test_image_upload_without_profile_saves_nothing(app, monkeypatch, tmp_path):
    at, started = upload_image(app, monkeypatch, tmp_path, profile="")

    assert any("프로필 입력이 필요합니다" in e.value for e in at.error)
    assert started == [] and not (tmp_path / "data" / "inbox").exists()


def test_image_upload_without_key_saves_nothing(app, monkeypatch, tmp_path):
    monkeypatch.delenv("GOOGLE_API_KEY")
    at, started = upload_image(app, monkeypatch, tmp_path)

    assert any("입력이 필요합니다" in e.value for e in at.error)
    assert started == [] and not (tmp_path / "data" / "inbox").exists()


def test_page_icon_file_is_in_repo_and_image():
    import app as screen

    icon = Path(screen.ICON)
    assert icon.is_file() and icon.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"  # v0.6.2 F18
    ignored = (Path(screen.__file__).parent / ".dockerignore").read_text(encoding="utf-8").split()
    assert "assets/" not in ignored and "assets" not in ignored and "*.png" not in ignored  # 이미지에 들어감


def test_app_has_no_bare_expressions_that_magic_would_draw():
    import ast

    import app as screen

    # 식만 있는 줄(예: a() if c else b())은 Streamlit magic이 화면 맨 위에 그린다.
    # 펼쳐 두기 콜백에서 None이 CSS 칸을 덮어 테마가 사라졌음 (v0.6.2 F15 보완)
    tree = ast.parse(Path(screen.__file__).read_text(encoding="utf-8"))
    bare = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and not isinstance(node.value, (ast.Call, ast.Constant))
    ]
    assert bare == []


# ---- v0.7 메일 (F1–F9) ----

MAIL_PASSWORD = "abcdefghijklmnop"


@pytest.fixture
def mail_env(monkeypatch):
    """메일 설정 환경 변수. 화면에서 저장해도 테스트가 끝나면 되돌린다."""
    from agent import settings

    for name in settings.MAIL_NAMES:
        monkeypatch.setenv(name, "")


@pytest.fixture
def sent(monkeypatch, mail_env):
    """mail.send를 가짜로 바꿔 보낸 메일을 모은다. 실제 메일 서버에 연결하지 않는다 (N3)."""
    from agent import mail

    messages = []
    monkeypatch.setattr(mail, "send", lambda message, sender, password: messages.append((message, sender, password)))
    return messages


def with_mail(monkeypatch):
    monkeypatch.setenv("JOBVIS_MAIL_FROM", "me@gmail.com")
    monkeypatch.setenv("JOBVIS_MAIL_PASSWORD", MAIL_PASSWORD)
    monkeypatch.setenv("JOBVIS_MAIL_TO", "phone@example.com")


def open_mail(at):
    at.button(key="mail-open").click().run()
    assert len(at.get("dialog")) == 1
    return at


def screen_text(at) -> str:
    parts = [m.value for m in at.markdown] + [e.value for e in at.error] + [t.value for t in at.toast]
    parts += [s.value for s in at.success] + [c.value for c in at.caption] + [b.label for b in at.button]
    return " ".join(parts) + " ".join(str(t.value) for t in at.text_input)


def test_mail_without_settings_shows_form_and_saves(app, sent, tmp_path):
    at = open_mail(app([scorable(2)]))

    assert any("앱 비밀번호" in c.value and "apppasswords" in c.value for c in at.caption)  # F8 안내
    assert not [b for b in at.button if b.key == "mail-send"]  # 설정 전에는 보내기 없음
    at.text_input(key="mail-from").input("me@gmail.com")
    at.text_input(key="mail-password").input("abcd efgh ijkl mnop")
    at.button[[b.label for b in at.button].index("저장")].click().run()

    saved = (tmp_path / "data" / "settings.env").read_text(encoding="utf-8")
    assert f"JOBVIS_MAIL_PASSWORD={MAIL_PASSWORD}" in saved and "JOBVIS_MAIL_TO=me@gmail.com" in saved
    assert any("시험 메일" in s.value for s in at.success)  # 저장한 뒤 시험 메일 안내
    assert MAIL_PASSWORD not in screen_text(at)  # 화면에 비밀번호 없음 (N2)

    at.button(key="mail-test").click().run()

    assert [(m["Subject"], s, p) for m, s, p in sent] == [("[JOBVIS] 시험 메일", "me@gmail.com", MAIL_PASSWORD)]
    assert any("시험 메일을 보냄 (me@gmail.com)" in s.value for s in at.success)


def test_mail_settings_reject_bad_address_without_saving(app, mail_env, tmp_path):
    at = open_mail(app([scorable(2)]))
    at.text_input(key="mail-from").input("me")
    at.text_input(key="mail-password").input(MAIL_PASSWORD)
    at.button[[b.label for b in at.button].index("저장")].click().run()

    assert any("주소 형식" in e.value for e in at.error)  # F9, 창이 다시 떠서 이유를 보인다
    assert not (tmp_path / "data" / "settings.env").exists()


def test_mail_picks_from_shown_cards_and_sends(app, sent, monkeypatch):
    with_mail(monkeypatch)
    at = open_mail(app([scorable(2, score="80", verdict="추천"), scorable(3), scorable(4, hidden="TRUE")]))

    labels = [c.label for c in at.checkbox if c.key.startswith("mail-pick-")]
    assert labels == ["회사2 · 백엔드 · 80점", "회사3 · 백엔드 · 평가 전"]  # 관심 없음은 빠진 지금 목록 (F2)
    assert not any(c.value for c in at.checkbox if c.key.startswith("mail-pick-"))  # 처음엔 아무것도 안 고름
    assert at.button(key="mail-send").disabled  # 0건 (F3)
    assert any("phone@example.com" in m.value for m in at.markdown)

    # 창 안 체크는 실제로는 창만 다시 그린다. AppTest는 전체를 다시 그려 창이 닫혀서 고른 상태를 넣고 다시 연다
    at.session_state["mail-pick-3"] = True
    open_mail(at)
    assert not at.button(key="mail-send").disabled and at.button(key="mail-send").label == "✉ 1건 보내기"
    at.button(key="mail-send").click().run()

    assert len(sent) == 1
    message, sender, password = sent[0]
    assert message["To"] == "phone@example.com" and sender == "me@gmail.com" and password == MAIL_PASSWORD
    assert message["Subject"].startswith("[JOBVIS] 공고 1건")
    assert "회사3" in message.get_body(("plain",)).get_content()
    assert "회사2" not in message.get_body(("plain",)).get_content()
    assert any("1건을 보냄 (phone@example.com)" in t.value for t in at.toast)  # F4
    assert not at.get("dialog")


def test_mail_pick_all_and_more_than_max_cannot_send(app, sent, monkeypatch):
    from agent import mail

    with_mail(monkeypatch)
    at = open_mail(app([scorable(n) for n in range(2, 2 + mail.MAX + 1)]))

    at.button(key="mail-all").click().run()
    open_mail(at)  # 창 안 버튼은 창만 다시 그린다. 시험에서는 창을 다시 연다

    assert all(c.value for c in at.checkbox if c.key.startswith("mail-pick-"))
    assert any(f"{mail.MAX}건까지" in w.value for w in at.warning)  # F3
    assert at.button(key="mail-send").disabled and not sent


def test_mail_pick_all_callback_checks_every_shown_card(app, sent, monkeypatch):
    with_mail(monkeypatch)
    at = open_mail(app([scorable(2), scorable(3)]))

    at.button(key="mail-all").click().run()

    assert at.session_state["mail-pick-2"] and at.session_state["mail-pick-3"]


def test_mail_failure_stays_in_dialog_without_secret(app, mail_env, monkeypatch):
    from agent import mail

    def fail(message, sender, password):
        raise mail.MailError(mail.AUTH_ERROR)

    monkeypatch.setattr(mail, "send", fail)
    with_mail(monkeypatch)
    at = app([scorable(2)])
    at.session_state["mail-pick-2"] = True
    open_mail(at)
    at.button(key="mail-send").click().run()

    assert any("앱 비밀번호가 맞지 않습니다" in e.value for e in at.error)  # F9
    assert len(at.get("dialog")) == 1 and not at.toast
    assert MAIL_PASSWORD not in screen_text(at)


def test_mail_dialog_without_postings_says_so(app, sent, monkeypatch):
    with_mail(monkeypatch)
    at = open_mail(app([]))

    assert any("보낼 공고가 없습니다" in i.value for i in at.info)


def test_mail_settings_can_be_deleted(app, mail_env, tmp_path):
    at = open_mail(app([scorable(2)]))
    at.text_input(key="mail-from").input("me@gmail.com")
    at.text_input(key="mail-password").input(MAIL_PASSWORD)
    at.button[[b.label for b in at.button].index("저장")].click().run()
    at.button(key="mail-delete").click().run()

    assert "JOBVIS_MAIL" not in (tmp_path / "data" / "settings.env").read_text(encoding="utf-8")
    assert any("지웠습니다" in s.value for s in at.success)


# ---- v0.7 모아 보기 (F10–F13) ----


def test_stats_dialog_ranks_stack_and_gaps_of_shown_cards(app, tmp_path):
    text = "skills: {main: [Gradle]}\nexperience: {years: 0}\ndirection: {jobs: [백엔드 개발]}\n"
    (tmp_path / "profile.yaml").write_text(text, encoding="utf-8")
    rows = [  # Gradle은 같은 말 사전에 없는 이름 (사전 이름은 대표 이름으로 보임, v0.7.3 F2)
        scorable(2, score="40", verdict="보통", stack="Gradle, AWS", gaps="AWS 경험"),
        scorable(3, score="80", verdict="추천", stack="gradle, Docker", gaps="AWS 경험, Kafka"),
        scorable(4, stack="<b>Go</b>"),
    ]
    at = app(rows)
    at.button(key="stats-open").click().run()

    assert len(at.get("dialog")) == 1
    html = " ".join(m.value for m in at.markdown)
    assert "공고 **3건** 기준 · 필터 없음" in html  # F10
    # 이름은 목록(점수 높은 순)에서 처음 나온 모양. 대소문자 달라도 내 기술은 초록 (F11)
    assert "<span class='jv-chip jv-mine' title='gradle · 내 프로필에 있는 기술'>gradle</span>" in html
    assert "<span class='jv-rank-num'>2건</span>" in html
    assert "jv-chip jv-lack' title='AWS'" in html
    assert "&lt;b&gt;Go&lt;/b&gt;" in html and "<b>Go</b>" not in html  # 시트 글자 escape
    assert html.index("AWS 경험") < html.index("Kafka")  # 가중치 순 (F12)
    assert any("평가 전 공고 1건은 뺌" in c.value for c in at.caption)


def test_stats_dialog_shows_filters_and_empty_message(app):
    at = app([scorable(2)])
    at.text_input(key="search").input("없는회사").run()
    at.button(key="stats-open").click().run()

    assert any("공고 **0건** 기준 · 필터 검색 &#x27;없는회사&#x27;" in m.value for m in at.markdown)
    assert sum("모을 공고가 없습니다" in c.value for c in at.caption) == 2  # F13


# ---- v0.7.1 화면 보완 (F1–F12) ----


def test_keyword_text_box_stays_without_suggestion_buttons(app, monkeypatch):
    started = []
    monkeypatch.setattr(runner, "start_collect", lambda state: started.append(state))
    at = app([])
    at.text_input(key="collect-keyword").input("데이터 엔지니어").run()  # Enter 없이 다른 곳을 눌러도 남음 (v0.7.1 F1)

    assert at.text_input(key="collect-keyword").value == "데이터 엔지니어"
    assert "keyword-pick" not in [w.key for w in at.get("button_group")]  # 추천 키워드 버튼 없음 (v0.7.2 F4)
    at.button(key="run-collect").click().run()
    assert started[0]["keyword"] == "데이터 엔지니어"


def test_top_buttons_have_clear_names_and_dialog_titles(app):
    at = app([scorable(2)])

    assert at.button(key="mail-open").label == "✉ 공고 메일 보내기"  # F2
    assert at.button(key="stats-open").label == "📊 기술 모아보기"
    at.button(key="stats-open").click().run()
    assert at.get("dialog")[0].proto.dialog.title == "📊 기술 모아보기"


def test_mail_dialog_title_matches_button(app, mail_env):
    at = app([scorable(2)])
    at.button(key="mail-open").click().run()

    assert at.get("dialog")[0].proto.dialog.title == "✉ 공고 메일 보내기"  # F2


def test_stats_dialog_has_summary_and_two_tabs(app, tmp_path):
    text = "skills: {main: [Python]}\nexperience: {years: 0}\ndirection: {jobs: [백엔드 개발]}\n"
    (tmp_path / "profile.yaml").write_text(text, encoding="utf-8")
    at = app([scorable(2, score="70", stack="Python, AWS, Docker", gaps="AWS 경험")])
    at.button(key="stats-open").click().run()

    html = " ".join(m.value for m in at.markdown)
    assert "많이 찾는 기술 3개 중 <span class='jv-chip jv-mine'" in html and "**1개**" in html  # F3
    assert [t.label for t in at.tabs][-2:] == ["많이 찾는 기술 3", "내가 부족한 것 1"]  # 개수 붙임 (v0.7.4 보완)


def test_stats_dialog_lists_every_skill_in_scroll_box(app):
    many = ", ".join(f"Tool{n}" for n in range(12))
    at = app([scorable(2, score="70", stack=f"Python, {many}", gaps="AWS 경험")])
    at.button(key="stats-open").click().run()

    html = " ".join(m.value for m in at.markdown)
    assert "많이 찾는 기술 13개 중" in html  # 10개로 자르지 않음 (v0.7.3 F1)
    # 공고 1건이라 모두 1건짜리: 순위 줄 없이 칩 묶음으로 (v0.7.4 F1)
    assert html.count("class='jv-rank-row'") == 0
    assert "1건씩 나온 것 13개" in html and "1건씩 나온 것 1개" in html
    assert all(f">Tool{n}</span>" in html for n in range(12))


def test_stats_dialog_ranks_only_repeated_skills_and_chips_the_rest(app, tmp_path):
    text = "skills: {main: [Go]}\nexperience: {years: 0}\ndirection: {jobs: [백엔드 개발]}\n"
    (tmp_path / "profile.yaml").write_text(text, encoding="utf-8")
    rows = [
        scorable(2, score="50", stack="Python, Go, Redis", gaps="AWS 경험, Kafka"),
        scorable(3, score="60", stack="Python, Airflow", gaps="AWS 경험"),
    ]
    at = app(rows)
    at.button(key="stats-open").click().run()

    html = " ".join(m.value for m in at.markdown)
    assert html.count("class='jv-rank-row'") == 2  # Python 2건, AWS 경험 2건만 막대 (v0.7.4 F1)
    once = html[html.index("1건씩 나온 것 3개") :]
    # 이름순, 내 기술은 초록
    assert once.index(">Airflow<") < once.index(">Go<") < once.index(">Redis<")
    assert "<span class='jv-chip jv-mine' title='Go · 내 프로필에 있는 기술'>Go</span>" in once
    assert "1건씩 나온 것 1개" in html and ">Kafka<" in html


def test_stats_dialog_saves_csv_and_copies_text(app):
    at = app([scorable(2, score="70", stack="Python, AWS", gaps="AWS 경험")])
    at.button(key="stats-open").click().run()

    download = at.get("download_button")[0]
    assert download.proto.label == "📥 엑셀로 저장"  # v0.7.4 F4
    assert at.button(key="stats-copy").label == "📋 전체 복사"  # F5
    hidden = next(m.value for m in at.markdown if "jv-copy-text" in m.value)
    assert "JOBVIS 기술 모아보기 (공고 1건 기준)&#10;" in hidden and "1건씩: AWS, Python" in hidden
    assert "\n" not in hidden  # 빈 줄에서 HTML이 끊기지 않게

    at.session_state["stats-copied"] = True  # 누른 뒤 다시 그린 모양 (창 안 버튼은 실제로는 창만 다시 그림)
    at.button(key="stats-open").click().run()
    assert at.button(key="stats-copy").label == "✓ 복사했습니다"


def test_stats_dialog_without_postings_has_no_export_buttons(app):
    at = app([])
    at.button(key="stats-open").click().run()

    assert not at.get("download_button")
    assert not [b for b in at.button if b.key == "stats-copy"]


def test_mail_dialog_is_wider_and_list_stays_one_line(app, sent, monkeypatch):
    import app as screen

    with_mail(monkeypatch)
    at = open_mail(app([scorable(2, score="80", verdict="추천")]))

    assert at.get("dialog")[0].proto.dialog.width == 2  # MEDIUM (v0.7.4 F3)
    assert '.st-key-mail-list label [data-testid="stWidgetLabel"] p { white-space: nowrap;' in screen.CSS
    assert ".st-key-mail-all button { padding: 0.3rem 1rem !important; }" in screen.CSS  # F2


def test_guide_has_mail_stats_and_folded_key_steps(app):
    import app as screen

    assert "**공고 메일 보내기**" in screen.GUIDE and "**기술 모아보기**" in screen.GUIDE  # F5
    at = app([])
    at.button(key="guide").click().run()
    folded = [e for e in at.expander if e.label in screen.KEY_STEPS]
    assert [e.label for e in folded] == ["🔑 제미나이 API 키 받기", "✉ Gmail 앱 비밀번호 받기"]
    assert not any(e.proto.expanded for e in folded)  # 접혀 있음
    steps = " ".join(screen.KEY_STEPS.values())
    assert "aistudio.google.com" in steps and "myaccount.google.com/apppasswords" in steps and "2단계 인증" in steps


def test_footer_shows_use_notice_and_version(app):
    import app as screen

    at = app([])
    footer = next(m.value for m in at.markdown if "class='jv-footer'" in m.value)
    assert "개인 사용" in footer and "공유하지 마세요" in footer and "이 PC에만" in footer  # F10
    assert "📖 사용법" in footer and "ai-job-search" in footer and f"JOBVIS {screen.VERSION}" in footer


def test_css_danger_hover_animations_and_reduced_motion():
    import app as screen

    for key in ("reset-open", "reset-yes", "profile-clear-all", "clear-all-yes", "key-delete", "mail-delete"):
        assert f".st-key-{key} button:hover" in screen.CSS  # F6
    assert all("danger" in palette for palette in screen.PALETTES.values())  # 두 테마 (N3)
    for name in ("jv-rise", "jv-grow", "jv-fill", "jv-unfold"):  # F8, F9, F11
        assert f"@keyframes {name}" in screen.CSS
    assert "@property --p" in screen.CSS
    motion = screen.CSS.split("@media (prefers-reduced-motion: reduce)")[1]
    assert "animation: none" in motion and "transform: none" in motion  # N2
    assert 'st-key-top-"] button' in screen.CSS  # 위 버튼은 작게 (F12)


# ---- v0.7.2 화면 다듬기 2 (F1–F9) ----


def test_view_select_shows_unscored_cards_only(app):
    at = app([scorable(2, score="80"), scorable(3), scorable(4)])
    at.selectbox(key="view").set_value("평가 전 공고").run()  # v0.7.2 F3

    assert names(at) == ["회사3", "회사4"]


def test_reset_is_one_button_with_help(app, monkeypatch):
    at = db_app(app, monkeypatch, [scorable(2)])

    button = at.sidebar.button(key="reset-open")
    assert button.label == "🗑 공고 초기화" and "처음부터 다시 수집" in button.help  # v0.7.2 F2
    assert "box-reset" not in [c.key for c in at.get("flex_container") if getattr(c, "key", None)]


def test_footer_is_three_lines_with_easter_egg():
    import app as screen

    assert [part.split("</b>")[0] for part in screen.FOOTER.split("<div><b>")[1:]] == ["이용", "데이터", "도움말"]
    assert f"<div class='jv-egg'>✦<span>{screen.EASTER_EGG}</span></div>" in screen.FOOTER  # v0.7.2 F7
    assert ".jv-egg:hover span { opacity: 1; }" in screen.CSS and "opacity: 0;" in screen.CSS


def test_more_button_scrolls_card_up_and_buttons_tint_on_hover():
    import app as screen

    script = screen.SCHEME_SYNC
    assert 'aria-expanded") === "true") return' in script  # 닫을 때는 움직이지 않음 (v0.7.2 F8)
    assert 'scrollIntoView({ block: "start"' in script and "prefers-reduced-motion: reduce" in script  # N2
    assert "scroll-margin-top: 4.5rem" in screen.CSS
    tint = screen.CSS.index('button[data-testid="stBaseButton-secondary"]:hover:not(:disabled)')
    assert tint < screen.CSS.index(".st-key-reset-open button:hover")  # 지우는 버튼 빨강이 이김 (F9)


def test_stats_tabs_have_same_height_and_filter_title_is_plain(app):
    at = app([scorable(2, score="70", stack="Python", gaps="AWS 경험")])

    assert "#### 필터" in [m.value for m in at.sidebar.markdown]  # 옆 설명 글 없음 (v0.7.2 F12)
    at.button(key="stats-open").click().run()
    boxes = [c for c in at.get("flex_container") if getattr(c, "key", None) in ("stats-wanted", "stats-lacking")]
    assert len(boxes) == 2  # 두 탭 칸 모두 같은 높이(STATS_HEIGHT) 칸 안에 (v0.7.2 F11)


def test_years_slider_goes_to_ten_unless_saved_value_is_larger(app, tmp_path):
    at = app([])
    slider = next(s for s in at.slider if s.label.startswith("경력"))
    assert slider.max == 10  # v0.7.2 F13

    text = "skills: {main: [Python]}\nexperience: {years: 12}\ndirection: {jobs: [백엔드 개발]}\n"
    (tmp_path / "profile.yaml").write_text(text, encoding="utf-8")
    at = app([])
    slider = next(s for s in at.slider if s.label.startswith("경력"))
    assert slider.max == 12 and slider.value == 12  # 저장된 값은 그대로

"""Streamlit 화면을 가짜 시트로 띄워 본다. 실제 시트·브라우저 없음 (v0.5 N5)."""

from datetime import date, timedelta
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
    heads = [m.value for m in at.markdown if "회사" in m.value]
    assert len(heads) == 3
    assert heads[0].startswith("**회사2 · 백엔드**") and "신뢰 높음" in heads[0]
    assert "jv-low" in heads[1]  # 신뢰 낮음 배지 색 (F5)
    assert "평가 전" in heads[2]  # 점수 순, 평가 전은 뒤
    assert len(at.get("popover")) == 3  # 자세히 (F4, v0.5.4 F5)

    at.toggle(key="scored-only").set_value(True).run()  # 평가된 공고만 보기 (F32)
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
    assert at.button(key="run-score").label == "🧮 체크한 공고 평가 (1건)"  # 체크한 공고 (F7)
    assert at.button(key="run-score-all").label == "평가 전 전부 평가 (2건)"  # --score all (F7)
    assert not [r for r in at.radio if r.label == "대상"]  # 수집 옆 평가 카드 없음 (v0.5.2 F38)
    keyword = next(s for s in at.selectbox if s.label == "키워드 *")
    assert set(runner.JOB_NAMES) <= set(keyword.options)  # 직무 이름이 추천 검색어 (F3)
    assert any("수집 카드에 키워드를 넣고" in m.value for m in at.markdown)  # 사용법 창 (F15, v0.5.4 F9)


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


def test_score_bar_sits_right_above_card_list(app):
    at = app([scorable(2), make_row(3, score="70", verdict="추천", trust="높음", body="글자")])

    texts = [m.value for m in at.markdown]
    bar = next(i for i, v in enumerate(texts) if v.startswith("**평가**"))
    first_card = next(i for i, v in enumerate(texts) if "회사2" in v)
    chart = next(i for i, v in enumerate(texts) if v == "**종합점수 TOP 5**")  # v0.5.2 F42
    assert chart < bar < first_card  # 차트·필터 아래, 카드 바로 위 (F38)


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

    assert any("채용공고를 한곳에 모아 보고, 내 프로필과 얼마나 맞는지 확인합니다" in m.value for m in at.markdown)


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
    assert at.button(key="run-score-all").label == "평가 전 전부 평가 (0건)"  # 평가 대상에서도 빠짐
    next(t for t in at.toggle if t.label == "관심 없는 공고만 보기").set_value(True).run()
    assert names(at) == ["회사3"] and at.button(key="hide-3").label == "되돌리기"

    at.button(key="hide-3").click().run()
    assert written[-1] == (3, False) and names(at) == []
    next(t for t in at.toggle if t.label == "관심 없는 공고만 보기").set_value(False).run()
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
    assert "jv-chip jv-mine'>Python<" in chips and "jv-chip'>Django<" in chips  # 대소문자 무시 (F4)
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
    next(t for t in at.toggle if t.label == "지원한 공고만 보기").set_value(True).run()
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

    labels = [w.label for w in at.sidebar.toggle]
    assert labels == ["평가된 공고만 보기", "추천 이상만 보기", "지원한 공고만 보기",
                      "이미지 필요한 공고만 보기", "관심 없는 공고만 보기"]  # F1, F2  # fmt: skip
    assert [w.label for w in at.sidebar.text_input] == ["검색"]
    assert [w.label for w in at.sidebar.selectbox] == ["정렬"]


def test_summary_text_applies_its_filter_and_marks_tile(app):
    rows = [scored(2, score="85", verdict="강력 추천"), scored(3, score="50", verdict="보통"),
            scorable(4, body="본문 미확보")]  # fmt: skip
    at = app(rows)
    assert at.button(key="tile-1").label == "점수가 있는 공고 →"
    assert "box-summary-0-on" in [c.key for c in at.get("flex_container") if getattr(c, "key", None)]

    at.button(key="tile-2").click().run()  # 추천 이상 (F12)
    assert names(at) == ["회사2"] and at.toggle(key="recommended-only").value
    assert "box-summary-2-on" in [c.key for c in at.get("flex_container") if getattr(c, "key", None)]

    at.button(key="tile-3").click().run()  # 이미지 필요만, 앞 필터는 풀림 (F3)
    assert names(at) == ["회사4"] and not at.toggle(key="recommended-only").value

    at.text_input(key="search").set_value("회사").run()
    at.button(key="tile-0").click().run()  # 전체 공고: 모두 풂
    assert names(at) == ["회사2", "회사3", "회사4"] and at.text_input(key="search").value == ""


def test_image_badge_and_upload_steps(app):
    at = app([scorable(2, body="본문 미확보"), scorable(3)])

    heads = {v.split("**")[1].split(" · ")[0]: v for v in (m.value for m in at.markdown) if v.startswith("**회사")}
    assert "📷 이미지 필요" in heads["회사2"] and 'title="사이트가 본문을' in heads["회사2"]  # F7
    assert "📷 이미지 필요" not in heads["회사3"]
    assert any("④ 위 받은함 카드의 🖼 받은함 읽기" in c.value for c in at.caption)  # F8


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
    assert not any("① 프로필 저장" in m.value for m in at.markdown)  # 화면에 사용법 접기 칸도 없음

    at.button(key="guide").click().run()

    assert len(at.get("dialog")) == 1 and any("① 프로필 저장" in m.value for m in at.markdown)


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
    assert any("① 프로필 저장" in m.value for m in at.markdown)
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
    assert len(at.get("dialog")) == 1 and any("① 프로필 저장" in m.value for m in at.markdown)  # 사용법 창

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
    assert "font-size: 4rem; font-weight: 900; color: var(--jv-title)" in screen.CSS  # F19
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

    assert 'st-key-box-filter"] { padding: 16px; }' in screen.CSS  # v0.6.1 F20
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

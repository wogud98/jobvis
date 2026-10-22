"""JOBVIS 화면. 실행: streamlit run app.py (PC 전용, localhost. 배포하지 않음, v0.5 N4).

테마는 .streamlit/config.toml의 밝은·어두운 테마와 아래 CSS (v0.5.1 F17–F19, v0.5.3 F13–F15).

수집·평가·받은함 버튼은 agent/runner.py를 별도 스레드로 돌린다 (v0.5.2). 이력서 채우기는 agent/resume.py.
정렬·필터·카드·요약 칸은 agent/view.py, 프로필 입력란은 agent/profile_form.py, 검사는 agent/user_profile.py,
이미지 저장은 agent/inbox.py에 있다.
"""

import hashlib
from datetime import date, datetime
from html import escape

import streamlit as st
from dotenv import load_dotenv

from agent import inbox, ocr, profile_form, resume, runner, scoring, settings, store, user_profile, view

PROFILE = user_profile.DEFAULT
LIST_FIELDS = ("요약", "주요업무", "우대사항")  # 글머리표로 보일 칸 (v0.5.3 F3)
CHART_HEIGHT = 230  # TOP 5 막대가 보기 좋은 높이
ACCENT = "#059669"  # .streamlit/config.toml의 primaryColor와 같게
FILL = "profile_fill"  # 이력서에서 채운 입력란 값 (session_state 키)
CHECKS = "check_overrides"  # 화면에서 바꾼 평가 체크 {시트 줄: 체크} (v0.5.2 F39)
HIDDEN = "hidden_overrides"  # 화면에서 바꾼 관심 없음 {시트 줄: 뺌} (v0.5.2 F44)
APPLIED = "applied_overrides"  # 화면에서 바꾼 지원 {시트 줄: 지원함} (v0.5.3 F11)
LAST_SEEN = "last_seen"  # 이 화면을 열기 전 마지막으로 연 시각 (v0.5.3 F9)
CHECK_ERROR = "check_error"
TOASTED = "toasted_job"  # 결과 알림을 띄운 작업 (v0.6.1 F5)
RELOADED = "reloaded_job"  # 결과를 다시 읽은 작업 (v0.6.1 F16)
PAGE, PAGE_FILTERS = "page", "page_filters"  # 지금 쪽 번호, 그 쪽을 고를 때의 필터 (v0.5.2 F41)
TAGLINE = "채용공고를 한곳에 모아 보고, 내 프로필과 얼마나 맞는지 확인합니다"  # JOBVIS 아래 문장 (v0.5.2 F43)
SORTS = {"점수 높은 순": "score_desc", "점수 낮은 순": "score_asc", "마감 임박 순": "deadline"}  # F40, v0.5.3 F8
TRUST_CLASS = {"높음": "high", "보통": "mid", "낮음": "low"}  # 신뢰 배지 색 (F5)

GUIDE = """
**① 프로필 저장** · 👤 프로필 탭
- `*` 표시한 필수 칸 3개만 채우면 평가할 수 있습니다. 나머지는 채울수록 점수 근거가 정확해집니다.
- 목록 칸은 눌러서 고르고, 목록에 없으면 직접 입력한 뒤 Enter로 추가합니다.
- 이력서·포트폴리오 파일을 올리면 빈 칸을 채워 줍니다. 확인하고 고친 뒤 **💾 저장**을 누르세요.

**② 수집** · 📋 공고 탭
- 수집 카드에 키워드를 넣고 **🔎 수집**을 누릅니다. 사람인·잡코리아 공개 페이지를 3초 간격으로 읽어서
  30건 수집은 몇 분 걸립니다.

**③ 평가**
- 공고 카드의 **평가** 칸을 체크하고 목록 위 **🧮 체크한 공고 평가**를 누릅니다.
  평가 전 공고를 한 번에 평가할 수도 있습니다.

**④ 공고 보기**
- 카드는 종합점수 높은 순입니다. 왼쪽 **필터**에서 검색·정렬하고, 필터는 « 로 접을 수 있습니다.
- 위 요약 칸의 숫자 아래 글(예: **점수가 있는 공고 →**)을 누르면 그 칸의 공고만 보입니다.
- **자세히**를 누르면 항목 점수, 강점·부족한 점, 요약, 기술(내 기술은 초록)이 뜹니다. 바깥을 누르면 닫히고,
  **📌 펼쳐 두기**를 누르면 카드 안에 열어 둡니다.
- **D-n**은 마감까지 남은 날(7일 이하는 빨강), **NEW**는 지난번에 연 뒤 들어온 공고입니다.
- 지원한 공고는 **지원함**, 보고 싶지 않은 공고는 **관심 없음**을 누릅니다.

**⑤ 이미지 넣기**
- **📷 이미지 필요** 배지가 붙은 공고는 사이트가 본문을 이미지로 올려 자동으로 읽지 못한 공고입니다.
- 자세히 → 원문 열기 → 공고 이미지 저장 → 끌어다 놓기 → **🖼 받은함 읽기** → 다시 평가하면 점수가 정확해집니다.

**그 밖에**
- 시트를 직접 고쳤으면 오른쪽 위 **🔄 새로고침**을 누릅니다.
- 다크 모드는 컴퓨터 설정을 따릅니다. 바꾸려면 오른쪽 위 **⋮ → Settings → Theme**.
- 터미널(`python main.py --keyword 백엔드`, `--score`, `--inbox`)로 해도 결과는 같습니다.
"""
RESUME_HELP = (
    f"PDF(글자 있는 것)·Word·txt·md. 파일 글자(앞 {resume.MAX_TEXT:,}자)가 LLM 제공자(기본 Gemini)로 전송됩니다. "
    "파일은 저장하지 않습니다."
)  # 이력서 채우기 도움말 (v0.5.2 N2, N3, v0.6.1 F10)
TRUST_HELP = (
    "점수를 매길 때 공고 원문을 얼마나 읽었는지입니다. "
    "높음: 원문을 다 읽음 · 보통: 이미지 일부를 못 읽음 · "
    f"낮음: 원문 없이 제목 등만 보고 매김(종합 최대 {scoring.CAP_LOW_TRUST}점)"
)  # 신뢰 배지 도움말 (v0.5.4 F10)
IMAGE_HELP = "사이트가 본문을 이미지로 올려 자동으로 읽지 못했습니다. 자세히에서 공고 이미지를 넣으세요."
PINNED = "pinned"  # 카드 안에 펼쳐 둔 공고 {시트 줄} (v0.5.4 F6)
GUIDE_SHOWN = "guide_shown"  # 처음 연 화면에서 사용법 창을 띄웠는지 (v0.5.4 F9)
CLEARED = "profile_cleared"  # 화면에서 비운 프로필 칸 {칸 keys} (v0.5.5 F1)
GENERATION = "profile_generation"  # 칸을 비울 때마다 올려 입력란을 새로 그린다 {칸 keys: 번호} (v0.5.5 F1)

# 테마별 색 (v0.5.3 F13–F15). 테두리·그림자(ink), 글자(text), 바탕(paper), 카드 면(card), 흐린 글자(muted)
PALETTES = {
    "light": {
        "ink": "#111111", "text": "#111111", "paper": "#fffdf5", "card": "#ffffff", "field": "#ffffff",
        "green": "#059669", "muted": "#444444", "sub": "#333333", "highlight": "#6ee7b7", "title": "#111111",
        "tile0": "#ffe066", "tile1": "#a5d8ff", "tile2": "#8ce99a", "tile3": "#ffc9c9", "tile-text": "#111111",
        # 고른 요약 칸은 색을 뒤집어 다른 칸과 바로 구분한다 (v0.6.1 F21)
        "sel": "#111111", "sel-text": "#ffffff",
        "high": "#8ce99a", "mid": "#ffe066", "low": "#ffa8a8", "closed": "#ced4da", "badge-text": "#111111",
    },
    "dark": {
        # 회청색 한 계열로 맞추고, 순백·순흑과 쨍한 색을 피해 눈부심을 줄인다 (v0.6.1 F22)
        "ink": "#4b5563", "text": "#e5e7eb", "paper": "#14161a", "card": "#1f232a", "field": "#181b20",
        "green": "#34d399", "muted": "#9ca3af", "sub": "#cbd0d6", "highlight": "#047857", "title": "#ffffff",
        "tile0": "#4a4024", "tile1": "#24384d", "tile2": "#243f31", "tile3": "#4a2c30", "tile-text": "#e5e7eb",
        "sel": "#d1d5db", "sel-text": "#111318",
        "high": "#2f5a43", "mid": "#5a4d22", "low": "#5c3034", "closed": "#3a3f47", "badge-text": "#e5e7eb",
    },
}  # fmt: skip


def chart_spec(data: list[tuple[str, int]]) -> dict:
    """TOP 5 가로 막대 명세. 선택·확대 params가 없어 움직이지 않는다 (v0.6.1 F23)."""
    return {
        "data": {"values": [{"공고": name, "종합점수": score} for name, score in data]},
        "mark": {"type": "bar", "color": ACCENT},
        "encoding": {
            "y": {
                "field": "공고",
                "type": "nominal",
                "sort": "-x",
                "title": None,
                "axis": {"labelLimit": 260},
            },  # 높은 점수가 위 (F42)
            "x": {"field": "종합점수", "type": "quantitative", "scale": {"domain": [0, 100]}},
            "tooltip": [{"field": "공고"}, {"field": "종합점수"}],
        },
        "height": CHART_HEIGHT,
    }


def css(theme: str | None) -> str:
    """테마에 맞춘 CSS. 모르는 값(테스트 등)은 밝은 테마."""
    palette = PALETTES.get(theme or "light", PALETTES["light"])
    return CSS.replace("/*VARS*/", " ".join(f"--jv-{name}: {value};" for name, value in palette.items()))


# 네오 브루탈리즘 (v0.5.2 F28): 굵은 검정 테두리, 흐림 없는 딱딱한 그림자, 단색 면, 초록 포인트 하나.
# 카드는 key가 "box-"로 시작하는 컨테이너. Streamlit 내부 클래스 대신 key로 붙는 st-key-* 클래스와
# data-testid에만 건다 (v0.5.1 N5)
CSS = """
<style>
:root { /*VARS*/ }
.stApp { background: var(--jv-paper); }
[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 1200px; padding-top: 2rem; }
/* 카드: 흰 면 + 3px 검정 테두리 + 오른쪽 아래 딱 떨어지는 그림자 */
div[class*="st-key-box"] {
  background: var(--jv-card) !important; border: 3px solid var(--jv-ink) !important; border-radius: 8px !important;
  box-shadow: 6px 6px 0 var(--jv-ink); padding: 18px 20px;
}
div[class*="st-key-box"] div[class*="st-key-box"] { box-shadow: 3px 3px 0 var(--jv-ink); }
div[class*="st-key-box-dim"] { opacity: 0.55; }
/* 요약 칸 4개는 단색 면으로 구분한다. 어두운 테마는 짙은 톤 (v0.5.4 F11) */
div[class*="st-key-box-summary-0"] { background: var(--jv-tile0) !important; }
div[class*="st-key-box-summary-1"] { background: var(--jv-tile1) !important; }
div[class*="st-key-box-summary-2"] { background: var(--jv-tile2) !important; }
div[class*="st-key-box-summary-3"] { background: var(--jv-tile3) !important; }
div[class*="st-key-box-summary"] * { color: var(--jv-tile-text) !important; }
/* 숫자 아래 글은 누르는 버튼. 마우스를 올리면 밑줄 (v0.5.4 F12) */
div[class*="st-key-box-summary"] div[class*="st-key-tile-"] button {
  padding: 0 !important; min-height: 0; border: none !important; box-shadow: none !important;
  background: transparent !important; font-size: 0.9rem; }
div[class*="st-key-box-summary"] div[class*="st-key-tile-"] button:hover {
  text-decoration: underline; transform: none !important; box-shadow: none !important; }
/* 프로필 칸 ↺는 작은 글자 버튼 (v0.5.5 F1) */
div[class*="st-key-box-profile"] div[class*="st-key-clear-"] button {
  padding: 0 4px !important; min-height: 0; border: none !important; box-shadow: none !important;
  background: transparent !important; font-size: 1.1rem; color: var(--jv-muted) !important; }
div[class*="st-key-box-profile"] div[class*="st-key-clear-"] button:hover {
  color: var(--jv-green) !important; transform: none !important; box-shadow: none !important; }
/* 지금 적용 중인 칸은 굵은 테두리 + 제목 앞 ✓. 초록은 다른 곳에도 써서 모양으로 구분 (v0.5.4 F12, v0.6.1 F15).
   면 색도 뒤집어 한눈에 보이게 (v0.6.1 F21) */
div[class*="st-key-box-summary"][class*="-on"] { border-width: 5px !important; transform: translate(-2px, -2px);
  box-shadow: 9px 9px 0 var(--jv-ink); }
div[class*="st-key-box-summary"][class*="-on"] { background: var(--jv-sel) !important; }
div[class*="st-key-box-summary"][class*="-on"] * { color: var(--jv-sel-text) !important; }
div[data-testid="stExpander"] details {
  background: var(--jv-card); border: 2px solid var(--jv-ink) !important; border-radius: 6px !important;
  box-shadow: 3px 3px 0 var(--jv-ink);
}
div[data-testid="stExpander"] summary { font-weight: 700; }
/* 버튼: 테두리·그림자, 누르면 그림자만큼 눌린다 */
div[data-testid="stButton"] button, div[data-testid="stLinkButton"] a {
  border: 2px solid var(--jv-ink) !important; border-radius: 6px; box-shadow: 4px 4px 0 var(--jv-ink);
  font-weight: 700; transition: transform 80ms, box-shadow 80ms;
}
div[data-testid="stButton"] button:hover:not(:disabled), div[data-testid="stLinkButton"] a:hover {
  transform: translate(-1px, -1px); box-shadow: 5px 5px 0 var(--jv-ink);
}
div[data-testid="stButton"] button:active:not(:disabled) { transform: translate(4px, 4px); box-shadow: none; }
div[data-testid="stButton"] button:disabled { box-shadow: none; border-style: dashed !important; }
/* 입력란 */
div[data-baseweb="select"] > div, div[data-baseweb="input"], div[data-baseweb="textarea"],
div[data-testid="stFileUploaderDropzone"] {
  border: 2px solid var(--jv-ink) !important; border-radius: 6px !important; background: var(--jv-field) !important;
}
div[data-testid="stAlert"] > div {
  border: 2px solid var(--jv-ink); border-radius: 6px; box-shadow: 3px 3px 0 var(--jv-ink);
}
/* 필터 사이드바와 자세히 창도 굵은 테두리 (v0.5.4 F1, F5) */
section[data-testid="stSidebar"] { border-right: 3px solid var(--jv-ink); background: var(--jv-paper); }
section[data-testid="stSidebar"] div[class*="st-key-box-filter"] { padding: 16px; }
div[data-testid="stPopoverBody"] { border: 3px solid var(--jv-ink) !important; box-shadow: 6px 6px 0 var(--jv-ink);
  max-height: 75vh; overflow-y: auto; }
/* 고르기 칸의 키워드 아무 데나 눌러도 지워지게, 삭제 버튼이 키워드 전체를 덮는다 (v0.5.1 F22) */
div[data-testid="stMultiSelect"] [data-tag] {
  position: relative; cursor: pointer; padding-right: 22px; border: 2px solid var(--jv-ink); border-radius: 4px;
}
div[data-testid="stMultiSelect"] [data-tag] > button[aria-label^="Remove"] {
  position: absolute; inset: 0; width: 100%; height: 100%; margin: 0; padding: 0 7px;
  display: flex; align-items: center; justify-content: flex-end;
  background: transparent; border: 0; border-radius: inherit; cursor: pointer;
}
div[data-testid="stMultiSelect"] [data-tag] > button[aria-label^="Remove"] svg { width: 0.7em; height: 0.7em; }
div[data-testid="stMultiSelect"] [data-tag]:hover { filter: brightness(0.88); text-decoration: line-through; }
div[data-testid="stMetricValue"] { font-size: 2.4rem; font-weight: 900; color: var(--jv-text); }
/* 제목은 크게, 어두운 테마에서는 흰색 (v0.6.1 F1). 뒤 형광 줄은 뺐다 (v0.6.1 F19) */
.jv-hero h1 { margin: 0; padding: 0; font-size: 4rem; font-weight: 900; color: var(--jv-title);
  letter-spacing: -0.03em; line-height: 1.05; }
.jv-hero p { margin: 4px 0 0; color: var(--jv-sub); font-weight: 600; }
.jv-score { font-size: 2.2rem; font-weight: 900; line-height: 1; color: var(--jv-green); }
.jv-muted { color: var(--jv-muted); font-size: 0.9rem; }
.jv-badge { display: inline-block; margin-right: 6px; padding: 1px 9px; border: 2px solid var(--jv-ink);
  border-radius: 4px; font-size: 0.8rem; font-weight: 800; }
.jv-verdict { background: var(--jv-card); color: var(--jv-text); }
.jv-high { background: var(--jv-high); color: var(--jv-badge-text); }
.jv-mid { background: var(--jv-mid); color: var(--jv-badge-text); }
.jv-low { background: var(--jv-low); color: var(--jv-badge-text); }
.jv-closed { background: var(--jv-closed); color: var(--jv-badge-text); }
.jv-plain { background: var(--jv-card); color: var(--jv-text); }
.jv-new { background: var(--jv-green); color: var(--jv-card); }
/* 자세히 (v0.5.3 F1–F5) */
.jv-bar-row { display: flex; align-items: center; gap: 10px; margin: 4px 0; }
.jv-bar-name { width: 3em; font-weight: 700; }
.jv-bar { flex: 1; height: 14px; border: 2px solid var(--jv-ink); border-radius: 4px; background: var(--jv-card); }
.jv-bar > div { height: 100%; border-right: 2px solid var(--jv-ink); }
.jv-bar > div.jv-high, .jv-bar > div.jv-mid, .jv-bar > div.jv-low { border-radius: 0; }
.jv-bar-num { width: 2.2em; text-align: right; font-weight: 900; }
.jv-chip { display: inline-block; margin: 0 6px 6px 0; padding: 2px 10px; border: 2px solid var(--jv-ink);
  border-radius: 4px; font-size: 0.85rem; font-weight: 700; background: var(--jv-card); color: var(--jv-text); }
.jv-chip.jv-mine { background: var(--jv-high); color: var(--jv-badge-text); }
.jv-strength { color: var(--jv-sub); font-size: 0.9rem; }
/* 카드 체크·점수·버튼 칸은 창이 좁아져도 글자가 잘리지 않게 (v0.6.1 F4) */
div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"] div[class*="st-key-check-"]) {
  flex-wrap: nowrap; }
div[data-testid="stColumn"]:has(div[class*="st-key-check-"]) { flex: 0 0 4.6rem; min-width: 4.6rem; }
div[data-testid="stColumn"]:has(div[class*="st-key-apply-"]) { flex: 0 0 7rem; min-width: 7rem; }
div:has(> .jv-score) > .jv-muted { white-space: nowrap; font-size: 0.8rem; }
div[data-testid="stColumn"]:has(> div .jv-badge) { flex: 1 1 0; min-width: 0; }
div[class*="st-key-check-"] label, div[class*="st-key-apply-"] button, div[class*="st-key-hide-"] button,
div[class*="st-key-run-score"] button { white-space: nowrap; }
/* 고른 키워드가 많으면 옆으로 숨기지 않고 줄을 바꿔 모두 보인다 (v0.6.1 F7) */
div[data-testid="stMultiSelect"] div:has(> span > [data-tag]) {
  flex-wrap: wrap; overflow: visible; height: auto; row-gap: 4px; padding-top: 3px; padding-bottom: 3px;
  min-width: 0; flex: 1 1 0; }
div[data-testid="stMultiSelect"] [data-tag] { flex-shrink: 0; max-width: 100%; }
div[data-testid="stMultiSelect"] div:has(> div > span > [data-tag]) { max-height: none; height: auto; }
/* 프로필 네 칸은 같은 줄끼리 높이를 맞춘다 (v0.6.1 F9) */
div[data-testid="stLayoutWrapper"]:has(> div[class*="st-key-box-profile-"]) { flex: 1 1 auto; }
div[class*="st-key-box-profile-"] { height: 100%; }
</style>
"""


@st.cache_data(show_spinner="공고를 읽는 중")
def load_rows() -> list[dict]:
    # 열 때 한 번 읽고, 새로고침을 누를 때만 다시 읽는다 (F7)
    return store.read_rows_readonly()


def reload_rows() -> None:
    """시트를 다시 읽게 한다. 화면에서 바꾼 체크는 시트에 이미 썼으니 버린다."""
    load_rows.clear()
    st.session_state.pop(CHECKS, None)
    st.session_state.pop(HIDDEN, None)
    st.session_state.pop(APPLIED, None)
    for key in [key for key in st.session_state if str(key).startswith("check-")]:
        del st.session_state[key]


def toggle_check(row: int) -> None:
    """카드 체크 칸을 바꾸면 시트 "평가" 칸에 바로 쓴다 (v0.5.2 F39). 실패하면 체크를 되돌린다."""
    key = f"check-{row}"
    checked = bool(st.session_state.get(key))
    try:
        store.set_check(row, checked)
    except Exception as e:  # 키·경로는 보이지 않는다
        st.session_state.pop(key, None)  # 시트 값으로 다시 그림
        st.session_state[CHECK_ERROR] = f"체크를 {store.place()}에 쓰지 못했습니다. {runner.error_text(e)}"
        return
    st.session_state.setdefault(CHECKS, {})[row] = checked


def toggle_hidden(row: int, hidden: bool) -> None:
    """관심 없음으로 빼거나 되돌린다. 시트 "관심없음" 칸에 바로 쓴다 (v0.5.2 F44)."""
    try:
        store.set_hidden(row, hidden)
    except Exception as e:  # 키·경로는 보이지 않는다
        st.session_state[CHECK_ERROR] = f"관심 없음을 {store.place()}에 쓰지 못했습니다. {runner.error_text(e)}"
        return
    st.session_state.setdefault(HIDDEN, {})[row] = hidden


def toggle_applied(row: int, applied: bool) -> None:
    """지원함 표시를 시트 "지원" 칸에 쓴다 (v0.5.3 F11)."""
    try:
        store.set_applied(row, applied)
    except Exception as e:  # 키·경로는 보이지 않는다
        st.session_state[CHECK_ERROR] = f"지원함을 {store.place()}에 쓰지 못했습니다. {runner.error_text(e)}"
        return
    st.session_state.setdefault(APPLIED, {})[row] = applied


def show_upload(card: view.Card) -> None:
    """공고 이미지 넣기. 이유와 순서를 먼저 보인다 (v0.5.4 F8)."""
    st.markdown("**📷 공고 이미지 넣기**")
    st.caption(
        f"{IMAGE_HELP}  \n"
        "① 원문 열기 → ② 공고 이미지 저장 → ③ 여기에 끌어다 놓고 받은함에 저장 → "
        "④ 위 받은함 카드의 🖼 받은함 읽기 → ⑤ 다시 평가"
    )
    files = st.file_uploader(
        "끌어다 놓거나 파일 고르기",
        type=list(inbox.EXTENSIONS),
        accept_multiple_files=True,
        key=f"upload-{card.row}",
    )
    # 화면이 다시 그려질 때마다 같은 파일이 또 저장되지 않게 버튼을 눌렀을 때만 저장한다
    if not files or not st.button("받은함에 저장", key=f"save-{card.row}"):
        return
    saved = []
    for file in files:
        try:
            saved.append(inbox.save_upload(card.source_code, card.job_id, file.name, file.getvalue()).name)
        except inbox.UploadError as e:
            st.error(str(e))  # 확장자가 아니거나 10MB 초과 (F49)
    if saved:
        # 화면은 저장만 하고 OCR은 받은함 읽기에서 (F48)
        st.success(f"저장함: {', '.join(saved)}. 위 받은함 카드에서 🖼 받은함 읽기를 누르세요.")


@st.dialog("📖 사용법", width="large")
def show_guide() -> None:
    """사용 순서를 번호로 보이는 새 창 (v0.5.4 F9). 바깥을 누르거나 X로 닫는다."""
    st.markdown(GUIDE)


def open_guide_first_time() -> None:
    """처음 연 화면(지난번 연 기록 없음)에서 한 번만 띄운다 (F9)."""
    if st.session_state.get(LAST_SEEN) is None and not st.session_state.get(GUIDE_SHOWN):
        st.session_state[GUIDE_SHOWN] = True
        show_guide()


def badge(text: str, kind: str, tip: str = "") -> str:
    title = f' title="{escape(tip)}"' if tip else ""  # 마우스를 올리면 뜨는 도움말 (v0.5.4 F10)
    return f'<span class="jv-badge jv-{kind}"{title}>{escape(text)}</span>'


def pin(row: int, pinned: bool) -> None:
    rows = st.session_state.setdefault(PINNED, set())
    rows.add(row) if pinned else rows.discard(row)


def show_card(card: view.Card, known: list[str]) -> None:
    # 시트 글자(회사·직무 등)는 HTML로 넣기 전에 escape한다
    today = date.today()
    closed = (view.days_left(card.deadline, today) or 0) < 0
    # 신뢰 낮음, 마감 지난 공고는 흐리게 (v0.5 F34, F5, v0.5.3 F7)
    key = f"box-{'dim-' if card.dim or closed else ''}card-{card.row}"
    with st.container(border=True, key=key):
        # 체크와 점수는 한 칸에 위아래로 둬서 좁은 창에서도 회사·직무 칸이 넓게 남는다 (v0.6.1 F4)
        left, head, hide = st.columns([1, 6, 1.1], vertical_alignment="center")
        check = score = left
        # 체크하면 시트 "평가" 칸에도 체크된다. 목록 위 평가 줄 버튼으로 평가 (v0.5.2 F38, F39)
        check.checkbox(
            "평가", value=card.checked, key=f"check-{card.row}", on_change=toggle_check, args=(card.row,),
            disabled=runner.running(),
        )  # fmt: skip
        number = "-" if card.score is None else str(card.score)  # F6
        score.markdown(
            f'<div class="jv-score">{number}</div><div class="jv-muted">{escape(card.stars)}</div>',
            unsafe_allow_html=True,
        )
        head.markdown(card_head(card, today), unsafe_allow_html=True)
        # 지원함 (v0.5.3 F11). 다시 누르면 취소
        hide.button(
            "✓ 지원함" if card.applied else "지원함", key=f"apply-{card.row}", on_click=toggle_applied,
            args=(card.row, not card.applied), disabled=runner.running(), use_container_width=True,
            type="primary" if card.applied else "secondary",
        )  # fmt: skip
        # 뺀 공고는 목록에서 사라지고 평가 대상에서도 빠진다. "관심 없는 공고만 보기"에서 되돌림 (v0.5.2 F44)
        hide.button(
            "되돌리기" if card.hidden else "관심 없음", key=f"hide-{card.row}", on_click=toggle_hidden,
            args=(card.row, not card.hidden), disabled=runner.running(), use_container_width=True,
        )  # fmt: skip
        # 자세히는 떠오르는 창이라 바깥을 누르면 닫힌다. 펼쳐 두면 카드 안에 남는다 (v0.5.4 F5, F6)
        if card.row in st.session_state.get(PINNED, set()):
            with st.container(border=True, key=f"box-pinned-{card.row}"):
                st.button("접기", key=f"unpin-{card.row}", on_click=pin, args=(card.row, False))
                show_details(card, known)
        else:
            with st.popover("자세히", width="stretch", key=f"more-{card.row}"):
                st.button("📌 펼쳐 두기", key=f"pin-{card.row}", on_click=pin, args=(card.row, True),
                          help="카드 안에 열어 둡니다. 접기를 누를 때까지 닫히지 않습니다")  # fmt: skip
                show_details(card, known)


def show_details(card: view.Card, known: list[str]) -> None:
    if card.score is None:  # 평가 전·제외: 수집 칸과 원문 앞부분 (v0.5.2 F31)
        show_unscored_details(card)
    else:
        show_scored_details(card, known)
    if card.url:
        st.link_button("원문 열기", card.url)  # 새 탭 (v0.5 F4)
    if card.can_upload:
        show_upload(card)


def card_head(card: view.Card, today: date) -> str:
    """카드 머리: 회사·직무, 배지(판정·신뢰·이미지 필요·마감·NEW·지원함), 출처·경력·마감, 첫 강점 (v0.5.4 F7)."""
    badges = badge(card.verdict, "verdict")
    if card.trust:
        badges += badge(f"신뢰 {card.trust}", TRUST_CLASS.get(card.trust, "mid"), TRUST_HELP)
    if card.can_upload:  # v0.5.4 F7
        badges += badge("📷 이미지 필요", "mid", IMAGE_HELP)
    deadline = view.deadline_badge(card.deadline, today)
    if deadline:
        badges += badge(*deadline)
    if view.is_new(card, st.session_state.get(LAST_SEEN)):
        badges += badge("NEW", "new")
    if card.applied:
        badges += badge("지원함", "high")
    meta = " · ".join(part for part in (card.source, card.experience, f"마감 {card.deadline or '없음'}") if part)
    text = f"**{escape(card.company)} · {escape(card.title)}**  \n{badges}<span class='jv-muted'>{escape(meta)}</span>"
    if card.score is not None and card.strengths:  # 펼치지 않아도 보이는 강점 한 줄 (F12)
        text += f"  \n<span class='jv-strength'>💪 {escape(card.strengths[0])}</span>"
    return text


def show_unscored_details(card: view.Card) -> None:
    if card.verdict == view.scoring.EXCLUDED:
        st.info("신입에게 경력을 요구하는 공고라 평가에서 제외했습니다.")
    else:
        st.info("아직 평가 전입니다. 🧮 평가를 누르면 요약·점수·강점·부족한 점이 채워집니다.")
    if card.info:
        st.markdown(" · ".join(f"**{name}** {escape(value)}" for name, value in card.info.items()))
    text = view.preview(card)
    if text:
        st.caption("원문 앞부분")
        st.text(text)  # 원문은 사이트 글자라 그대로(서식 없이) 보인다
    elif card.can_upload:
        st.warning("본문이 없습니다. 아래에 공고 이미지를 넣으면 평가가 정확해집니다.")


def score_bars(scores: dict[str, int | None]) -> str:
    """항목 점수 막대 (v0.5.3 F1). 근거 없는 항목(문화 등)은 그리지 않는다 (F6)."""
    rows = []
    for name, value in scores.items():
        if value is None:
            continue
        kind = "high" if value >= 70 else "mid" if value >= 40 else "low"
        rows.append(
            f"<div class='jv-bar-row'><span class='jv-bar-name'>{name}</span>"
            f"<div class='jv-bar'><div class='jv-{kind}' style='width:{max(0, min(value, 100))}%'></div></div>"
            f"<span class='jv-bar-num'>{value}</span></div>"
        )
    return "".join(rows)


def bullets(items: list[str]) -> str:
    return "\n".join(f"- {escape(item)}" for item in items) or f"- {view.NONE}"


def show_scored_details(card: view.Card, known: list[str]) -> None:
    """점수 막대 → 강점·부족한 점 두 칸 → 요약·업무·우대 글머리표 → 기술 칩 → 참고·점수 기준 (v0.5.3 F1–F6)."""
    st.markdown(score_bars(card.scores), unsafe_allow_html=True)
    good, bad = st.columns(2)
    good.markdown(f"**✅ 강점**\n\n{bullets(card.strengths)}")
    bad.markdown(f"**⚠️ 부족한 점**\n\n{bullets(card.gaps)}")
    for name in LIST_FIELDS:
        items = view.split_items(card.details[name] if card.details[name] != view.NONE else "")
        if items:  # 빈 칸은 보이지 않는다 (F3)
            st.markdown(f"**{name}**\n\n{bullets(items)}")
    chips = view.stack_chips(card.details["기술스택"] if card.details["기술스택"] != view.NONE else "", known)
    if chips:
        html = "".join(f"<span class='jv-chip{' jv-mine' * mine}'>{escape(name)}</span>" for name, mine in chips)
        st.markdown(f"**기술스택** <span class='jv-muted'>초록은 내 프로필에 있는 기술</span><br>{html}",
                    unsafe_allow_html=True)  # fmt: skip
    notes = []
    if card.trust:
        notes.append(f"신뢰 {card.trust} (본문: {card.body or '없음'})")
    if card.adjust:
        notes.append(f"보정 {card.adjust}")
    if notes:
        st.caption(" · ".join(notes))
    with st.expander("점수 기준"):
        st.markdown(score_guide())


def score_guide() -> str:
    """점수 기준 글 (v0.5.3 F5). 숫자는 scoring 상수에서 가져온다."""
    pairs = zip(view.SCORE_NAMES, scoring.WEIGHTS.values(), strict=True)
    weights = " · ".join(f"{name} {weight}" for name, weight in pairs)
    return (
        "- 항목 점수(기술·경력·문화·방향)는 0–100점입니다.\n"
        f"- 종합점수는 가중 평균입니다({weights}). "
        "공고에 근거가 없는 항목(주로 문화)은 빼고 나머지로 나눕니다.\n"
        "- 별점은 종합점수 20점마다 1개입니다.\n"
        f"- 요구 경력이 부족하면 종합 최대 {scoring.CAP_SHORT}점, "
        f"본문 없이 제목만 보고 매기면 최대 {scoring.CAP_LOW_TRUST}점입니다."
    )


@st.fragment(run_every=1.0)
def show_live_job() -> None:
    """실행 중인 작업의 진행 상황. 1초마다 이 부분만 다시 그린다 (F5, F9)."""
    job = runner.current()
    if job is None:
        return
    if job.finished:
        st.session_state[RELOADED] = f"{job.label}-{job.started}"  # 다시 읽기는 한 번만 (v0.6.1 F16)
        reload_rows()  # 끝나면 시트를 다시 읽는다 (F6, F9). 평가한 줄은 체크가 풀려 있다
        st.rerun(scope="app")
    st.progress(
        job.done / job.total if job.total else 0.0, text=f"{job.label} 중: {job.stage} ({job.done}/{job.total})"
    )


def show_job_result() -> None:
    job = runner.current()
    if job is None or not job.finished:
        return
    title = f"{job.label} 결과 ({job.started} 시작)"
    if job.error:
        st.error(f"{title}\n\n{job.error}")  # 키·경로 없이 (F13)
        return
    result = job.result
    # 결과 한 줄과 할 일은 잠깐 뜨는 알림으로 한 번만. 화면에 남는 칸은 문제가 있을 때만 (v0.6.1 F5)
    shown = f"{job.label}-{job.started}"
    if st.session_state.get(TOASTED) != shown:
        st.session_state[TOASTED] = shown
        st.toast(" ".join([result.headline, *result.todo]), icon="✅")
    if not result.problems:
        return
    for line in result.problems:
        st.error(escape(line))
    if result.details:
        with st.expander("자세히"):
            st.markdown("\n".join(f"- {escape(line.strip())}" for line in result.details))


def start_job(starter, *args) -> None:
    try:
        starter(*args)
    except (runner.RunError, user_profile.ProfileError) as e:
        st.error(str(e))
        return
    except Exception as e:  # 모르는 지역·직무 이름 등
        st.error(runner.error_text(e))
        return
    st.rerun()


def show_collect_card() -> None:
    busy = runner.running()  # 한 번에 하나만 (F12)
    with st.container(border=True, key="box-run-collect"):
        st.markdown("**수집**")  # 사이트·요청 간격 안내는 사용법에만 (v0.6.1 F3)
        try:
            raw = user_profile.read_raw(PROFILE)
        except user_profile.ProfileError:
            raw = None
        keyword = st.selectbox(
            "키워드 *", runner.keyword_options(raw), index=None, accept_new_options=True,
            placeholder="골라 주세요. 없으면 입력 후 Enter", help="사이트 검색창에 넣을 말 (F3)",
        )  # fmt: skip
        left, right = st.columns(2)
        location = left.selectbox("지역", runner.REGION_NAMES, index=None, placeholder="전체")
        job = right.selectbox("직무", runner.JOB_NAMES, index=None, accept_new_options=True, placeholder="전체")
        left, middle, right = st.columns([1.2, 1.4, 1])
        career = left.radio("경력", [runner.CAREER_ALL, *runner.codes.CAREERS], horizontal=True)
        names = middle.multiselect("사이트", list(runner.SOURCE_NAMES), default=list(runner.SOURCE_NAMES))
        count = right.number_input("사이트당 개수", 1, runner.MAX_COUNT, 10)
        if st.button("🔎 수집", type="primary", disabled=busy, key="run-collect", use_container_width=True):
            try:
                sources = [runner.SOURCE_NAMES[name] for name in names]
                state = runner.collect_state(keyword or "", location, job, career, sources, int(count))
            except Exception as e:
                st.error(runner.error_text(e))
                return
            start_job(runner.start_collect, state)


def show_inbox_card() -> None:
    """받은함은 수집 쪽 작업이라 수집 카드 아래에 둔다. 이미지가 있을 때만 (F10, v0.5.2 F38)."""
    images = runner.inbox_count()
    if not images:
        return
    with st.container(border=True, key="box-run-inbox"):
        st.markdown(f"**받은함** <span class='jv-muted'>공고 이미지 {images}장</span>", unsafe_allow_html=True)
        if not ocr.available():
            st.info(f"OCR이 설치돼 있지 않습니다. {ocr.INSTALL_HINT}")  # F11
        elif st.button("🖼 받은함 읽기", disabled=runner.running(), key="run-inbox"):
            start_job(runner.start_inbox)


def start_score(mode: str) -> None:
    try:
        profile = runner.load_profile(PROFILE)  # 없거나 틀리면 실행하지 않음 (F8)
    except user_profile.ProfileError as e:
        st.error(f"{e}\n\n프로필 탭에서 입력하고 저장해 주세요.")
        return
    start_job(runner.start_score, mode, profile)


def show_score_bar(rows: list[dict]) -> None:
    """공고 목록 바로 위 평가 줄 (v0.5.2 F38). 카드에서 체크하고 바로 누른다."""
    busy = runner.running()
    checked, unscored = runner.score_targets(rows, "checked"), runner.score_targets(rows, "all")
    with st.container(border=True, key="box-score-bar"):
        st.markdown("**평가** <span class='jv-muted'>카드의 평가 칸을 체크하고 누릅니다</span>", unsafe_allow_html=True)
        left, right = st.columns(2)  # 버튼 글자가 잘리지 않게 안내 줄 아래 두 칸 (v0.6.1 F4)
        if left.button(
            f"🧮 체크한 공고 평가 ({checked}건)", type="primary", disabled=busy or not checked,
            key="run-score", use_container_width=True,
        ):  # fmt: skip
            start_score("checked")
        if right.button(
            f"평가 전 전부 평가 ({unscored}건)", disabled=busy or not unscored,
            key="run-score-all", use_container_width=True,
        ):  # fmt: skip
            start_score("all")
        error = st.session_state.pop(CHECK_ERROR, None)
        if error:
            st.error(error)


def show_run_panel() -> None:
    show_collect_card()
    show_inbox_card()
    if runner.running():
        show_live_job()
    show_job_result()


FILTER_KEYS = {"search": "", "sources": [], "experiences": [], "scored-only": False, "recommended-only": False,
               "applied-only": False, "image-only": False, "hidden-only": False}  # fmt: skip
TILE_FILTERS = (None, "scored-only", "recommended-only", "image-only")  # 요약 칸 순서대로 켤 필터 (v0.5.4 F12)


def pick_tile(index: int) -> None:
    """요약 칸의 보기를 누르면 필터를 모두 풀고 그 칸의 필터만 켠다. 전체 공고는 모두 풀기만 (v0.5.4 F12)."""
    st.session_state.update(FILTER_KEYS)
    if TILE_FILTERS[index]:
        st.session_state[TILE_FILTERS[index]] = True


def tile_on(index: int) -> bool:
    """지금 필터가 그 칸을 누른 상태와 같은지. 초록 테두리로 보인다."""
    state = {key: st.session_state.get(key, empty) for key, empty in FILTER_KEYS.items()}
    wanted = dict(FILTER_KEYS)
    if TILE_FILTERS[index]:
        wanted[TILE_FILTERS[index]] = True
    return state == wanted


def reload_after_job() -> None:
    """끝난 작업의 결과를 한 번은 꼭 다시 읽는다 (v0.6.1 F16).

    보통은 진행 막대(show_live_job)가 끝을 보고 다시 읽지만, 작업이 화면을 그리는 사이에 끝나면
    진행 막대가 그려지지 않아 다시 읽기를 놓친다.
    """
    job = runner.current()
    done = f"{job.label}-{job.started}" if job and job.finished else None
    if done and st.session_state.get(RELOADED) != done:
        st.session_state[RELOADED] = done
        reload_rows()


def show_postings() -> None:
    reload_after_job()
    try:
        rows, error = load_rows(), None
    except Exception as e:
        rows, error = None, e
    show_run_panel()
    if error is not None:
        st.error(view.error_message(error))  # v0.5 F9
        st.sidebar.caption("공고를 읽으면 필터가 보입니다.")
        return
    if not rows:
        st.info("공고 없음, 위 수집 카드에서 키워드를 넣고 수집하세요.")  # v0.5 F10
        st.sidebar.caption("공고가 생기면 필터가 보입니다.")
        return

    # 화면에서 바꾼 체크·관심 없음·지원 (F39, F44, v0.5.3 F11)
    rows = view.with_checks(
        rows, st.session_state.get(CHECKS, {}), st.session_state.get(HIDDEN, {}), st.session_state.get(APPLIED, {})
    )
    items = view.cards(rows)
    for index, (column, (label, value, note)) in enumerate(zip(st.columns(4), view.summary(items), strict=True)):
        on = "-on" if tile_on(index) else ""
        with column.container(border=True, key=f"box-summary-{index}{on}"):  # 칸마다 색 (F28)
            st.metric(f"✓ {label}" if on else label, value)
            # 숫자 아래 설명 글을 누르면 그 필터로 목록을 보인다 (v0.5.4 F3, F12)
            st.button(f"{note} →", key=f"tile-{index}", on_click=pick_tile, args=(index,), type="tertiary")

    sources, experiences = view.options(items)
    # 필터는 왼쪽 사이드바에 고정한다. 목록을 내려도 보이고 « 로 접는다 (v0.5.4 F1)
    with st.sidebar, st.container(border=True, key="box-filter"):  # 메인 카드와 같은 모양 (v0.6.1 F20)
        st.markdown("#### 필터 <span class='jv-muted'>📋 공고 목록에 적용</span>", unsafe_allow_html=True)
        filters = view.Filters(
            query=st.text_input("검색", placeholder="회사명·직무", key="search"),  # v0.5.3 F10
            # 처음엔 비워 두고 "전체"로 보인다. 고른 것이 있을 때만 거른다 (v0.5.2 F29)
            sources=st.multiselect("출처", sources, placeholder="전체", key="sources"),
            experiences=st.multiselect(
                "경력", experiences, placeholder="전체", help="신입·경력·무관으로 묶음", key="experiences"
            ),
            # 점수 정렬에서 평가 전은 늘 아래 (F40). 마감 임박 순은 점수와 상관없이 (v0.5.3 F8)
            sort=SORTS[st.selectbox("정렬", list(SORTS))],
            scored_only=st.toggle("평가된 공고만 보기", key="scored-only"),  # 기본은 전체 (v0.5.2 F32)
            recommended_only=st.toggle("추천 이상만 보기", key="recommended-only"),  # 강력 추천 + 추천 (v0.5.4 F12)
            applied_only=st.toggle("지원한 공고만 보기", key="applied-only"),  # v0.5.3 F11
            image_only=st.toggle("이미지 필요한 공고만 보기", key="image-only", help=IMAGE_HELP),  # v0.5.4 F2
            hidden_only=st.toggle(
                "관심 없는 공고만 보기", key="hidden-only", help="관심 없음으로 뺀 공고. 되돌리기로 목록에 다시 넣음"
            ),
        )
    shown = view.apply(items, filters)
    data = view.chart(shown)  # 필터를 지난 공고 중 높은 5개 (F42)
    if data:  # 점수 있는 공고가 있을 때만 칸을 보인다 (v0.6.1 F6)
        with st.container(border=True, key="box-chart"):  # 필터가 사이드바로 가서 가로 전체 (v0.5.4 F1)
            st.markdown(f"**종합점수 TOP {view.TOP}**")
            # 확대·끌기 없는 고정 차트. st.bar_chart는 늘 움직여서 vega-lite 명세로 그린다 (v0.6.1 F23)
            st.vega_lite_chart(spec=chart_spec(data), width="stretch")

    show_score_bar(rows)  # 목록 바로 위. 대상 수는 필터와 상관없이 전체 시트 기준 (F38)
    if st.session_state.get(PAGE_FILTERS) != filters:  # 필터·정렬을 바꾸면 1쪽부터 (F41)
        st.session_state[PAGE_FILTERS], st.session_state[PAGE] = filters, 1
    cards, number, pages = view.page(shown, st.session_state.get(PAGE, 1))
    first = (number - 1) * view.PAGE_SIZE
    where = f" · {first + 1}–{first + len(cards)}번째" if pages > 1 else ""
    st.caption(f"{len(shown)}건 / 전체 {len(items)}건{where}")
    known = my_skills()
    for card in cards:
        show_card(card, known)
    if pages > 1:
        show_pager(number, pages)


def my_skills() -> list[str]:
    """기술 칩에서 초록으로 보일 내 기술: 주력 + 다룰 수 있음 (v0.5.3 F4). 프로필이 없거나 깨졌으면 빈 목록."""
    try:
        values = profile_form.to_form(user_profile.read_raw(PROFILE))
    except user_profile.ProfileError:
        return []
    return [*values[("skills", "main")], *values[("skills", "can_use")]]


def remember_visit() -> None:
    """세션을 처음 열 때 지난번에 연 시각을 읽어 두고 지금으로 바꾼다 (v0.5.3 F9)."""
    if LAST_SEEN not in st.session_state:
        st.session_state[LAST_SEEN] = view.read_last_seen(view.LAST_SEEN)
        view.write_last_seen(view.LAST_SEEN, datetime.now())


def go_page(number: int) -> None:
    st.session_state[PAGE] = number


def show_pager(number: int, pages: int) -> None:
    """목록 아래 쪽 넘기기 (v0.5.2 F41). 누르면 다시 그리기 전에 쪽 번호를 바꾼다."""
    _, back, label, forward, _ = st.columns([2, 1, 1, 1, 2], vertical_alignment="center")
    back.button("◀ 이전", key="page-back", disabled=number <= 1, on_click=go_page, args=(number - 1,),
                use_container_width=True)  # fmt: skip
    label.markdown(f"<div style='text-align:center'><b>{number}</b> / {pages}쪽</div>", unsafe_allow_html=True)
    forward.button("다음 ▶", key="page-forward", disabled=number >= pages, on_click=go_page, args=(number + 1,),
                   use_container_width=True)  # fmt: skip


def field_key(field: profile_form.Field, default) -> str:
    """입력란 key. 기본값(파일·이력서 값)이 바뀌거나 칸을 비우면 새 key라 새 값으로 그려진다 (v0.5 F21, v0.5.5 F1)."""
    digest = hashlib.sha1(repr(default).encode()).hexdigest()[:8]
    generation = st.session_state.get(GENERATION, {}).get(field.keys, 0)
    return f"field-{'.'.join(field.keys)}-{generation}-{digest}"


def clear_field(keys: tuple) -> None:
    """↺: 이 칸만 화면에서 비운다. 파일은 저장을 누르기 전까지 그대로 (v0.5.5 F1)."""
    st.session_state.setdefault(CLEARED, set()).add(keys)
    generations = st.session_state.setdefault(GENERATION, {})
    generations[keys] = generations.get(keys, 0) + 1


@st.dialog("전체 초기화")
def confirm_clear_all() -> None:
    """모든 칸을 화면에서 비우기 전에 묻는다 (v0.5.5 F2)."""
    st.markdown("화면에 입력한 모든 칸과 이력서로 채운 값을 비웁니다.")
    st.caption("profile.yaml은 💾 저장을 누르기 전까지 그대로입니다. 새로고침하면 저장된 값이 다시 나옵니다.")
    clear, cancel = st.columns(2)
    # 콜백에서 비워야 창 안 버튼만 다시 그려질 때도 값이 바뀐다. 누르면 창을 닫는다
    if clear.button("비우기", type="primary", key="clear-all-yes", use_container_width=True, on_click=clear_all):
        st.rerun()
    if cancel.button("취소", key="clear-all-no", use_container_width=True):
        st.rerun()


def clear_all() -> None:
    for field in profile_form.FIELDS:
        clear_field(field.keys)
    st.session_state.pop(FILL, None)  # 이력서로 채운 값도 버린다 (F2)


def show_field(field: profile_form.Field, default, taken: list[str] = ()):
    label = field.label + (" *" if field.required else "")
    key = field_key(field, default)
    if field.kind == "pick":  # 추천 목록에서 고르고, 없으면 입력해 추가 (F10, F11)
        # 앞 칸에 고른 기술은 보기와 고른 값에서 뺀다 (v0.5.2 F37). key가 있어 다른 칸을 바꿔도 고른 값은 남는다
        current = st.session_state.get(key, default)
        st.session_state[key] = [item for item in current if item not in taken]
        choices = [item for item in profile_form.options(field.suggestions, current) if item not in taken]
        return st.multiselect(
            label, choices, key=key, accept_new_options=True, help=field.help, placeholder=field.placeholder
        )
    if field.kind == "years":  # 가로 슬라이더 (v0.5 F18)
        return st.slider(label, 0, max(profile_form.SLIDER_MAX, default), default, step=1, help=field.help, key=key)
    if field.kind == "degree":  # 최종 학력 고르기 + 전공 (F13)
        degree, major = default
        choices = ["", *profile_form.DEGREES]
        left, right = st.columns(2)
        picked = left.selectbox(
            label, choices, index=choices.index(degree), format_func=lambda d: d or "선택 안 함", help=field.help,
            key=f"{key}-degree",
        )  # fmt: skip
        return picked, right.text_input("전공", major, placeholder=field.placeholder, key=f"{key}-major")
    if field.kind == "culture":  # 눌러 고르기 + 직접 적기 (F12)
        picked, others = default
        chosen = st.pills(
            label, list(field.suggestions), selection_mode="multi", default=picked, help=field.help, key=f"{key}-pick"
        )
        text = st.text_area(
            "직접 적기 · 한 줄에 하나", others, placeholder=field.placeholder, height=80, key=f"{key}-text"
        )
        return chosen, text
    if field.kind == "lines":
        return st.text_area(
            f"{label} · 한 줄에 하나", default, placeholder=field.placeholder, height=90, help=field.help, key=key
        )
    return st.text_input(label, default, placeholder=field.placeholder, help=field.help, key=key)


def show_field_with_clear(field: profile_form.Field, default, taken: list[str]):
    """입력란 오른쪽 위에 ↺ (v0.5.5 F1)."""
    box, reset = st.columns([14, 1], vertical_alignment="top")
    reset.button(
        "↺", key=f"clear-{'.'.join(field.keys)}", on_click=clear_field, args=(field.keys,), type="tertiary",
        help="이 칸 비우기 (저장 전까지 파일은 그대로)",
    )  # fmt: skip
    with box:
        return show_field(field, default, taken)


def show_resume_fill(values: dict, fill: dict | None) -> None:
    """이력서·포트폴리오 파일 → LLM → 입력란 (v0.5.2 F16–F22). 저장은 하지 않는다."""
    # 제목은 접기 칸 이름. 형식·전송 안내는 파일 칸 ? 도움말로 (v0.6.1 F10, F18)
    if fill:  # 채운 칸 표시 (F20)
        st.markdown(
            "<span class='jv-muted'>이력서에서 채움</span> "
            + "".join(badge(label, "verdict") for label in fill["filled"]),
            unsafe_allow_html=True,
        )
        show_missing(fill.get("missing", []))
        if "경력 연수" in fill["filled"]:
            st.warning("경력 연수는 LLM이 계산한 값입니다. 맞는지 확인해 주세요.")
        st.caption("확인하고 고친 뒤 아래 **저장**을 눌러야 profile.yaml에 씁니다.")
        if st.button("채운 값 버리기", key="resume-discard"):
            st.session_state.pop(FILL, None)
            st.rerun()
    files = st.file_uploader(
        "이력서·포트폴리오 파일 (여러 개 가능)",
        type=[suffix[1:] for suffix in resume.EXTENSIONS],
        accept_multiple_files=True,
        key="resume-files",
        help=RESUME_HELP,  # N2, N3
    )
    run, toggle = st.columns([1, 2], vertical_alignment="center")
    overwrite = toggle.toggle("이미 적은 칸도 바꾸기", key="resume-overwrite")  # 기본은 빈 칸만 (F19)
    if not run.button("✨ 이력서로 채우기", disabled=not files, key="resume-fill"):
        return
    text, skipped = resume.read_files([(file.name, file.getvalue()) for file in files])
    for name, reason in skipped:  # 그 파일만 건너뜀 (F21)
        st.warning(f"{name}: {reason}")
    if not text:
        st.error("글자를 읽을 수 있는 파일이 없습니다.")
        return
    try:
        with st.spinner("LLM이 이력서를 읽는 중"):
            found = resume.ask(text)
    except resume.ResumeError as e:  # 아무 칸도 바꾸지 않음 (F21)
        st.error(f"이력서를 읽지 못했습니다: {e}")
        return
    except Exception as e:  # LLM 키·네트워크 오류. 키는 보이지 않는다
        st.error(runner.error_text(e))
        return
    merged, filled = resume.merge(values, found, overwrite)
    if not filled:
        st.info("새로 채울 칸이 없습니다.")
        show_missing(resume.missing(values, found))
        return
    st.session_state.pop(CLEARED, None)  # 이력서로 채우면 비운 표시는 버린다 (v0.5.5 F1)
    st.session_state[FILL] = {"values": merged, "filled": filled, "missing": resume.missing(merged, found)}
    st.rerun()


def show_missing(labels: list[str]) -> None:
    """이력서에 근거가 없어 비워 둔 칸 (v0.5.2 F35). 추측해 채우지 않고 직접 채우게 한다."""
    if labels:
        st.markdown(
            "<span class='jv-muted'>이력서에 없어 비워 둠</span> "
            + "".join(badge(f"입력 필요 · {label}", "mid") for label in labels),
            unsafe_allow_html=True,
        )


def show_profile() -> None:
    try:
        raw = user_profile.read_raw(PROFILE)  # 탭을 그릴 때마다 파일을 다시 읽는다 (v0.5 F21)
    except user_profile.ProfileError as e:
        st.error(str(e))  # 깨진 파일은 덮어쓰지 않는다
        return
    if raw is not None:
        try:
            _, warnings = user_profile.validate(raw)
            for warning in warnings:
                st.warning(warning)
        except user_profile.ProfileError as e:
            st.warning(f"지금 파일에 고칠 칸이 있습니다.\n\n{e}")

    fill = st.session_state.get(FILL)  # 이력서에서 채운 값. 저장 전까지 파일 대신 입력란 기본값 (v0.5.2 F18)
    # 프로필이 비어 있거나 방금 채웠으면 펼치고, 아니면 접어 둔다 (v0.6.1 F18)
    blank = profile_form.to_form(raw) == profile_form.to_form(None)
    fill_box = st.expander("📄 이력서·포트폴리오로 채우기", expanded=blank or bool(fill))  # 입력란을 그린 뒤 채운다
    badges = st.empty()  # 입력란을 그린 뒤 채운다 (F8)
    defaults = fill["values"] if fill else profile_form.to_form(raw)
    empty = profile_form.to_form(None)
    for keys in st.session_state.get(CLEARED, set()):  # 비운 칸은 빈 값으로 (v0.5.5 F1, F2)
        defaults[keys] = empty[keys]
    picks = [field for field in profile_form.FIELDS if field.kind == "pick"]
    current = {field_key(field, defaults[field.keys]) for field in picks}
    prefixes = tuple(f"field-{'.'.join(field.keys)}-" for field in picks)
    for old in [key for key in st.session_state if str(key).startswith(prefixes) and key not in current]:
        del st.session_state[old]  # 고르기 칸은 값을 직접 넣으므로 예전 기본값의 고른 값은 버린다
    values = {}
    # 입력하는 동안 필수 칸 배지가 바뀌도록 st.form을 쓰지 않는다 (F8).
    # key를 주지 않아 파일이 바뀌면 입력란이 새 값으로 그려진다 (v0.5 F21)
    for row in (profile_form.GROUPS[:2], profile_form.GROUPS[2:]):  # 2×2 (F9, F19)
        for column, (group, title, note) in zip(st.columns(2), row, strict=True):
            with column.container(border=True, key=f"box-profile-{group}"):
                st.markdown(f"#### {title} <span class='jv-muted'>{note}</span>", unsafe_allow_html=True)
                for field in profile_form.group_fields(group):
                    taken = profile_form.taken(values, field.keys)
                    values[field.keys] = show_field_with_clear(field, defaults[field.keys], taken)
    badges.markdown(
        "".join(
            badge(f"{'✓' if done else '✗'} {name}", "high" if done else "low")
            for name, done in profile_form.required_status(values)
        ),
        unsafe_allow_html=True,
    )
    with fill_box:
        show_resume_fill(values, fill)

    save, clear_all, _ = st.columns([1, 1, 6], vertical_alignment="center")
    # 전체 초기화는 확인 창을 거친다 (v0.5.5 F2)
    if clear_all.button("전체 초기화", key="profile-clear-all", help="화면 입력만 비움. 저장 전까지 파일은 그대로"):
        confirm_clear_all()
    if save.button("💾 저장", type="primary", key="profile-save"):
        try:
            profile, _ = user_profile.validate(profile_form.from_form(values))
        except user_profile.ProfileError as e:
            st.error(str(e))  # 저장하지 않는다 (v0.5 F20)
            return
        user_profile.save(profile, PROFILE)
        st.session_state.pop(FILL, None)  # 저장한 뒤에는 파일 값을 기본값으로
        st.session_state.pop(CLEARED, None)
        st.success(f"저장함 ({datetime.now():%Y-%m-%d %H:%M:%S})")


KEY_SAVED = "key_saved"  # 방금 키를 저장했는지 (v0.6 F4)
KEY_DELETED = "key_deleted"  # 방금 키를 지웠는지 (v0.6.1 F14)
KEY_PROMPTED = "key_prompted"  # 키가 없어 창을 한 번 띄웠는지 (v0.6.1 F17)
KEY_ERROR = "key_error"  # 저장하지 못한 이유 (v0.6.1 F17)


def delete_key() -> None:
    st.session_state[KEY_DELETED] = settings.delete_key()


def save_key(field: str) -> None:
    """저장 버튼 콜백. 창 안 버튼만 다시 그려질 때도 저장되게 콜백에서 한다 (v0.6.1 F17)."""
    try:
        settings.save_key(st.session_state.get(field, ""))
    except ValueError as e:  # 문구에 키는 들어 있지 않다 (F5)
        st.session_state[KEY_ERROR] = str(e)
        return
    st.session_state[KEY_SAVED] = True


def save_key_form(where: str) -> None:
    field = f"key-input-{where}"
    with st.form(f"key_form_{where}", clear_on_submit=True, border=False):
        box, button = st.columns([4, 1], vertical_alignment="bottom")  # 입력란과 저장을 한 줄에 (v0.6.1 F2)
        box.text_input(
            settings.key_name(), type="password", placeholder="여기에 붙여넣기", label_visibility="collapsed", key=field
        )
        button.form_submit_button("저장", type="primary", use_container_width=True, on_click=save_key, args=(field,))
    error = st.session_state.pop(KEY_ERROR, None)
    if error:
        st.error(error)


@st.dialog("🔑 LLM 키")
def show_key_dialog() -> None:
    """키 넣기·바꾸기·지우기 창. 화면 위 🔑 버튼으로 연다 (v0.6 F4, F5, v0.6.1 F14, F17)."""
    if st.session_state.get(KEY_SAVED):  # 저장했으면 창을 닫고 화면 전체를 다시 그린다
        st.rerun()
    deleted = st.session_state.pop(KEY_DELETED, None)
    if deleted is not None:  # 이 PC에서만 지운다. Google의 키는 그대로 (F14)
        st.info(
            "이 PC에서 키를 지웠습니다. 키 자체를 없애려면 "
            f"[Google AI Studio]({settings.KEY_PAGES['GOOGLE_API_KEY']})에서 삭제하세요."
            + ("" if deleted else " .env에 적은 키는 .env에서 직접 지워야 다음 실행에도 지워집니다.")
        )
    page = settings.key_page()
    if settings.has_key():
        st.markdown(f"지금 키 **{settings.masked()}** · 새 키를 넣으면 바뀝니다.")
        st.caption(".env에 키를 적어 두었다면 다음 실행부터는 .env 값이 우선합니다.")
        save_key_form("change")
        # PC를 넘기거나 키가 샜다고 의심될 때 (v0.6.1 F14)
        st.button("🗑 이 PC에서 키 삭제", key="key-delete", on_click=delete_key,
                  help="이 PC에 저장한 키만 지웁니다. Google에서 키를 없애지는 않습니다")  # fmt: skip
        return
    st.markdown("**LLM 키를 넣어 주세요**")
    st.caption(
        f"평가·이력서 채우기에 씁니다. [{page}]({page})에서 무료로 발급받아 붙여넣으세요. "
        "이 PC에만 저장되고 화면에는 끝 4자리만 보입니다. 처음이면 📖 사용법도 보세요."
    )
    save_key_form("new")


def key_button(column) -> None:
    """화면 위 🔑 버튼 (v0.6.1 F17). 키가 없으면 눈에 띄는 색, 처음 연 화면에서 한 번 창을 띄운다."""
    if st.session_state.pop(KEY_SAVED, False):
        st.toast(f"키를 저장함 ({settings.masked()}). 이제 평가와 이력서 채우기를 쓸 수 있습니다.", icon="🔑")
    missing = not settings.has_key()
    label = "🔑 키 넣기" if missing else f"🔑 키 {settings.masked()}"
    clicked = column.button(label, type="primary" if missing else "secondary", use_container_width=True, key="key-open")
    first = missing and not st.session_state.get(KEY_PROMPTED)
    pending = KEY_ERROR in st.session_state or KEY_DELETED in st.session_state  # 창 안 안내를 보여야 함
    if clicked or first or pending:
        st.session_state[KEY_PROMPTED] = True
        show_key_dialog()


def main() -> None:
    load_dotenv()
    settings.load()  # .env 다음, 비어 있는 값만 (v0.6 D6)
    st.set_page_config(page_title="JOBVIS", layout="wide")
    st.markdown(css(st.context.theme.type), unsafe_allow_html=True)  # 테마를 바꾸면 다시 그린다 (F13)
    remember_visit()
    if settings.has_key():  # 키가 없으면 키 창이 먼저 뜬다. 창은 한 번에 하나 (v0.6.1 F17)
        open_guide_first_time()
    title, key, guide, refresh = st.columns([4, 1.2, 1, 1], vertical_alignment="center")
    title.markdown(
        f'<div class="jv-hero"><h1>JOBVIS</h1><p>{TAGLINE}</p></div>',
        unsafe_allow_html=True,
    )  # F20
    if guide.button("📖 사용법", use_container_width=True, key="guide"):  # 새 창 (v0.5.4 F9)
        show_guide()
    if refresh.button("🔄 새로고침", use_container_width=True):
        reload_rows()
    key_button(key)
    postings_tab, profile_tab = st.tabs(["📋 공고", "👤 프로필"])  # v0.5 F1
    with postings_tab:
        show_postings()
    with profile_tab:
        show_profile()


if __name__ == "__main__":  # 테스트에서 import할 때는 화면을 그리지 않는다
    main()

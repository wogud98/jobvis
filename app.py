"""JOBVIS 화면. 실행: streamlit run app.py (PC 전용, localhost. 배포하지 않음, v0.5 N4).

테마는 .streamlit/config.toml과 아래 CSS (v0.5.1 F17–F19).

시트는 읽기만 한다. 파일은 profile.yaml과 data/inbox/에만 쓴다 (F8).
정렬·필터·카드·요약 칸은 agent/view.py, 프로필 입력란은 agent/profile_form.py, 검사는 agent/user_profile.py,
이미지 저장은 agent/inbox.py에 있다.
"""

from datetime import datetime
from html import escape

import streamlit as st
from dotenv import load_dotenv

from agent import inbox, profile_form, sheets, user_profile, view

PROFILE = user_profile.DEFAULT
SUMMARY_FIELDS = ("요약", "주요업무", "우대사항", "기술스택")
SCORE_FIELDS = ("기술", "경력", "문화", "방향")
CHART_HEIGHT = 230  # 필터 카드 높이와 비슷하게 차트가 카드를 채우도록 (F21)
ACCENT = "#6d5ef5"  # .streamlit/config.toml의 primaryColor와 같게
TRUST_CLASS = {"높음": "high", "보통": "mid", "낮음": "low"}  # 신뢰 배지 색 (F5)

POSTINGS_GUIDE = """
1. 터미널에서 `python main.py --keyword 백엔드`로 공고를 모으고 `--score`로 평가합니다.
   이 화면은 결과를 보기만 합니다.
2. 카드는 종합점수 높은 순입니다.
   **자세히**를 누르면 요약, 항목별 점수, 강점·부족한 점, 원문 링크가 나옵니다.
3. **신뢰 낮음**은 본문 없이 제목만 보고 매긴 점수라 흐리게 보입니다.
   카드에 공고 이미지를 넣고 `--inbox`를 실행하면 본문이 채워집니다.
4. 시트가 바뀌었으면 오른쪽 위 **새로고침**을 누릅니다.
"""
PROFILE_GUIDE = """
- `*` 표시한 필수 칸 3개만 채우면 평가할 수 있습니다. 나머지는 채울수록 점수 근거가 정확해집니다.
- 목록 칸은 눌러서 고르고, 목록에 없으면 직접 입력한 뒤 Enter로 추가합니다.
- **저장**을 누르면 `profile.yaml`에 씁니다. 파일을 직접 고쳐도 됩니다(주석은 화면에서 저장하면 사라짐).
"""

# 글래스모피즘 카드와 그라데이션 배경 (F17–F19). Streamlit 내부 클래스 대신 key로 붙는 st-key-* 클래스와
# data-testid에만 건다 (N5)
CSS = """
<style>
.stApp { background: linear-gradient(135deg, #e9e4ff 0%, #dceefe 45%, #e2f7ef 100%); }
[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 1200px; padding-top: 2rem; }
div[class*="st-key-glass"], div[data-testid="stExpander"] details {
  background: rgba(255, 255, 255, 0.55) !important;
  backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
  border: 1px solid rgba(255, 255, 255, 0.75) !important; border-radius: 20px !important;
  box-shadow: 0 8px 28px rgba(80, 70, 160, 0.10);
}
div[class*="st-key-glass"] { padding: 18px 20px; }
div[class*="st-key-glass-dim"] { opacity: 0.55; }
div[class*="st-key-glass"] div[class*="st-key-glass"] { box-shadow: none; }
/* 종합점수·필터 카드 높이를 맞춘다 (F21). 열은 이미 같은 높이라 카드가 열을 채우게 한다 */
div[data-testid="stLayoutWrapper"]:has(> div[class*="st-key-glass-chart"]),
div[data-testid="stLayoutWrapper"]:has(> div[class*="st-key-glass-filters"]) { flex: 1 1 auto; }
div[class*="st-key-glass-chart"], div[class*="st-key-glass-filters"] { height: 100%; }
/* 고르기 칸의 키워드 아무 데나 눌러도 지워지게, 삭제 버튼이 키워드 전체를 덮는다 (F22) */
div[data-testid="stMultiSelect"] [data-tag] { position: relative; cursor: pointer; padding-right: 22px; }
div[data-testid="stMultiSelect"] [data-tag] > button[aria-label^="Remove"] {
  position: absolute; inset: 0; width: 100%; height: 100%; margin: 0; padding: 0 7px;
  display: flex; align-items: center; justify-content: flex-end;
  background: transparent; border: 0; border-radius: inherit; cursor: pointer;
}
div[data-testid="stMultiSelect"] [data-tag] > button[aria-label^="Remove"] svg { width: 0.7em; height: 0.7em; }
div[data-testid="stMultiSelect"] [data-tag]:hover { filter: brightness(0.88); text-decoration: line-through; }
div[data-testid="stMetricValue"] { font-size: 2.1rem; font-weight: 700; color: #3b2f8f; }
.jv-hero h1 { margin: 0; padding: 0; font-size: 2.2rem; color: #2c2370; }
.jv-hero p { margin: 0; color: #5a5680; }
.jv-score { font-size: 2rem; font-weight: 800; line-height: 1; color: #3b2f8f; }
.jv-muted { color: #5f5b85; font-size: 0.9rem; }
.jv-badge { display: inline-block; margin-right: 6px; padding: 2px 10px; border-radius: 999px;
  font-size: 0.82rem; font-weight: 600; }
.jv-verdict { background: #ece8ff; color: #3b2f8f; }
.jv-high { background: #d9f5e6; color: #11734a; }
.jv-mid { background: #fff1cc; color: #7a5600; }
.jv-low { background: #fde4e4; color: #a12d2d; }
</style>
"""


@st.cache_data(show_spinner="시트를 읽는 중")
def load_rows() -> list[dict]:
    # 열 때 한 번 읽고, 새로고침을 누를 때만 다시 읽는다 (F7)
    return sheets.read_rows_readonly()


def show_upload(card: view.Card) -> None:
    files = st.file_uploader(
        "공고 이미지 넣기 (끌어다 놓거나 파일 고르기)",
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
        # 화면은 OCR을 돌리지 않는다 (F48)
        st.success(f"저장함: {', '.join(saved)}. 터미널에서 `python main.py --inbox`를 실행하세요.")


def show_guide(text: str) -> None:
    with st.expander("📖 사용법"):  # 기본 접힘 (F1, F7)
        st.markdown(text)


def badge(text: str, kind: str) -> str:
    return f'<span class="jv-badge jv-{kind}">{escape(text)}</span>'


def show_card(card: view.Card) -> None:
    # 시트 글자(회사·직무 등)는 HTML로 넣기 전에 escape한다
    key = f"glass-{'dim-' if card.dim else ''}card-{card.row}"  # 신뢰 낮음은 흐리게 (v0.5 F34, F5)
    with st.container(border=True, key=key):
        score, head = st.columns([1, 7], vertical_alignment="center")
        number = "-" if card.score is None else str(card.score)  # F6
        score.markdown(
            f'<div class="jv-score">{number}</div><div class="jv-muted">{escape(card.stars)}</div>',
            unsafe_allow_html=True,
        )
        badges = badge(card.verdict, "verdict") + (
            badge(f"신뢰 {card.trust}", TRUST_CLASS.get(card.trust, "mid")) if card.trust else ""
        )
        meta = " · ".join(part for part in (card.source, card.experience, f"마감 {card.deadline or '없음'}") if part)
        head.markdown(
            f"**{escape(card.company)} · {escape(card.title)}**  \n"
            f"{badges}<span class='jv-muted'>{escape(meta)}</span>",
            unsafe_allow_html=True,
        )
        with st.expander("자세히"):  # 펼침 내용은 v0.5와 같음 (F4)
            for name in SUMMARY_FIELDS:
                st.markdown(f"**{name}** {card.details[name]}")
            st.markdown(" · ".join(f"**{name}** {card.details[name]}" for name in SCORE_FIELDS))
            st.markdown(f"**강점** {card.details['강점']}")
            st.markdown(f"**부족한 점** {card.details['부족한 점']}")
            if card.trust:
                st.markdown(f"**신뢰** {card.trust} (본문: {card.body or '없음'})")
            if card.adjust:
                st.markdown(f"**보정** {card.adjust}")
            if card.url:
                st.link_button("원문 열기", card.url)  # 새 탭 (v0.5 F4)
            if card.can_upload:
                show_upload(card)


def show_postings() -> None:
    show_guide(POSTINGS_GUIDE)
    try:
        rows = load_rows()
    except Exception as e:
        st.error(view.error_message(e))  # v0.5 F9
        return
    if not rows:
        st.info("공고 없음, 터미널에서 수집하세요. 예: `python main.py --keyword 백엔드`")  # v0.5 F10
        return

    items = view.cards(rows)
    for column, (label, value, note) in zip(st.columns(4), view.summary(items), strict=True):  # F2
        with column.container(border=True, key=f"glass-summary-{label}"):
            st.metric(label, value)
            st.caption(note)

    chart_box, filter_box = st.columns([2, 1])  # F3, F19
    sources, experiences = view.options(items)
    with filter_box.container(border=True, key="glass-filters"):
        st.markdown("**필터**")
        filters = view.Filters(
            sources=st.multiselect("출처", sources, default=sources),
            experiences=st.multiselect("경력", experiences, default=experiences),
            show_unscored=st.toggle("평가 전 공고 보기"),
        )
    shown = view.apply(items, filters)
    with chart_box.container(border=True, key="glass-chart"):
        st.markdown("**종합점수**")
        data = view.chart(shown)
        if data:  # 필터를 지난 공고만 (v0.5 F5)
            st.bar_chart(
                {"공고": [name for name, _ in data], "종합점수": [score for _, score in data]},
                x="공고",
                y="종합점수",
                horizontal=True,
                color=ACCENT,
                height=CHART_HEIGHT,
            )
        else:
            st.caption("점수 있는 공고가 없습니다.")

    st.caption(f"{len(shown)}건 / 전체 {len(items)}건")
    for card in shown:
        show_card(card)


def show_field(field: profile_form.Field, default):
    label = field.label + (" *" if field.required else "")
    if field.kind == "pick":  # 추천 목록에서 고르고, 없으면 입력해 추가 (F10, F11)
        return st.multiselect(
            label, profile_form.options(field.suggestions, default), default=default,
            accept_new_options=True, help=field.help, placeholder=field.placeholder,
        )  # fmt: skip
    if field.kind == "years":  # 가로 슬라이더 (v0.5 F18)
        return st.slider(label, 0, max(profile_form.SLIDER_MAX, default), default, step=1, help=field.help)
    if field.kind == "degree":  # 최종 학력 고르기 + 전공 (F13)
        degree, major = default
        choices = ["", *profile_form.DEGREES]
        left, right = st.columns(2)
        picked = left.selectbox(
            label, choices, index=choices.index(degree), format_func=lambda d: d or "선택 안 함", help=field.help
        )
        return picked, right.text_input("전공", major, placeholder=field.placeholder)
    if field.kind == "culture":  # 눌러 고르기 + 직접 적기 (F12)
        picked, others = default
        chosen = st.pills(label, list(field.suggestions), selection_mode="multi", default=picked, help=field.help)
        return chosen, st.text_area("직접 적기 · 한 줄에 하나", others, placeholder=field.placeholder, height=80)
    if field.kind == "lines":
        return st.text_area(
            f"{label} · 한 줄에 하나", default, placeholder=field.placeholder, height=90, help=field.help
        )
    return st.text_input(label, default, placeholder=field.placeholder, help=field.help)


def show_profile() -> None:
    show_guide(PROFILE_GUIDE)
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

    badges = st.empty()  # 입력란을 그린 뒤 채운다 (F8)
    defaults = profile_form.to_form(raw)
    values = {}
    # 입력하는 동안 필수 칸 배지가 바뀌도록 st.form을 쓰지 않는다 (F8).
    # key를 주지 않아 파일이 바뀌면 입력란이 새 값으로 그려진다 (v0.5 F21)
    for row in (profile_form.GROUPS[:2], profile_form.GROUPS[2:]):  # 2×2 (F9, F19)
        for column, (group, title, note) in zip(st.columns(2), row, strict=True):
            with column.container(border=True, key=f"glass-profile-{group}"):
                st.markdown(f"#### {title} <span class='jv-muted'>{note}</span>", unsafe_allow_html=True)
                for field in profile_form.group_fields(group):
                    values[field.keys] = show_field(field, defaults[field.keys])
    badges.markdown(
        "".join(
            badge(f"{'✓' if done else '✗'} {name}", "high" if done else "low")
            for name, done in profile_form.required_status(values)
        ),
        unsafe_allow_html=True,
    )

    if st.button("💾 저장", type="primary", key="profile-save"):
        try:
            profile, _ = user_profile.validate(profile_form.from_form(values))
        except user_profile.ProfileError as e:
            st.error(str(e))  # 저장하지 않는다 (v0.5 F20)
            return
        user_profile.save(profile, PROFILE)
        st.success(f"저장함 ({datetime.now():%Y-%m-%d %H:%M:%S})")


def main() -> None:
    load_dotenv()
    st.set_page_config(page_title="JOBVIS", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    title, refresh = st.columns([6, 1], vertical_alignment="center")
    title.markdown(
        '<div class="jv-hero"><h1>JOBVIS</h1><p>채용공고를 모아 내 프로필과 맞춰 본 결과</p></div>',
        unsafe_allow_html=True,
    )  # F20
    if refresh.button("🔄 새로고침", use_container_width=True):
        load_rows.clear()
    postings_tab, profile_tab = st.tabs(["📋 공고", "👤 프로필"])  # v0.5 F1
    with postings_tab:
        show_postings()
    with profile_tab:
        show_profile()


main()

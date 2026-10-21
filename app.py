"""JOBVIS 화면. 실행: streamlit run app.py (PC 전용, localhost. 배포하지 않음, v0.5 N4)

시트는 읽기만 한다. 파일은 profile.yaml과 data/inbox/에만 쓴다 (F8).
정렬·필터·카드 내용은 agent/view.py, 프로필 검사는 agent/user_profile.py, 이미지 저장은 agent/inbox.py에 있다.
"""

from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from agent import inbox, sheets, user_profile, view

PROFILE = user_profile.DEFAULT
SUMMARY_FIELDS = ("요약", "주요업무", "우대사항", "기술스택")
SCORE_FIELDS = ("기술", "경력", "문화", "방향")


@st.cache_data(show_spinner="시트를 읽는 중")
def load_rows() -> list[dict]:
    # 열 때 한 번 읽고, 새로고침을 누를 때만 다시 읽는다 (F7)
    return sheets.read_rows_readonly()


def card_title(card: view.Card) -> str:
    score = "-" if card.score is None else str(card.score)
    parts = [score, card.stars, card.verdict, f"{card.company} · {card.title}", f"마감 {card.deadline or '없음'}"]
    parts += [card.source] + ([f"신뢰 {card.trust}"] if card.trust else [])
    text = " | ".join(part for part in parts if part)
    if card.dim:  # 신뢰 낮음은 흐리게 (F34). 대괄호는 색 문법과 겹쳐 바꾼다
        return ":gray[" + text.replace("[", "(").replace("]", ")") + "]"
    return text


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


def show_card(card: view.Card) -> None:
    with st.expander(card_title(card)):
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
            st.link_button("원문 열기", card.url)  # 새 탭 (F4)
        if card.can_upload:
            show_upload(card)


def show_postings() -> None:
    try:
        rows = load_rows()
    except Exception as e:
        st.error(view.error_message(e))  # F9
        return
    if not rows:
        st.info("공고 없음, 터미널에서 수집하세요. 예: `python main.py --keyword 백엔드`")  # F10
        return

    items = view.cards(rows)
    sources, experiences = view.options(items)
    left, middle, right = st.columns(3)
    filters = view.Filters(
        sources=left.multiselect("출처", sources, default=sources),
        experiences=middle.multiselect("경력", experiences, default=experiences),
        show_unscored=right.toggle("평가 전 공고 보기"),
    )
    shown = view.apply(items, filters)

    data = view.chart(shown)
    if data:  # 필터를 지난 공고만 (F5)
        st.bar_chart(
            {"공고": [name for name, _ in data], "종합점수": [score for _, score in data]},
            x="공고",
            y="종합점수",
            horizontal=True,
        )
    st.caption(f"{len(shown)}건 / 전체 {len(items)}건")
    for card in shown:
        show_card(card)


def show_profile() -> None:
    st.caption(f"`{PROFILE}`에 저장합니다. 파일을 직접 고쳐도 됩니다. 화면에서 저장하면 파일의 주석은 사라집니다.")
    try:
        raw = user_profile.read_raw(PROFILE)  # 탭을 그릴 때마다 파일을 다시 읽는다 (F21)
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

    defaults = user_profile.to_form(raw)
    values = {}
    with st.form("profile"):
        # key를 주지 않는다. 파일이 바뀌어 기본값이 바뀌면 입력란도 새 값으로 다시 그려진다 (F21)
        for keys, label, kind in user_profile.FORM_FIELDS:
            if kind == "years":  # 가로 슬라이더 (F18)
                top = max(user_profile.SLIDER_MAX, defaults[keys])
                values[keys] = st.slider(label, 0, top, defaults[keys], step=1)
            elif kind == "list":  # 한 줄에 하나씩 (F19)
                values[keys] = st.text_area(f"{label} · 한 줄에 하나", defaults[keys])
            else:
                values[keys] = st.text_input(label, defaults[keys])
        submitted = st.form_submit_button("저장")

    if submitted:
        try:
            profile, _ = user_profile.validate(user_profile.from_form(values))
        except user_profile.ProfileError as e:
            st.error(str(e))  # 저장하지 않는다 (F20)
            return
        user_profile.save(profile, PROFILE)
        st.success(f"저장함 ({datetime.now():%Y-%m-%d %H:%M:%S})")


def main() -> None:
    load_dotenv()
    st.set_page_config(page_title="JOBVIS", layout="wide")
    title, refresh = st.columns([5, 1])
    title.title("JOBVIS")
    if refresh.button("새로고침"):
        load_rows.clear()
    postings_tab, profile_tab = st.tabs(["공고", "프로필"])  # F1
    with postings_tab:
        show_postings()
    with profile_tab:
        show_profile()


main()

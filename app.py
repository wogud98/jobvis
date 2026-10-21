"""JOBVIS 화면. 실행: streamlit run app.py (PC 전용, localhost. 배포하지 않음, v0.5 N4).

테마는 .streamlit/config.toml과 아래 CSS (v0.5.1 F17–F19).

수집·평가·받은함 버튼은 agent/runner.py를 별도 스레드로 돌린다 (v0.5.2). 이력서 채우기는 agent/resume.py.
정렬·필터·카드·요약 칸은 agent/view.py, 프로필 입력란은 agent/profile_form.py, 검사는 agent/user_profile.py,
이미지 저장은 agent/inbox.py에 있다.
"""

import hashlib
from datetime import datetime
from html import escape

import streamlit as st
from dotenv import load_dotenv

from agent import inbox, ocr, profile_form, resume, runner, sheets, user_profile, view

PROFILE = user_profile.DEFAULT
SUMMARY_FIELDS = ("요약", "주요업무", "우대사항", "기술스택")
SCORE_FIELDS = ("기술", "경력", "문화", "방향")
CHART_HEIGHT = 230  # 필터 카드 높이와 비슷하게 차트가 카드를 채우도록 (F21)
ACCENT = "#059669"  # .streamlit/config.toml의 primaryColor와 같게
FILL = "profile_fill"  # 이력서에서 채운 입력란 값 (session_state 키)
CHECKS = "check_overrides"  # 화면에서 바꾼 평가 체크 {시트 줄: 체크} (v0.5.2 F39)
CHECK_ERROR = "check_error"
TRUST_CLASS = {"높음": "high", "보통": "mid", "낮음": "low"}  # 신뢰 배지 색 (F5)

POSTINGS_GUIDE = """
1. **수집** 카드에 키워드를 넣고 수집을 누릅니다. 30건 수집은 몇 분 걸립니다.
   공고 카드의 **평가** 칸을 체크하고 목록 위 **🧮 체크한 공고 평가**를 누릅니다(평가 전 전부도 가능).
   터미널(`python main.py --keyword 백엔드`, `--score`)로 해도 결과는 같습니다.
2. 카드는 종합점수 높은 순입니다.
   **자세히**를 누르면 요약, 항목별 점수, 강점·부족한 점, 원문 링크가 나옵니다.
3. **신뢰 낮음**은 본문 없이 제목만 보고 매긴 점수라 흐리게 보입니다.
   카드에 공고 이미지를 넣고 **받은함 읽기**를 누르면 본문이 채워집니다.
4. 시트가 바뀌었으면 오른쪽 위 **새로고침**을 누릅니다.
"""
PROFILE_GUIDE = """
- `*` 표시한 필수 칸 3개만 채우면 평가할 수 있습니다. 나머지는 채울수록 점수 근거가 정확해집니다.
- 목록 칸은 눌러서 고르고, 목록에 없으면 직접 입력한 뒤 Enter로 추가합니다.
- 이력서·포트폴리오 파일을 올리면 빈 칸을 채워 줍니다. 확인하고 고친 뒤 저장하세요.
- **저장**을 누르면 `profile.yaml`에 씁니다. 파일을 직접 고쳐도 됩니다(주석은 화면에서 저장하면 사라짐).
"""

# 네오 브루탈리즘 (v0.5.2 F28): 굵은 검정 테두리, 흐림 없는 딱딱한 그림자, 단색 면, 초록 포인트 하나.
# 카드는 key가 "box-"로 시작하는 컨테이너. Streamlit 내부 클래스 대신 key로 붙는 st-key-* 클래스와
# data-testid에만 건다 (v0.5.1 N5)
CSS = """
<style>
:root { --jv-ink: #111111; --jv-paper: #fffdf5; --jv-green: #059669; }
.stApp { background: var(--jv-paper); }
[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 1200px; padding-top: 2rem; }
/* 카드: 흰 면 + 3px 검정 테두리 + 오른쪽 아래 딱 떨어지는 그림자 */
div[class*="st-key-box"] {
  background: #ffffff !important; border: 3px solid var(--jv-ink) !important; border-radius: 8px !important;
  box-shadow: 6px 6px 0 var(--jv-ink); padding: 18px 20px;
}
div[class*="st-key-box"] div[class*="st-key-box"] { box-shadow: 3px 3px 0 var(--jv-ink); }
div[class*="st-key-box-dim"] { opacity: 0.55; }
/* 요약 칸 4개는 단색 면으로 구분한다 */
div[class*="st-key-box-summary-0"] { background: #ffe066 !important; }
div[class*="st-key-box-summary-1"] { background: #a5d8ff !important; }
div[class*="st-key-box-summary-2"] { background: #8ce99a !important; }
div[class*="st-key-box-summary-3"] { background: #ffc9c9 !important; }
div[data-testid="stExpander"] details {
  background: #ffffff; border: 2px solid var(--jv-ink) !important; border-radius: 6px !important;
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
  border: 2px solid var(--jv-ink) !important; border-radius: 6px !important; background: #ffffff !important;
}
div[data-testid="stAlert"] > div {
  border: 2px solid var(--jv-ink); border-radius: 6px; box-shadow: 3px 3px 0 var(--jv-ink);
}
/* 종합점수·필터 카드 높이를 맞춘다 (v0.5.1 F21). 열은 이미 같은 높이라 카드가 열을 채우게 한다 */
div[data-testid="stLayoutWrapper"]:has(> div[class*="st-key-box-chart"]),
div[data-testid="stLayoutWrapper"]:has(> div[class*="st-key-box-filters"]) { flex: 1 1 auto; }
div[class*="st-key-box-chart"], div[class*="st-key-box-filters"] { height: 100%; }
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
div[data-testid="stMetricValue"] { font-size: 2.4rem; font-weight: 900; color: var(--jv-ink); }
.jv-hero h1 { margin: 0; padding: 0 6px; font-size: 2.6rem; font-weight: 900; color: var(--jv-ink);
  letter-spacing: -0.03em; display: inline-block; background: linear-gradient(transparent 58%, #6ee7b7 58%); }
.jv-hero p { margin: 4px 0 0; color: #333333; font-weight: 600; }
.jv-score { font-size: 2.2rem; font-weight: 900; line-height: 1; color: var(--jv-green); }
.jv-muted { color: #444444; font-size: 0.9rem; }
.jv-badge { display: inline-block; margin-right: 6px; padding: 1px 9px; border: 2px solid var(--jv-ink);
  border-radius: 4px; font-size: 0.8rem; font-weight: 800; }
.jv-verdict { background: #ffffff; color: var(--jv-ink); }
.jv-high { background: #8ce99a; color: var(--jv-ink); }
.jv-mid { background: #ffe066; color: var(--jv-ink); }
.jv-low { background: #ffa8a8; color: var(--jv-ink); }
</style>
"""


@st.cache_data(show_spinner="시트를 읽는 중")
def load_rows() -> list[dict]:
    # 열 때 한 번 읽고, 새로고침을 누를 때만 다시 읽는다 (F7)
    return sheets.read_rows_readonly()


def reload_rows() -> None:
    """시트를 다시 읽게 한다. 화면에서 바꾼 체크는 시트에 이미 썼으니 버린다."""
    load_rows.clear()
    st.session_state.pop(CHECKS, None)
    for key in [key for key in st.session_state if str(key).startswith("check-")]:
        del st.session_state[key]


def toggle_check(row: int) -> None:
    """카드 체크 칸을 바꾸면 시트 "평가" 칸에 바로 쓴다 (v0.5.2 F39). 실패하면 체크를 되돌린다."""
    key = f"check-{row}"
    checked = bool(st.session_state.get(key))
    try:
        sheets.set_check(row, checked)
    except Exception as e:  # 키·경로는 보이지 않는다
        st.session_state.pop(key, None)  # 시트 값으로 다시 그림
        st.session_state[CHECK_ERROR] = f"체크를 시트에 쓰지 못했습니다. {runner.error_text(e)}"
        return
    st.session_state.setdefault(CHECKS, {})[row] = checked


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
    key = f"box-{'dim-' if card.dim else ''}card-{card.row}"  # 신뢰 낮음은 흐리게 (v0.5 F34, F5)
    with st.container(border=True, key=key):
        check, score, head = st.columns([0.7, 1, 7], vertical_alignment="center")
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
        badges = badge(card.verdict, "verdict") + (
            badge(f"신뢰 {card.trust}", TRUST_CLASS.get(card.trust, "mid")) if card.trust else ""
        )
        meta = " · ".join(part for part in (card.source, card.experience, f"마감 {card.deadline or '없음'}") if part)
        head.markdown(
            f"**{escape(card.company)} · {escape(card.title)}**  \n"
            f"{badges}<span class='jv-muted'>{escape(meta)}</span>",
            unsafe_allow_html=True,
        )
        with st.expander("자세히"):
            if card.score is None:  # 평가 전·제외: 수집 칸과 원문 앞부분 (v0.5.2 F31)
                show_unscored_details(card)
            else:
                show_scored_details(card)
            if card.url:
                st.link_button("원문 열기", card.url)  # 새 탭 (v0.5 F4)
            if card.can_upload:
                show_upload(card)


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


def show_scored_details(card: view.Card) -> None:
    # 평가한 공고의 펼침 내용은 v0.5와 같음 (F4)
    for name in SUMMARY_FIELDS:
        st.markdown(f"**{name}** {card.details[name]}")
    st.markdown(" · ".join(f"**{name}** {card.details[name]}" for name in SCORE_FIELDS))
    st.markdown(f"**강점** {card.details['강점']}")
    st.markdown(f"**부족한 점** {card.details['부족한 점']}")
    if card.trust:
        st.markdown(f"**신뢰** {card.trust} (본문: {card.body or '없음'})")
    if card.adjust:
        st.markdown(f"**보정** {card.adjust}")


@st.fragment(run_every=1.0)
def show_live_job() -> None:
    """실행 중인 작업의 진행 상황. 1초마다 이 부분만 다시 그린다 (F5, F9)."""
    job = runner.current()
    if job is None:
        return
    if job.finished:
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
    # 결과 한 줄, 할 일, 문제만 보이고 나머지는 접어 둔다 (F24)
    st.success(f"{escape(result.headline)}  \n{title}")
    for line in result.todo:
        st.warning(escape(line))
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
        st.markdown(
            "**수집** <span class='jv-muted'>사람인·잡코리아 공개 페이지, 요청 간격 3초</span>", unsafe_allow_html=True
        )
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
        note, left, right = st.columns([2, 1.2, 1.2], vertical_alignment="center")
        note.markdown(
            "**평가** <span class='jv-muted'>카드의 평가 칸을 체크하고 누릅니다. 저장된 프로필로 LLM 채점</span>",
            unsafe_allow_html=True,
        )
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


def show_postings() -> None:
    show_guide(POSTINGS_GUIDE)
    try:
        rows, error = load_rows(), None
    except Exception as e:
        rows, error = None, e
    show_run_panel()
    if error is not None:
        st.error(view.error_message(error))  # v0.5 F9
        return
    if not rows:
        st.info("공고 없음, 위 수집 카드에서 키워드를 넣고 수집하세요.")  # v0.5 F10
        return

    rows = view.with_checks(rows, st.session_state.get(CHECKS, {}))  # 화면에서 바꾼 체크 (F39)
    items = view.cards(rows)
    for index, (column, (label, value, note)) in enumerate(zip(st.columns(4), view.summary(items), strict=True)):
        with column.container(border=True, key=f"box-summary-{index}"):  # 칸마다 색 (F28)
            st.metric(label, value)
            st.caption(note)

    chart_box, filter_box = st.columns([2, 1])  # F3, F19
    sources, experiences = view.options(items)
    with filter_box.container(border=True, key="box-filters"):
        st.markdown("**필터**")
        filters = view.Filters(
            # 처음엔 비워 두고 "전체"로 보인다. 고른 것이 있을 때만 거른다 (v0.5.2 F29)
            sources=st.multiselect("출처", sources, placeholder="전체"),
            experiences=st.multiselect("경력", experiences, placeholder="전체", help="신입·경력·무관으로 묶음"),
            scored_only=st.toggle("평가된 공고만 보기"),  # 기본은 전체 (v0.5.2 F32)
        )
    shown = view.apply(items, filters)
    with chart_box.container(border=True, key="box-chart"):
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

    show_score_bar(rows)  # 목록 바로 위. 대상 수는 필터와 상관없이 전체 시트 기준 (F38)
    st.caption(f"{len(shown)}건 / 전체 {len(items)}건")
    for card in shown:
        show_card(card)


def pick_key(field: profile_form.Field, default: list[str]) -> str:
    # 기본값(파일·이력서 값)이 바뀌면 새 key라 입력란이 새 값으로 그려진다 (v0.5 F21)
    digest = hashlib.sha1(repr(default).encode()).hexdigest()[:8]
    return f"pick-{'.'.join(field.keys)}-{digest}"


def show_field(field: profile_form.Field, default, taken: list[str] = ()):
    label = field.label + (" *" if field.required else "")
    if field.kind == "pick":  # 추천 목록에서 고르고, 없으면 입력해 추가 (F10, F11)
        # 앞 칸에 고른 기술은 보기와 고른 값에서 뺀다 (v0.5.2 F37). key가 있어 다른 칸을 바꿔도 고른 값은 남는다
        key = pick_key(field, default)
        current = st.session_state.get(key, default)
        st.session_state[key] = [item for item in current if item not in taken]
        choices = [item for item in profile_form.options(field.suggestions, current) if item not in taken]
        return st.multiselect(
            label, choices, key=key, accept_new_options=True, help=field.help, placeholder=field.placeholder
        )
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


def show_resume_fill(values: dict, fill: dict | None) -> None:
    """이력서·포트폴리오 파일 → LLM → 입력란 (v0.5.2 F16–F22). 저장은 하지 않는다."""
    st.markdown(
        "**📄 이력서·포트폴리오로 채우기** <span class='jv-muted'>PDF(글자 있는 것)·Word·txt·md, 여러 개 가능</span>",
        unsafe_allow_html=True,
    )
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
        "이력서 파일",
        type=[suffix[1:] for suffix in resume.EXTENSIONS],
        accept_multiple_files=True,
        key="resume-files",
        label_visibility="collapsed",
    )
    st.caption(
        f"파일 글자(앞 {resume.MAX_TEXT:,}자)가 LLM 제공자(기본 Gemini)로 전송됩니다. 파일은 저장하지 않습니다."
    )  # N2, N3
    overwrite = st.toggle("이미 적은 칸도 바꾸기", key="resume-overwrite")  # 기본은 빈 칸만 (F19)
    if not st.button("✨ 이력서로 채우기", disabled=not files, key="resume-fill"):
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

    fill_box = st.container(border=True, key="box-resume")  # 맨 위에 두고 입력란을 그린 뒤 채운다
    badges = st.empty()  # 입력란을 그린 뒤 채운다 (F8)
    fill = st.session_state.get(FILL)  # 이력서에서 채운 값. 저장 전까지 파일 대신 입력란 기본값 (v0.5.2 F18)
    defaults = fill["values"] if fill else profile_form.to_form(raw)
    keys = {pick_key(field, defaults[field.keys]) for field in profile_form.FIELDS if field.kind == "pick"}
    for old in [key for key in st.session_state if str(key).startswith("pick-") and key not in keys]:
        del st.session_state[old]  # 예전 기본값의 고른 값은 버린다
    values = {}
    # 입력하는 동안 필수 칸 배지가 바뀌도록 st.form을 쓰지 않는다 (F8).
    # key를 주지 않아 파일이 바뀌면 입력란이 새 값으로 그려진다 (v0.5 F21)
    for row in (profile_form.GROUPS[:2], profile_form.GROUPS[2:]):  # 2×2 (F9, F19)
        for column, (group, title, note) in zip(st.columns(2), row, strict=True):
            with column.container(border=True, key=f"box-profile-{group}"):
                st.markdown(f"#### {title} <span class='jv-muted'>{note}</span>", unsafe_allow_html=True)
                for field in profile_form.group_fields(group):
                    values[field.keys] = show_field(field, defaults[field.keys], profile_form.taken(values, field.keys))
    badges.markdown(
        "".join(
            badge(f"{'✓' if done else '✗'} {name}", "high" if done else "low")
            for name, done in profile_form.required_status(values)
        ),
        unsafe_allow_html=True,
    )
    with fill_box:
        show_resume_fill(values, fill)

    if st.button("💾 저장", type="primary", key="profile-save"):
        try:
            profile, _ = user_profile.validate(profile_form.from_form(values))
        except user_profile.ProfileError as e:
            st.error(str(e))  # 저장하지 않는다 (v0.5 F20)
            return
        user_profile.save(profile, PROFILE)
        st.session_state.pop(FILL, None)  # 저장한 뒤에는 파일 값을 기본값으로
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
        reload_rows()
    postings_tab, profile_tab = st.tabs(["📋 공고", "👤 프로필"])  # v0.5 F1
    with postings_tab:
        show_postings()
    with profile_tab:
        show_profile()


main()

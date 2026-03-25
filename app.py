import io
import os
from datetime import date, datetime, time

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from modules.classifier import classify_articles
from modules.daum_search import search_daum_news
from modules.excel_writer import create_excel
from modules.file_parser import parse_input_file
from modules.naver_search import search_naver_news

load_dotenv()


def _secret(key: str) -> str:
    """Streamlit Cloud Secrets 우선, 없으면 .env 환경변수 fallback"""
    try:
        return st.secrets.get(key, os.getenv(key, ""))
    except FileNotFoundError:
        return os.getenv(key, "")

# ────────────────────────────────────────────────
# 페이지 설정
# ────────────────────────────────────────────────
st.set_page_config(
    page_title="뉴스 모니터링",
    page_icon="📰",
    layout="wide",
)

st.title("📰 뉴스 모니터링 프로그램")

# ────────────────────────────────────────────────
# 세션 상태 초기화
# ────────────────────────────────────────────────
if "parsed_data" not in st.session_state:
    st.session_state.parsed_data = None
if "excel_bytes" not in st.session_state:
    st.session_state.excel_bytes = None
if "result_summary" not in st.session_state:
    st.session_state.result_summary = None

# ────────────────────────────────────────────────
# 사이드바: API 키 설정
# ────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ API 설정")
    st.caption(".env 파일에 입력하거나 여기에 직접 입력하세요.")

    openai_key = st.text_input(
        "OpenAI API Key",
        value=_secret("OPENAI_API_KEY"),
        type="password",
        placeholder="sk-...",
    )
    naver_client_id = st.text_input(
        "네이버 Client ID",
        value=_secret("NAVER_CLIENT_ID"),
        placeholder="네이버 개발자센터에서 발급",
    )
    naver_client_secret = st.text_input(
        "네이버 Client Secret",
        value=_secret("NAVER_CLIENT_SECRET"),
        type="password",
        placeholder="네이버 개발자센터에서 발급",
    )

    st.divider()
    st.caption("💡 API 키는 .env 파일에 저장하면 매번 입력하지 않아도 됩니다.")

# ────────────────────────────────────────────────
# 메인 영역: 2컬럼 레이아웃
# ────────────────────────────────────────────────
col_left, col_right = st.columns([1, 1], gap="large")

# ── 좌측: 파일 업로드 ──────────────────────────
with col_left:
    st.subheader("① 입력 파일 업로드")
    uploaded_file = st.file_uploader(
        "키워드 및 분류 기준이 작성된 .docx 파일을 업로드하세요",
        type=["docx"],
        help="파일 형식이 달라도 GPT가 내용을 자동으로 해석합니다.",
    )

    if uploaded_file:
        if st.button("📄 파일 분석", use_container_width=True):
            if not openai_key:
                st.error("사이드바에 OpenAI API Key를 입력해주세요.")
            else:
                with st.spinner("GPT가 파일을 분석하는 중..."):
                    try:
                        client = OpenAI(api_key=openai_key)
                        parsed = parse_input_file(
                            io.BytesIO(uploaded_file.read()), client
                        )
                        st.session_state.parsed_data = parsed
                        st.session_state.excel_bytes = None
                        st.session_state.result_summary = None
                    except Exception as e:
                        st.error(f"파일 분석 실패: {e}")

    # 파일 분석 결과 표시
    if st.session_state.parsed_data:
        data = st.session_state.parsed_data
        st.success("✅ 파일 분석 완료")

        with st.expander("분석 결과 확인", expanded=True):
            st.markdown(f"**키워드:** {', '.join(data.get('keywords', []))}")
            st.markdown("**분류 기준:**")
            for cat, desc in data.get("categories", {}).items():
                st.markdown(f"- **{cat}**: {desc}")

# ── 우측: 검색 설정 ────────────────────────────
with col_right:
    st.subheader("② 검색 설정")

    search_date = st.date_input("날짜", value=date.today())

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        start_time = st.time_input("시작 시간", value=time(9, 0))
    with col_t2:
        end_time = st.time_input("종료 시간", value=time(13, 0))

    st.markdown("**검색 엔진 선택**")
    use_naver = st.checkbox("네이버 뉴스", value=True)
    use_daum = st.checkbox("다음 뉴스", value=True)

    if not use_naver and not use_daum:
        st.warning("검색 엔진을 최소 1개 이상 선택해주세요.")

# ────────────────────────────────────────────────
# 검색 시작 버튼
# ────────────────────────────────────────────────
st.divider()

can_search = (
    st.session_state.parsed_data is not None
    and (use_naver or use_daum)
)

if st.button(
    "🔍 검색 시작",
    type="primary",
    disabled=not can_search,
    use_container_width=True,
):
    # 입력값 검증
    errors = []
    if not openai_key:
        errors.append("OpenAI API Key가 없습니다.")
    if use_naver and (not naver_client_id or not naver_client_secret):
        errors.append("네이버 API 키(Client ID / Client Secret)가 없습니다.")
    if start_time >= end_time:
        errors.append("시작 시간이 종료 시간보다 앞이어야 합니다.")

    if errors:
        for e in errors:
            st.error(e)
        st.stop()

    start_dt = datetime.combine(search_date, start_time)
    end_dt = datetime.combine(search_date, end_time)

    data = st.session_state.parsed_data
    keywords = data.get("keywords", [])
    categories = data.get("categories", {})

    # ── 진행 상황 UI ──
    status_box = st.empty()
    progress_bar = st.progress(0)
    log_box = st.empty()

    all_articles = []
    total_steps = len(keywords)

    # ── STEP 1: 기사 수집 ──
    status_box.info("🔎 기사 수집 중...")
    for i, keyword in enumerate(keywords):
        log_box.caption(f"수집 중: [{keyword}] ({i + 1}/{total_steps})")

        if use_naver:
            try:
                naver_articles = search_naver_news(
                    keyword, start_dt, end_dt, naver_client_id, naver_client_secret
                )
                all_articles.extend(naver_articles)
            except Exception as e:
                st.warning(f"네이버 [{keyword}] 수집 실패: {e}")

        if use_daum:
            try:
                daum_articles = search_daum_news(keyword, start_dt, end_dt)
                all_articles.extend(daum_articles)
            except Exception as e:
                st.warning(f"다음 [{keyword}] 수집 실패: {e}")

        progress_bar.progress((i + 1) / total_steps * 0.4)

    # ── 중복 제거 (URL 기준) ──
    seen = set()
    unique_articles = []
    for a in all_articles:
        if a["link"] not in seen:
            seen.add(a["link"])
            unique_articles.append(a)

    log_box.caption(f"수집 완료: 총 {len(unique_articles)}건 (중복 제거 후)")

    if not unique_articles:
        status_box.warning("수집된 기사가 없습니다. 검색 조건을 확인해주세요.")
        progress_bar.empty()
        log_box.empty()
        st.stop()

    # ── STEP 2: GPT 분류 ──
    status_box.info("🤖 AI 분류 중...")
    client = OpenAI(api_key=openai_key)

    def on_progress(current: int, total: int):
        log_box.caption(f"분류 중: {current}/{total}건")
        progress_bar.progress(0.4 + (current / total) * 0.5 if total > 0 else 0.4)

    try:
        classified = classify_articles(
            unique_articles,
            categories,
            client,
            progress_callback=on_progress,
        )
    except Exception as e:
        st.error(f"분류 중 오류 발생: {e}")
        st.stop()

    # ── STEP 3: 엑셀 생성 ──
    status_box.info("📊 엑셀 파일 생성 중...")
    log_box.caption("엑셀 생성 중...")

    try:
        excel_bytes = create_excel(
            classified,
            list(categories.keys()),
        )
        st.session_state.excel_bytes = excel_bytes
    except Exception as e:
        st.error(f"엑셀 생성 실패: {e}")
        st.stop()

    # ── 완료 ──
    progress_bar.progress(1.0)
    status_box.success(f"✅ 완료! 총 {len(unique_articles)}건 처리")
    log_box.empty()

    # 카테고리별 건수 요약 (일람/미분류는 항상 포함)
    summary = {"일람": len(unique_articles)}
    for cat in categories.keys():
        summary[cat] = sum(1 for a in classified if a.get("category") == cat)
    summary["미분류"] = sum(1 for a in classified if a.get("category") == "미분류")
    st.session_state.result_summary = summary

# ────────────────────────────────────────────────
# 결과 요약 & 다운로드
# ────────────────────────────────────────────────
if st.session_state.result_summary:
    st.subheader("📊 분류 결과 요약")
    cols = st.columns(len(st.session_state.result_summary))
    for col, (cat, count) in zip(cols, st.session_state.result_summary.items()):
        col.metric(label=cat, value=f"{count}건")

if st.session_state.excel_bytes:
    filename = f"뉴스모니터링_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    st.download_button(
        label="📥 엑셀 다운로드",
        data=st.session_state.excel_bytes,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary",
    )

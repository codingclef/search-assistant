import io
import os
from datetime import date, datetime, time

import pandas as pd

import streamlit as st
from openai import OpenAI

from modules.classifier import classify_articles
from modules.daum_search import search_daum_news
from modules.excel_writer import create_excel
from modules.naver_search import search_naver_news
from modules.sheets import load_presets, save_preset, delete_preset, load_feedback, save_feedback


def _secret(key: str) -> str:
    """Streamlit Cloud Secrets 우선, 없으면 환경변수 fallback"""
    try:
        return st.secrets.get(key, os.getenv(key, ""))
    except FileNotFoundError:
        return os.getenv(key, "")


# ────────────────────────────────────────────────
# 페이지 설정
# ────────────────────────────────────────────────
st.set_page_config(
    page_title="뉴스 모니터링 어시스턴트",
    page_icon="📰",
    layout="wide",
)

st.title("📰 뉴스 모니터링 어시스턴트")

# ────────────────────────────────────────────────
# 세션 상태 초기화
# ────────────────────────────────────────────────
if "excel_bytes" not in st.session_state:
    st.session_state.excel_bytes = None
if "result_summary" not in st.session_state:
    st.session_state.result_summary = None
if "val_errors" not in st.session_state:
    st.session_state.val_errors = set()
if "classified" not in st.session_state:
    st.session_state.classified = None
if "categories_state" not in st.session_state:
    st.session_state.categories_state = {}
if "run_id" not in st.session_state:
    st.session_state.run_id = 0

# 분류 기준 행 관리 (고유 ID 방식)
if "cat_ids" not in st.session_state:
    st.session_state.cat_ids = [0, 1]
if "cat_counter" not in st.session_state:
    st.session_state.cat_counter = 2

# ────────────────────────────────────────────────
# API 키 로드 (내부용, UI 노출 없음)
# ────────────────────────────────────────────────
openai_key = _secret("OPENAI_API_KEY")
naver_client_id = _secret("NAVER_CLIENT_ID")
naver_client_secret = _secret("NAVER_CLIENT_SECRET")
app_password = _secret("APP_PASSWORD")

missing = []
if not openai_key:
    missing.append("OPENAI_API_KEY")
if not naver_client_id or not naver_client_secret:
    missing.append("NAVER API 키")
if missing:
    st.error(f"설정 누락: {', '.join(missing)} — 관리자에게 문의하세요.")

# ────────────────────────────────────────────────
# 메인 영역: 2컬럼 레이아웃
# ────────────────────────────────────────────────
col_left, col_right = st.columns([3, 2], gap="large")

# ── 좌측: 키워드 & 분류 기준 입력 ──────────────
with col_left:

    # 프리셋
    st.subheader("① 프리셋")
    presets = load_presets()

    if presets:
        col_sel, col_load, col_del = st.columns([4, 1, 1])
        with col_sel:
            selected_preset = st.selectbox(
                "저장된 프리셋",
                options=list(presets.keys()),
                label_visibility="collapsed",
            )
        with col_load:
            if st.button("불러오기", use_container_width=True):
                p = presets[selected_preset]
                st.session_state["preset_keywords"] = p["keywords"]
                st.session_state["preset_name_input"] = selected_preset
                # 분류기준 행 초기화 후 재구성
                new_ids = list(range(len(p["categories"])))
                st.session_state.cat_ids = new_ids
                st.session_state.cat_counter = len(new_ids)
                for i, (name, cond) in enumerate(p["categories"].items()):
                    st.session_state[f"cat_name_{i}"] = name
                    st.session_state[f"cat_cond_{i}"] = cond
                st.rerun()
        with col_del:
            if st.button("삭제", use_container_width=True):
                delete_preset(selected_preset)
                st.rerun()
    else:
        st.caption("저장된 프리셋이 없습니다.")

    # 프리셋 저장
    col_name, col_save = st.columns([4, 1])
    with col_name:
        preset_name = st.text_input(
            "프리셋 이름",
            placeholder="예: 장애인고용공단_평일",
            label_visibility="collapsed",
            key="preset_name_input",
        )
    with col_save:
        save_clicked = st.button("저장", use_container_width=True)

    # 에러/성공 메시지는 컬럼 바깥에서 표시 (두 컬럼 합친 너비)
    if save_clicked:
        kw = st.session_state.get("keywords_input", "").strip()
        cats = {}
        for cid in st.session_state.cat_ids:
            n = st.session_state.get(f"cat_name_{cid}", "").strip()
            c = st.session_state.get(f"cat_cond_{cid}", "").strip()
            if n:
                cats[n] = c

        if not preset_name.strip():
            st.error("프리셋 이름을 입력해주세요.")
        elif not kw:
            st.error("키워드를 입력한 후 저장해주세요.")
        elif not cats:
            st.error("분류 기준을 1개 이상 입력한 후 저장해주세요.")
        else:
            if save_preset(preset_name.strip(), kw, cats):
                st.success(f"'{preset_name}' 저장 완료!")
                st.rerun()

    st.divider()

    # 키워드
    st.subheader("② 키워드")
    keywords_raw = st.text_area(
        "모니터링할 키워드를 쉼표(,)로 구분하여 입력하세요",
        value=st.session_state.get("preset_keywords", ""),
        placeholder="예: 삼성전자, 이재용, 갤럭시",
        height=80,
        label_visibility="collapsed",
        key="keywords_input",
    )
    if "keywords" in st.session_state.val_errors:
        st.error("키워드를 입력해주세요.")

    st.divider()

    # 분류 기준
    st.subheader("③ 분류 기준")
    st.caption("시트명과 해당 시트에 넣을 기사의 조건을 입력하세요.")
    st.caption("💡 일람 (수집된 모든 기사)과 보류 (AI가 분류하지 못한 기사) 시트는 입력 여부와 관계없이 항상 자동으로 생성됩니다.")

    # 헤더
    h1, h2, h3 = st.columns([2, 5, 1])
    h1.markdown("**시트명**")
    h2.markdown("**분류 조건**")

    # 분류 기준 행 목록
    _name_placeholders = [
        "예: 부정기사",
        "예: 중요기사",
    ]
    _cond_placeholders = [
        "예: 회사에 대한 직접적인 비판 기사(운영 미숙이나 주요 사업의 실효성 문제점 등 비판)라고 판단되는 경우",
        "예: 임원 인터뷰 기사 등 중요한 기사라고 판단되는 경우",
    ]

    for row_idx, cat_id in enumerate(list(st.session_state.cat_ids)):
        c1, c2, c3 = st.columns([2, 5, 1])
        with c1:
            st.text_input(
                "시트명",
                key=f"cat_name_{cat_id}",
                placeholder=_name_placeholders[min(row_idx, len(_name_placeholders) - 1)],
                label_visibility="collapsed",
            )
        with c2:
            st.text_area(
                "분류 조건",
                key=f"cat_cond_{cat_id}",
                placeholder=_cond_placeholders[min(row_idx, len(_cond_placeholders) - 1)],
                label_visibility="collapsed",
                height=100,
            )
        with c3:
            st.write("")
            st.write("")
            if st.button("✕", key=f"del_{cat_id}", help="삭제"):
                st.session_state.cat_ids.remove(cat_id)
                st.rerun()

    if "categories" in st.session_state.val_errors:
        st.error("시트명을 1개 이상 입력해주세요.")

    # 시트 추가 버튼
    if st.button("＋ 시트 추가", use_container_width=False):
        st.session_state.cat_ids.append(st.session_state.cat_counter)
        st.session_state.cat_counter += 1
        st.rerun()

# ── 우측: 모니터링 설정 ────────────────────────
with col_right:
    st.subheader("④ 모니터링 설정")

    search_date = st.date_input("날짜", value=date.today())

    _time_help = (
        "⏱ 언론사 기사가 검색엔진에 노출되기까지 수 분~수십 분 지연이 발생할 수 있습니다.\n\n"
        "예) 9시부터 모니터링하려면 시작 시간을 08:50으로 설정하는 것을 권장합니다."
    )
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        start_time = st.time_input("시작 시간", value=time(9, 0), help=_time_help)
    with col_t2:
        end_time = st.time_input("종료 시간", value=time(13, 0))

    if "time_range" in st.session_state.val_errors:
        st.error("시작 시간이 종료 시간보다 앞이어야 합니다.")

    st.markdown("**검색 엔진**")
    use_naver = st.checkbox("네이버 뉴스", value=True)
    use_daum = st.checkbox("다음 뉴스", value=True)

    if "engines" in st.session_state.val_errors:
        st.error("검색 엔진을 최소 1개 이상 선택해주세요.")

    st.divider()
    entered_pw = st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요")
    if "password" in st.session_state.val_errors:
        st.error("비밀번호가 일치하지 않습니다.")

    st.write("")
    monitoring_clicked = st.button("🔍 모니터링 시작", type="primary", use_container_width=True)

# ────────────────────────────────────────────────
# 모니터링 시작 처리
# ────────────────────────────────────────────────

# 입력값 수집
keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]
categories = {}
for cat_id in st.session_state.cat_ids:
    name = st.session_state.get(f"cat_name_{cat_id}", "").strip()
    cond = st.session_state.get(f"cat_cond_{cat_id}", "").strip()
    if name:
        categories[name] = cond

if monitoring_clicked:

    # ── 입력값 검증 ──
    errors = set()
    if not keywords:
        errors.add("keywords")
    if not categories:
        errors.add("categories")
    if start_time >= end_time:
        errors.add("time_range")
    if not use_naver and not use_daum:
        errors.add("engines")
    if app_password and entered_pw != app_password:
        errors.add("password")

    if errors:
        st.session_state.val_errors = errors
        st.rerun()

    # 검증 통과 → 에러 초기화 후 실행
    st.session_state.val_errors = set()

    start_dt = datetime.combine(search_date, start_time)
    end_dt = datetime.combine(search_date, end_time)

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
    feedback_examples = load_feedback()

    def on_progress(current: int, total: int):
        log_box.caption(f"분류 중: {current}/{total}건")
        progress_bar.progress(0.4 + (current / total) * 0.5 if total > 0 else 0.4)

    try:
        classified = classify_articles(
            unique_articles,
            categories,
            client,
            progress_callback=on_progress,
            feedback_examples=feedback_examples,
        )
    except Exception as e:
        st.error(f"분류 중 오류 발생: {e}")
        st.stop()

    # ── STEP 3: 엑셀 생성 ──
    status_box.info("📊 엑셀 파일 생성 중...")
    log_box.caption("엑셀 생성 중...")

    try:
        excel_bytes = create_excel(classified, list(categories.keys()))
        st.session_state.excel_bytes = excel_bytes
    except Exception as e:
        st.error(f"엑셀 생성 실패: {e}")
        st.stop()

    # ── 완료 ──
    progress_bar.progress(1.0)
    status_box.success(f"✅ 완료! 총 {len(unique_articles)}건 처리")
    log_box.empty()

    # 결과 세션 저장
    st.session_state.classified = classified
    st.session_state.categories_state = categories
    st.session_state.run_id += 1

    # 카테고리별 건수 요약
    summary = {"일람": len(unique_articles)}
    for cat in categories.keys():
        summary[cat] = sum(1 for a in classified if a.get("category") == cat)
    summary["보류"] = sum(1 for a in classified if a.get("category") == "보류")
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

# ────────────────────────────────────────────────
# 엑셀 출력 형식 미리보기
# ────────────────────────────────────────────────
st.divider()
with st.expander("📋 엑셀 출력 형식 미리보기"):
    st.markdown("**일람 시트** (수집된 모든 기사)")
    st.table({
        "No.": [1, 2],
        "키워드": ["삼성전자", "이재용"],
        "날짜/시간": ["2024-03-25 09:30", "2024-03-25 10:15"],
        "검색엔진": ["네이버", "다음"],
        "언론사": ["한국경제", "조선일보"],
        "기사제목": ["삼성전자 신형 반도체 공개", "이재용 회장 해외 출장"],
        "링크": ["https://...", "https://..."],
        "분류결과": ["단순언급", "부정적"],
    })

    st.markdown("**그 외 시트** (각 분류 기준 / 보류)")
    st.table({
        "No.": [1, 2],
        "키워드": ["삼성전자", "이재용"],
        "날짜/시간": ["2024-03-25 09:30", "2024-03-25 10:15"],
        "검색엔진": ["네이버", "다음"],
        "언론사": ["한국경제", "조선일보"],
        "기사제목": ["삼성전자 신형 반도체 공개", "이재용 회장 해외 출장"],
        "링크": ["https://...", "https://..."],
        "분류이유": ["제품 출시 관련 단순 보도", "경영 활동 관련 부정적 내용 포함"],
    })

# ────────────────────────────────────────────────
# 분류 결과 확인 & 피드백
# ────────────────────────────────────────────────
if st.session_state.classified is not None:
    st.divider()
    st.subheader("💬 분류 결과 확인 및 피드백")
    st.caption(
        "일람 탭에서 잘못 분류된 기사의 **분류결과** 셀을 클릭해 수정한 뒤 "
        "**피드백 저장**을 누르면 다음 실행부터 AI 분류에 반영됩니다."
    )

    classified_data = st.session_state.classified
    cats = st.session_state.categories_state

    # DataFrame 생성
    rows = []
    for i, a in enumerate(classified_data):
        pub_dt = a.get("published_at")
        date_str = pub_dt.strftime("%Y-%m-%d %H:%M") if isinstance(pub_dt, datetime) else ""
        rows.append({
            "No.": i + 1,
            "키워드": a.get("keyword", ""),
            "날짜/시간": date_str,
            "검색엔진": a.get("search_engine", ""),
            "언론사": a.get("source", ""),
            "기사제목": a.get("title", ""),
            "링크": a.get("link", ""),
            "분류결과": a.get("category", ""),
            "분류이유(AI)": a.get("reason", ""),
        })

    df_all = pd.DataFrame(rows)
    cat_options = list(cats.keys()) + ["보류"]

    col_config = {
        "No.": st.column_config.NumberColumn(disabled=True, width="small"),
        "키워드": st.column_config.TextColumn(disabled=True),
        "날짜/시간": st.column_config.TextColumn(disabled=True),
        "검색엔진": st.column_config.TextColumn(disabled=True, width="small"),
        "언론사": st.column_config.TextColumn(disabled=True),
        "기사제목": st.column_config.TextColumn(disabled=True),
        "링크": st.column_config.LinkColumn(disabled=True),
        "분류결과": st.column_config.SelectboxColumn(
            options=cat_options,
            required=True,
        ),
        "분류이유(AI)": st.column_config.TextColumn(disabled=True),
    }

    tab_names = ["일람"] + list(cats.keys()) + ["보류"]
    tabs = st.tabs(tab_names)

    # 일람 탭: 편집 가능
    with tabs[0]:
        edited_df = st.data_editor(
            df_all,
            column_config=col_config,
            hide_index=True,
            use_container_width=True,
            key=f"feedback_editor_{st.session_state.run_id}",
        )
        if st.button("💾 피드백 저장", type="secondary"):
            changes = [
                {"title": classified_data[i]["title"], "category": edited}
                for i, (orig, edited) in enumerate(
                    zip(df_all["분류결과"], edited_df["분류결과"])
                )
                if orig != edited
            ]
            if changes:
                if save_feedback(changes):
                    st.success(f"✅ {len(changes)}건 피드백 저장 완료! 다음 실행부터 반영됩니다.")
            else:
                st.info("변경된 분류가 없습니다.")

    # 카테고리별 탭: 읽기 전용
    for i, cat in enumerate(cats.keys()):
        with tabs[i + 1]:
            cat_df = df_all[df_all["분류결과"] == cat].reset_index(drop=True)
            if cat_df.empty:
                st.caption("해당 카테고리로 분류된 기사가 없습니다.")
            else:
                st.dataframe(cat_df, hide_index=True, use_container_width=True,
                             column_config=col_config)

    # 보류 탭: 읽기 전용
    with tabs[-1]:
        unc_df = df_all[df_all["분류결과"] == "보류"].reset_index(drop=True)
        if unc_df.empty:
            st.caption("보류로 분류된 기사가 없습니다.")
        else:
            st.dataframe(unc_df, hide_index=True, use_container_width=True,
                         column_config=col_config)

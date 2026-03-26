import io
import os
from datetime import date, datetime, time

import pandas as pd

import streamlit as st
from openai import OpenAI

from modules.classifier import classify_articles
from modules.daum_search import search_daum_news
from modules.excel_writer import create_excel
from modules.i18n import get_strings
from modules.naver_search import search_naver_news
from modules.sheets import load_presets, save_preset, delete_preset, load_feedback, save_feedback


def _secret(key: str) -> str:
    """Streamlit Cloud Secrets 우선, 없으면 환경변수 fallback"""
    try:
        return st.secrets.get(key, os.getenv(key, ""))
    except FileNotFoundError:
        return os.getenv(key, "")


# ────────────────────────────────────────────────
# 페이지 설정 (언어 반영)
# ────────────────────────────────────────────────
_lang_init = "ja" if st.session_state.get("lang_select") == "日本語" else "ko"
_S_init = get_strings(_lang_init)

st.set_page_config(
    page_title=_S_init["page_title"],
    page_icon="📰",
    layout="wide",
)

# ────────────────────────────────────────────────
# 언어 선택 & 문자열 로드
# ────────────────────────────────────────────────
col_title_row, col_lang_row = st.columns([5, 1])
with col_title_row:
    st.title(_S_init["title"])
with col_lang_row:
    st.radio(
        "lang",
        options=["한국어", "日本語"],
        key="lang_select",
        horizontal=True,
        label_visibility="collapsed",
    )

lang = "ja" if st.session_state.get("lang_select") == "日本語" else "ko"
S = get_strings(lang)

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
    st.error(S["missing_config"].format(keys=", ".join(missing)))

# ────────────────────────────────────────────────
# 메인 영역: 2컬럼 레이아웃
# ────────────────────────────────────────────────
col_left, col_right = st.columns([3, 2], gap="large")

# ── 좌측: 키워드 & 분류 기준 입력 ──────────────
with col_left:

    # 프리셋
    st.subheader(S["section_preset"])
    presets = load_presets()

    if presets:
        col_sel, col_load, col_del = st.columns([4, 1, 1])
        with col_sel:
            selected_preset = st.selectbox(
                "preset_select",
                options=list(presets.keys()),
                label_visibility="collapsed",
            )
        with col_load:
            if st.button(S["preset_load"], use_container_width=True):
                p = presets[selected_preset]
                st.session_state["preset_keywords"] = p["keywords"]
                st.session_state["preset_name_input"] = selected_preset
                new_ids = list(range(len(p["categories"])))
                st.session_state.cat_ids = new_ids
                st.session_state.cat_counter = len(new_ids)
                for i, (name, cond) in enumerate(p["categories"].items()):
                    st.session_state[f"cat_name_{i}"] = name
                    st.session_state[f"cat_cond_{i}"] = cond
                st.rerun()
        with col_del:
            if st.button(S["preset_delete"], use_container_width=True):
                delete_preset(selected_preset)
                st.rerun()
    else:
        st.caption(S["preset_none"])

    # 프리셋 저장
    col_name, col_save = st.columns([4, 1])
    with col_name:
        preset_name = st.text_input(
            "preset_name",
            placeholder=S["preset_name_placeholder"],
            label_visibility="collapsed",
            key="preset_name_input",
        )
    with col_save:
        save_clicked = st.button(S["preset_save"], use_container_width=True)

    if save_clicked:
        kw = st.session_state.get("keywords_input", "").strip()
        cats = {}
        for cid in st.session_state.cat_ids:
            n = st.session_state.get(f"cat_name_{cid}", "").strip()
            c = st.session_state.get(f"cat_cond_{cid}", "").strip()
            if n:
                cats[n] = c

        if not preset_name.strip():
            st.error(S["preset_err_name"])
        elif not kw:
            st.error(S["preset_err_keyword"])
        elif not cats:
            st.error(S["preset_err_categories"])
        else:
            if save_preset(preset_name.strip(), kw, cats):
                st.success(S["preset_save_success"].format(name=preset_name))
                st.rerun()

    st.divider()

    # 키워드
    st.subheader(S["section_keywords"])
    keywords_raw = st.text_area(
        S["keywords_label"],
        value=st.session_state.get("preset_keywords", ""),
        placeholder=S["keywords_placeholder"],
        height=80,
        label_visibility="collapsed",
        key="keywords_input",
    )
    if "keywords" in st.session_state.val_errors:
        st.error(S["keywords_err"])

    st.divider()

    # 분류 기준
    st.subheader(S["section_categories"])
    st.caption(S["categories_caption"])
    st.caption(S["categories_tip"])

    h1, h2, h3 = st.columns([2, 5, 1])
    h1.markdown(S["col_sheet_name"])
    h2.markdown(S["col_condition"])

    _name_phs = [S["sheet_name_ph_0"], S["sheet_name_ph_1"]]
    _cond_phs = [S["cond_ph_0"], S["cond_ph_1"]]

    for row_idx, cat_id in enumerate(list(st.session_state.cat_ids)):
        c1, c2, c3 = st.columns([2, 5, 1])
        with c1:
            st.text_input(
                "sheet_name",
                key=f"cat_name_{cat_id}",
                placeholder=_name_phs[min(row_idx, len(_name_phs) - 1)],
                label_visibility="collapsed",
            )
        with c2:
            st.text_area(
                "cond",
                key=f"cat_cond_{cat_id}",
                placeholder=_cond_phs[min(row_idx, len(_cond_phs) - 1)],
                label_visibility="collapsed",
                height=100,
            )
        with c3:
            st.write("")
            st.write("")
            if st.button("✕", key=f"del_{cat_id}", help=S["preset_delete"]):
                st.session_state.cat_ids.remove(cat_id)
                st.rerun()

    if "categories" in st.session_state.val_errors:
        st.error(S["categories_err"])

    if st.button(S["add_sheet"], use_container_width=False):
        st.session_state.cat_ids.append(st.session_state.cat_counter)
        st.session_state.cat_counter += 1
        st.rerun()

# ── 우측: 모니터링 설정 ────────────────────────
with col_right:
    st.subheader(S["section_settings"])

    search_date = st.date_input(S["date_label"], value=date.today())

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        start_time = st.time_input(S["start_time_label"], value=time(9, 0), help=S["time_help"])
    with col_t2:
        end_time = st.time_input(S["end_time_label"], value=time(13, 0))

    if "time_range" in st.session_state.val_errors:
        st.error(S["time_range_err"])

    st.markdown(S["search_engine_label"])
    use_naver = st.checkbox(S["naver_checkbox"], value=True)
    use_daum = st.checkbox(S["daum_checkbox"], value=True)

    if "engines" in st.session_state.val_errors:
        st.error(S["engines_err"])

    st.divider()
    entered_pw = st.text_input(S["password_label"], type="password", placeholder=S["password_placeholder"])
    if "password" in st.session_state.val_errors:
        st.error(S["password_err"])

    st.write("")
    monitoring_clicked = st.button(S["start_button"], type="primary", use_container_width=True)

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

    st.session_state.val_errors = set()

    start_dt = datetime.combine(search_date, start_time)
    end_dt = datetime.combine(search_date, end_time)

    status_box = st.empty()
    progress_bar = st.progress(0)
    log_box = st.empty()

    all_articles = []
    total_steps = len(keywords)

    # ── STEP 1: 기사 수집 ──
    status_box.info(S["status_collecting"])
    for i, keyword in enumerate(keywords):
        log_box.caption(S["log_collecting"].format(keyword=keyword, i=i + 1, total=total_steps))

        if use_naver:
            try:
                naver_articles = search_naver_news(
                    keyword, start_dt, end_dt, naver_client_id, naver_client_secret
                )
                all_articles.extend(naver_articles)
            except Exception as e:
                st.warning(S["warn_naver_fail"].format(keyword=keyword, e=e))

        if use_daum:
            try:
                daum_articles = search_daum_news(keyword, start_dt, end_dt)
                all_articles.extend(daum_articles)
            except Exception as e:
                st.warning(S["warn_daum_fail"].format(keyword=keyword, e=e))

        progress_bar.progress((i + 1) / total_steps * 0.4)

    # ── 중복 제거 (URL 기준) + 키워드 병합 ──
    seen = {}  # link -> unique_articles 인덱스
    unique_articles = []
    for a in all_articles:
        link = a["link"]
        if link not in seen:
            seen[link] = len(unique_articles)
            unique_articles.append(a)
        else:
            # 이미 있는 기사에 키워드 추가 (중복 제외)
            existing = unique_articles[seen[link]]
            existing_kws = [k.strip() for k in existing["keyword"].split(",")]
            if a["keyword"] not in existing_kws:
                existing["keyword"] = existing["keyword"] + ", " + a["keyword"]

    log_box.caption(S["log_collected"].format(count=len(unique_articles)))

    if not unique_articles:
        status_box.warning(S["warn_no_articles"])
        progress_bar.empty()
        log_box.empty()
        st.stop()

    # 일본어 모드일 때 검색엔진 표시값 변환
    if lang == "ja":
        eng_map = {"네이버": S["engine_naver"], "다음": S["engine_daum"]}
        for a in unique_articles:
            a["search_engine"] = eng_map.get(a["search_engine"], a["search_engine"])

    # ── STEP 2: GPT 분류 ──
    status_box.info(S["status_classifying"])
    client = OpenAI(api_key=openai_key)
    feedback_examples = load_feedback()

    def on_progress(current: int, total: int):
        log_box.caption(S["log_classifying"].format(current=current, total=total))
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
        st.error(S["err_classify"].format(e=e))
        st.stop()

    # ── STEP 3: 엑셀 생성 ──
    status_box.info(S["status_excel"])
    log_box.caption(S["log_excel"])

    try:
        excel_bytes = create_excel(classified, list(categories.keys()), lang=lang)
        st.session_state.excel_bytes = excel_bytes
    except Exception as e:
        st.error(S["err_excel"].format(e=e))
        st.stop()

    # ── 완료 ──
    progress_bar.progress(1.0)
    status_box.success(S["status_done"].format(count=len(unique_articles)))
    log_box.empty()

    # 결과 세션 저장
    st.session_state.classified = classified
    st.session_state.categories_state = categories
    st.session_state.run_id += 1
    st.session_state.result_lang = lang

    # 카테고리별 건수 요약
    summary = {S["sheet_ilam"]: len(unique_articles)}
    for cat in categories.keys():
        summary[cat] = sum(1 for a in classified if a.get("category") == cat)
    summary[S["sheet_holdup"]] = sum(1 for a in classified if a.get("category") == "보류")
    st.session_state.result_summary = summary

# ────────────────────────────────────────────────
# 결과 요약 & 다운로드
# ────────────────────────────────────────────────
if st.session_state.result_summary:
    st.subheader(S["section_results"])
    cols = st.columns(len(st.session_state.result_summary))
    for col, (cat, count) in zip(cols, st.session_state.result_summary.items()):
        col.metric(label=cat, value=f"{count}{S['count_unit']}")

if st.session_state.excel_bytes:
    filename = f"{S['filename_prefix']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    st.download_button(
        label=S["download_button"],
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
with st.expander(S["preview_expander"]):
    st.markdown(S["preview_ilam"])
    st.table({
        S["col_no"]: [1, 2],
        S["col_keyword"]: [S["preview_kw_1"], S["preview_kw_2"]],
        S["col_datetime"]: ["2024-03-25 09:30", "2024-03-25 10:15"],
        S["col_engine"]: [S["engine_naver"], S["engine_daum"]],
        S["col_media"]: [S["preview_media_1"], S["preview_media_2"]],
        S["col_title"]: [S["preview_title_1"], S["preview_title_2"]],
        S["col_link"]: ["https://...", "https://..."],
        S["col_category"]: [S["preview_cat_1"], S["preview_cat_2"]],
    })

    st.markdown(S["preview_other"])
    st.table({
        S["col_no"]: [1, 2],
        S["col_keyword"]: [S["preview_kw_1"], S["preview_kw_2"]],
        S["col_datetime"]: ["2024-03-25 09:30", "2024-03-25 10:15"],
        S["col_engine"]: [S["engine_naver"], S["engine_daum"]],
        S["col_media"]: [S["preview_media_1"], S["preview_media_2"]],
        S["col_title"]: [S["preview_title_1"], S["preview_title_2"]],
        S["col_link"]: ["https://...", "https://..."],
        S["col_reason"]: [S["preview_reason_1"], S["preview_reason_2"]],
    })

# ────────────────────────────────────────────────
# 분류 결과 확인 & 피드백
# ────────────────────────────────────────────────
if st.session_state.classified is not None:
    st.divider()
    st.subheader(S["section_feedback"])
    st.caption(S["feedback_caption"])

    classified_data = st.session_state.classified
    cats = st.session_state.categories_state

    rows = []
    for i, a in enumerate(classified_data):
        pub_dt = a.get("published_at")
        date_str = pub_dt.strftime("%Y-%m-%d %H:%M") if isinstance(pub_dt, datetime) else ""
        rows.append({
            S["col_no"]: i + 1,
            S["col_keyword"]: a.get("keyword", ""),
            S["col_datetime"]: date_str,
            S["col_engine"]: a.get("search_engine", ""),
            S["col_media"]: a.get("source", ""),
            S["col_title"]: a.get("title", ""),
            S["col_link"]: a.get("link", ""),
            S["col_category"]: a.get("category", ""),
            S["col_reason_ai"]: a.get("reason", ""),
        })

    df_all = pd.DataFrame(rows)
    cat_options = list(cats.keys()) + ["보류"]

    col_config = {
        S["col_no"]: st.column_config.NumberColumn(disabled=True, width="small"),
        S["col_keyword"]: st.column_config.TextColumn(disabled=True),
        S["col_datetime"]: st.column_config.TextColumn(disabled=True),
        S["col_engine"]: st.column_config.TextColumn(disabled=True, width="small"),
        S["col_media"]: st.column_config.TextColumn(disabled=True),
        S["col_title"]: st.column_config.TextColumn(disabled=True),
        S["col_link"]: st.column_config.LinkColumn(disabled=True),
        S["col_category"]: st.column_config.SelectboxColumn(
            options=cat_options,
            required=True,
        ),
        S["col_reason_ai"]: st.column_config.TextColumn(disabled=True),
    }

    tab_names = [S["sheet_ilam"]] + list(cats.keys()) + [S["sheet_holdup"]]
    tabs = st.tabs(tab_names)

    with tabs[0]:
        edited_df = st.data_editor(
            df_all,
            column_config=col_config,
            hide_index=True,
            use_container_width=True,
            key=f"feedback_editor_{st.session_state.run_id}",
        )
        if st.button(S["feedback_save_button"], type="secondary"):
            changes = [
                {"title": classified_data[i]["title"], "category": edited}
                for i, (orig, edited) in enumerate(
                    zip(df_all[S["col_category"]], edited_df[S["col_category"]])
                )
                if orig != edited
            ]
            if changes:
                if save_feedback(changes):
                    st.success(S["feedback_save_success"].format(count=len(changes)))
            else:
                st.info(S["feedback_no_changes"])

    for i, cat in enumerate(cats.keys()):
        with tabs[i + 1]:
            cat_df = df_all[df_all[S["col_category"]] == cat].reset_index(drop=True)
            if cat_df.empty:
                st.caption(S["no_articles_in_cat"])
            else:
                st.dataframe(cat_df, hide_index=True, use_container_width=True,
                             column_config=col_config)

    with tabs[-1]:
        unc_df = df_all[df_all[S["col_category"]] == "보류"].reset_index(drop=True)
        if unc_df.empty:
            st.caption(S["no_articles_holdup"])
        else:
            st.dataframe(unc_df, hide_index=True, use_container_width=True,
                         column_config=col_config)

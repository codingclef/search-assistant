from __future__ import annotations

import io
from datetime import datetime

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

COLUMNS = ["키워드", "날짜/시간", "언론사", "기사제목", "링크", "분류이유"]
COL_WIDTHS = [15, 20, 15, 55, 45, 45]

HEADER_BG = "4472C4"
HEADER_FG = "FFFFFF"


SHEET_ILAM = "일람"
SHEET_UNCLASSIFIED = "미분류"


def create_excel(
    articles: list[dict],
    category_names: list[str],
) -> bytes:
    """
    분류된 기사를 카테고리별 시트로 나눠 엑셀 파일을 생성합니다.

    시트 순서 (항상 고정):
    1. 일람      - 모든 기사 (시스템 기본 시트)
    2. docx에 정의된 카테고리들
    3. 미분류    - 분류 불가 기사 (시스템 기본 시트)
    """
    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # 기본 시트 제거

    # 1. 일람 시트 (모든 기사)
    ws_ilam = wb.create_sheet(title=SHEET_ILAM)
    _setup_header(ws_ilam)
    for article in articles:
        _add_row(ws_ilam, article)
    _apply_column_widths(ws_ilam)

    # 2. docx 정의 카테고리 시트
    for cat_name in category_names:
        sheet_title = cat_name[:31]  # Excel 시트명 31자 제한
        ws = wb.create_sheet(title=sheet_title)
        _setup_header(ws)
        for article in articles:
            if article.get("category") == cat_name:
                _add_row(ws, article)
        _apply_column_widths(ws)

    # 3. 미분류 시트 (분류 불가 기사)
    ws_unc = wb.create_sheet(title=SHEET_UNCLASSIFIED)
    _setup_header(ws_unc)
    for article in articles:
        if article.get("category") == SHEET_UNCLASSIFIED:
            _add_row(ws_unc, article)
    _apply_column_widths(ws_unc)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.read()


def _setup_header(ws) -> None:
    """헤더 행 스타일 적용"""
    header_fill = PatternFill(
        start_color=HEADER_BG, end_color=HEADER_BG, fill_type="solid"
    )
    header_font = Font(bold=True, color=HEADER_FG, size=11)

    for col, header in enumerate(COLUMNS, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    ws.row_dimensions[1].height = 22
    ws.freeze_panes = "A2"  # 헤더 고정


def _add_row(ws, article: dict) -> None:
    """기사 데이터 1행 추가"""
    row = ws.max_row + 1

    pub_dt = article.get("published_at")
    if isinstance(pub_dt, datetime):
        date_str = pub_dt.strftime("%Y-%m-%d %H:%M")
    else:
        date_str = str(pub_dt) if pub_dt else ""

    values = [
        article.get("keyword", ""),
        date_str,
        article.get("source", ""),
        article.get("title", ""),
        article.get("link", ""),
        article.get("reason", ""),
    ]

    for col, value in enumerate(values, 1):
        cell = ws.cell(row=row, column=col, value=value)
        cell.alignment = Alignment(wrap_text=True, vertical="top")

        # 링크 컬럼 하이퍼링크 처리
        if col == 5 and value:
            try:
                cell.hyperlink = value
                cell.font = Font(color="0563C1", underline="single")
            except Exception:
                pass

    # 행 높이
    ws.row_dimensions[row].height = 40


def _apply_column_widths(ws) -> None:
    """컬럼 너비 설정"""
    for col, width in enumerate(COL_WIDTHS, 1):
        ws.column_dimensions[get_column_letter(col)].width = width

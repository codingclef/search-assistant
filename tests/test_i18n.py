"""
Tests for modules/i18n.py

Verifies that both KO and JA dicts are complete, consistent,
and contain all keys required by app.py and excel_writer.py.
"""
import pytest
from modules.i18n import get_strings, KO, JA


def test_get_strings_ko_returns_ko_dict():
    assert get_strings("ko") is KO


def test_get_strings_ja_returns_ja_dict():
    assert get_strings("ja") is JA


def test_get_strings_unknown_lang_defaults_to_ko():
    assert get_strings("en") is KO
    assert get_strings("") is KO


def test_ko_and_ja_have_identical_keys():
    missing_in_ja = set(KO.keys()) - set(JA.keys())
    missing_in_ko = set(JA.keys()) - set(KO.keys())
    assert not missing_in_ja, f"Keys in KO but missing in JA: {missing_in_ja}"
    assert not missing_in_ko, f"Keys in JA but missing in KO: {missing_in_ko}"


def test_all_ko_values_are_non_empty_strings():
    for key, value in KO.items():
        assert isinstance(value, str), f"KO[{key!r}] is not a string (got {type(value)})"
        assert value.strip(), f"KO[{key!r}] is empty or whitespace-only"


def test_all_ja_values_are_non_empty_strings():
    for key, value in JA.items():
        assert isinstance(value, str), f"JA[{key!r}] is not a string (got {type(value)})"
        assert value.strip(), f"JA[{key!r}] is empty or whitespace-only"


# Keys that app.py and excel_writer.py depend on
_REQUIRED_KEYS = [
    # settings UI
    "start_label", "end_label", "section_settings",
    "time_range_err", "time_help", "start_button",
    "search_engine_label", "naver_checkbox", "daum_checkbox",
    "engines_err", "password_label", "password_placeholder", "password_err",
    # sections
    "section_preset", "section_keywords", "section_categories", "section_results",
    "section_feedback",
    # preset
    "preset_load", "preset_save", "preset_delete", "preset_rename",
    "preset_name_placeholder", "preset_none", "preset_select_placeholder",
    "preset_save_success", "preset_err_name", "preset_err_keyword",
    "preset_err_categories",
    # keywords
    "keywords_label", "keywords_placeholder", "keywords_err",
    # categories
    "add_sheet", "categories_err", "categories_caption",
    # status / progress
    "spinner_text", "status_collecting", "status_classifying",
    "status_excel", "status_done", "log_collecting", "log_collected",
    "log_classifying", "log_excel", "elapsed_label",
    "warn_no_articles", "warn_naver_fail", "warn_daum_fail",
    "err_classify", "err_excel",
    # results
    "count_unit", "download_button", "filename_prefix",
    # feedback
    "feedback_save_button", "feedback_save_success", "feedback_no_changes",
    "feedback_caption", "ilam_feedback_hint",
    "no_articles_in_cat", "no_articles_holdup", "no_articles_na",
    # excel columns
    "col_no", "col_keyword", "col_datetime", "col_engine",
    "col_media", "col_title", "col_link", "col_category",
    "col_reason", "col_reason_ai",
    # sheet / tab names
    "sheet_ilam", "sheet_holdup", "sheet_na",
    # engine labels
    "engine_naver", "engine_daum",
]


@pytest.mark.parametrize("key", _REQUIRED_KEYS)
def test_required_key_exists_in_ko(key):
    assert key in KO, f"Required key {key!r} is missing from KO"


@pytest.mark.parametrize("key", _REQUIRED_KEYS)
def test_required_key_exists_in_ja(key):
    assert key in JA, f"Required key {key!r} is missing from JA"

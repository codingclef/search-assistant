"""
Tests for modules/daum_search.py

Covers URL timestamp extraction and date string parsing.
Network calls (search_daum_news) are not tested here.
"""
from datetime import datetime, timedelta, timezone

import pytest

from modules.daum_search import _extract_pub_dt_from_link, _parse_date


class TestExtractPubDtFromLink:
    def test_valid_daum_url_extracts_datetime(self):
        url = "https://v.daum.net/v/20260327165924428"
        result = _extract_pub_dt_from_link(url)
        assert result == datetime(2026, 3, 27, 16, 59, 24)

    def test_different_valid_daum_url(self):
        url = "https://v.daum.net/v/20240101090000123"
        result = _extract_pub_dt_from_link(url)
        assert result == datetime(2024, 1, 1, 9, 0, 0)

    def test_url_without_daum_timestamp_returns_none(self):
        url = "https://www.chosun.com/article/12345"
        assert _extract_pub_dt_from_link(url) is None

    def test_daum_url_without_timestamp_suffix_returns_none(self):
        url = "https://v.daum.net/v/abc123"
        assert _extract_pub_dt_from_link(url) is None

    def test_partial_timestamp_13_digits_returns_none(self):
        url = "https://v.daum.net/v/2026032716592"  # 13자리 (부족)
        assert _extract_pub_dt_from_link(url) is None

    def test_empty_string_returns_none(self):
        assert _extract_pub_dt_from_link("") is None

    def test_none_input_returns_none(self):
        assert _extract_pub_dt_from_link(None) is None

    def test_naver_url_returns_none(self):
        url = "https://n.news.naver.com/article/123456789012"
        assert _extract_pub_dt_from_link(url) is None


class TestParseDate:
    # 절대 날짜 형식
    def test_dot_format_with_time(self):
        assert _parse_date("2024.03.25 09:30") == datetime(2024, 3, 25, 9, 30)

    def test_dash_format_with_time(self):
        assert _parse_date("2024-03-25 09:30") == datetime(2024, 3, 25, 9, 30)

    def test_dot_format_date_only(self):
        assert _parse_date("2024.03.25") == datetime(2024, 3, 25, 0, 0)

    def test_dash_format_date_only(self):
        assert _parse_date("2024-03-25") == datetime(2024, 3, 25, 0, 0)

    def test_midnight_time(self):
        assert _parse_date("2024.01.01 00:00") == datetime(2024, 1, 1, 0, 0)

    def test_end_of_day_time(self):
        assert _parse_date("2024.12.31 23:59") == datetime(2024, 12, 31, 23, 59)

    # 상대 시간 형식
    def test_relative_minutes_returns_recent_time(self):
        result = _parse_date("30분 전")
        assert result is not None
        now_kst = datetime.now(tz=timezone.utc).replace(tzinfo=None) + timedelta(hours=9)
        expected = now_kst - timedelta(minutes=30)
        assert abs((result - expected).total_seconds()) < 10  # 10초 이내

    def test_relative_1_minute(self):
        result = _parse_date("1분 전")
        assert result is not None
        now_kst = datetime.now(tz=timezone.utc).replace(tzinfo=None) + timedelta(hours=9)
        expected = now_kst - timedelta(minutes=1)
        assert abs((result - expected).total_seconds()) < 10

    def test_relative_hours_returns_recent_time(self):
        result = _parse_date("2시간 전")
        assert result is not None
        now_kst = datetime.now(tz=timezone.utc).replace(tzinfo=None) + timedelta(hours=9)
        expected = now_kst - timedelta(hours=2)
        assert abs((result - expected).total_seconds()) < 10

    def test_relative_1_hour(self):
        result = _parse_date("1시간 전")
        assert result is not None
        now_kst = datetime.now(tz=timezone.utc).replace(tzinfo=None) + timedelta(hours=9)
        expected = now_kst - timedelta(hours=1)
        assert abs((result - expected).total_seconds()) < 10

    # 엣지 케이스
    def test_empty_string_returns_none(self):
        assert _parse_date("") is None

    def test_none_input_returns_none(self):
        assert _parse_date(None) is None

    def test_unrecognized_format_returns_none(self):
        assert _parse_date("어제") is None
        assert _parse_date("방금") is None
        assert _parse_date("invalid-date") is None

    def test_whitespace_only_returns_none(self):
        assert _parse_date("   ") is None

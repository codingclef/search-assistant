"""
Tests for modules/naver_search.py

Covers HTML cleaning and media source extraction.
Network calls (search_naver_news) are not tested here.
"""
import pytest
from modules.naver_search import _clean_html, _extract_source


class TestCleanHtml:
    def test_strips_bold_tag(self):
        assert _clean_html("<b>제목</b>") == "제목"

    def test_strips_nested_tags(self):
        assert _clean_html("<b><em>텍스트</em></b>") == "텍스트"

    def test_strips_span_with_attributes(self):
        assert _clean_html('<span class="highlight">기사</span>') == "기사"

    def test_decodes_quot_entity(self):
        assert _clean_html("&quot;삼성전자&quot;") == '"삼성전자"'

    def test_decodes_amp_entity(self):
        assert _clean_html("A&amp;B") == "A&B"

    def test_decodes_lt_gt_entities(self):
        assert _clean_html("&lt;b&gt;텍스트&lt;/b&gt;") == "<b>텍스트</b>"

    def test_decodes_apos_entity(self):
        assert _clean_html("it&#39;s") == "it's"

    def test_strips_leading_trailing_whitespace(self):
        assert _clean_html("  안녕  ") == "안녕"

    def test_empty_string(self):
        assert _clean_html("") == ""

    def test_plain_text_unchanged(self):
        assert _clean_html("Samsung Electronics") == "Samsung Electronics"

    def test_combined_tag_and_entity(self):
        result = _clean_html('<b>삼성 &quot;파운드리&quot;</b>')
        assert result == '삼성 "파운드리"'

    def test_multiple_tags(self):
        assert _clean_html("<p><b>제목</b> <span>내용</span></p>") == "제목 내용"

    def test_only_tags_returns_empty(self):
        assert _clean_html("<b></b><em></em>") == ""


class TestExtractSource:
    # 종합일간지
    def test_chosun(self):
        assert _extract_source("https://www.chosun.com/article/123") == "조선일보"

    def test_joongang(self):
        assert _extract_source("https://joongang.co.kr/article/123") == "중앙일보"

    def test_hani(self):
        assert _extract_source("https://www.hani.co.kr/article/123") == "한겨레"

    def test_donga(self):
        assert _extract_source("https://www.donga.com/news/123") == "동아일보"

    # 경제지
    def test_mk(self):
        assert _extract_source("https://www.mk.co.kr/news/123") == "매일경제"

    def test_hankyung(self):
        assert _extract_source("https://www.hankyung.com/article/123") == "한국경제"

    def test_edaily(self):
        assert _extract_source("https://www.edaily.co.kr/news/123") == "이데일리"

    def test_mt(self):
        assert _extract_source("https://news.mt.co.kr/article/123") == "머니투데이"

    # 방송
    def test_yonhapnews(self):
        assert _extract_source("https://www.yonhapnews.co.kr/article/123") == "연합뉴스"

    def test_yna(self):
        assert _extract_source("https://www.yna.co.kr/article/123") == "연합뉴스"

    def test_kbs(self):
        assert _extract_source("https://news.kbs.co.kr/news/view.do?ncd=123") == "KBS"

    def test_mbc(self):
        assert _extract_source("https://www.mbc.co.kr/news/123") == "MBC"

    def test_sbs(self):
        assert _extract_source("https://news.sbs.co.kr/article/123") == "SBS"

    def test_ytn(self):
        assert _extract_source("https://www.ytn.co.kr/article/123") == "YTN"

    def test_jtbc(self):
        assert _extract_source("https://news.jtbc.co.kr/article/123") == "JTBC"

    # IT/전문지
    def test_etnews(self):
        assert _extract_source("https://www.etnews.com/article/123") == "전자신문"

    def test_sisajournal(self):
        assert _extract_source("https://www.sisajournal.com/news/articleView.html") == "시사저널"

    # 인터넷
    def test_newsis(self):
        assert _extract_source("https://www.newsis.com/view/123") == "뉴시스"

    def test_news1(self):
        assert _extract_source("https://www.news1.kr/articles/123") == "뉴스1"

    # 알 수 없는 도메인 → TLD 제거 후 반환
    def test_unknown_com_domain(self):
        result = _extract_source("https://www.unknownnews.com/article/123")
        assert result == "unknownnews"

    def test_unknown_co_kr_domain(self):
        result = _extract_source("https://www.somenews.co.kr/article/123")
        assert result == "somenews"

    def test_unknown_net_domain(self):
        result = _extract_source("https://pressnet.net/article/123")
        assert result == "pressnet"

    # 엣지 케이스
    def test_empty_string(self):
        assert _extract_source("") == ""

    def test_none_url(self):
        assert _extract_source(None) == ""

    def test_url_without_scheme(self):
        # 스킴 없으면 매칭 안 됨
        result = _extract_source("www.chosun.com/article")
        assert result == ""

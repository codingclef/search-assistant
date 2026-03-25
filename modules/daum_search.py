from __future__ import annotations

import requests
import re
import time as time_module
from datetime import datetime, timedelta
from bs4 import BeautifulSoup


def search_daum_news(
    keyword: str,
    start_dt: datetime,
    end_dt: datetime,
) -> list[dict]:
    """
    다음 뉴스를 크롤링하여 기사를 수집합니다.
    공식 API가 없으므로 웹 크롤링 방식을 사용합니다.
    start_dt ~ end_dt 범위의 기사만 반환합니다.
    """
    articles = []

    sd = start_dt.strftime("%Y%m%d%H%M%S")
    ed = end_dt.strftime("%Y%m%d%H%M%S")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9",
    }

    page = 1
    while page <= 20:
        params = {
            "w": "news",
            "q": keyword,
            "sort": "recency",
            "period": "u",
            "sd": sd,
            "ed": ed,
            "p": page,
        }

        try:
            response = requests.get(
                "https://search.daum.net/search",
                params=params,
                headers=headers,
                timeout=10,
            )

            if response.status_code != 200:
                break

            soup = BeautifulSoup(response.text, "lxml")

            # 다음 뉴스 검색 결과 아이템 셀렉터 (다음 HTML 구조에 맞게 시도)
            news_items = (
                soup.select("li.item-ad")
                or soup.select(".c-item-search")
                or soup.select("ul.list-basic > li")
                or soup.select(".wrap_cont")
            )

            if not news_items:
                break

            found = 0
            for item in news_items:
                article = _parse_item(item, keyword, start_dt, end_dt)
                if article:
                    articles.append(article)
                    found += 1

            # 이 페이지에서 아무것도 못 가져오면 중단
            if found == 0:
                break

        except Exception:
            break

        page += 1
        time_module.sleep(0.5)

    return articles


def _parse_item(
    item,
    keyword: str,
    start_dt: datetime,
    end_dt: datetime,
) -> dict | None:
    """BeautifulSoup 아이템에서 기사 정보를 파싱합니다."""
    try:
        # 제목 & 링크
        title_el = (
            item.select_one("a.tit-g")
            or item.select_one(".tit_g a")
            or item.select_one("a[class*='tit']")
            or item.select_one("strong a")
            or item.select_one("h3 a")
            or item.select_one("h4 a")
            or item.select_one("a[href*='news']")
        )

        if not title_el:
            return None

        title = title_el.get_text(strip=True)
        link = title_el.get("href", "")

        if not title or not link:
            return None

        # 언론사
        source_el = (
            item.select_one(".info_news")
            or item.select_one(".f-ebold")
            or item.select_one("[class*='source']")
            or item.select_one("[class*='media']")
            or item.select_one("[class*='press']")
        )
        source = source_el.get_text(strip=True) if source_el else ""

        # 날짜
        date_el = (
            item.select_one(".info_date")
            or item.select_one("[class*='date']")
            or item.select_one("[class*='time']")
            or item.select_one("span.f-small")
        )
        date_str = date_el.get_text(strip=True) if date_el else ""
        pub_dt = _parse_date(date_str)

        if pub_dt is None:
            return None

        if not (start_dt <= pub_dt <= end_dt):
            return None

        # 요약
        desc_el = (
            item.select_one(".f-eb")
            or item.select_one("[class*='desc']")
            or item.select_one("p")
        )
        description = desc_el.get_text(strip=True) if desc_el else ""

        return {
            "keyword": keyword,
            "title": title,
            "link": link,
            "published_at": pub_dt,
            "source": source,
            "description": description,
            "category": "",
            "reason": "",
        }

    except Exception:
        return None


def _parse_date(date_str: str) -> datetime | None:
    """다양한 다음 날짜 형식을 파싱합니다."""
    if not date_str:
        return None

    date_str = date_str.strip()

    # 절대 날짜: "2024.03.25 09:30", "2024-03-25 09:30"
    for fmt in ["%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M", "%Y.%m.%d", "%Y-%m-%d"]:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    now = datetime.now()

    # 상대 시간: "3분 전", "2시간 전"
    match = re.search(r"(\d+)분\s*전", date_str)
    if match:
        return now - timedelta(minutes=int(match.group(1)))

    match = re.search(r"(\d+)시간\s*전", date_str)
    if match:
        return now - timedelta(hours=int(match.group(1)))

    return None

from __future__ import annotations

import requests
import re
import time as time_module
from datetime import datetime
from email.utils import parsedate_to_datetime


def search_naver_news(
    keyword: str,
    start_dt: datetime,
    end_dt: datetime,
    client_id: str,
    client_secret: str,
) -> list[dict]:
    """
    네이버 검색 API로 뉴스 기사를 수집합니다.
    start_dt ~ end_dt 범위의 기사만 반환합니다.
    """
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }

    articles = []
    start = 1

    while start <= 1000:
        params = {
            "query": keyword,
            "display": 100,
            "start": start,
            "sort": "date",
        }

        try:
            response = requests.get(
                "https://openapi.naver.com/v1/search/news.json",
                headers=headers,
                params=params,
                timeout=10,
            )

            if response.status_code != 200:
                break

            data = response.json()
            items = data.get("items", [])

            if not items:
                break

            stop = False
            for item in items:
                try:
                    pub_dt = parsedate_to_datetime(item["pubDate"])
                    # 타임존 정보 제거 후 KST 기준 naive datetime으로 변환
                    import pytz
                    kst = pytz.timezone("Asia/Seoul")
                    pub_dt = pub_dt.astimezone(kst).replace(tzinfo=None)
                except Exception:
                    try:
                        # pytz 없을 경우 UTC+9 수동 처리
                        from datetime import timezone, timedelta
                        pub_dt = parsedate_to_datetime(item["pubDate"])
                        kst_offset = timezone(timedelta(hours=9))
                        pub_dt = pub_dt.astimezone(kst_offset).replace(tzinfo=None)
                    except Exception:
                        continue

                # start_dt보다 오래된 기사가 나오면 중단 (날짜순 정렬)
                if pub_dt < start_dt:
                    stop = True
                    break

                if pub_dt <= end_dt:
                    link = item.get("originallink") or item.get("link", "")
                    articles.append({
                        "keyword": keyword,
                        "title": _clean_html(item.get("title", "")),
                        "link": link,
                        "published_at": pub_dt,
                        "source": _extract_source(link),
                        "description": _clean_html(item.get("description", "")),
                        "category": "",
                        "reason": "",
                    })

            if stop:
                break

        except Exception:
            break

        start += 100
        time_module.sleep(0.1)

    return articles


def _clean_html(text: str) -> str:
    """HTML 태그 제거"""
    return re.sub(r"<[^>]+>", "", text).strip()


def _extract_source(url: str) -> str:
    """URL에서 언론사 도메인 추출"""
    match = re.search(r"https?://(?:www\.)?([^/]+)", url or "")
    if match:
        domain = match.group(1)
        # 알려진 언론사 도메인 매핑
        known_sources = {
            "chosun.com": "조선일보",
            "joongang.co.kr": "중앙일보",
            "donga.com": "동아일보",
            "hani.co.kr": "한겨레",
            "khan.co.kr": "경향신문",
            "mk.co.kr": "매일경제",
            "hankyung.com": "한국경제",
            "yonhapnews.co.kr": "연합뉴스",
            "yna.co.kr": "연합뉴스",
            "jtbc.co.kr": "JTBC",
            "kbs.co.kr": "KBS",
            "mbc.co.kr": "MBC",
            "sbs.co.kr": "SBS",
        }
        for k, v in known_sources.items():
            if k in domain:
                return v
        # 매핑 없으면 도메인 그대로 반환
        domain = re.sub(r"\.(co\.kr|com|net|org|kr)$", "", domain)
        domain = re.sub(r"\.(co|com|net|org)$", "", domain)
        return domain
    return ""

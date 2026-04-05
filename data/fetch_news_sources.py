#!/usr/bin/env python3
"""
뉴스 외부 수집 레이어 — fetch_news.py의 외부 API 호출 담당
- Google News RSS (무료, 무제한)
- Brave Search API (유료, 최근 24시간)
- 관련도 스코어링
"""

import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import HTTP_RETRY_CONFIG
from utils.http import retry_request

BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/news/search"


# ── Google News RSS (무료) ──


def fetch_google_news_rss(query: str, count: int = 5, lang: str = "ko") -> list[dict]:
    """Google News RSS로 무료 뉴스 수집 (자동 재시도)"""
    encoded = urllib.parse.quote(query)
    url = (
        f"https://news.google.com/rss/search?q={encoded}&hl={lang}&gl=KR&ceid=KR:{lang}"
    )
    body = retry_request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=10,
        max_retries=HTTP_RETRY_CONFIG["max_retries"],
        base_delay=HTTP_RETRY_CONFIG["base_delay"],
    )
    root = ET.fromstring(body)

    items = []
    for item in root.findall(".//item")[:count]:
        title = item.findtext("title", "")
        link = item.findtext("link", "")
        pub_date = item.findtext("pubDate", "")
        source = item.findtext("source", "")
        items.append(
            {
                "title": title,
                "url": link,
                "source": source,
                "published_at": pub_date,
            }
        )
    return items


# ── Brave Search API (유료) ──


def search_brave_news(query: str, count: int = 2) -> list[dict]:
    """Brave Search API로 뉴스 검색"""
    if not BRAVE_API_KEY:
        raise ValueError("BRAVE_API_KEY 환경변수가 설정되지 않았습니다")

    params = urllib.parse.urlencode(
        {
            "q": query,
            "count": count,
            "freshness": "pd",  # 최근 24시간
        }
    )
    url = f"{BRAVE_SEARCH_URL}?{params}"

    try:
        import gzip as _gzip
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": BRAVE_API_KEY,
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
                raw = _gzip.decompress(raw)
        data = json.loads(raw)
        return data.get("results", [])
    except urllib.error.URLError as e:
        raise ConnectionError(f"Brave Search 네트워크 오류: {e}")


# ── 관련도 스코어링 ──


def calculate_relevance(title: str, keywords: list[str]) -> float:
    """기사 제목 기반 관련도 스코어 계산 (0.0 ~ 1.0)"""
    title_lower = title.lower()
    matched = sum(1 for kw in keywords if kw.lower() in title_lower)
    if not keywords:
        return 0.5
    return round(min(matched / len(keywords), 1.0), 2)

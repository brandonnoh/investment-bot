#!/usr/bin/env python3
"""
종목 발굴 검색/추출 레이어 — Brave/Naver 뉴스 검색, 종목 매칭
fetch_opportunities.py의 파이프라인 오케스트레이션으로부터 분리된 순수 검색 함수들.
"""

import contextlib
import gzip
import json
import logging
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

try:
    from analysis.sentiment import calculate_sentiment
except ImportError:

    def calculate_sentiment(title, summary):
        """감성 분석 폴백 — 항상 0.0 반환."""
        return 0.0


with contextlib.suppress(ImportError):
    from data.ticker_master import (
        extract_companies,
        extract_ticker_codes,
        extract_us_tickers,
    )

logger = logging.getLogger(__name__)


def search_brave(query: str, count: int = 10) -> list:
    """Brave Search API로 뉴스 검색.

    Args:
        query: 검색 키워드
        count: 결과 수 (기본 10)

    Returns:
        뉴스 결과 리스트 [{"title", "description", "url"}, ...]
    """
    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        logger.warning("BRAVE_API_KEY 미설정 — Brave 검색 건너뜀")
        return []

    encoded_q = urllib.parse.quote(query)
    url = (
        f"https://api.search.brave.com/res/v1/news/search"
        f"?q={encoded_q}&count={count}&search_lang=ko"
    )
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key,
        },
    )

    try:
        resp = urllib.request.urlopen(req, timeout=15)
        raw = resp.read()
        # gzip 압축 응답 자동 처리
        if resp.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        data = json.loads(raw)
        results = data.get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "description": r.get("description", ""),
                "url": r.get("url", ""),
                "source": "brave",
            }
            for r in results
        ]
    except Exception as e:
        logger.error(f"Brave 검색 실패: {e}")
        return []


def search_naver_news(query: str, count: int = 10) -> list:
    """Naver 뉴스 검색 API (선택사항 — 환경변수 없으면 빈 결과).

    Args:
        query: 검색 키워드
        count: 결과 수 (기본 10)

    Returns:
        뉴스 결과 리스트 [{"title", "description", "url"}, ...]
    """
    client_id = os.environ.get("NAVER_CLIENT_ID", "")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return []

    encoded_q = urllib.parse.quote(query)
    url = (
        f"https://openapi.naver.com/v1/search/news.json?query={encoded_q}&display={count}&sort=date"
    )
    req = urllib.request.Request(
        url,
        headers={
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
        },
    )

    try:
        resp = urllib.request.urlopen(req, timeout=15)
        raw = resp.read()
        data = json.loads(raw)
        items = data.get("items", [])
        # HTML 태그 제거
        tag_re = re.compile(r"<[^>]+>")
        return [
            {
                "title": tag_re.sub("", item.get("title", "")),
                "description": tag_re.sub("", item.get("description", "")),
                "url": item.get("link", ""),
                "source": "naver",
            }
            for item in items
        ]
    except Exception as e:
        logger.error(f"Naver 뉴스 검색 실패: {e}")
        return []


def _resolve_kr_ticker(code: str, master: list) -> dict | None:
    """6자리 코드로 KS/KQ 종목 탐색. 매칭 결과 dict 또는 None 반환.

    Args:
        code: 6자리 종목 코드
        master: 종목 사전 리스트

    Returns:
        {"ticker": ..., "name": ...} 또는 None
    """
    ticker_ks = f"{code}.KS"
    for item in master:
        if item["ticker"] == ticker_ks:
            return {"ticker": ticker_ks, "name": item["name"]}
    ticker_kq = f"{code}.KQ"
    for item in master:
        if item["ticker"] == ticker_kq:
            return {"ticker": ticker_kq, "name": item["name"]}
    return None


def _match_tickers_in_text(text: str, master: list) -> list[dict]:
    """텍스트에서 KR 코드, 종목명, 미국 티커 모두 매칭. 매칭 리스트 반환.

    Args:
        text: 제목 + 설명 합산 텍스트
        master: 종목 사전 리스트

    Returns:
        [{"ticker": ..., "name": ...}, ...] (중복 포함 가능)
    """
    matched: list[dict] = []

    # 1. 종목코드(6자리) 추출
    for code in extract_ticker_codes(text):
        result = _resolve_kr_ticker(code, master)
        if result:
            matched.append(result)

    # 2. 종목명 직접 매칭
    for item in extract_companies(text, master):
        matched.append({"ticker": item["ticker"], "name": item["name"]})

    # 3. 미국 티커 추출
    for t in extract_us_tickers(text):
        matched.append({"ticker": t, "name": config.US_TICKER_MAP.get(t, t)})

    return matched


def extract_opportunities(news: list, master: list, keyword: str) -> list:
    """뉴스 결과에서 종목 후보 추출.

    각 뉴스에서 종목코드(6자리)와 종목명을 매칭하여 후보 리스트 생성.

    Args:
        news: 뉴스 결과 리스트
        master: 종목 사전 리스트
        keyword: 발굴 키워드

    Returns:
        종목 후보 리스트 [{"ticker", "name", "discovered_via", ...}, ...]
    """
    opportunities = []
    seen_tickers: set = set()

    for article in news:
        title = article.get("title", "")
        desc = article.get("description", "")
        url = article.get("url", "")
        source = article.get("source", "unknown")
        text = f"{title} {desc}"

        for m in _match_tickers_in_text(text, master):
            ticker = m["ticker"]
            if ticker not in seen_tickers:
                seen_tickers.add(ticker)
                opportunities.append(
                    {
                        "ticker": ticker,
                        "name": m["name"],
                        "discovered_via": keyword,
                        "source": source,
                        "url": url,
                        "sentiment": calculate_sentiment(title, desc),
                        "title": title,
                        "composite_score": None,
                        "price_at_discovery": None,
                    }
                )

    return opportunities

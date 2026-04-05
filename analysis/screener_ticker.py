#!/usr/bin/env python3
"""
종목 단위 분석 — Yahoo Finance 시세 조회 및 단일 종목 지표 계산
screener.py에서 분리된 모듈
"""

from __future__ import annotations

import json
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import YAHOO_HEADERS, YAHOO_TIMEOUT  # noqa: E402


def fetch_yahoo_quote(ticker: str) -> dict:
    """Yahoo Finance에서 단일 종목 시세 조회"""
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1mo"
    req = urllib.request.Request(url, headers=YAHOO_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=YAHOO_TIMEOUT) as resp:
            data = json.load(resp)
            result = data["chart"]["result"]
            if not result:
                raise ValueError(f"데이터 없음: {ticker}")
            return result[0]
    except urllib.error.URLError as e:
        raise ConnectionError(f"네트워크 오류 ({ticker}): {e}")
    except (KeyError, IndexError) as e:
        raise ValueError(f"응답 파싱 실패 ({ticker}): {e}")


def analyze_ticker(ticker_info: dict) -> Optional[dict]:
    """종목 분석 — 현재가, 1개월 수익률, 거래량"""
    ticker = ticker_info["ticker"]
    try:
        data = fetch_yahoo_quote(ticker)
        meta = data["meta"]
        price = meta["regularMarketPrice"]
        prev_close = meta.get("chartPreviousClose", meta.get("previousClose", price))

        # 1개월 수익률 계산
        indicators = data.get("indicators", {})
        closes = indicators.get("quote", [{}])[0].get("close", [])
        valid_closes = [c for c in closes if c is not None]

        month_return = None
        if valid_closes and len(valid_closes) >= 2:
            first_close = valid_closes[0]
            if first_close > 0:
                month_return = round((price - first_close) / first_close * 100, 2)

        # 전일 대비 변동률
        day_change = (
            round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0
        )

        volume = meta.get("regularMarketVolume", 0)

        return {
            "ticker": ticker,
            "name": ticker_info["name"],
            "market": ticker_info["market"],
            "price": price,
            "day_change": day_change,
            "month_return": month_return,
            "volume": volume,
            "currency": meta.get("currency", "USD"),
        }
    except Exception as e:
        print(f"    ❌ {ticker_info['name']} ({ticker}): {e}")
        return None

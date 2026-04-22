#!/usr/bin/env python3
"""
스크리너 유니버스 정의 및 유니버스 스크리닝 로직

- UNIVERSE_KOSPI200: 코스피 200 전체 종목 (200개)
- UNIVERSE_SP500: S&P 500 전체 종목 (500개)
- UNIVERSE_SP100: UNIVERSE_SP500 별칭 (하위 호환)
- SCREENING_TARGETS: 섹터별 대표 종목/ETF
- screen_universe(): 유니버스 전체 스크리닝
- merge_universe(): 기존 종목 + 발굴 종목 병합
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis.screener_ticker import analyze_ticker  # noqa: E402
from analysis.universe_kr import UNIVERSE_KOSPI200  # noqa: E402
from analysis.universe_us import UNIVERSE_SP500  # noqa: E402

# 하위 호환 별칭
UNIVERSE_SP100 = UNIVERSE_SP500

# 섹터별 대표 종목/ETF
SCREENING_TARGETS = {
    "에너지": {
        "description": "에너지/유가 관련",
        "tickers": [
            {"ticker": "XLE", "name": "Energy Select SPDR", "market": "US"},
            {"ticker": "XOP", "name": "SPDR S&P Oil & Gas", "market": "US"},
            {"ticker": "USO", "name": "US Oil Fund", "market": "US"},
            {"ticker": "261220.KS", "name": "KODEX WTI원유선물", "market": "KR"},
        ],
    },
    "방산": {
        "description": "방위산업/방산",
        "tickers": [
            {"ticker": "ITA", "name": "iShares US Aerospace & Defense", "market": "US"},
            {"ticker": "LMT", "name": "Lockheed Martin", "market": "US"},
            {"ticker": "RTX", "name": "RTX Corp", "market": "US"},
            {"ticker": "458730.KS", "name": "TIGER 미국방산TOP10", "market": "KR"},
            {"ticker": "012450.KS", "name": "한화에어로스페이스", "market": "KR"},
        ],
    },
    "AI 인프라": {
        "description": "AI/반도체/데이터센터",
        "tickers": [
            {"ticker": "NVDA", "name": "NVIDIA", "market": "US"},
            {"ticker": "SMH", "name": "VanEck Semiconductor", "market": "US"},
            {"ticker": "AVGO", "name": "Broadcom", "market": "US"},
            {"ticker": "005930.KS", "name": "삼성전자", "market": "KR"},
            {"ticker": "000660.KS", "name": "SK하이닉스", "market": "KR"},
        ],
    },
}


def screen_universe(universe: list[dict], top_n: int = 10) -> list[dict]:
    """유니버스 전체 종목 스크리닝 — month_return 기준 상위 top_n개 반환."""
    results = []
    total = len(universe)
    for i, ticker_info in enumerate(universe):
        result = analyze_ticker(ticker_info)
        if result:
            results.append(result)
        if (i + 1) % 10 == 0:
            print(f"    {i + 1}/{total} 처리 완료 ({len(results)}개 성공)...")
            time.sleep(0.5)

    results.sort(key=lambda x: x.get("month_return") or -999, reverse=True)
    return results[:top_n]


def merge_universe(existing: list, opportunities: list) -> list:
    """기존 스크리닝 대상 + 발굴 종목 병합 (중복 제거)"""
    seen = set()
    merged = []
    for item in existing + opportunities:
        ticker = item.get("ticker", "")
        if ticker and ticker not in seen:
            seen.add(ticker)
            merged.append(item)
    return merged

#!/usr/bin/env python3
"""
스크리너 유니버스 정의 및 유니버스 스크리닝 로직

- UNIVERSE_KOSPI200: 코스피 200 주요 종목 (시가총액 상위 50개)
- UNIVERSE_SP100: S&P 100 주요 종목
- SCREENING_TARGETS: 섹터별 대표 종목/ETF
- screen_universe(): 유니버스 전체 스크리닝
- merge_universe(): 기존 종목 + 발굴 종목 병합
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis.screener_ticker import analyze_ticker  # noqa: E402

# ── 유니버스 정의 ──

# 코스피 200 주요 종목 (시가총액 상위 50개)
UNIVERSE_KOSPI200 = [
    {"ticker": "005930.KS", "name": "삼성전자", "market": "KR"},
    {"ticker": "000660.KS", "name": "SK하이닉스", "market": "KR"},
    {"ticker": "035420.KS", "name": "NAVER", "market": "KR"},
    {"ticker": "207940.KS", "name": "삼성바이오로직스", "market": "KR"},
    {"ticker": "005380.KS", "name": "현대차", "market": "KR"},
    {"ticker": "000270.KS", "name": "기아", "market": "KR"},
    {"ticker": "005490.KS", "name": "POSCO홀딩스", "market": "KR"},
    {"ticker": "051910.KS", "name": "LG화학", "market": "KR"},
    {"ticker": "055550.KS", "name": "신한지주", "market": "KR"},
    {"ticker": "105560.KS", "name": "KB금융", "market": "KR"},
    {"ticker": "028260.KS", "name": "삼성물산", "market": "KR"},
    {"ticker": "006400.KS", "name": "삼성SDI", "market": "KR"},
    {"ticker": "068270.KS", "name": "셀트리온", "market": "KR"},
    {"ticker": "086790.KS", "name": "하나금융지주", "market": "KR"},
    {"ticker": "003550.KS", "name": "LG", "market": "KR"},
    {"ticker": "066570.KS", "name": "LG전자", "market": "KR"},
    {"ticker": "034730.KS", "name": "SK", "market": "KR"},
    {"ticker": "012330.KS", "name": "현대모비스", "market": "KR"},
    {"ticker": "009150.KS", "name": "삼성전기", "market": "KR"},
    {"ticker": "096770.KS", "name": "SK이노베이션", "market": "KR"},
    {"ticker": "017670.KS", "name": "SK텔레콤", "market": "KR"},
    {"ticker": "030200.KS", "name": "KT", "market": "KR"},
    {"ticker": "316140.KS", "name": "우리금융지주", "market": "KR"},
    {"ticker": "032830.KS", "name": "삼성생명", "market": "KR"},
    {"ticker": "009540.KS", "name": "HD현대중공업", "market": "KR"},
    {"ticker": "042660.KS", "name": "한화오션", "market": "KR"},
    {"ticker": "012450.KS", "name": "한화에어로스페이스", "market": "KR"},
    {"ticker": "047810.KS", "name": "한국항공우주", "market": "KR"},
    {"ticker": "003670.KS", "name": "포스코퓨처엠", "market": "KR"},
    {"ticker": "010130.KS", "name": "고려아연", "market": "KR"},
    {"ticker": "004020.KS", "name": "현대제철", "market": "KR"},
    {"ticker": "000100.KS", "name": "유한양행", "market": "KR"},
    {"ticker": "128940.KS", "name": "한미약품", "market": "KR"},
    {"ticker": "035720.KS", "name": "카카오", "market": "KR"},
    {"ticker": "323410.KS", "name": "카카오뱅크", "market": "KR"},
    {"ticker": "018260.KS", "name": "삼성에스디에스", "market": "KR"},
    {"ticker": "024110.KS", "name": "IBK기업은행", "market": "KR"},
    {"ticker": "011200.KS", "name": "HMM", "market": "KR"},
    {"ticker": "015760.KS", "name": "한국전력", "market": "KR"},
    {"ticker": "003490.KS", "name": "대한항공", "market": "KR"},
    {"ticker": "036570.KS", "name": "엔씨소프트", "market": "KR"},
    {"ticker": "011170.KS", "name": "롯데케미칼", "market": "KR"},
    {"ticker": "009830.KS", "name": "한화솔루션", "market": "KR"},
    {"ticker": "047050.KS", "name": "포스코인터내셔널", "market": "KR"},
    {"ticker": "139480.KS", "name": "이마트", "market": "KR"},
    {"ticker": "032640.KS", "name": "LG유플러스", "market": "KR"},
    {"ticker": "000720.KS", "name": "현대건설", "market": "KR"},
    {"ticker": "326030.KS", "name": "SK바이오팜", "market": "KR"},
    {"ticker": "006280.KS", "name": "녹십자", "market": "KR"},
    {"ticker": "263750.KS", "name": "펄어비스", "market": "KR"},
]

# S&P 100 주요 종목
UNIVERSE_SP100 = [
    {"ticker": "AAPL", "name": "Apple", "market": "US"},
    {"ticker": "MSFT", "name": "Microsoft", "market": "US"},
    {"ticker": "NVDA", "name": "NVIDIA", "market": "US"},
    {"ticker": "AMZN", "name": "Amazon", "market": "US"},
    {"ticker": "META", "name": "Meta", "market": "US"},
    {"ticker": "GOOGL", "name": "Alphabet", "market": "US"},
    {"ticker": "TSLA", "name": "Tesla", "market": "US"},
    {"ticker": "LLY", "name": "Eli Lilly", "market": "US"},
    {"ticker": "AVGO", "name": "Broadcom", "market": "US"},
    {"ticker": "UNH", "name": "UnitedHealth", "market": "US"},
    {"ticker": "JPM", "name": "JPMorgan", "market": "US"},
    {"ticker": "XOM", "name": "Exxon Mobil", "market": "US"},
    {"ticker": "V", "name": "Visa", "market": "US"},
    {"ticker": "MA", "name": "Mastercard", "market": "US"},
    {"ticker": "PG", "name": "Procter & Gamble", "market": "US"},
    {"ticker": "HD", "name": "Home Depot", "market": "US"},
    {"ticker": "COST", "name": "Costco", "market": "US"},
    {"ticker": "MRK", "name": "Merck", "market": "US"},
    {"ticker": "ABBV", "name": "AbbVie", "market": "US"},
    {"ticker": "CVX", "name": "Chevron", "market": "US"},
    {"ticker": "PEP", "name": "PepsiCo", "market": "US"},
    {"ticker": "KO", "name": "Coca-Cola", "market": "US"},
    {"ticker": "CRM", "name": "Salesforce", "market": "US"},
    {"ticker": "TMO", "name": "Thermo Fisher", "market": "US"},
    {"ticker": "WMT", "name": "Walmart", "market": "US"},
    {"ticker": "ORCL", "name": "Oracle", "market": "US"},
    {"ticker": "BAC", "name": "Bank of America", "market": "US"},
    {"ticker": "ACN", "name": "Accenture", "market": "US"},
    {"ticker": "MCD", "name": "McDonald's", "market": "US"},
    {"ticker": "CSCO", "name": "Cisco", "market": "US"},
    {"ticker": "AMD", "name": "AMD", "market": "US"},
    {"ticker": "ABT", "name": "Abbott", "market": "US"},
    {"ticker": "NFLX", "name": "Netflix", "market": "US"},
    {"ticker": "LIN", "name": "Linde", "market": "US"},
    {"ticker": "GE", "name": "GE Aerospace", "market": "US"},
    {"ticker": "TXN", "name": "Texas Instruments", "market": "US"},
    {"ticker": "DHR", "name": "Danaher", "market": "US"},
    {"ticker": "RTX", "name": "RTX Corp", "market": "US"},
    {"ticker": "QCOM", "name": "Qualcomm", "market": "US"},
    {"ticker": "DIS", "name": "Disney", "market": "US"},
    {"ticker": "VZ", "name": "Verizon", "market": "US"},
    {"ticker": "IBM", "name": "IBM", "market": "US"},
    {"ticker": "CAT", "name": "Caterpillar", "market": "US"},
    {"ticker": "AMGN", "name": "Amgen", "market": "US"},
    {"ticker": "NOW", "name": "ServiceNow", "market": "US"},
    {"ticker": "GS", "name": "Goldman Sachs", "market": "US"},
    {"ticker": "INTU", "name": "Intuit", "market": "US"},
    {"ticker": "SPGI", "name": "S&P Global", "market": "US"},
    {"ticker": "UPS", "name": "UPS", "market": "US"},
    {"ticker": "BA", "name": "Boeing", "market": "US"},
    {"ticker": "HON", "name": "Honeywell", "market": "US"},
    {"ticker": "SYK", "name": "Stryker", "market": "US"},
    {"ticker": "BKNG", "name": "Booking Holdings", "market": "US"},
    {"ticker": "AXP", "name": "American Express", "market": "US"},
    {"ticker": "BLK", "name": "BlackRock", "market": "US"},
    {"ticker": "GILD", "name": "Gilead", "market": "US"},
    {"ticker": "DE", "name": "Deere & Company", "market": "US"},
    {"ticker": "ISRG", "name": "Intuitive Surgical", "market": "US"},
    {"ticker": "ADI", "name": "Analog Devices", "market": "US"},
    {"ticker": "T", "name": "AT&T", "market": "US"},
    {"ticker": "NEE", "name": "NextEra Energy", "market": "US"},
    {"ticker": "PM", "name": "Philip Morris", "market": "US"},
    {"ticker": "LOW", "name": "Lowe's", "market": "US"},
    {"ticker": "SCHW", "name": "Charles Schwab", "market": "US"},
    {"ticker": "MS", "name": "Morgan Stanley", "market": "US"},
    {"ticker": "CB", "name": "Chubb", "market": "US"},
    {"ticker": "TJX", "name": "TJX Companies", "market": "US"},
    {"ticker": "ADP", "name": "ADP", "market": "US"},
    {"ticker": "MMC", "name": "Marsh McLennan", "market": "US"},
    {"ticker": "ZTS", "name": "Zoetis", "market": "US"},
    {"ticker": "REGN", "name": "Regeneron", "market": "US"},
    {"ticker": "VRTX", "name": "Vertex Pharma", "market": "US"},
    {"ticker": "EOG", "name": "EOG Resources", "market": "US"},
    {"ticker": "SLB", "name": "SLB", "market": "US"},
    {"ticker": "MO", "name": "Altria", "market": "US"},
    {"ticker": "USB", "name": "U.S. Bancorp", "market": "US"},
    {"ticker": "PNC", "name": "PNC Financial", "market": "US"},
    {"ticker": "SO", "name": "Southern Company", "market": "US"},
    {"ticker": "DUK", "name": "Duke Energy", "market": "US"},
    {"ticker": "BSX", "name": "Boston Scientific", "market": "US"},
    {"ticker": "ICE", "name": "Intercontinental Exchange", "market": "US"},
    {"ticker": "COP", "name": "ConocoPhillips", "market": "US"},
    {"ticker": "ETN", "name": "Eaton", "market": "US"},
    {"ticker": "F", "name": "Ford", "market": "US"},
    {"ticker": "GM", "name": "General Motors", "market": "US"},
    {"ticker": "PYPL", "name": "PayPal", "market": "US"},
    {"ticker": "UBER", "name": "Uber", "market": "US"},
    {"ticker": "LMT", "name": "Lockheed Martin", "market": "US"},
    {"ticker": "NOC", "name": "Northrop Grumman", "market": "US"},
    {"ticker": "GD", "name": "General Dynamics", "market": "US"},
    {"ticker": "HCA", "name": "HCA Healthcare", "market": "US"},
    {"ticker": "PANW", "name": "Palo Alto Networks", "market": "US"},
    {"ticker": "LRCX", "name": "Lam Research", "market": "US"},
    {"ticker": "KLAC", "name": "KLA Corp", "market": "US"},
    {"ticker": "AMAT", "name": "Applied Materials", "market": "US"},
    {"ticker": "MU", "name": "Micron Technology", "market": "US"},
    {"ticker": "INTC", "name": "Intel", "market": "US"},
    {"ticker": "ADBE", "name": "Adobe", "market": "US"},
    {"ticker": "PLTR", "name": "Palantir", "market": "US"},
]

# 스크리닝 대상 섹터별 대표 종목/ETF
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
    """유니버스 전체 종목 스크리닝 — month_return 기준 상위 top_n개 반환.

    레이트 리밋 방지를 위해 10종목마다 0.5초 대기.
    실패 종목은 건너뛰고 계속 진행.
    """
    results = []
    total = len(universe)
    for i, ticker_info in enumerate(universe):
        result = analyze_ticker(ticker_info)
        if result:
            results.append(result)
        # 10종목마다 진행 상황 출력 + 레이트 리밋 대기
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

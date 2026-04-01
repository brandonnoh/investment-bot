#!/usr/bin/env python3
from __future__ import annotations
"""
종목 스크리너 — 오늘의 주목 섹터 + 신규 종목 발굴
Yahoo Finance API로 섹터별 주요 종목/ETF 분석
출력: output/intel/screener.md
"""

import json
import sys
import time  # noqa: F401  — screen_universe 레이트 리밋 대기용
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import OUTPUT_DIR, YAHOO_HEADERS, YAHOO_TIMEOUT

KST = timezone(timedelta(hours=9))

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


def generate_universe_section(
    kospi_top: list[dict],
    sp_top: list[dict],
    kospi_scanned: int,
    sp_scanned: int,
) -> str:
    """유니버스 스크리닝 결과 마크다운 섹션 생성"""
    lines = [
        "---",
        "",
        "## 🌏 유니버스 스크리닝 (1개월 수익률 기준)",
        "",
        f"> 코스피 200 상위 {kospi_scanned}개 + S&P 100 상위 {sp_scanned}개 스캔",
        "",
    ]

    def _table(stocks: list[dict], market_label: str) -> list[str]:
        section = [f"### {market_label} TOP 10", ""]
        if not stocks:
            section.append("> 데이터 수집 실패")
            section.append("")
            return section
        section.append("| 순위 | 종목 | 현재가 | 1개월 수익률 | 전일比 |")
        section.append("|------|------|--------|-------------|--------|")
        for i, s in enumerate(stocks, 1):
            is_us = s["market"] == "US"
            price_str = f"${s['price']:,.2f}" if is_us else f"{s['price']:,.0f}원"
            month_str = (
                f"{s['month_return']:+.2f}%"
                if s.get("month_return") is not None
                else "N/A"
            )
            day_str = f"{s['day_change']:+.2f}%"
            flag = "🔺" if (s.get("month_return") or 0) > 0 else "🔻"
            section.append(
                f"| {i} | {flag} {s['name']} ({s['ticker']}) | {price_str} | {month_str} | {day_str} |"
            )
        section.append("")
        return section

    lines.extend(_table(kospi_top, "코스피 200"))
    lines.extend(_table(sp_top, "S&P 100"))
    return "\n".join(lines)


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


def analyze_ticker(ticker_info: dict) -> dict | None:
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


def screen_sectors() -> dict:
    """섹터별 주요 종목 분석"""
    sector_results = {}

    for sector_name, sector_info in SCREENING_TARGETS.items():
        print(f"\n  📊 {sector_name} 섹터 분석 중...")
        results = []
        for ticker_info in sector_info["tickers"]:
            result = analyze_ticker(ticker_info)
            if result:
                results.append(result)
                status = "🔺" if (result.get("month_return") or 0) > 0 else "🔻"
                month_str = (
                    f"{result['month_return']:+.2f}%"
                    if result["month_return"] is not None
                    else "N/A"
                )
                print(
                    f"    {status} {result['name']}: {result['price']:,.2f} (1M: {month_str})"
                )

        # 1개월 수익률 기준 정렬
        results.sort(key=lambda x: x.get("month_return") or -999, reverse=True)
        sector_results[sector_name] = {
            "description": sector_info["description"],
            "stocks": results,
        }

    return sector_results


def pick_highlights(sector_results: dict) -> list[dict]:
    """주목 종목 3~5개 선별"""
    candidates = []
    for sector_name, data in sector_results.items():
        for stock in data["stocks"]:
            if stock.get("month_return") is not None:
                candidates.append(
                    {
                        **stock,
                        "sector": sector_name,
                    }
                )

    # 1개월 수익률 상위 + 일간 양전환 우선
    candidates.sort(
        key=lambda x: (
            x.get("month_return", -999),
            x.get("day_change", 0),
        ),
        reverse=True,
    )

    return candidates[:5]


def generate_screener_report(sector_results: dict, highlights: list[dict]) -> str:
    """스크리너 마크다운 리포트 생성"""
    now = datetime.now(KST)
    lines = [
        f"# 🔍 종목 스크리너 — {now.strftime('%Y-%m-%d')}",
        f"> 생성 시각: {now.strftime('%H:%M KST')}",
        "",
        "---",
        "",
    ]

    # 주목 종목 TOP 5
    lines.append("## ⭐ 오늘의 주목 종목")
    lines.append("")
    if highlights:
        lines.append("| 순위 | 종목 | 섹터 | 현재가 | 1개월 수익률 | 일간 등락 |")
        lines.append("|------|------|------|--------|-------------|----------|")
        for i, h in enumerate(highlights, 1):
            price_str = (
                f"${h['price']:,.2f}" if h["market"] == "US" else f"{h['price']:,.0f}원"
            )
            month_str = (
                f"{h['month_return']:+.2f}%" if h["month_return"] is not None else "N/A"
            )
            day_str = f"{h['day_change']:+.2f}%"
            flag = "🔺" if (h.get("month_return") or 0) > 0 else "🔻"
            lines.append(
                f"| {i} | {flag} {h['name']} ({h['ticker']}) | {h['sector']} | {price_str} | {month_str} | {day_str} |"
            )
            # 복합 점수가 있으면 서브 점수도 표시
            if h.get("composite_score") is not None:
                score_pct = (
                    f"{h['composite_score']:.0%}"
                    if h["composite_score"] <= 1
                    else str(h["composite_score"])
                )
                sub = h.get("sub_scores", {})
                if sub:
                    lines.append(
                        f"|   | ↳ 종합 점수 {score_pct} — 수익률 {sub.get('return', 0):.0%} | RSI {sub.get('rsi', 0):.0%} | 감성 {sub.get('sentiment', 0):.0%} | 매크로 {sub.get('macro', 0):.0%} | |"
                    )
                else:
                    lines.append(f"|   | ↳ 종합 점수 {score_pct} | | | | |")
        lines.append("")
    else:
        lines.append("> 분석 데이터 부족")
        lines.append("")

    # 섹터별 상세
    lines.append("---")
    lines.append("")
    lines.append("## 📊 섹터별 분석")
    lines.append("")

    for sector_name, data in sector_results.items():
        lines.append(f"### {sector_name} — {data['description']}")
        lines.append("")
        stocks = data["stocks"]
        if stocks:
            lines.append("| 종목 | 현재가 | 전일比 | 1개월 수익률 | 거래량 |")
            lines.append("|------|--------|--------|-------------|--------|")
            for s in stocks:
                price_str = (
                    f"${s['price']:,.2f}"
                    if s["market"] == "US"
                    else f"{s['price']:,.0f}원"
                )
                day_str = f"{s['day_change']:+.2f}%"
                month_str = (
                    f"{s['month_return']:+.2f}%"
                    if s["month_return"] is not None
                    else "N/A"
                )
                vol_str = f"{s['volume']:,.0f}" if s["volume"] else "N/A"
                flag = "🟢" if s["day_change"] >= 0 else "🔴"
                lines.append(
                    f"| {flag} {s['name']} | {price_str} | {day_str} | {month_str} | {vol_str} |"
                )
            lines.append("")
        else:
            lines.append("> 데이터 수집 실패")
            lines.append("")

    lines.append("---")
    lines.append(f"*자동 생성 by investment-bot screener | {now.isoformat()}*")
    lines.append("")

    return "\n".join(lines)


def run():
    """스크리너 파이프라인 실행"""
    print(
        f"\n🔍 종목 스크리너 시작 — {datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}"
    )

    # 섹터별 분석
    sector_results = screen_sectors()

    # opportunities.json이 있으면 발굴 종목 통합
    opp_path = OUTPUT_DIR / "opportunities.json"
    if opp_path.exists():
        try:
            with open(opp_path, encoding="utf-8") as f:
                opp_data = json.load(f)
            opp_tickers = [
                {
                    "ticker": o["ticker"],
                    "name": o.get("name", ""),
                    "sector": "발굴",
                    "market": o.get("market", "KR"),
                    "discovered_via": o.get("discovered_via", ""),
                }
                for o in opp_data.get("opportunities", [])
            ]
            # 기존 섹터 종목 리스트 추출
            existing_tickers = []
            for data in sector_results.values():
                existing_tickers.extend(data.get("stocks", []))
            merged = merge_universe(existing_tickers, opp_tickers)
            # 발굴 종목 중 기존에 없던 것들을 별도 섹터로 추가
            new_opps = [t for t in merged if t.get("sector") == "발굴"]
            if new_opps:
                sector_results["발굴 종목"] = {
                    "description": "AI 발굴 신규 종목",
                    "stocks": new_opps,
                }
                print(f"  🆕 발굴 종목 {len(new_opps)}개 통합")
        except Exception as e:
            print(f"  ⚠️ opportunities.json 로드 실패: {e}")

    # 주목 종목 선별
    highlights = pick_highlights(sector_results)

    # 유니버스 스크리닝
    print(f"\n  🌏 코스피 200 유니버스 스크리닝 ({len(UNIVERSE_KOSPI200)}개)...")
    kospi_top = []
    try:
        kospi_top = screen_universe(UNIVERSE_KOSPI200)
        print(f"  ✅ 코스피 TOP {len(kospi_top)}개 추출 완료")
    except Exception as e:
        print(f"  ⚠️ 코스피 유니버스 스크리닝 실패: {e}")

    print(f"\n  🌏 S&P 100 유니버스 스크리닝 ({len(UNIVERSE_SP100)}개)...")
    sp_top = []
    try:
        sp_top = screen_universe(UNIVERSE_SP100)
        print(f"  ✅ S&P 100 TOP {len(sp_top)}개 추출 완료")
    except Exception as e:
        print(f"  ⚠️ S&P 100 유니버스 스크리닝 실패: {e}")

    # 리포트 생성
    report = generate_screener_report(sector_results, highlights)
    report += "\n" + generate_universe_section(
        kospi_top, sp_top, len(UNIVERSE_KOSPI200), len(UNIVERSE_SP100)
    )

    # screener_results.json 저장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUTPUT_DIR / "screener_results.json"
    results_data = {
        "generated_at": datetime.now(KST).isoformat(),
        "kospi200_top10": kospi_top,
        "sp100_top10": sp_top,
        "total_kospi_scanned": len(UNIVERSE_KOSPI200),
        "total_sp_scanned": len(UNIVERSE_SP100),
    }
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results_data, f, ensure_ascii=False, indent=2)
    print(f"  💾 유니버스 결과 저장: {results_path}")

    # screener.md 저장
    output_path = OUTPUT_DIR / "screener.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n  📄 스크리너 저장: {output_path}")
    print(f"  ⭐ 주목 종목: {len(highlights)}개")
    print()

    return report


if __name__ == "__main__":
    run()

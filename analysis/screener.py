#!/usr/bin/env python3
"""
종목 스크리너 — 오늘의 주목 섹터 + 신규 종목 발굴
Yahoo Finance API로 섹터별 주요 종목/ETF 분석
출력: output/intel/screener.md
"""
import json
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import OUTPUT_DIR, YAHOO_HEADERS, YAHOO_TIMEOUT
from db.init_db import init_db

KST = timezone(timedelta(hours=9))

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
        day_change = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0

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
                month_str = f"{result['month_return']:+.2f}%" if result['month_return'] is not None else "N/A"
                print(f"    {status} {result['name']}: {result['price']:,.2f} (1M: {month_str})")

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
                candidates.append({
                    **stock,
                    "sector": sector_name,
                })

    # 1개월 수익률 상위 + 일간 양전환 우선
    candidates.sort(key=lambda x: (
        x.get("month_return", -999),
        x.get("day_change", 0),
    ), reverse=True)

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
            price_str = f"${h['price']:,.2f}" if h["market"] == "US" else f"{h['price']:,.0f}원"
            month_str = f"{h['month_return']:+.2f}%" if h['month_return'] is not None else "N/A"
            day_str = f"{h['day_change']:+.2f}%"
            flag = "🔺" if (h.get("month_return") or 0) > 0 else "🔻"
            lines.append(f"| {i} | {flag} {h['name']} ({h['ticker']}) | {h['sector']} | {price_str} | {month_str} | {day_str} |")
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
                price_str = f"${s['price']:,.2f}" if s["market"] == "US" else f"{s['price']:,.0f}원"
                day_str = f"{s['day_change']:+.2f}%"
                month_str = f"{s['month_return']:+.2f}%" if s['month_return'] is not None else "N/A"
                vol_str = f"{s['volume']:,.0f}" if s['volume'] else "N/A"
                flag = "🟢" if s['day_change'] >= 0 else "🔴"
                lines.append(f"| {flag} {s['name']} | {price_str} | {day_str} | {month_str} | {vol_str} |")
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
    print(f"\n🔍 종목 스크리너 시작 — {datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}")

    # 섹터별 분석
    sector_results = screen_sectors()

    # 주목 종목 선별
    highlights = pick_highlights(sector_results)

    # 리포트 생성
    report = generate_screener_report(sector_results, highlights)

    # 저장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "screener.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n  📄 스크리너 저장: {output_path}")
    print(f"  ⭐ 주목 종목: {len(highlights)}개")
    print()

    return report


if __name__ == "__main__":
    run()

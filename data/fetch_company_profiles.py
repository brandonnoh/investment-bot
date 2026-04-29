#!/usr/bin/env python3
"""스크리너 추천 종목 기업 프로필 사전 수집 — yfinance .info → company_profiles DB"""

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from analysis.value_screener_strategies import (  # noqa: E402
    STRATEGY_META,
    get_opportunities_cached,
)
from db.connection import get_db_conn  # noqa: E402

KST = timezone(timedelta(hours=9))
# 전략별 상위 N개만 수집
_TOP_N = 25
# yfinance rate limit 방지 (초)
_RATE_LIMIT = 0.3


def _collect_target_tickers() -> dict[str, list[str]]:
    """5개 전략에서 상위 종목을 모아 {ticker: [strategy_ids...]} 매핑 반환."""
    ticker_strategies: dict[str, list[str]] = {}
    for strategy_id in STRATEGY_META:
        opps = get_opportunities_cached(strategy_id)
        for opp in opps[:_TOP_N]:
            ticker = opp.get("ticker", "")
            if not ticker:
                continue
            ticker_strategies.setdefault(ticker, [])
            if strategy_id not in ticker_strategies[ticker]:
                ticker_strategies[ticker].append(strategy_id)
    return ticker_strategies


def _fetch_profile(ticker: str) -> dict | None:
    """yfinance에서 기업 프로필 조회. 유효하지 않으면 None 반환."""
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).info
    except Exception as e:
        print(f"  [skip] {ticker}: yfinance 오류 — {e}")
        return None

    if not info or (not info.get("currentPrice") and not info.get("marketCap")):
        print(f"  [skip] {ticker}: 유효한 데이터 없음")
        return None

    return {
        "name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "exchange": info.get("exchange"),
        "country": info.get("country"),
        "description": info.get("longBusinessSummary"),
        "website": info.get("website"),
        "employees": info.get("fullTimeEmployees"),
        "market_cap": info.get("marketCap"),
        "current_price": info.get("currentPrice"),
        "price_52w_high": info.get("fiftyTwoWeekHigh"),
        "price_52w_low": info.get("fiftyTwoWeekLow"),
    }


def _upsert_profile(conn, ticker: str, profile: dict, strategies: list[str]):
    """company_profiles 테이블에 UPSERT."""
    now = datetime.now(KST).isoformat()
    conn.execute(
        """INSERT INTO company_profiles
           (ticker, name, sector, industry, exchange, country, description,
            website, employees, market_cap, current_price,
            price_52w_high, price_52w_low, screen_strategies, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(ticker) DO UPDATE SET
             name=excluded.name, sector=excluded.sector,
             industry=excluded.industry, exchange=excluded.exchange,
             country=excluded.country, description=excluded.description,
             website=excluded.website, employees=excluded.employees,
             market_cap=excluded.market_cap, current_price=excluded.current_price,
             price_52w_high=excluded.price_52w_high,
             price_52w_low=excluded.price_52w_low,
             screen_strategies=excluded.screen_strategies,
             updated_at=excluded.updated_at""",
        (
            ticker,
            profile["name"],
            profile["sector"],
            profile["industry"],
            profile["exchange"],
            profile["country"],
            profile["description"],
            profile["website"],
            profile["employees"],
            profile["market_cap"],
            profile["current_price"],
            profile["price_52w_high"],
            profile["price_52w_low"],
            json.dumps(strategies, ensure_ascii=False),
            now,
        ),
    )


def run():
    """스크리너 추천 종목 기업 프로필 수집 메인."""
    print("[company_profiles] 추천 종목 프로필 수집 시작")
    ticker_strategies = _collect_target_tickers()
    total = len(ticker_strategies)
    print(f"[company_profiles] 대상 종목 {total}개")

    success = 0
    with get_db_conn() as conn:
        for i, (ticker, strategies) in enumerate(ticker_strategies.items(), 1):
            print(f"  ({i}/{total}) {ticker} 수집 중...")
            profile = _fetch_profile(ticker)
            if profile:
                _upsert_profile(conn, ticker, profile, strategies)
                success += 1
            time.sleep(_RATE_LIMIT)
        conn.commit()

    print(f"[company_profiles] 완료: {success}/{total}개 저장")


if __name__ == "__main__":
    run()

#!/usr/bin/env python3
"""
유니버스 전체 일봉 & 펀더멘탈 사전 수집 모듈

KOSPI200 50개 + SP100 99개 = 총 149개 티커의
- prices_daily: 오늘 일봉 UPSERT (매일 누적 → RSI 계산 가능)
- fundamentals: PER/PBR/ROE UPSERT

기존 fetch_yahoo_quote / fetch_yahoo_financials 재사용으로 인증 문제 없음.
파이프라인 실행(07:40) 전 07:00에 실행.
"""

import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from analysis.screener_universe import UNIVERSE_KOSPI200, UNIVERSE_SP100  # noqa: E402
from data.fetch_fundamentals_sources import (  # noqa: E402
    fetch_naver_per_pbr,
    fetch_yahoo_financials,
)
from data.fetch_gold_krx import fetch_kiwoom_investor  # noqa: E402
from data.fetch_prices import fetch_yahoo_quote  # noqa: E402

KST = timezone(timedelta(hours=9))
DB_PATH = PROJECT_ROOT / "db" / "history.db"

RATE_LIMIT_BATCH = 20
RATE_LIMIT_SLEEP = 0.5


def _meta_to_daily_row(ticker: str, meta: dict) -> dict | None:
    """Yahoo Finance meta 객체 → prices_daily 행 변환"""
    close = meta.get("regularMarketPrice")
    if not close:
        return None
    prev_close = meta.get("chartPreviousClose") or meta.get("previousClose") or close
    change_pct = round((close - prev_close) / prev_close * 100, 4) if prev_close else 0.0
    ts = meta.get("regularMarketTime", 0)
    date_str = (
        datetime.fromtimestamp(ts, tz=KST).strftime("%Y-%m-%d")
        if ts
        else datetime.now(KST).strftime("%Y-%m-%d")
    )
    return {
        "ticker": ticker,
        "date": date_str,
        "open": meta.get("regularMarketOpen") or close,
        "high": meta.get("regularMarketDayHigh") or close,
        "low": meta.get("regularMarketDayLow") or close,
        "close": close,
        "volume": meta.get("regularMarketVolume") or 0,
        "change_pct": change_pct,
    }


def _upsert_daily(conn: sqlite3.Connection, row: dict) -> None:
    """prices_daily 테이블에 오늘 행 UPSERT"""
    conn.execute(
        """INSERT OR REPLACE INTO prices_daily
           (ticker, date, open, high, low, close, volume, change_pct, data_source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'yahoo_universe')""",
        (
            row["ticker"],
            row["date"],
            row["open"],
            row["high"],
            row["low"],
            row["close"],
            row["volume"],
            row["change_pct"],
        ),
    )


def _upsert_fundamentals(conn: sqlite3.Connection, ticker: str, name: str, market: str) -> None:
    """fundamentals 테이블에 Yahoo 펀더멘탈 + Naver(KR PBR) + 키움 수급 UPSERT"""
    data = fetch_yahoo_financials(ticker)
    if not data:
        return

    # KR 종목: Naver에서 PBR/EPS 보충 (Yahoo가 한국 지표 미제공)
    pbr = data.get("pbr")
    eps = data.get("eps")
    if market == "KR":
        try:
            code = ticker.split(".")[0]
            naver = fetch_naver_per_pbr(code)
            if pbr is None:
                pbr = naver.get("pbr")
            if data.get("per") is None:
                data["per"] = naver.get("per")
            if eps is None:
                eps = naver.get("eps")
        except Exception:
            pass
    else:
        eps = data.get("eps")

    # KR 종목은 키움 API로 외국인/기관 순매수 추가 수집
    foreign_net = inst_net = None
    if market == "KR":
        try:
            code = ticker.split(".")[0]
            inv = fetch_kiwoom_investor(code)
            foreign_net = inv.get("foreign_net")
            inst_net = inv.get("inst_net")
        except Exception:
            pass

    now = datetime.now(KST).isoformat()
    conn.execute(
        """INSERT INTO fundamentals
               (ticker, name, market, per, pbr, roe, debt_ratio,
                revenue_growth, operating_margin, fcf, eps,
                dividend_yield, market_cap, sector, data_source, updated_at,
                foreign_net, inst_net)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'yahoo_universe', ?, ?, ?)
           ON CONFLICT(ticker) DO UPDATE SET
               per=COALESCE(excluded.per, per),
               pbr=COALESCE(excluded.pbr, pbr),
               roe=COALESCE(excluded.roe, roe),
               debt_ratio=COALESCE(excluded.debt_ratio, debt_ratio),
               revenue_growth=COALESCE(excluded.revenue_growth, revenue_growth),
               operating_margin=COALESCE(excluded.operating_margin, operating_margin),
               eps=COALESCE(excluded.eps, eps),
               dividend_yield=COALESCE(excluded.dividend_yield, dividend_yield),
               market_cap=excluded.market_cap,
               sector=COALESCE(excluded.sector, sector),
               data_source=CASE
                   WHEN fundamentals.data_source LIKE 'dart%' THEN fundamentals.data_source
                   ELSE 'yahoo_universe'
               END,
               updated_at=excluded.updated_at,
               foreign_net=excluded.foreign_net, inst_net=excluded.inst_net""",
        (
            ticker,
            name,
            market,
            data.get("per"),
            pbr,
            data.get("roe"),
            data.get("debt_ratio"),
            data.get("revenue_growth"),
            data.get("operating_margin"),
            data.get("fcf"),
            eps,
            data.get("dividend_yield"),
            data.get("market_cap"),
            data.get("sector"),
            now,
            foreign_net,
            inst_net,
        ),
    )


def _process_ticker(conn: sqlite3.Connection, info: dict) -> bool:
    """단일 티커 일봉 + 펀더멘탈 수집. 성공 시 True."""
    ticker = info["ticker"]
    name = info["name"]
    market = info["market"]
    try:
        meta = fetch_yahoo_quote(ticker)
        row = _meta_to_daily_row(ticker, meta)
        if row:
            _upsert_daily(conn, row)
        # ETF는 펀더멘탈 스킵 (PER/PBR 의미 없음)
        if market in ("KR", "US"):
            _upsert_fundamentals(conn, ticker, name, market)
        return True
    except Exception as e:
        print(f"    [WARN] {ticker} 실패 — {e}")
        return False


def run() -> dict:
    """유니버스 전체 일봉 + 펀더멘탈 수집"""
    universe = UNIVERSE_KOSPI200 + UNIVERSE_SP100
    total = len(universe)
    success = fail = 0

    print(f"[fetch_universe_daily] 유니버스 {total}개 수집 시작...")
    conn = sqlite3.connect(str(DB_PATH))
    try:
        for i, info in enumerate(universe):
            if _process_ticker(conn, info):
                success += 1
            else:
                fail += 1
            if (i + 1) % RATE_LIMIT_BATCH == 0:
                conn.commit()
                print(f"    {i + 1}/{total} 완료 (성공 {success} / 실패 {fail})...")
                time.sleep(RATE_LIMIT_SLEEP)
        conn.commit()
    finally:
        conn.close()

    print(f"[fetch_universe_daily] 완료 — 성공 {success} / 실패 {fail} / 전체 {total}")
    return {"success": success, "fail": fail, "total": total}


if __name__ == "__main__":
    run()

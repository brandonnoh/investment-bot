#!/usr/bin/env python3
"""
유니버스 캐시 모듈 — KOSPI200 + S&P100 전체 종목의 PER/PBR/ROE 주 1회 수집

output/intel/universe_cache.json에 캐시하여
매일 파이프라인은 이 캐시를 읽기만 하면 된다.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from analysis.screener_universe import (  # noqa: E402
    UNIVERSE_KOSPI200,
    UNIVERSE_SP100,
)
from analysis.sector_map import get_ticker_sector  # noqa: E402

KST = timezone(timedelta(hours=9))
OUTPUT_DIR = PROJECT_ROOT / "output" / "intel"
CACHE_PATH = OUTPUT_DIR / "universe_cache.json"
SLEEP_BETWEEN = 0.3


# ── yfinance 수집 ──


def _fetch_ticker_info(ticker: str) -> dict | None:
    """yfinance로 단일 종목 PER/PBR/ROE 수집"""
    try:
        import yfinance as yf  # noqa: PLC0415

        info = yf.Ticker(ticker).info
        if not info or info.get("regularMarketPrice") is None:
            return None
        return _extract_metrics(info)
    except Exception:
        return None


def _extract_metrics(info: dict) -> dict:
    """yfinance info에서 PER/PBR/ROE 추출"""
    per = info.get("trailingPE") or info.get("forwardPE")
    pbr = info.get("priceToBook")
    roe_raw = info.get("returnOnEquity")
    roe = round(roe_raw * 100, 2) if roe_raw is not None else None
    name = info.get("longName") or info.get("shortName")
    return {
        "name": name,
        "per": _safe_round(per),
        "pbr": _safe_round(pbr),
        "roe": roe,
    }


def _safe_round(val, digits: int = 2) -> float | None:
    """None 안전 반올림"""
    if val is None:
        return None
    try:
        return round(float(val), digits)
    except (ValueError, TypeError):
        return None


# ── 종목 처리 ──


def _build_stock_entry(
    ticker_info: dict,
    fetched: dict,
) -> dict:
    """단일 종목 캐시 엔트리 구성"""
    ticker = ticker_info["ticker"]
    sector = get_ticker_sector(ticker) or "기타"
    return {
        "name": fetched.get("name") or ticker_info["name"],
        "market": ticker_info["market"],
        "per": fetched.get("per"),
        "pbr": fetched.get("pbr"),
        "roe": fetched.get("roe"),
        "sector": sector,
    }


def _process_ticker(
    ticker_info: dict,
    stocks: dict,
    idx: int,
    total: int,
) -> None:
    """단일 종목 수집 처리 (graceful)"""
    ticker = ticker_info["ticker"]
    fetched = _fetch_ticker_info(ticker)
    if fetched is None:
        print(f"  [{idx}/{total}] {ticker} 실패 — 건너뜀")
        return
    stocks[ticker] = _build_stock_entry(ticker_info, fetched)
    name = stocks[ticker]["name"]
    print(f"  [{idx}/{total}] {ticker} ({name}) OK")


# ── 유니버스 수집 ──


def _collect_all(universe: list[dict]) -> dict:
    """전체 유니버스 수집 → stocks dict"""
    stocks: dict = {}
    total = len(universe)
    for i, ticker_info in enumerate(universe, 1):
        _process_ticker(ticker_info, stocks, i, total)
        time.sleep(SLEEP_BETWEEN)
    return stocks


# ── 저장 ──


def _save_cache(stocks: dict) -> None:
    """universe_cache.json 저장"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = {
        "updated_at": datetime.now(KST).isoformat(),
        "total": len(stocks),
        "stocks": stocks,
    }
    CACHE_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── 진입점 ──


def run() -> dict:
    """유니버스 캐시 수집 실행"""
    print("=== 유니버스 캐시 수집 시작 ===")
    universe = UNIVERSE_KOSPI200 + UNIVERSE_SP100
    print(f"  대상: {len(universe)}개 종목")

    stocks = _collect_all(universe)
    _save_cache(stocks)

    print(f"=== 유니버스 캐시 완료: {len(stocks)}개 수집 ===")
    return stocks


if __name__ == "__main__":
    run()

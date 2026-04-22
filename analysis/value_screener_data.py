#!/usr/bin/env python3
"""
value_screener 데이터 로드 헬퍼 — 캐시/DB/Yahoo 폴백 계층
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.fetch_fundamentals_sources import fetch_yahoo_financials  # noqa: E402

OUTPUT_DIR = PROJECT_ROOT / "output" / "intel"
FUNDAMENTALS_PATH = OUTPUT_DIR / "fundamentals.json"
SECTOR_SCORES_PATH = OUTPUT_DIR / "sector_scores.json"
UNIVERSE_CACHE_PATH = OUTPUT_DIR / "universe_cache.json"

TOP_SECTOR_COUNT = 3


def load_universe_cache() -> dict[str, dict]:
    """universe_cache.json 로드 (없으면 빈 dict)"""
    if not UNIVERSE_CACHE_PATH.exists():
        return {}
    try:
        data = json.loads(UNIVERSE_CACHE_PATH.read_text(encoding="utf-8"))
        return data.get("stocks", {})
    except (json.JSONDecodeError, KeyError):
        return {}


def load_fundamentals_cache() -> dict[str, dict]:
    """fundamentals.json에서 티커별 캐시 딕셔너리 반환"""
    if not FUNDAMENTALS_PATH.exists():
        return {}
    try:
        data = json.loads(FUNDAMENTALS_PATH.read_text(encoding="utf-8"))
        return {item["ticker"]: item for item in data.get("fundamentals", [])}
    except (json.JSONDecodeError, KeyError):
        return {}


def load_sector_scores() -> list[dict]:
    """sector_scores.json에서 상위 섹터 리스트 반환"""
    if not SECTOR_SCORES_PATH.exists():
        print("  sector_scores.json 없음 — sector_intel 먼저 실행 필요")
        return []
    try:
        data = json.loads(SECTOR_SCORES_PATH.read_text(encoding="utf-8"))
        eligible = [
            s for s in data.get("sectors", [])
            if s.get("signal") in ("favorable", "neutral")
        ]
        return eligible[:TOP_SECTOR_COUNT]
    except (json.JSONDecodeError, KeyError):
        return []


def load_fundamentals_from_db(conn, ticker: str) -> dict:
    """DB fundamentals 테이블에서 PER/PBR/ROE/종목명 조회"""
    try:
        cur = conn.execute(
            "SELECT per, pbr, roe, name FROM fundamentals WHERE ticker=?", (ticker,)
        )
        row = cur.fetchone()
        if row:
            return {"per": row[0], "pbr": row[1], "roe": row[2], "name": row[3]}
    except Exception as e:
        print(f"  [WARN] fundamentals DB 조회 실패 ({ticker}): {e}")
    return {}


def resolve_fundamentals(
    ticker: str,
    conn,
    cache: dict[str, dict],
    uni_cache: dict[str, dict] | None,
) -> dict:
    """PER/PBR/ROE 조회: DB → universe_cache → fundamentals.json → Yahoo"""
    fund = load_fundamentals_from_db(conn, ticker)
    if fund.get("per") is not None:
        return fund

    if uni_cache:
        entry = uni_cache.get(ticker)
        if entry and entry.get("per") is not None:
            return entry

    cached = cache.get(ticker)
    if cached and cached.get("per") is not None:
        return cached

    try:
        return fetch_yahoo_financials(ticker) or {}
    except Exception as e:
        print(f"  [WARN] Yahoo 펀더멘탈 조회 실패 ({ticker}): {e}")
        return {}

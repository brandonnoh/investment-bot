#!/usr/bin/env python3
"""
펀더멘탈 데이터 수집 — DB 저장 + 오케스트레이션
외부 API 수집 레이어는 fetch_fundamentals_sources.py 참고
"""

import json
import logging
import os
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 외부 API 수집 함수 re-export (하위 호환)
from data.fetch_fundamentals_sources import (  # noqa: F401
    DART_CORP_CODES,
    _parse_dart_amount,
    fetch_dart_financials,
    fetch_naver_per_pbr,
    _safe_raw,
    fetch_yahoo_financials,
)

KST = timezone(timedelta(hours=9))
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "db" / "history.db"
OUTPUT_DIR = PROJECT_ROOT / "output" / "intel"


def save_fundamentals_to_db(conn: sqlite3.Connection, records: list):
    """펀더멘탈 데이터를 DB에 저장 (UPSERT).

    Args:
        conn: SQLite 연결 객체
        records: 펀더멘탈 레코드 리스트
    """
    now = datetime.now(KST).isoformat()
    for rec in records:
        conn.execute(
            """INSERT OR REPLACE INTO fundamentals
               (ticker, name, market, per, pbr, roe, debt_ratio,
                revenue_growth, operating_margin, fcf, eps,
                dividend_yield, market_cap, data_source, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rec.get("ticker"),
                rec.get("name"),
                rec.get("market"),
                rec.get("per"),
                rec.get("pbr"),
                rec.get("roe"),
                rec.get("debt_ratio"),
                rec.get("revenue_growth"),
                rec.get("operating_margin"),
                rec.get("fcf"),
                rec.get("eps"),
                rec.get("dividend_yield"),
                rec.get("market_cap"),
                rec.get("data_source"),
                now,
            ),
        )
    conn.commit()


def load_fundamentals(conn: sqlite3.Connection) -> list:
    """DB에서 펀더멘탈 데이터 조회.

    Returns:
        펀더멘탈 레코드 리스트
    """
    cursor = conn.execute(
        """SELECT ticker, name, market, per, pbr, roe, debt_ratio,
                  revenue_growth, operating_margin, fcf, eps,
                  dividend_yield, market_cap, data_source, updated_at
           FROM fundamentals ORDER BY ticker"""
    )
    columns = [
        "ticker",
        "name",
        "market",
        "per",
        "pbr",
        "roe",
        "debt_ratio",
        "revenue_growth",
        "operating_margin",
        "fcf",
        "eps",
        "dividend_yield",
        "market_cap",
        "data_source",
        "updated_at",
    ]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def generate_json(records: list) -> dict:
    """fundamentals.json 생성용 딕셔너리.

    Args:
        records: 펀더멘탈 레코드 리스트

    Returns:
        JSON 직렬화 가능한 딕셔너리
    """
    now = datetime.now(KST).isoformat()
    return {
        "updated_at": now,
        "count": len(records),
        "fundamentals": records,
    }


def _collect_for_ticker(ticker_info: dict) -> Optional[dict]:
    """개별 종목의 펀더멘탈 데이터 수집.

    한국 종목: DART 우선 → Yahoo 보완
    미국 종목: Yahoo 전용

    Args:
        ticker_info: {"ticker": ..., "name": ..., "market": ...}

    Returns:
        병합된 펀더멘탈 딕셔너리 또는 None
    """
    ticker = ticker_info["ticker"]
    market = ticker_info.get("market", "")
    name = ticker_info.get("name", "")

    result = {
        "ticker": ticker,
        "name": name,
        "market": market,
        "per": None,
        "pbr": None,
        "roe": None,
        "debt_ratio": None,
        "revenue_growth": None,
        "operating_margin": None,
        "fcf": None,
        "eps": None,
        "dividend_yield": None,
        "market_cap": None,
        "data_source": None,
    }

    dart_data = None
    yahoo_data = None

    # 한국 종목: DART + Yahoo
    if market == "KR" and ticker.endswith((".KS", ".KQ")):
        stock_code = ticker.split(".")[0]
        dart_data = fetch_dart_financials(stock_code)
        yahoo_data = fetch_yahoo_financials(ticker)

        if dart_data:
            # DART 데이터 우선 적용
            for key in [
                "revenue_growth",
                "operating_margin",
                "roe",
                "debt_ratio",
                "fcf",
            ]:
                if dart_data.get(key) is not None:
                    result[key] = dart_data[key]
            result["data_source"] = "dart"

        if yahoo_data:
            # Yahoo로 나머지 보완 (DART에 없는 필드)
            for key in ["per", "pbr", "eps", "dividend_yield", "market_cap", "fcf"]:
                if result.get(key) is None and yahoo_data.get(key) is not None:
                    result[key] = yahoo_data[key]
            # DART가 없었으면 Yahoo 값으로 채움
            for key in ["roe", "debt_ratio", "revenue_growth", "operating_margin"]:
                if result.get(key) is None and yahoo_data.get(key) is not None:
                    result[key] = yahoo_data[key]
            if result["data_source"] is None:
                result["data_source"] = "yahoo"
            elif result["data_source"] == "dart":
                result["data_source"] = "dart+yahoo"

        # 국내 종목 PER/PBR 네이버에서 보완
        if market == "KR" and stock_code:
            naver_ratios = fetch_naver_per_pbr(stock_code)
            if result.get("per") is None:
                result["per"] = naver_ratios["per"]
            if result.get("pbr") is None:
                result["pbr"] = naver_ratios["pbr"]

    # 미국 종목: Yahoo 전용
    elif market == "US" or not ticker.endswith((".KS", ".KQ")):
        yahoo_data = fetch_yahoo_financials(ticker)
        if yahoo_data:
            for key, val in yahoo_data.items():
                if val is not None:
                    result[key] = val
            result["data_source"] = "yahoo"

    # 데이터가 하나도 없으면 None
    has_data = any(
        result.get(k) is not None
        for k in ["per", "pbr", "roe", "revenue_growth", "operating_margin"]
    )
    if not has_data:
        return None

    return result


def run(conn=None, output_dir=None) -> list:
    """펀더멘탈 데이터 수집 파이프라인.

    1. ticker_master에서 종목 목록 조회
    2. 종목별 DART/Yahoo 수집
    3. DB 저장 (UPSERT)
    4. fundamentals.json 출력

    Args:
        conn: SQLite 연결 (None이면 기본 DB)
        output_dir: 출력 디렉토리 (None이면 기본)

    Returns:
        수집된 펀더멘탈 레코드 리스트
    """
    out_dir = Path(output_dir) if output_dir else OUTPUT_DIR

    own_conn = False
    if conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH))
        own_conn = True

    # 1. 종목 목록 조회
    try:
        from data.ticker_master import load_master_from_db

        tickers = load_master_from_db(conn)
    except Exception as e:
        logger.warning(f"종목 사전 로드 실패: {e}")
        tickers = []

    if not tickers:
        logger.info("종목 사전 비어있음 — 펀더멘탈 수집 건너뜀")
        # 기존 DB 데이터로 JSON 생성
        existing = load_fundamentals(conn)
        if existing:
            _save_json(out_dir, existing)
        if own_conn:
            conn.close()
        return existing

    # 2. 종목별 수집
    collected = []
    for t in tickers:
        # COMMODITY, ETF 등 펀더멘탈 의미 없는 종목 스킵
        if t.get("market") == "COMMODITY":
            continue
        ticker = t["ticker"]
        # ETF 패턴 스킵 (6자리 코드가 아닌 경우 또는 특정 패턴)
        if ticker.startswith("GOLD_"):
            continue

        try:
            result = _collect_for_ticker(t)
            if result:
                collected.append(result)
                logger.info(
                    f"  ✅ {ticker} 펀더멘탈 수집 완료 ({result['data_source']})"
                )
            else:
                logger.info(f"  ⚠️ {ticker} 펀더멘탈 데이터 없음")
        except Exception as e:
            logger.error(f"  ❌ {ticker} 펀더멘탈 수집 실패: {e}")

    # 3. DB 저장 (수집된 것만 업데이트, 실패한 종목은 기존 데이터 유지)
    if collected:
        save_fundamentals_to_db(conn, collected)

    # 4. DB에서 전체 데이터 로드 (기존 + 신규)
    all_records = load_fundamentals(conn)

    # 5. JSON 저장
    _save_json(out_dir, all_records)

    print(f"  ✅ 펀더멘탈 수집 완료: {len(collected)}개 수집, 총 {len(all_records)}개")

    if own_conn:
        conn.close()

    return all_records


def _save_json(out_dir: Path, records: list):
    """fundamentals.json 파일 저장"""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_data = generate_json(records)
    json_path = out_dir / "fundamentals.json"
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"fundamentals.json 저장 실패: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(f"\n펀더멘탈 ({len(result)}개):")
    for rec in result:
        print(
            f"  {rec['ticker']:15s} {rec.get('name', ''):15s} "
            f"PER={rec.get('per')} PBR={rec.get('pbr')} ROE={rec.get('roe')}"
        )

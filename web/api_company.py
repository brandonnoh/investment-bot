#!/usr/bin/env python3
"""기업 프로필 API — company_profiles + fundamentals 조인 + 최근 뉴스"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.connection import get_db_conn


def load_company_profile(ticker: str) -> dict:
    """ticker에 해당하는 기업 프로필 + 펀더멘탈 + 최근 뉴스를 병합 반환."""
    try:
        with get_db_conn() as conn:
            profile = _load_profile(conn, ticker)
            # company_profiles 없으면 ticker_master로 기본 프로필 생성
            if not profile:
                profile = _load_ticker_master(conn, ticker)
            if not profile:
                return {}
            fundamentals = _load_fundamentals(conn, ticker)
            news = _load_recent_news(conn, ticker)
    except Exception as e:
        print(f"[api_company] 조회 실패: {e}")
        return {}

    # 펀더멘탈 값이 프로필 값보다 우선 (더 최신)
    result = {**profile, **fundamentals}
    result["recent_news"] = news
    # description: 하위 호환 필드 (description_kr 우선, 없으면 description_en)
    result["description"] = (
        result.get("description_kr")
        or result.get("description_en")
        or result.get("description")
        or ""
    )
    # JSON 문자열 필드를 리스트로 변환
    for field, fallback in (("screen_strategies", []), ("analyst_reports", [])):
        raw = result.get(field)
        if isinstance(raw, str):
            try:
                result[field] = json.loads(raw)
            except Exception:
                result[field] = fallback
    return result


def _load_ticker_master(conn, ticker: str) -> dict:
    """ticker_master에서 기본 정보 조회 — company_profiles 없을 때 fallback."""
    row = conn.execute(
        "SELECT ticker, name, sector, market FROM ticker_master WHERE ticker = ?", (ticker,)
    ).fetchone()
    if not row:
        return {}
    return {"ticker": row["ticker"], "name": row["name"], "sector": row["sector"]}


def _load_profile(conn, ticker: str) -> dict:
    """company_profiles 테이블에서 조회."""
    row = conn.execute("SELECT * FROM company_profiles WHERE ticker = ?", (ticker,)).fetchone()
    return dict(row) if row else {}


def _load_fundamentals(conn, ticker: str) -> dict:
    """fundamentals 테이블에서 주요 지표 조회."""
    row = conn.execute(
        """SELECT per, pbr, roe, debt_ratio, revenue_growth,
                  operating_margin, eps, dividend_yield, market_cap,
                  foreign_net, inst_net
           FROM fundamentals WHERE ticker = ?""",
        (ticker,),
    ).fetchone()
    if not row:
        return {}
    # None이 아닌 값만 병합 (펀더멘탈이 우선)
    return {k: v for k, v in dict(row).items() if v is not None}


def _load_recent_news(conn, ticker: str) -> list[dict]:
    """ticker 관련 최근 뉴스 5건 조회 (title/summary LIKE 검색)."""
    # .KS/.KQ 제거한 순수 종목 코드로 검색
    code = ticker.split(".")[0]
    pat = f"%{code}%"
    rows = conn.execute(
        """SELECT title, summary, source, url, published_at, sentiment
           FROM news
           WHERE title LIKE ? OR summary LIKE ?
           ORDER BY relevance_score DESC, published_at DESC
           LIMIT 5""",
        (pat, pat),
    ).fetchall()
    return [dict(r) for r in rows]

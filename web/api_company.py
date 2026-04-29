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
    # screen_strategies를 리스트로 변환
    raw = result.get("screen_strategies")
    if isinstance(raw, str):
        try:
            result["screen_strategies"] = json.loads(raw)
        except Exception:
            result["screen_strategies"] = []
    return result


def _load_profile(conn, ticker: str) -> dict:
    """company_profiles 테이블에서 조회."""
    row = conn.execute(
        "SELECT * FROM company_profiles WHERE ticker = ?", (ticker,)
    ).fetchone()
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

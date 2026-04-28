#!/usr/bin/env python3
"""
어드바이저 저장 전략 DB 관리 (api.py 300줄 초과 방지용 분리 모듈)
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.connection import get_db_conn

DB_PATH = Path(__file__).parent.parent / "db" / "history.db"


def save_advisor_strategy(
    capital: int,
    leverage_amt: int,
    risk_level: int,
    recommendation: str,
    loans: list | None = None,
    monthly_savings: int = 0,
) -> int:
    """어드바이저 결과 DB 저장 → 생성된 id 반환."""
    saved_at = datetime.now(timezone.utc).isoformat()
    loans_json = json.dumps(loans or [], ensure_ascii=False)
    with get_db_conn() as conn:
        cur = conn.execute(
            """INSERT INTO advisor_strategies
               (capital, leverage_amt, risk_level, recommendation, saved_at, loans_json, monthly_savings)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (capital, leverage_amt, risk_level, recommendation, saved_at, loans_json, monthly_savings),
        )
        return cur.lastrowid


def load_advisor_strategies(limit: int = 20) -> list[dict]:
    """저장된 전략 목록 최신순 조회."""
    if not DB_PATH.exists():
        return []
    try:
        with get_db_conn() as conn:
            rows = conn.execute(
                """SELECT id, capital, leverage_amt, risk_level, recommendation,
                          saved_at, loans_json, monthly_savings
                   FROM advisor_strategies ORDER BY saved_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[api_advisor] 전략 목록 조회 실패: {e}")
        return []


def delete_advisor_strategy(strategy_id: int) -> bool:
    """전략 삭제 → 성공 여부 반환."""
    try:
        with get_db_conn() as conn:
            cur = conn.execute("DELETE FROM advisor_strategies WHERE id = ?", (strategy_id,))
        return cur.rowcount > 0
    except Exception as e:
        print(f"[api_advisor] 전략 삭제 실패: {e}")
        return False

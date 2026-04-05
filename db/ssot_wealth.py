#!/usr/bin/env python3
"""
SSoT Wealth — 자산/입금 관련 API
비금융 자산, 월 적립, 전체 자산 히스토리/요약 담당
"""

import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH


def get_conn():
    """DB 연결 반환 (순환 import 방지용 로컬 정의)"""
    return sqlite3.connect(str(DB_PATH))


KST = timezone(timedelta(hours=9))


# ══════════════════════════════════════════════════════════════
# Extra Assets (비금융 자산)
# ══════════════════════════════════════════════════════════════


def get_extra_assets(conn=None) -> List[Dict]:
    """비금융 자산 목록 반환"""
    own_conn = conn is None
    if own_conn:
        conn = get_conn()

    cursor = conn.cursor()
    cursor.execute("""
        SELECT name, asset_type, current_value_krw, monthly_deposit_krw,
               is_fixed, maturity_date, note
        FROM extra_assets
        ORDER BY asset_type, name
    """)

    assets = []
    for row in cursor.fetchall():
        assets.append(
            {
                "name": row[0],
                "type": row[1],
                "current_value_krw": row[2],
                "monthly_deposit_krw": row[3],
                "is_fixed": bool(row[4]),
                "maturity_date": row[5],
                "note": row[6],
            }
        )

    if own_conn:
        conn.close()
    return assets


def update_extra_asset(
    name: str,
    current_value_krw: float = None,
    monthly_deposit_krw: float = None,
    conn=None,
):
    """비금융 자산 업데이트"""
    own_conn = conn is None
    if own_conn:
        conn = get_conn()

    cursor = conn.cursor()
    now = datetime.now(KST).isoformat()

    updates = []
    params = []
    if current_value_krw is not None:
        updates.append("current_value_krw = ?")
        params.append(current_value_krw)
    if monthly_deposit_krw is not None:
        updates.append("monthly_deposit_krw = ?")
        params.append(monthly_deposit_krw)

    if updates:
        updates.append("updated_at = ?")
        params.append(now)
        params.append(name)
        cursor.execute(
            f"UPDATE extra_assets SET {', '.join(updates)} WHERE name = ?", params
        )
        conn.commit()

    if own_conn:
        conn.close()


def apply_monthly_deposits(conn=None):
    """월 적립금 자동 적용 (월말 크론잡용)"""
    own_conn = conn is None
    if own_conn:
        conn = get_conn()

    cursor = conn.cursor()
    now = datetime.now(KST).isoformat()

    cursor.execute(
        """
        UPDATE extra_assets
        SET current_value_krw = current_value_krw + monthly_deposit_krw,
            updated_at = ?
        WHERE monthly_deposit_krw > 0 AND is_fixed = 0
    """,
        (now,),
    )

    updated = cursor.rowcount
    conn.commit()

    if own_conn:
        conn.close()

    return updated


def get_extra_assets_total(conn=None) -> float:
    """비금융 자산 총합"""
    own_conn = conn is None
    if own_conn:
        conn = get_conn()

    cursor = conn.cursor()
    cursor.execute("SELECT SUM(current_value_krw) FROM extra_assets")
    total = cursor.fetchone()[0] or 0

    if own_conn:
        conn.close()
    return total


# ══════════════════════════════════════════════════════════════
# Total Wealth History
# ══════════════════════════════════════════════════════════════


def save_total_wealth_snapshot(
    investment_value: float,
    extra_assets: float,
    pnl_krw: float,
    pnl_pct: float,
    fx_rate: float,
    date: str = None,
    conn=None,
):
    """전체 자산 일별 스냅샷 저장"""
    own_conn = conn is None
    if own_conn:
        conn = get_conn()

    cursor = conn.cursor()
    if date is None:
        date = datetime.now(KST).strftime("%Y-%m-%d")

    total = investment_value + extra_assets

    cursor.execute(
        """
        INSERT OR REPLACE INTO total_wealth_history
        (date, investment_value_krw, extra_assets_krw, total_wealth_krw,
         investment_pnl_krw, investment_pnl_pct, fx_rate)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (date, investment_value, extra_assets, total, pnl_krw, pnl_pct, fx_rate),
    )
    conn.commit()

    if own_conn:
        conn.close()


def get_total_wealth_history(days: int = 30, conn=None) -> List[Dict]:
    """전체 자산 히스토리 조회"""
    own_conn = conn is None
    if own_conn:
        conn = get_conn()

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT date, investment_value_krw, extra_assets_krw, total_wealth_krw,
               investment_pnl_krw, investment_pnl_pct, fx_rate
        FROM total_wealth_history
        ORDER BY date DESC
        LIMIT ?
    """,
        (days,),
    )

    history = []
    for row in cursor.fetchall():
        history.append(
            {
                "date": row[0],
                "investment_value_krw": row[1],
                "extra_assets_krw": row[2],
                "total_wealth_krw": row[3],
                "investment_pnl_krw": row[4],
                "investment_pnl_pct": row[5],
                "fx_rate": row[6],
            }
        )

    if own_conn:
        conn.close()
    return history


# ══════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════


def get_wealth_summary(conn=None) -> Dict:
    """전체 자산 요약"""
    from db.ssot import get_holdings

    own_conn = conn is None
    if own_conn:
        conn = get_conn()

    holdings = get_holdings(conn)
    extra_assets = get_extra_assets(conn)
    extra_total = sum(a["current_value_krw"] for a in extra_assets)
    monthly_recurring = sum(a["monthly_deposit_krw"] for a in extra_assets)

    # 가장 최근 wealth history
    cursor = conn.cursor()
    cursor.execute("""
        SELECT total_wealth_krw, investment_pnl_krw, investment_pnl_pct
        FROM total_wealth_history
        ORDER BY date DESC
        LIMIT 1
    """)
    row = cursor.fetchone()

    if own_conn:
        conn.close()

    return {
        "holdings_count": len(holdings),
        "extra_assets_count": len(extra_assets),
        "extra_assets_total": extra_total,
        "monthly_recurring": monthly_recurring,
        "last_total_wealth": row[0] if row else None,
        "last_investment_pnl": row[1] if row else None,
        "last_investment_pnl_pct": row[2] if row else None,
    }

#!/usr/bin/env python3
"""
SSoT Wealth — 자산/입금 관련 API
비금융 자산, 월 적립, 전체 자산 히스토리/요약 담당
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from db.connection import get_db_conn


def get_conn():
    """DB 연결 반환 (WAL + busy_timeout=30초)"""
    return get_db_conn()


KST = timezone(timedelta(hours=9))


# ══════════════════════════════════════════════════════════════
# Extra Assets (비금융 자산)
# ══════════════════════════════════════════════════════════════


def get_extra_assets(conn=None) -> list[dict]:
    """비금융 자산 목록 반환"""
    own_conn = conn is None
    if own_conn:
        conn = get_conn()

    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, asset_type, current_value_krw, monthly_deposit_krw,
               is_fixed, maturity_date, note
        FROM extra_assets
        ORDER BY asset_type, name
    """)

    assets = []
    for row in cursor.fetchall():
        assets.append(
            {
                "id": row[0],
                "name": row[1],
                "type": row[2],
                "current_value_krw": row[3],
                "monthly_deposit_krw": row[4],
                "is_fixed": bool(row[5]),
                "maturity_date": row[6],
                "note": row[7],
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
        cursor.execute(f"UPDATE extra_assets SET {', '.join(updates)} WHERE name = ?", params)
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


def get_total_wealth_history(days: int = 30, conn=None) -> list[dict]:
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


def get_wealth_summary(conn=None) -> dict:
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


# ══════════════════════════════════════════════════════════════
# Extra Assets CRUD
# ══════════════════════════════════════════════════════════════


def create_extra_asset(
    name: str,
    asset_type: str,
    current_value_krw: float,
    monthly_deposit_krw: float = 0,
    is_fixed: bool = False,
    maturity_date: str = None,
    note: str = None,
) -> int:
    """비금융 자산 신규 생성, 생성된 id 반환"""
    conn = get_conn()
    try:
        cursor = conn.cursor()
        now = datetime.now(KST).isoformat()
        cursor.execute(
            """
            INSERT INTO extra_assets
            (name, asset_type, current_value_krw, monthly_deposit_krw,
             is_fixed, maturity_date, note, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                asset_type,
                current_value_krw,
                monthly_deposit_krw,
                1 if is_fixed else 0,
                maturity_date,
                note,
                now,
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def update_extra_asset_by_id(
    asset_id: int,
    name: str,
    asset_type: str,
    current_value_krw: float,
    monthly_deposit_krw: float,
    is_fixed: bool,
    maturity_date: str = None,
    note: str = None,
) -> bool:
    """비금융 자산 전체 필드 업데이트, 성공 여부 반환"""
    conn = get_conn()
    try:
        cursor = conn.cursor()
        now = datetime.now(KST).isoformat()
        cursor.execute(
            """
            UPDATE extra_assets
            SET name = ?, asset_type = ?, current_value_krw = ?,
                monthly_deposit_krw = ?, is_fixed = ?,
                maturity_date = ?, note = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                name,
                asset_type,
                current_value_krw,
                monthly_deposit_krw,
                1 if is_fixed else 0,
                maturity_date,
                note,
                now,
                asset_id,
            ),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def delete_extra_asset_by_id(asset_id: int) -> bool:
    """비금융 자산 삭제, 성공 여부 반환"""
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM extra_assets WHERE id = ?", (asset_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()

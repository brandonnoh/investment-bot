#!/usr/bin/env python3
"""
SSoT (Single Source of Truth) — DB 중심 자산 관리 API
config.py/JSON 대신 DB를 유일한 진실 소스로 사용
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from db.connection import get_db_conn

KST = timezone(timedelta(hours=9))


def get_conn():
    """DB 연결 반환 (WAL + busy_timeout=30초)"""
    return get_db_conn()


# ══════════════════════════════════════════════════════════════
# Holdings (보유 종목)
# ══════════════════════════════════════════════════════════════


def get_holdings(conn=None) -> list[dict]:
    """현재 보유 종목 목록 반환 (config.py PORTFOLIO 대체)"""
    own_conn = conn is None
    if own_conn:
        conn = get_conn()

    cursor = conn.cursor()
    cursor.execute("""
        SELECT ticker, name, sector, currency, qty, avg_cost, buy_fx_rate, account, note
        FROM holdings
        ORDER BY ticker
    """)

    holdings = []
    for row in cursor.fetchall():
        holdings.append(
            {
                "ticker": row[0],
                "name": row[1],
                "sector": row[2],
                "currency": row[3],
                "qty": row[4],
                "avg_cost": row[5],
                "buy_fx_rate": row[6],
                "account": row[7] or "",  # 계좌 구분 (없으면 빈 문자열)
                "note": row[8],
            }
        )

    if own_conn:
        conn.close()
    return holdings


def update_holding(
    ticker: str,
    qty: float = None,
    avg_cost: float = None,
    buy_fx_rate: float = None,
    conn=None,
):
    """보유 종목 업데이트"""
    own_conn = conn is None
    if own_conn:
        conn = get_conn()

    cursor = conn.cursor()
    now = datetime.now(KST).isoformat()

    updates = []
    params = []
    if qty is not None:
        updates.append("qty = ?")
        params.append(qty)
    if avg_cost is not None:
        updates.append("avg_cost = ?")
        params.append(avg_cost)
    if buy_fx_rate is not None:
        updates.append("buy_fx_rate = ?")
        params.append(buy_fx_rate)

    if updates:
        updates.append("updated_at = ?")
        params.append(now)
        params.append(ticker)
        cursor.execute(f"UPDATE holdings SET {', '.join(updates)} WHERE ticker = ?", params)
        conn.commit()

    if own_conn:
        conn.close()


def add_holding(
    ticker: str,
    name: str,
    qty: float,
    avg_cost: float,
    sector: str = "",
    currency: str = "KRW",
    buy_fx_rate: float = None,
    note: str = "",
    conn=None,
):
    """새 종목 추가"""
    own_conn = conn is None
    if own_conn:
        conn = get_conn()

    cursor = conn.cursor()
    now = datetime.now(KST).isoformat()

    cursor.execute(
        """
        INSERT OR REPLACE INTO holdings
        (ticker, name, sector, currency, qty, avg_cost, buy_fx_rate, note, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (ticker, name, sector, currency, qty, avg_cost, buy_fx_rate, note, now),
    )
    conn.commit()

    if own_conn:
        conn.close()


def remove_holding(ticker: str, conn=None):
    """종목 삭제"""
    own_conn = conn is None
    if own_conn:
        conn = get_conn()

    cursor = conn.cursor()
    cursor.execute("DELETE FROM holdings WHERE ticker = ?", (ticker,))
    conn.commit()

    if own_conn:
        conn.close()


# ══════════════════════════════════════════════════════════════
# Transactions (매수/매도 기록)
# ══════════════════════════════════════════════════════════════


def record_transaction(
    ticker: str,
    tx_type: str,
    qty: float,
    price: float,
    fx_rate: float = None,
    fee: float = 0,
    note: str = "",
    conn=None,
):
    """매수/매도 기록 추가"""
    own_conn = conn is None
    if own_conn:
        conn = get_conn()

    cursor = conn.cursor()
    now = datetime.now(KST).isoformat()

    cursor.execute(
        """
        INSERT INTO transactions
        (ticker, tx_type, qty, price, fx_rate, fee, note, executed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (ticker, tx_type.upper(), qty, price, fx_rate, fee, note, now),
    )
    conn.commit()

    if own_conn:
        conn.close()


def get_transactions(ticker: str = None, limit: int = 100, conn=None) -> list[dict]:
    """거래 내역 조회"""
    own_conn = conn is None
    if own_conn:
        conn = get_conn()

    cursor = conn.cursor()
    if ticker:
        cursor.execute(
            """
            SELECT id, ticker, tx_type, qty, price, fx_rate, fee, note, executed_at
            FROM transactions
            WHERE ticker = ?
            ORDER BY executed_at DESC
            LIMIT ?
        """,
            (ticker, limit),
        )
    else:
        cursor.execute(
            """
            SELECT id, ticker, tx_type, qty, price, fx_rate, fee, note, executed_at
            FROM transactions
            ORDER BY executed_at DESC
            LIMIT ?
        """,
            (limit,),
        )

    txs = []
    for row in cursor.fetchall():
        txs.append(
            {
                "id": row[0],
                "ticker": row[1],
                "tx_type": row[2],
                "qty": row[3],
                "price": row[4],
                "fx_rate": row[5],
                "fee": row[6],
                "note": row[7],
                "executed_at": row[8],
            }
        )

    if own_conn:
        conn.close()
    return txs


# 하위 호환: ssot_wealth의 자산/입금 관련 함수 re-export
from db.ssot_wealth import (  # noqa: E402
    apply_monthly_deposits,
    get_extra_assets,
    get_extra_assets_total,
    get_total_wealth_history,
    get_wealth_summary,
    save_total_wealth_snapshot,
    update_extra_asset,
)

__all__ = [
    "get_conn",
    "get_holdings",
    "update_holding",
    "add_holding",
    "remove_holding",
    "record_transaction",
    "get_transactions",
    # ssot_wealth re-exports
    "get_extra_assets",
    "update_extra_asset",
    "apply_monthly_deposits",
    "get_extra_assets_total",
    "save_total_wealth_snapshot",
    "get_total_wealth_history",
    "get_wealth_summary",
]


if __name__ == "__main__":
    # 테스트
    summary = get_wealth_summary()
    print("=== Wealth Summary ===")
    print(f"Holdings: {summary['holdings_count']}건")
    print(f"Extra Assets: {summary['extra_assets_count']}건")
    print(f"Extra Total: {summary['extra_assets_total']:,.0f}원")
    print(f"Monthly Recurring: {summary['monthly_recurring']:,.0f}원")
    print(
        f"Last Total Wealth: {summary['last_total_wealth']:,.0f}원"
        if summary["last_total_wealth"]
        else "No history"
    )

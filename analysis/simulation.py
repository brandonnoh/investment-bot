#!/usr/bin/env python3
"""
포트폴리오 시뮬레이션 — "만약 이랬다면" 가상 손익 계산
발굴된 opportunities의 추천 시점 → 현재 손익 역산
"""
from __future__ import annotations

import json
import logging
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output" / "intel"
DB_PATH = PROJECT_ROOT / "db" / "history.db"


def _get_price_on_date(conn: sqlite3.Connection, ticker: str, target_date: str) -> float | None:
    """prices_daily에서 ±3일 내 가장 가까운 날의 종가 조회."""
    rows = conn.execute(
        """SELECT date, close FROM prices_daily
           WHERE ticker = ? AND date BETWEEN date(?, '-3 days') AND date(?, '+3 days')
           ORDER BY ABS(julianday(date) - julianday(?)) LIMIT 1""",
        (ticker, target_date, target_date, target_date),
    ).fetchall()
    return rows[0][1] if rows else None


def simulate_trade(
    conn: sqlite3.Connection,
    ticker: str,
    buy_date: str,
    sell_date: str,
    qty: float = 1,
    buy_price: float | None = None,
) -> dict:
    """단일 가상 매매 손익 계산."""
    entry_price = buy_price if buy_price is not None else _get_price_on_date(conn, ticker, buy_date)
    exit_price = _get_price_on_date(conn, ticker, sell_date)

    if entry_price is None:
        return {"ticker": ticker, "buy_date": buy_date, "sell_date": sell_date,
                "buy_price": None, "sell_price": None, "qty": qty,
                "pnl": None, "pnl_pct": None, "error": f"매수가 없음 ({buy_date})"}
    if exit_price is None:
        return {"ticker": ticker, "buy_date": buy_date, "sell_date": sell_date,
                "buy_price": entry_price, "sell_price": None, "qty": qty,
                "pnl": None, "pnl_pct": None, "error": f"매도가 없음 ({sell_date})"}

    pnl = (exit_price - entry_price) * qty
    pnl_pct = (exit_price - entry_price) / entry_price * 100

    return {
        "ticker": ticker, "buy_date": buy_date, "sell_date": sell_date,
        "buy_price": entry_price, "sell_price": exit_price, "qty": qty,
        "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2), "error": None,
    }


def simulate_batch(conn: sqlite3.Connection, trades: list) -> list:
    """여러 가상 매매 일괄 계산."""
    return [
        simulate_trade(
            conn, t["ticker"], t["buy_date"], t["sell_date"],
            t.get("qty", 1), t.get("buy_price"),
        )
        for t in trades
    ]


def _build_opportunity_simulations(conn: sqlite3.Connection) -> list:
    """opportunities DB에서 발굴 종목의 가상 1주 수익률 시뮬레이션."""
    today = datetime.now(KST).date().isoformat()
    rows = conn.execute(
        """SELECT ticker, name, discovered_at, composite_score
           FROM opportunities
           WHERE discovered_at IS NOT NULL
           ORDER BY discovered_at DESC LIMIT 20"""
    ).fetchall()

    results = []
    for ticker, name, discovered_at, score in rows:
        buy_date = discovered_at[:10] if discovered_at else None
        if not buy_date:
            continue
        sim = simulate_trade(conn, ticker, buy_date, today, qty=1)
        sim["name"] = name
        sim["composite_score"] = score
        results.append(sim)
    return results


def run(conn: sqlite3.Connection | None = None, output_dir: Path | None = None) -> dict:
    """시뮬레이션 파이프라인 실행."""
    out_dir = Path(output_dir) if output_dir else OUTPUT_DIR
    own_conn = False
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH))
        own_conn = True

    try:
        simulations = _build_opportunity_simulations(conn)
        successful = [s for s in simulations if s.get("error") is None]
        avg_return = (
            sum(s["pnl_pct"] for s in successful) / len(successful)
            if successful else 0.0
        )
        report = {
            "generated_at": datetime.now(KST).isoformat(),
            "simulations": simulations,
            "summary": {
                "total": len(simulations),
                "successful": len(successful),
                "avg_return_pct": round(avg_return, 2),
            },
        }
        out_path = out_dir / "simulation_report.json"
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        logger.info(f"시뮬레이션 완료: {len(simulations)}건, 평균 수익률 {avg_return:.1f}%")
        return report
    finally:
        if own_conn:
            conn.close()

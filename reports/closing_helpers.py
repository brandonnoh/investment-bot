#!/usr/bin/env python3
"""
장 마감 리포트 헬퍼/유틸리티 모듈
포트폴리오 스냅샷, OHLC 조회, 포맷 함수, 알림 조회, 월말 적립 적용
"""

from __future__ import annotations

import calendar
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH

KST = timezone(timedelta(hours=9))


def save_portfolio_snapshot(conn: sqlite3.Connection, portfolio_summary: dict):
    """portfolio_summary.json 데이터를 portfolio_history 테이블에 저장.

    같은 날짜 데이터가 있으면 UPDATE, 없으면 INSERT.
    """
    today = datetime.now(KST).strftime("%Y-%m-%d")
    total = portfolio_summary.get("total", {})

    total_value_krw = total.get("current_value_krw")
    total_invested_krw = total.get("invested_krw")
    total_pnl_krw = total.get("pnl_krw")
    total_pnl_pct = total.get("pnl_pct")
    fx_rate = portfolio_summary.get("exchange_rate")
    fx_pnl_krw = total.get("fx_pnl_krw")
    holdings_snapshot = json.dumps(
        portfolio_summary.get("holdings", []), ensure_ascii=False
    )

    conn.execute(
        """INSERT INTO portfolio_history
           (date, total_value_krw, total_invested_krw, total_pnl_krw, total_pnl_pct,
            fx_rate, fx_pnl_krw, holdings_snapshot)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(date) DO UPDATE SET
               total_value_krw = excluded.total_value_krw,
               total_invested_krw = excluded.total_invested_krw,
               total_pnl_krw = excluded.total_pnl_krw,
               total_pnl_pct = excluded.total_pnl_pct,
               fx_rate = excluded.fx_rate,
               fx_pnl_krw = excluded.fx_pnl_krw,
               holdings_snapshot = excluded.holdings_snapshot""",
        (
            today,
            total_value_krw,
            total_invested_krw,
            total_pnl_krw,
            total_pnl_pct,
            fx_rate,
            fx_pnl_krw,
            holdings_snapshot,
        ),
    )
    conn.commit()

    value_man = round((total_value_krw or 0) / 10000)
    print(f"  ✅ 포트폴리오 스냅샷 저장: {today} 총 {value_man:,}만원")


def get_today_ohlc(ticker: str) -> dict | None:
    """DB에서 오늘 수집된 해당 종목의 OHLC 계산"""
    if not DB_PATH.exists():
        return None

    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT price, prev_close, timestamp FROM prices
               WHERE ticker = ? AND timestamp LIKE ?
               ORDER BY timestamp""",
            (ticker, f"{today_str}%"),
        )
        rows = cursor.fetchall()
        if not rows:
            return None

        prices_today = [r[0] for r in rows]
        return {
            "open": prices_today[0],
            "high": max(prices_today),
            "low": min(prices_today),
            "close": prices_today[-1],
            "prev_close": rows[0][1],
            "data_points": len(rows),
            "first_ts": rows[0][2],
            "last_ts": rows[-1][2],
        }
    finally:
        conn.close()


def get_today_macro_ohlc(indicator: str) -> dict | None:
    """DB에서 오늘 수집된 매크로 지표의 OHLC 계산"""
    if not DB_PATH.exists():
        return None

    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT value, change_pct, timestamp FROM macro
               WHERE indicator = ? AND timestamp LIKE ?
               ORDER BY timestamp""",
            (indicator, f"{today_str}%"),
        )
        rows = cursor.fetchall()
        if not rows:
            return None

        values = [r[0] for r in rows]
        return {
            "open": values[0],
            "high": max(values),
            "low": min(values),
            "close": values[-1],
            "change_pct": rows[-1][1],
            "data_points": len(rows),
        }
    finally:
        conn.close()


def fmt_price(val, currency="KRW"):
    """가격 포맷"""
    if val is None:
        return "N/A"
    if currency == "KRW":
        return f"{val:,.0f}"
    return f"{val:,.2f}"


def fmt_change(pct):
    """변동률 포맷"""
    if pct is None:
        return "—"
    emoji = "🔴" if pct < -1 else "🟢" if pct > 1 else "⚪"
    return f"{emoji} {pct:+.2f}%"


def get_today_alerts() -> list[dict]:
    """DB에서 오늘 발생한 알림 조회"""
    if not DB_PATH.exists():
        return []

    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT level, message, triggered_at FROM alerts
               WHERE triggered_at LIKE ?
               ORDER BY triggered_at""",
            (f"{today_str}%",),
        )
        rows = cursor.fetchall()
        results = []
        for r in rows:
            # 시간 부분만 추출
            try:
                ts = datetime.fromisoformat(r[2])
                time_str = ts.strftime("%H:%M")
            except (ValueError, TypeError):
                time_str = "??:??"
            results.append(
                {
                    "level": r[0],
                    "message": r[1],
                    "time": time_str,
                }
            )
        return results
    finally:
        conn.close()


def is_last_business_day_of_month(dt: datetime) -> bool:
    """오늘이 이번 달 마지막 영업일(월~금)인지 확인."""
    year, month = dt.year, dt.month
    last_day = calendar.monthrange(year, month)[1]

    # 해당 월의 마지막 영업일 찾기 (말일부터 역순으로 월~금 첫 번째 날)
    for day in range(last_day, 0, -1):
        candidate = dt.replace(day=day)
        if candidate.weekday() < 5:  # 0=월 ... 4=금
            return dt.day == day
    return False


def apply_monthly_deposits(force: bool = False) -> list[str]:
    """매월 마지막 영업일에 monthly_deposit_krw > 0인 항목의 current_value_krw를 증가.

    SSoT: DB extra_assets 테이블 사용.
    중복 방지: updated_at의 연-월이 오늘과 같으면 건너뜀.
    force=True 이면 날짜 체크 없이 강제 실행 (테스트용).

    반환: 로그 메시지 목록
    """
    from db.ssot import apply_monthly_deposits as db_apply_deposits
    from db.ssot import get_extra_assets

    logs: list[str] = []
    now = datetime.now(KST)

    # 오늘이 마지막 영업일인지 확인 (force=True면 무조건 실행)
    if not force and not is_last_business_day_of_month(now):
        return logs

    # SSoT: DB에서 현재 상태 조회
    assets = get_extra_assets()
    if not assets:
        logs.append("⚠️ extra_assets 테이블 비어있음, 월말 적립 건너뜀")
        return logs

    # 적립 대상 미리 확인
    deposit_targets = [a for a in assets if a.get("monthly_deposit_krw", 0) > 0]
    if not deposit_targets:
        logs.append("ℹ️ monthly_deposit_krw > 0인 항목 없음, 변경 사항 없음")
        return logs

    for a in deposit_targets:
        logs.append(
            f"✅ 월말 적립 예정: {a['name']} "
            f"{a['current_value_krw']:,} → {a['current_value_krw'] + a['monthly_deposit_krw']:,}원 (+{a['monthly_deposit_krw']:,})"
        )

    # SSoT: DB에 적립 적용
    updated = db_apply_deposits()
    logs.append(f"💾 DB extra_assets 업데이트 완료 ({updated}건)")

    return logs

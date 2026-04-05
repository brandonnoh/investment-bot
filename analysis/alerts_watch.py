#!/usr/bin/env python3
"""
실시간 알림 감시 모듈 (Phase 2.5 핵심)
DB 최신 데이터 기반 임계값 체크 + 중복 방지 + OpenClaw cron 즉시 Discord 전송

- 알림 발생 시: DB 저장 → alerts.json 생성 → openclaw cron add로 Discord 즉시 전송
- 알림 없을 시: 조용히 종료 (system event 실행 금지 — 토큰 낭비 방지)
- 중복 방지: 같은 종목+같은 방향 알림은 1시간 내 재발송 금지

공통 감지 로직은 alerts.py에서 import — 중복 코드 제거 (F12)
"""

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# 공통 함수를 alerts.py에서 import (F12 통합)
from analysis.alerts import (
    check_macro_alerts,
    check_portfolio_alert,
    check_stock_alerts,
    save_alerts_to_db,
    save_alerts_to_json,
)

# Discord 발송 모듈 (분리된 alerts_watch_notify에서 re-export)
from analysis.alerts_watch_notify import fire_discord_alert  # noqa: F401
from config import DB_PATH
from config import PORTFOLIO_LEGACY as PORTFOLIO
from db.init_db import init_db

KST = timezone(timedelta(hours=9))

# 중복 알림 방지 간격 (초) — 당일 장 중 같은 알림 반복 방지
DEDUP_INTERVAL_SECONDS = 28800  # 8시간 (하루 장 시간 커버)

# 미국 시장 종목/지표 — 한국 장 시간엔 가격 불변이므로 알림 스킵
US_TICKERS = {"TSLA", "GOOGL", "XOP"}  # 미국 주식
US_MACRO_INDICATORS = {
    "WTI 유가",
    "금 현물",
    "브렌트유",
    "달러 인덱스",
    "VIX",
}  # 미국 지표

# 한국 장 시간 (KST)
KR_MARKET_OPEN = (9, 0)  # 09:00
KR_MARKET_CLOSE = (15, 30)  # 15:30


def is_kr_market_hours() -> bool:
    """현재 한국 장 시간 여부 (09:00~15:30 KST, 월~금)"""
    now = datetime.now(KST)
    if now.weekday() >= 5:  # 토/일
        return False
    t = (now.hour, now.minute)
    return KR_MARKET_OPEN <= t <= KR_MARKET_CLOSE


def filter_us_during_kr_hours(prices: list[dict], macro: list[dict]):
    """한국 장 시간 중엔 미국 종목/지표 필터링 — 미국장 마감으로 가격 불변"""
    if not is_kr_market_hours():
        return prices, macro  # 미국 장 시간이면 전부 허용

    filtered_prices = [p for p in prices if p.get("ticker") not in US_TICKERS]
    filtered_macro = [m for m in macro if m.get("indicator") not in US_MACRO_INDICATORS]

    skipped_p = len(prices) - len(filtered_prices)
    skipped_m = len(macro) - len(filtered_macro)
    if skipped_p + skipped_m > 0:
        print(
            f"  ⏭️  한국 장 시간 — 미국 종목 {skipped_p}개, 매크로 {skipped_m}개 알림 스킵 (미국장 마감)"
        )

    return filtered_prices, filtered_macro


# ── DB 기반 데이터 로드 (실시간 모드 전용) ──


def get_latest_prices_from_db() -> list[dict]:
    """DB에서 각 종목의 최신 가격 조회"""
    if not DB_PATH.exists():
        return []

    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()
        # 각 종목별 가장 최근 레코드
        cursor.execute("""
            SELECT p.ticker, p.name, p.price, p.prev_close, p.change_pct, p.market, p.timestamp
            FROM prices p
            INNER JOIN (
                SELECT ticker, MAX(timestamp) AS max_ts
                FROM prices
                GROUP BY ticker
            ) latest ON p.ticker = latest.ticker AND p.timestamp = latest.max_ts
        """)
        rows = cursor.fetchall()
        results = []
        for row in rows:
            # PORTFOLIO에서 avg_cost, currency, qty 매칭
            stock_info = next((s for s in PORTFOLIO if s["ticker"] == row[0]), {})
            results.append(
                {
                    "ticker": row[0],
                    "name": row[1],
                    "price": row[2],
                    "prev_close": row[3],
                    "change_pct": row[4],
                    "market": row[5],
                    "timestamp": row[6],
                    "avg_cost": stock_info.get("avg_cost", 0),
                    "currency": stock_info.get("currency", "USD"),
                    "qty": stock_info.get("qty", 0),
                }
            )
        return results
    finally:
        conn.close()


def get_latest_macro_from_db() -> list[dict]:
    """DB에서 각 매크로 지표의 최신 값 조회"""
    if not DB_PATH.exists():
        return []

    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.indicator, m.value, m.change_pct, m.timestamp
            FROM macro m
            INNER JOIN (
                SELECT indicator, MAX(timestamp) AS max_ts
                FROM macro
                GROUP BY indicator
            ) latest ON m.indicator = latest.indicator AND m.timestamp = latest.max_ts
        """)
        rows = cursor.fetchall()
        return [
            {"indicator": r[0], "value": r[1], "change_pct": r[2], "timestamp": r[3]}
            for r in rows
        ]
    finally:
        conn.close()


# ── 중복 방지 (실시간 모드 전용) ──


def is_duplicate_alert(
    event_type: str, ticker: str | None, direction: str, conn=None
) -> bool:
    """같은 종목+같은 방향 알림이 최근 1시간 내에 이미 발송되었는지 확인

    Args:
        event_type: 알림 유형
        ticker: 종목 티커 (None 가능)
        direction: 방향 (drop/surge/high 등)
        conn: DB 연결 (None이면 DB_PATH로 새 연결 생성)
    """
    own_conn = False
    if conn is None:
        if not DB_PATH.exists():
            return False
        conn = sqlite3.connect(str(DB_PATH))
        own_conn = True

    try:
        cursor = conn.cursor()
        cutoff = (
            datetime.now(KST) - timedelta(seconds=DEDUP_INTERVAL_SECONDS)
        ).isoformat()

        if ticker:
            cursor.execute(
                """
                SELECT COUNT(*) FROM alerts
                WHERE event_type = ? AND ticker = ? AND triggered_at > ? AND notified = 1
            """,
                (event_type, ticker, cutoff),
            )
        else:
            cursor.execute(
                """
                SELECT COUNT(*) FROM alerts
                WHERE event_type = ? AND ticker IS NULL AND triggered_at > ? AND notified = 1
            """,
                (event_type, cutoff),
            )

        count = cursor.fetchone()[0]
        return count > 0
    finally:
        if own_conn:
            conn.close()


def _filter_duplicates(alerts: list[dict]) -> list[dict]:
    """중복 알림 필터링"""
    filtered = []
    for a in alerts:
        direction = "drop" if a["value"] < 0 else "surge"
        if a["event_type"] in ("usd_krw_high", "vix_high"):
            direction = "high"
        if not is_duplicate_alert(a["event_type"], a.get("ticker"), direction):
            filtered.append(a)
    return filtered


# ── 실시간 모드 실행 ──


def run():
    """알림 감시 파이프라인 실행 (DB 기반 실시간 모드)"""
    print(f"\n🚨 알림 감시 시작 — {datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}")

    # DB 초기화 확인
    if not DB_PATH.exists():
        init_db()

    # DB에서 최신 데이터 로드
    prices = get_latest_prices_from_db()
    macro = get_latest_macro_from_db()

    if not prices and not macro:
        print("  ⚠️  DB에 데이터 없음 — 수집 먼저 실행 필요")
        print()
        return []

    print(f"  📊 종목 {len(prices)}개, 매크로 {len(macro)}개 로드")

    # 한국 장 시간 중 미국 종목/지표 필터링 (가격 불변 알림 방지)
    prices, macro = filter_us_during_kr_hours(prices, macro)

    # 공통 감지 로직 사용 (alerts.py에서 import)
    all_alerts = []
    all_alerts.extend(check_stock_alerts(prices))
    all_alerts.extend(check_macro_alerts(macro))
    all_alerts.extend(check_portfolio_alert(prices))

    # 중복 필터링 (실시간 모드만)
    all_alerts = _filter_duplicates(all_alerts)

    # 결과 출력
    if all_alerts:
        print(f"\n  ⚠️  {len(all_alerts)}건 신규 알림 감지:")
        for a in all_alerts:
            print(f"    {a['message']}")
    else:
        print("\n  ✅ 이상 없음 (또는 중복 알림 필터됨)")

    # 저장 (notified=True — Discord 전송 표시)
    save_alerts_to_db(all_alerts, notified=True)
    save_alerts_to_json(all_alerts)

    # Discord 즉시 전송 — 알림 있을 때만!
    fire_discord_alert(all_alerts)

    print()
    return all_alerts


if __name__ == "__main__":
    run()

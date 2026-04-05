"""성과 추적 + 가중치 학습 모듈

- outcome_1w/outcome_1m 자동 기록 (발굴 후 1주/1개월 수익률)
- 리포트 생성은 analysis.performance_report 위임
- output/intel/performance_report.json 출력
"""

import logging
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

KST = timezone(timedelta(hours=9))
logger = logging.getLogger(__name__)


def _get_db_conn():
    """파일 DB 연결 반환"""
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _find_closest_price(conn, ticker, target_date, window_days=5):
    """target_date 근처 가장 가까운 종가 찾기 (거래일 보정).

    Args:
        conn: DB 연결
        ticker: 종목 티커
        target_date: 목표 날짜 (YYYY-MM-DD)
        window_days: 앞뒤 탐색 범위

    Returns:
        종가 또는 None
    """
    target = datetime.strptime(target_date, "%Y-%m-%d")
    start = (target - timedelta(days=window_days)).strftime("%Y-%m-%d")
    end = (target + timedelta(days=window_days)).strftime("%Y-%m-%d")

    row = conn.execute(
        """
        SELECT close, date FROM prices_daily
        WHERE ticker = ? AND date BETWEEN ? AND ?
        ORDER BY ABS(julianday(date) - julianday(?))
        LIMIT 1
    """,
        (ticker, start, end, target_date),
    ).fetchone()

    if row:
        return row["close"]
    return None


def update_outcomes(conn=None):
    """발굴 종목의 1주/1개월 수익률 자동 기록.

    Args:
        conn: DB 연결 (None이면 파일 DB 사용)

    Returns:
        dict: {"updated_1w": int, "updated_1m": int}
    """
    close_conn = False
    if conn is None:
        conn = _get_db_conn()
        close_conn = True

    result = {"updated_1w": 0, "updated_1m": 0}
    now = datetime.now(KST)

    try:
        # outcome_1w 미기록 + 7일 경과 종목
        rows_1w = conn.execute(
            """
            SELECT id, ticker, discovered_at, price_at_discovery
            FROM opportunities
            WHERE outcome_1w IS NULL
              AND price_at_discovery IS NOT NULL
              AND julianday(?) - julianday(discovered_at) >= 7
        """,
            (now.strftime("%Y-%m-%d"),),
        ).fetchall()

        for row in rows_1w:
            discovered = row["discovered_at"][:10]
            target = (
                datetime.strptime(discovered, "%Y-%m-%d") + timedelta(days=7)
            ).strftime("%Y-%m-%d")
            price = _find_closest_price(conn, row["ticker"], target)
            if price and row["price_at_discovery"]:
                pct = round(
                    (price - row["price_at_discovery"])
                    / row["price_at_discovery"]
                    * 100,
                    2,
                )
                conn.execute(
                    "UPDATE opportunities SET outcome_1w = ? WHERE id = ?",
                    (pct, row["id"]),
                )
                result["updated_1w"] += 1
                logger.info(f"outcome_1w 기록: {row['ticker']} = {pct}%")

        # outcome_1m 미기록 + 30일 경과 종목
        rows_1m = conn.execute(
            """
            SELECT id, ticker, discovered_at, price_at_discovery
            FROM opportunities
            WHERE outcome_1m IS NULL
              AND price_at_discovery IS NOT NULL
              AND julianday(?) - julianday(discovered_at) >= 30
        """,
            (now.strftime("%Y-%m-%d"),),
        ).fetchall()

        for row in rows_1m:
            discovered = row["discovered_at"][:10]
            target = (
                datetime.strptime(discovered, "%Y-%m-%d") + timedelta(days=30)
            ).strftime("%Y-%m-%d")
            price = _find_closest_price(conn, row["ticker"], target)
            if price and row["price_at_discovery"]:
                pct = round(
                    (price - row["price_at_discovery"])
                    / row["price_at_discovery"]
                    * 100,
                    2,
                )
                conn.execute(
                    "UPDATE opportunities SET outcome_1m = ? WHERE id = ?",
                    (pct, row["id"]),
                )
                result["updated_1m"] += 1
                logger.info(f"outcome_1m 기록: {row['ticker']} = {pct}%")

        conn.commit()
    except Exception as e:
        logger.error(f"outcome 업데이트 실패: {e}")

    if close_conn:
        conn.close()

    return result


# 리포트 생성 함수 re-export (하위 호환)
from analysis.performance_report import (
    generate_monthly_report,  # noqa: E402, F401
    generate_weight_suggestion,  # noqa: E402, F401
    save_performance_report,  # noqa: E402
)


def run(conn=None, output_dir=None):
    """파이프라인 진입점.

    Args:
        conn: DB 연결 (None이면 파일 DB)
        output_dir: 출력 디렉토리

    Returns:
        dict: 실행 결과
    """
    try:
        report = save_performance_report(conn=conn, output_dir=output_dir)
        return {
            "outcomes": report.get("outcome_summary", {}),
            "report_saved": True,
        }
    except Exception as e:
        logger.error(f"성과 추적 실행 실패: {e}")
        return {
            "outcomes": {"updated_1w": 0, "updated_1m": 0},
            "report_saved": False,
        }

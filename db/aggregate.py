#!/usr/bin/env python3
"""
일봉 자동 집계 모듈
prices/macro 원시 데이터(10분 해상도) → OHLCV 일봉 집계
중복 집계 방지 (UPSERT 패턴)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _extract_date(timestamp):
    """타임스탬프에서 날짜(YYYY-MM-DD) 추출"""
    return timestamp[:10]


def _aggregate_prices(conn, target_date=None):
    """prices 원시 → prices_daily OHLCV 집계

    Args:
        conn: sqlite3.Connection
        target_date: 특정 날짜만 집계 (YYYY-MM-DD), None이면 전체
    """
    where_clause = ""
    params = ()
    if target_date:
        where_clause = "WHERE SUBSTR(timestamp, 1, 10) = ?"
        params = (target_date,)

    # 날짜+종목별 OHLCV 집계
    # open: 첫 번째 타임스탬프의 가격, close: 마지막 타임스탬프의 가격
    query = f"""
        SELECT
            ticker,
            SUBSTR(timestamp, 1, 10) AS date,
            -- open: 가장 이른 시간의 가격
            (SELECT p2.price FROM prices p2
             WHERE p2.ticker = p.ticker
               AND SUBSTR(p2.timestamp, 1, 10) = SUBSTR(p.timestamp, 1, 10)
             ORDER BY p2.timestamp ASC LIMIT 1) AS open_price,
            MAX(price) AS high,
            MIN(price) AS low,
            -- close: 가장 늦은 시간의 가격
            (SELECT p3.price FROM prices p3
             WHERE p3.ticker = p.ticker
               AND SUBSTR(p3.timestamp, 1, 10) = SUBSTR(p.timestamp, 1, 10)
             ORDER BY p3.timestamp DESC LIMIT 1) AS close_price,
            -- volume: 마지막 레코드의 volume (누적 거래량)
            (SELECT p4.volume FROM prices p4
             WHERE p4.ticker = p.ticker
               AND SUBSTR(p4.timestamp, 1, 10) = SUBSTR(p.timestamp, 1, 10)
             ORDER BY p4.timestamp DESC LIMIT 1) AS volume,
            -- change_pct: 마지막 레코드의 change_pct
            (SELECT p5.change_pct FROM prices p5
             WHERE p5.ticker = p.ticker
               AND SUBSTR(p5.timestamp, 1, 10) = SUBSTR(p.timestamp, 1, 10)
             ORDER BY p5.timestamp DESC LIMIT 1) AS change_pct,
            -- data_source: 마지막 레코드의 data_source
            (SELECT p6.data_source FROM prices p6
             WHERE p6.ticker = p.ticker
               AND SUBSTR(p6.timestamp, 1, 10) = SUBSTR(p.timestamp, 1, 10)
             ORDER BY p6.timestamp DESC LIMIT 1) AS data_source
        FROM prices p
        {where_clause}
        GROUP BY ticker, SUBSTR(timestamp, 1, 10)
    """

    rows = conn.execute(query, params).fetchall()

    for row in rows:
        conn.execute(
            """
            INSERT INTO prices_daily (ticker, date, open, high, low, close, volume, change_pct, data_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker, date) DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume,
                change_pct = excluded.change_pct,
                data_source = excluded.data_source
            """,
            (row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8]),
        )

    conn.commit()
    return len(rows)


def _aggregate_macro(conn, target_date=None):
    """macro 원시 → macro_daily OHLC 집계

    Args:
        conn: sqlite3.Connection
        target_date: 특정 날짜만 집계 (YYYY-MM-DD), None이면 전체
    """
    where_clause = ""
    params = ()
    if target_date:
        where_clause = "WHERE SUBSTR(timestamp, 1, 10) = ?"
        params = (target_date,)

    query = f"""
        SELECT
            indicator,
            SUBSTR(timestamp, 1, 10) AS date,
            (SELECT m2.value FROM macro m2
             WHERE m2.indicator = m.indicator
               AND SUBSTR(m2.timestamp, 1, 10) = SUBSTR(m.timestamp, 1, 10)
             ORDER BY m2.timestamp ASC LIMIT 1) AS open_val,
            MAX(value) AS high,
            MIN(value) AS low,
            (SELECT m3.value FROM macro m3
             WHERE m3.indicator = m.indicator
               AND SUBSTR(m3.timestamp, 1, 10) = SUBSTR(m.timestamp, 1, 10)
             ORDER BY m3.timestamp DESC LIMIT 1) AS close_val,
            (SELECT m4.change_pct FROM macro m4
             WHERE m4.indicator = m.indicator
               AND SUBSTR(m4.timestamp, 1, 10) = SUBSTR(m.timestamp, 1, 10)
             ORDER BY m4.timestamp DESC LIMIT 1) AS change_pct
        FROM macro m
        {where_clause}
        GROUP BY indicator, SUBSTR(timestamp, 1, 10)
    """

    rows = conn.execute(query, params).fetchall()

    for row in rows:
        conn.execute(
            """
            INSERT INTO macro_daily (indicator, date, open, high, low, close, change_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(indicator, date) DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                change_pct = excluded.change_pct
            """,
            (row[0], row[1], row[2], row[3], row[4], row[5], row[6]),
        )

    conn.commit()
    return len(rows)


def aggregate_daily(conn, target_date=None):
    """prices + macro 일봉 집계 실행

    Args:
        conn: sqlite3.Connection
        target_date: 특정 날짜만 집계 (YYYY-MM-DD), None이면 전체
    Returns:
        dict: 집계 결과 요약
    """
    prices_count = _aggregate_prices(conn, target_date)
    macro_count = _aggregate_macro(conn, target_date)

    return {
        "prices_daily": prices_count,
        "macro_daily": macro_count,
    }


def run(conn=None, target_date=None):
    """파이프라인 진입점 — 일봉 집계 실행

    Args:
        conn: sqlite3.Connection (None이면 파일 DB 사용)
        target_date: 특정 날짜만 집계 (YYYY-MM-DD)
    """
    print("📊 일봉 집계 시작...")

    if conn is None:
        conn = get_db_conn()
        try:
            result = aggregate_daily(conn, target_date)
        finally:
            conn.close()
    else:
        result = aggregate_daily(conn, target_date)

    print(f"  ✅ prices_daily: {result['prices_daily']}건, macro_daily: {result['macro_daily']}건")
    return result


if __name__ == "__main__":
    run()

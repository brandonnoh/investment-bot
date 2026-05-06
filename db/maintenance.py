#!/usr/bin/env python3
"""
DB 보존 정책 + 자동 정리 모듈
원시 데이터 N개월, 뉴스 N개월 보존 후 삭제
삭제 전 집계 완료 확인 (미집계 원시 데이터 보호)
VACUUM으로 DB 용량 최적화
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import RETENTION_POLICY
from db.connection import get_db_conn

KST = timezone(timedelta(hours=9))


def _cutoff_date(months):
    """현재 KST 기준 N개월 전 날짜 문자열 (YYYY-MM-DD)"""
    now = datetime.now(KST)
    # 월 단위로 빼기 (30일 * N개월 근사)
    cutoff = now - timedelta(days=30 * months)
    return cutoff.strftime("%Y-%m-%d")


def purge_old_data(conn, raw_months=None, news_months=None):
    """보존 정책에 따라 오래된 데이터 삭제

    Args:
        conn: sqlite3.Connection
        raw_months: 원시 데이터 보존 개월 수 (None이면 config 사용)
        news_months: 뉴스 보존 개월 수 (None이면 config 사용)

    Returns:
        dict: 삭제 결과 요약
    """
    if raw_months is None:
        raw_months = RETENTION_POLICY["raw_months"]
    if news_months is None:
        news_months = RETENTION_POLICY["news_months"]

    raw_cutoff = _cutoff_date(raw_months)
    news_cutoff = _cutoff_date(news_months)

    result = {
        "prices_deleted": 0,
        "macro_deleted": 0,
        "news_deleted": 0,
        "prices_skipped_no_agg": 0,
        "macro_skipped_no_agg": 0,
    }

    # ── 원시 prices 정리 ──
    # 보존 기간 초과 날짜 목록 (ticker별)
    old_prices = conn.execute(
        "SELECT id, ticker, SUBSTR(timestamp, 1, 10) AS date FROM prices "
        "WHERE SUBSTR(timestamp, 1, 10) < ?",
        (raw_cutoff,),
    ).fetchall()

    ids_to_delete = []
    skipped_dates = set()
    for row in old_prices:
        pid, ticker, date = row[0], row[1], row[2]
        # 해당 날짜+종목의 집계가 존재하는지 확인
        agg = conn.execute(
            "SELECT 1 FROM prices_daily WHERE ticker = ? AND date = ?",
            (ticker, date),
        ).fetchone()
        if agg:
            ids_to_delete.append(pid)
        else:
            skipped_dates.add((ticker, date))

    if ids_to_delete:
        placeholders = ",".join("?" * len(ids_to_delete))
        conn.execute(f"DELETE FROM prices WHERE id IN ({placeholders})", ids_to_delete)
    result["prices_deleted"] = len(ids_to_delete)
    result["prices_skipped_no_agg"] = len(skipped_dates)

    # ── 원시 macro 정리 ──
    old_macro = conn.execute(
        "SELECT id, indicator, SUBSTR(timestamp, 1, 10) AS date FROM macro "
        "WHERE SUBSTR(timestamp, 1, 10) < ?",
        (raw_cutoff,),
    ).fetchall()

    ids_to_delete = []
    skipped_dates = set()
    for row in old_macro:
        mid, indicator, date = row[0], row[1], row[2]
        agg = conn.execute(
            "SELECT 1 FROM macro_daily WHERE indicator = ? AND date = ?",
            (indicator, date),
        ).fetchone()
        if agg:
            ids_to_delete.append(mid)
        else:
            skipped_dates.add((indicator, date))

    if ids_to_delete:
        placeholders = ",".join("?" * len(ids_to_delete))
        conn.execute(f"DELETE FROM macro WHERE id IN ({placeholders})", ids_to_delete)
    result["macro_deleted"] = len(ids_to_delete)
    result["macro_skipped_no_agg"] = len(skipped_dates)

    # ── 뉴스 정리 (집계 확인 불필요) ──
    cursor = conn.execute(
        "DELETE FROM news WHERE SUBSTR(published_at, 1, 10) < ?",
        (news_cutoff,),
    )
    result["news_deleted"] = cursor.rowcount

    conn.commit()
    return result


def vacuum_db(conn):
    """VACUUM 실행 + WAL 모드 복구.
    SQLite VACUUM은 journal_mode를 DELETE로 리셋할 수 있으므로 반드시 WAL 재설정 필요.
    WAL 파일이 커지면 'database disk image is malformed' 에러가 발생하므로 VACUUM 전 TRUNCATE 체크포인트 수행.
    """
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.execute("VACUUM")
    conn.execute("PRAGMA journal_mode=WAL")


def run(conn=None):
    """파이프라인 진입점 — 보존 정책 적용 + VACUUM

    Args:
        conn: sqlite3.Connection (None이면 파일 DB 사용)

    Returns:
        dict: 정리 결과 요약
    """
    print("🧹 DB 유지보수 시작...")

    own_conn = conn is None
    if own_conn:
        conn = get_db_conn()

    try:
        result = purge_old_data(conn)
        vacuum_db(conn)

        total = result["prices_deleted"] + result["macro_deleted"] + result["news_deleted"]
        skipped = result["prices_skipped_no_agg"] + result["macro_skipped_no_agg"]

        print(
            f"  삭제: prices {result['prices_deleted']}건, "
            f"macro {result['macro_deleted']}건, "
            f"news {result['news_deleted']}건"
        )
        if skipped:
            print(f"  ⚠️ 집계 미완료로 보존: {skipped}건")
        print(f"  ✅ VACUUM 완료 (총 {total}건 정리)")

        return result
    finally:
        if own_conn:
            conn.close()


if __name__ == "__main__":
    run()

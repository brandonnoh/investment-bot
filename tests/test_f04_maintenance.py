#!/usr/bin/env python3
"""
F04 테스트 — DB 보존 정책 + 자동 정리
보존 기간 초과 원시 데이터 삭제, 뉴스 보존, 집계 미완료 보호, VACUUM
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


KST = timezone(timedelta(hours=9))


def _now_kst():
    return datetime.now(KST)


def _ts(days_ago):
    """현재 기준 N일 전 KST 타임스탬프 문자열"""
    dt = _now_kst() - timedelta(days=days_ago)
    return dt.strftime("%Y-%m-%dT%H:%M:%S+09:00")


def _date(days_ago):
    """현재 기준 N일 전 날짜 문자열 (YYYY-MM-DD)"""
    dt = _now_kst() - timedelta(days=days_ago)
    return dt.strftime("%Y-%m-%d")


def _insert_prices(conn, ticker, timestamp, price=100.0):
    """prices 테이블에 샘플 행 삽입"""
    conn.execute(
        "INSERT INTO prices (ticker, name, price, prev_close, change_pct, volume, timestamp, market) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (ticker, "테스트", price, 99.0, 1.0, 1000, timestamp, "KR"),
    )


def _insert_macro(conn, indicator, timestamp, value=100.0):
    """macro 테이블에 샘플 행 삽입"""
    conn.execute(
        "INSERT INTO macro (indicator, value, change_pct, timestamp) VALUES (?, ?, ?, ?)",
        (indicator, value, 0.5, timestamp),
    )


def _insert_news(conn, title, published_at):
    """news 테이블에 샘플 행 삽입"""
    conn.execute(
        "INSERT INTO news (title, summary, source, url, published_at, relevance_score, tickers, category) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (title, "요약", "RSS", "https://example.com", published_at, 0.8, "[]", "stock"),
    )


def _insert_prices_daily(conn, ticker, date, close=100.0):
    """prices_daily 테이블에 집계 행 삽입"""
    conn.execute(
        "INSERT INTO prices_daily (ticker, date, open, high, low, close, volume, change_pct) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (ticker, date, close, close, close, close, 1000, 1.0),
    )


def _insert_macro_daily(conn, indicator, date, close=100.0):
    """macro_daily 테이블에 집계 행 삽입"""
    conn.execute(
        "INSERT INTO macro_daily (indicator, date, open, high, low, close, change_pct) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (indicator, date, close, close, close, close, 0.5),
    )


def _count(conn, table):
    """테이블 행 수 반환"""
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# ── config.py RETENTION_POLICY 존재 테스트 ──


class TestRetentionConfig:
    """config.py에 RETENTION_POLICY 설정 존재 확인"""

    def test_retention_policy_exists(self):
        """RETENTION_POLICY 딕셔너리가 config.py에 존재"""
        from config import RETENTION_POLICY

        assert isinstance(RETENTION_POLICY, dict)

    def test_retention_policy_has_raw_months(self):
        """원시 데이터 보존 개월 수 설정"""
        from config import RETENTION_POLICY

        assert "raw_months" in RETENTION_POLICY
        assert RETENTION_POLICY["raw_months"] == 3

    def test_retention_policy_has_news_months(self):
        """뉴스 보존 개월 수 설정"""
        from config import RETENTION_POLICY

        assert "news_months" in RETENTION_POLICY
        assert RETENTION_POLICY["news_months"] == 12


# ── db/maintenance.py 모듈 테스트 ──


class TestPurgeRawData:
    """원시 데이터 (prices, macro) 보존 정책 적용"""

    def test_old_prices_deleted(self, db_conn):
        """보존 기간 초과 prices 행 삭제"""
        from db.maintenance import purge_old_data

        # 120일 전 (3개월 초과) — 삭제 대상
        _insert_prices(db_conn, "005930.KS", _ts(120))
        _insert_prices_daily(db_conn, "005930.KS", _date(120))
        # 30일 전 — 보존 대상
        _insert_prices(db_conn, "005930.KS", _ts(30))
        db_conn.commit()

        result = purge_old_data(db_conn, raw_months=3, news_months=12)

        assert _count(db_conn, "prices") == 1
        assert result["prices_deleted"] == 1

    def test_old_macro_deleted(self, db_conn):
        """보존 기간 초과 macro 행 삭제"""
        from db.maintenance import purge_old_data

        _insert_macro(db_conn, "KOSPI", _ts(120))
        _insert_macro_daily(db_conn, "KOSPI", _date(120))
        _insert_macro(db_conn, "KOSPI", _ts(30))
        db_conn.commit()

        result = purge_old_data(db_conn, raw_months=3, news_months=12)

        assert _count(db_conn, "macro") == 1
        assert result["macro_deleted"] == 1

    def test_recent_data_preserved(self, db_conn):
        """보존 기간 내 데이터는 삭제하지 않음"""
        from db.maintenance import purge_old_data

        _insert_prices(db_conn, "005930.KS", _ts(10))
        _insert_prices(db_conn, "005930.KS", _ts(60))
        _insert_macro(db_conn, "KOSPI", _ts(10))
        _insert_macro(db_conn, "KOSPI", _ts(60))
        db_conn.commit()

        result = purge_old_data(db_conn, raw_months=3, news_months=12)

        assert _count(db_conn, "prices") == 2
        assert _count(db_conn, "macro") == 2
        assert result["prices_deleted"] == 0
        assert result["macro_deleted"] == 0


class TestPurgeNews:
    """뉴스 보존 정책 적용"""

    def test_old_news_deleted(self, db_conn):
        """12개월 초과 뉴스 삭제"""
        from db.maintenance import purge_old_data

        _insert_news(db_conn, "오래된 뉴스", _ts(400))  # 13개월 이상
        _insert_news(db_conn, "최근 뉴스", _ts(30))
        db_conn.commit()

        result = purge_old_data(db_conn, raw_months=3, news_months=12)

        assert _count(db_conn, "news") == 1
        assert result["news_deleted"] == 1

    def test_recent_news_preserved(self, db_conn):
        """12개월 이내 뉴스는 보존"""
        from db.maintenance import purge_old_data

        _insert_news(db_conn, "최근 뉴스1", _ts(30))
        _insert_news(db_conn, "최근 뉴스2", _ts(300))
        db_conn.commit()

        result = purge_old_data(db_conn, raw_months=3, news_months=12)

        assert _count(db_conn, "news") == 2
        assert result["news_deleted"] == 0


class TestAggregationSafety:
    """집계 미완료 원시 데이터 보호"""

    def test_unaggregated_data_not_deleted(self, db_conn):
        """집계되지 않은 원시 데이터는 삭제하지 않음 (보존 기간 초과여도)"""
        from db.maintenance import purge_old_data

        # 120일 전 prices — 집계 안 됨 (prices_daily에 없음)
        _insert_prices(db_conn, "TSLA", _ts(120))
        # 120일 전 macro — 집계 안 됨
        _insert_macro(db_conn, "VIX", _ts(120))
        db_conn.commit()

        result = purge_old_data(db_conn, raw_months=3, news_months=12)

        # 집계 안 됐으므로 삭제되면 안 됨
        assert _count(db_conn, "prices") == 1
        assert _count(db_conn, "macro") == 1
        assert result["prices_skipped_no_agg"] >= 1
        assert result["macro_skipped_no_agg"] >= 1

    def test_aggregated_data_deleted(self, db_conn):
        """집계 완료된 원시 데이터는 삭제"""
        from db.maintenance import purge_old_data

        # 120일 전 prices — 집계 완료
        _insert_prices(db_conn, "005930.KS", _ts(120))
        _insert_prices_daily(db_conn, "005930.KS", _date(120))
        # 120일 전 macro — 집계 완료
        _insert_macro(db_conn, "KOSPI", _ts(120))
        _insert_macro_daily(db_conn, "KOSPI", _date(120))
        db_conn.commit()

        result = purge_old_data(db_conn, raw_months=3, news_months=12)

        assert _count(db_conn, "prices") == 0
        assert _count(db_conn, "macro") == 0
        assert result["prices_deleted"] == 1
        assert result["macro_deleted"] == 1


class TestVacuum:
    """VACUUM 실행 테스트"""

    def test_vacuum_runs(self, db_conn):
        """VACUUM 실행 후 에러 없이 완료"""
        from db.maintenance import vacuum_db

        # 데이터 삽입 후 삭제 → VACUUM
        _insert_prices(db_conn, "005930.KS", _ts(10))
        db_conn.commit()
        db_conn.execute("DELETE FROM prices")
        db_conn.commit()

        # 인메모리 DB에서도 에러 없이 실행되어야 함
        vacuum_db(db_conn)


class TestRunFunction:
    """run() 파이프라인 진입점 테스트"""

    def test_run_with_conn(self, db_conn):
        """run(conn)으로 전체 유지보수 실행"""
        from db.maintenance import run

        # 오래된 데이터 + 집계 완료
        _insert_prices(db_conn, "005930.KS", _ts(120))
        _insert_prices_daily(db_conn, "005930.KS", _date(120))
        _insert_macro(db_conn, "KOSPI", _ts(120))
        _insert_macro_daily(db_conn, "KOSPI", _date(120))
        _insert_news(db_conn, "오래된 뉴스", _ts(400))
        # 최근 데이터
        _insert_prices(db_conn, "005930.KS", _ts(10))
        _insert_news(db_conn, "최근 뉴스", _ts(10))
        db_conn.commit()

        result = run(conn=db_conn)

        assert result["prices_deleted"] == 1
        assert result["macro_deleted"] == 1
        assert result["news_deleted"] == 1
        # 최근 데이터 보존
        assert _count(db_conn, "prices") == 1
        assert _count(db_conn, "news") == 1

    def test_run_returns_summary(self, db_conn):
        """run() 결과에 필수 키 포함"""
        from db.maintenance import run

        result = run(conn=db_conn)

        assert "prices_deleted" in result
        assert "macro_deleted" in result
        assert "news_deleted" in result

    def test_custom_retention_months(self, db_conn):
        """커스텀 보존 기간 적용"""
        from db.maintenance import purge_old_data

        # 45일 전 데이터 — 1개월(30일) 기준이면 삭제, 3개월(90일) 기준이면 보존
        _insert_prices(db_conn, "005930.KS", _ts(45))
        _insert_prices_daily(db_conn, "005930.KS", _date(45))
        db_conn.commit()

        result = purge_old_data(db_conn, raw_months=1, news_months=12)
        assert _count(db_conn, "prices") == 0
        assert result["prices_deleted"] == 1

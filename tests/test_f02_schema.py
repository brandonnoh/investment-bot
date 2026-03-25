#!/usr/bin/env python3
"""
F02 테스트 — DB 스키마 재설계
prices_daily, macro_daily, portfolio_history 테이블,
data_source/sentiment 컬럼, 인덱스, 마이그레이션 안전 검증
"""
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── 헬퍼 함수 ──


def get_table_names(conn):
    """DB 내 모든 테이블 이름 반환"""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    return [row[0] for row in cursor.fetchall()]


def get_columns(conn, table_name):
    """테이블의 컬럼 정보 반환 [(cid, name, type, notnull, default, pk)]"""
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    return cursor.fetchall()


def get_column_names(conn, table_name):
    """테이블의 컬럼 이름 목록 반환"""
    return [col[1] for col in get_columns(conn, table_name)]


def get_index_names(conn):
    """DB 내 모든 인덱스 이름 반환"""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    return [row[0] for row in cursor.fetchall()]


# ── 스키마 생성 테스트 ──


class TestSchemaCreation:
    """새 DB에 전체 스키마가 올바르게 생성되는지 검증"""

    def test_all_tables_created(self, db_conn):
        """모든 필수 테이블이 생성되어야 함"""
        tables = get_table_names(db_conn)
        expected = [
            "alerts",
            "macro",
            "macro_daily",
            "news",
            "portfolio_history",
            "prices",
            "prices_daily",
        ]
        for table in expected:
            assert table in tables, f"테이블 '{table}' 누락"

    def test_prices_daily_columns(self, db_conn):
        """prices_daily 테이블 컬럼 검증"""
        cols = get_column_names(db_conn, "prices_daily")
        expected = [
            "id", "ticker", "date", "open", "high", "low", "close",
            "volume", "change_pct", "data_source",
        ]
        for col in expected:
            assert col in cols, f"prices_daily 컬럼 '{col}' 누락"

    def test_macro_daily_columns(self, db_conn):
        """macro_daily 테이블 컬럼 검증"""
        cols = get_column_names(db_conn, "macro_daily")
        expected = [
            "id", "indicator", "date", "open", "high", "low", "close",
            "change_pct",
        ]
        for col in expected:
            assert col in cols, f"macro_daily 컬럼 '{col}' 누락"

    def test_portfolio_history_columns(self, db_conn):
        """portfolio_history 테이블 컬럼 검증"""
        cols = get_column_names(db_conn, "portfolio_history")
        expected = [
            "id", "date", "total_value_krw", "total_invested_krw",
            "total_pnl_krw", "total_pnl_pct", "fx_rate", "fx_pnl_krw",
            "holdings_snapshot",
        ]
        for col in expected:
            assert col in cols, f"portfolio_history 컬럼 '{col}' 누락"

    def test_prices_has_data_source(self, db_conn):
        """prices 테이블에 data_source 컬럼 존재"""
        cols = get_column_names(db_conn, "prices")
        assert "data_source" in cols

    def test_news_has_sentiment(self, db_conn):
        """news 테이블에 sentiment 컬럼 존재"""
        cols = get_column_names(db_conn, "news")
        assert "sentiment" in cols


# ── 인덱스 테스트 ──


class TestIndexOptimization:
    """인덱스가 올바르게 생성되는지 검증"""

    def test_prices_daily_index(self, db_conn):
        """prices_daily에 ticker+date 유니크 인덱스"""
        indexes = get_index_names(db_conn)
        assert "idx_prices_daily_ticker_date" in indexes

    def test_macro_daily_index(self, db_conn):
        """macro_daily에 indicator+date 유니크 인덱스"""
        indexes = get_index_names(db_conn)
        assert "idx_macro_daily_indicator_date" in indexes

    def test_portfolio_history_index(self, db_conn):
        """portfolio_history에 date 유니크 인덱스"""
        indexes = get_index_names(db_conn)
        assert "idx_portfolio_history_date" in indexes

    def test_existing_indexes_preserved(self, db_conn):
        """기존 인덱스가 유지되어야 함"""
        indexes = get_index_names(db_conn)
        assert "idx_prices_ticker_ts" in indexes
        assert "idx_macro_indicator_ts" in indexes
        assert "idx_alerts_triggered" in indexes
        assert "idx_news_title_source" in indexes


# ── CRUD 테스트 ──


class TestCRUD:
    """새 테이블에 데이터 삽입/조회 검증"""

    def test_prices_daily_insert_and_query(self, db_conn):
        """prices_daily CRUD"""
        db_conn.execute("""
            INSERT INTO prices_daily (ticker, date, open, high, low, close, volume, change_pct, data_source)
            VALUES ('005930.KS', '2026-03-25', 81000, 82500, 80500, 82000, 15000000, 0.61, 'naver')
        """)
        db_conn.commit()
        row = db_conn.execute(
            "SELECT * FROM prices_daily WHERE ticker='005930.KS' AND date='2026-03-25'"
        ).fetchone()
        assert row is not None
        assert row["close"] == 82000
        assert row["data_source"] == "naver"

    def test_macro_daily_insert_and_query(self, db_conn):
        """macro_daily CRUD"""
        db_conn.execute("""
            INSERT INTO macro_daily (indicator, date, open, high, low, close, change_pct)
            VALUES ('KOSPI', '2026-03-25', 2640.0, 2660.0, 2630.0, 2650.32, -0.45)
        """)
        db_conn.commit()
        row = db_conn.execute(
            "SELECT * FROM macro_daily WHERE indicator='KOSPI' AND date='2026-03-25'"
        ).fetchone()
        assert row is not None
        assert row["close"] == 2650.32

    def test_portfolio_history_insert_and_query(self, db_conn):
        """portfolio_history CRUD"""
        import json
        holdings = json.dumps([{"ticker": "005930.KS", "value": 3444000}])
        db_conn.execute("""
            INSERT INTO portfolio_history
            (date, total_value_krw, total_invested_krw, total_pnl_krw, total_pnl_pct, fx_rate, fx_pnl_krw, holdings_snapshot)
            VALUES ('2026-03-25', 50000000, 48000000, 2000000, 4.17, 1380.5, 150000, ?)
        """, (holdings,))
        db_conn.commit()
        row = db_conn.execute(
            "SELECT * FROM portfolio_history WHERE date='2026-03-25'"
        ).fetchone()
        assert row is not None
        assert row["total_pnl_pct"] == 4.17
        parsed = json.loads(row["holdings_snapshot"])
        assert parsed[0]["ticker"] == "005930.KS"

    def test_prices_data_source_nullable(self, db_conn):
        """prices.data_source는 NULL 허용 (하위 호환)"""
        db_conn.execute("""
            INSERT INTO prices (ticker, name, price, prev_close, change_pct, volume, timestamp, market)
            VALUES ('TSLA', '테슬라', 275.5, 270.0, 2.04, 80000000, '2026-03-25T04:00:00+09:00', 'US')
        """)
        db_conn.commit()
        row = db_conn.execute("SELECT data_source FROM prices WHERE ticker='TSLA'").fetchone()
        assert row is not None
        assert row["data_source"] is None

    def test_news_sentiment_nullable(self, db_conn):
        """news.sentiment는 NULL 허용 (하위 호환)"""
        db_conn.execute("""
            INSERT INTO news (title, summary, source, url, published_at, relevance_score, tickers, category)
            VALUES ('테스트 뉴스', '요약', 'RSS', 'http://test.com', '2026-03-25', 0.5, '[]', 'stock')
        """)
        db_conn.commit()
        row = db_conn.execute("SELECT sentiment FROM news WHERE title='테스트 뉴스'").fetchone()
        assert row is not None
        assert row["sentiment"] is None


# ── 유니크 제약조건 테스트 ──


class TestUniqueConstraints:
    """유니크 인덱스 동작 검증"""

    def test_prices_daily_unique_ticker_date(self, db_conn):
        """prices_daily에 같은 ticker+date 중복 삽입 시 에러"""
        db_conn.execute("""
            INSERT INTO prices_daily (ticker, date, open, high, low, close, volume, change_pct)
            VALUES ('TSLA', '2026-03-25', 270, 280, 265, 275, 80000000, 2.04)
        """)
        db_conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute("""
                INSERT INTO prices_daily (ticker, date, open, high, low, close, volume, change_pct)
                VALUES ('TSLA', '2026-03-25', 271, 281, 266, 276, 90000000, 2.50)
            """)

    def test_macro_daily_unique_indicator_date(self, db_conn):
        """macro_daily에 같은 indicator+date 중복 삽입 시 에러"""
        db_conn.execute("""
            INSERT INTO macro_daily (indicator, date, open, high, low, close, change_pct)
            VALUES ('KOSPI', '2026-03-25', 2640, 2660, 2630, 2650, -0.45)
        """)
        db_conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute("""
                INSERT INTO macro_daily (indicator, date, open, high, low, close, change_pct)
                VALUES ('KOSPI', '2026-03-25', 2641, 2661, 2631, 2651, -0.50)
            """)

    def test_portfolio_history_unique_date(self, db_conn):
        """portfolio_history에 같은 date 중복 삽입 시 에러"""
        db_conn.execute("""
            INSERT INTO portfolio_history (date, total_value_krw, total_invested_krw, total_pnl_krw, total_pnl_pct, fx_rate, fx_pnl_krw, holdings_snapshot)
            VALUES ('2026-03-25', 50000000, 48000000, 2000000, 4.17, 1380.5, 150000, '[]')
        """)
        db_conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute("""
                INSERT INTO portfolio_history (date, total_value_krw, total_invested_krw, total_pnl_krw, total_pnl_pct, fx_rate, fx_pnl_krw, holdings_snapshot)
                VALUES ('2026-03-25', 51000000, 48000000, 3000000, 6.25, 1381.0, 160000, '[]')
            """)


# ── 마이그레이션 안전 테스트 ──


class TestMigrationSafety:
    """기존 DB에 대한 마이그레이션이 안전한지 검증"""

    def test_migrate_adds_data_source_to_prices(self):
        """기존 prices 테이블에 data_source 컬럼 추가"""
        from db.init_db import init_schema
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        # 기존 스키마 (data_source 없음)
        conn.execute("""
            CREATE TABLE prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                prev_close REAL,
                change_pct REAL,
                volume INTEGER,
                timestamp TEXT NOT NULL,
                market TEXT
            )
        """)
        conn.execute("""
            INSERT INTO prices (ticker, name, price, timestamp)
            VALUES ('TSLA', '테슬라', 275.5, '2026-03-25')
        """)
        conn.commit()

        # 마이그레이션 실행
        init_schema(conn)

        # data_source 컬럼 추가됨, 기존 데이터 보존
        cols = get_column_names(conn, "prices")
        assert "data_source" in cols
        row = conn.execute("SELECT * FROM prices WHERE ticker='TSLA'").fetchone()
        assert row is not None
        assert row["price"] == 275.5
        conn.close()

    def test_migrate_adds_sentiment_to_news(self):
        """기존 news 테이블에 sentiment 컬럼 추가"""
        from db.init_db import init_schema
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        # 기존 스키마 (sentiment 없음)
        conn.execute("""
            CREATE TABLE news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                summary TEXT,
                source TEXT,
                url TEXT,
                published_at TEXT,
                relevance_score REAL,
                tickers TEXT,
                category TEXT
            )
        """)
        conn.execute("""
            INSERT INTO news (title, source) VALUES ('테스트', 'RSS')
        """)
        conn.commit()

        init_schema(conn)

        cols = get_column_names(conn, "news")
        assert "sentiment" in cols
        row = conn.execute("SELECT * FROM news WHERE title='테스트'").fetchone()
        assert row is not None
        conn.close()

    def test_migrate_creates_new_tables(self):
        """기존 DB에 새 테이블들이 추가됨"""
        from db.init_db import init_schema
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        # 기존 테이블만 생성
        conn.execute("CREATE TABLE prices (id INTEGER PRIMARY KEY, ticker TEXT, name TEXT NOT NULL, price REAL NOT NULL, timestamp TEXT NOT NULL)")
        conn.execute("CREATE TABLE macro (id INTEGER PRIMARY KEY, indicator TEXT NOT NULL, value REAL NOT NULL, timestamp TEXT NOT NULL)")
        conn.commit()

        init_schema(conn)

        tables = get_table_names(conn)
        assert "prices_daily" in tables
        assert "macro_daily" in tables
        assert "portfolio_history" in tables
        conn.close()

    def test_idempotent_migration(self):
        """init_schema를 두 번 실행해도 안전"""
        from db.init_db import init_schema
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_schema(conn)
        # 데이터 삽입
        conn.execute("""
            INSERT INTO prices_daily (ticker, date, open, high, low, close, volume, change_pct)
            VALUES ('TSLA', '2026-03-25', 270, 280, 265, 275, 80000000, 2.04)
        """)
        conn.commit()

        # 두 번째 실행
        init_schema(conn)

        # 데이터 보존 확인
        row = conn.execute("SELECT * FROM prices_daily WHERE ticker='TSLA'").fetchone()
        assert row is not None
        assert row["close"] == 275
        conn.close()

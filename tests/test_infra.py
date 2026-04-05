#!/usr/bin/env python3
"""
F01 테스트 인프라 — 모듈 import 테스트 + DB fixture 검증 + 샘플 데이터 검증
"""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

# 프로젝트 루트를 모듈 경로에 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


# ── 모듈 import 테스트 ──


class TestModuleImports:
    """기존 전체 모듈이 정상적으로 import되는지 검증"""

    def test_import_config(self):
        """config 모듈 import"""
        import config

        assert hasattr(config, "PORTFOLIO_LEGACY")
        assert hasattr(config, "MACRO_INDICATORS")
        assert hasattr(config, "ALERT_THRESHOLDS")
        assert hasattr(config, "DB_PATH")
        assert hasattr(config, "OUTPUT_DIR")
        assert hasattr(config, "get_market")

    def test_import_db_init(self):
        """db.init_db 모듈 import"""
        from db.init_db import init_db

        assert callable(init_db)

    def test_import_fetch_prices(self):
        """data.fetch_prices 모듈 import"""
        from data.fetch_prices import run

        assert callable(run)

    def test_import_fetch_macro(self):
        """data.fetch_macro 모듈 import"""
        from data.fetch_macro import run

        assert callable(run)

    def test_import_fetch_news(self):
        """data.fetch_news 모듈 import"""
        from data.fetch_news import run

        assert callable(run)

    def test_import_alerts(self):
        """analysis.alerts 모듈 import"""
        from analysis.alerts import run

        assert callable(run)

    def test_import_alerts_watch(self):
        """analysis.alerts_watch 모듈 import"""
        from analysis.alerts_watch import run

        assert callable(run)

    def test_import_screener(self):
        """analysis.screener 모듈 import"""
        from analysis.screener import run

        assert callable(run)

    def test_import_portfolio(self):
        """analysis.portfolio 모듈 import"""
        from analysis.portfolio import run

        assert callable(run)

    def test_import_daily_report(self):
        """reports.daily 모듈 import"""
        from reports.daily import run

        assert callable(run)

    def test_import_weekly_report(self):
        """reports.weekly 모듈 import"""
        from reports.weekly import run

        assert callable(run)

    def test_import_closing_report(self):
        """reports.closing 모듈 import"""
        from reports.closing import run

        assert callable(run)


# ── DB Fixture 테스트 ──


class TestDBFixture:
    """인메모리 DB fixture가 올바르게 스키마를 생성하는지 검증"""

    def test_db_connection(self, db_conn):
        """DB 연결 정상"""
        assert db_conn is not None
        cursor = db_conn.cursor()
        cursor.execute("SELECT 1")
        assert cursor.fetchone()[0] == 1

    def test_prices_table_exists(self, db_conn):
        """prices 테이블 존재"""
        cursor = db_conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='prices'"
        )
        assert cursor.fetchone() is not None

    def test_macro_table_exists(self, db_conn):
        """macro 테이블 존재"""
        cursor = db_conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='macro'"
        )
        assert cursor.fetchone() is not None

    def test_news_table_exists(self, db_conn):
        """news 테이블 존재"""
        cursor = db_conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='news'"
        )
        assert cursor.fetchone() is not None

    def test_alerts_table_exists(self, db_conn):
        """alerts 테이블 존재"""
        cursor = db_conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='alerts'"
        )
        assert cursor.fetchone() is not None

    def test_prices_insert_and_query(self, db_conn, sample_prices_db_rows):
        """prices 테이블 CRUD"""
        cursor = db_conn.cursor()
        cursor.executemany(
            "INSERT INTO prices (ticker, name, price, prev_close, change_pct, volume, timestamp, market) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            sample_prices_db_rows,
        )
        db_conn.commit()
        cursor.execute("SELECT COUNT(*) FROM prices")
        assert cursor.fetchone()[0] == 2

        cursor.execute("SELECT price FROM prices WHERE ticker = '005930.KS'")
        assert cursor.fetchone()[0] == 82000

    def test_macro_insert_and_query(self, db_conn, sample_macro_db_rows):
        """macro 테이블 CRUD"""
        cursor = db_conn.cursor()
        cursor.executemany(
            "INSERT INTO macro (indicator, value, change_pct, timestamp) VALUES (?, ?, ?, ?)",
            sample_macro_db_rows,
        )
        db_conn.commit()
        cursor.execute("SELECT COUNT(*) FROM macro")
        assert cursor.fetchone()[0] == 3

    def test_news_insert_and_query(self, db_conn, sample_news_db_rows):
        """news 테이블 CRUD"""
        cursor = db_conn.cursor()
        cursor.executemany(
            "INSERT INTO news (title, summary, source, url, published_at, relevance_score, tickers, category) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            sample_news_db_rows,
        )
        db_conn.commit()
        cursor.execute("SELECT COUNT(*) FROM news")
        assert cursor.fetchone()[0] == 2

    def test_news_unique_constraint(self, db_conn, sample_news_db_rows):
        """news 중복 삽입 방지 (title+source unique)"""
        cursor = db_conn.cursor()
        cursor.executemany(
            "INSERT INTO news (title, summary, source, url, published_at, relevance_score, tickers, category) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            sample_news_db_rows,
        )
        db_conn.commit()

        # 같은 title+source로 재삽입 시도 → 중복 에러
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO news (title, summary, source, url, published_at, relevance_score, tickers, category) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                sample_news_db_rows[0],
            )

    def test_alerts_insert_and_query(self, db_conn):
        """alerts 테이블 CRUD"""
        cursor = db_conn.cursor()
        cursor.execute(
            "INSERT INTO alerts (level, event_type, ticker, message, value, threshold, triggered_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "RED",
                "stock_drop",
                "005930.KS",
                "삼성전자 -5.3% 급락",
                -5.3,
                -5.0,
                "2026-03-25T15:30:00+09:00",
            ),
        )
        db_conn.commit()
        cursor.execute(
            "SELECT level, ticker FROM alerts WHERE event_type = 'stock_drop'"
        )
        row = cursor.fetchone()
        assert row["level"] == "RED"
        assert row["ticker"] == "005930.KS"


# ── 샘플 데이터 Fixture 테스트 ──


class TestSampleDataFixtures:
    """pytest fixture로 주입되는 샘플 데이터가 올바른 형식인지 검증"""

    def test_sample_prices_structure(self, sample_prices):
        """prices 샘플 데이터 구조 검증"""
        assert "prices" in sample_prices
        assert "updated_at" in sample_prices
        assert len(sample_prices["prices"]) >= 1
        price = sample_prices["prices"][0]
        required_keys = {
            "name",
            "ticker",
            "price",
            "prev_close",
            "change_pct",
            "volume",
            "market",
            "timestamp",
        }
        assert required_keys.issubset(price.keys())

    def test_sample_macro_structure(self, sample_macro):
        """macro 샘플 데이터 구조 검증"""
        assert "indicators" in sample_macro
        assert "updated_at" in sample_macro
        assert len(sample_macro["indicators"]) >= 1
        indicator = sample_macro["indicators"][0]
        required_keys = {
            "name",
            "ticker",
            "value",
            "change_pct",
            "category",
            "timestamp",
        }
        assert required_keys.issubset(indicator.keys())

    def test_sample_news_structure(self, sample_news):
        """news 샘플 데이터 구조 검증"""
        assert "news" in sample_news
        assert "updated_at" in sample_news
        assert len(sample_news["news"]) >= 1
        article = sample_news["news"][0]
        required_keys = {
            "title",
            "summary",
            "source",
            "url",
            "published_at",
            "relevance_score",
            "tickers",
            "category",
        }
        assert required_keys.issubset(article.keys())

    def test_fixture_json_files_loadable(self):
        """fixtures/ 디렉토리의 JSON 파일이 정상 로드되는지 검증"""
        for fname in ["sample_prices.json", "sample_macro.json", "sample_news.json"]:
            fpath = FIXTURES_DIR / fname
            assert fpath.exists(), f"{fname} 파일이 없습니다"
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            assert isinstance(data, dict)


# ── config.py 테스트 ──


class TestConfig:
    """config.py 핵심 설정이 올바른지 검증"""

    def test_portfolio_not_empty(self):
        """포트폴리오에 종목이 있어야 함"""
        from config import PORTFOLIO_LEGACY as PORTFOLIO

        assert len(PORTFOLIO) > 0

    def test_portfolio_required_fields(self):
        """포트폴리오 각 항목에 필수 필드가 있어야 함"""
        from config import PORTFOLIO_LEGACY as PORTFOLIO

        required = {"name", "ticker", "avg_cost", "currency", "qty", "account"}
        for item in PORTFOLIO:
            assert required.issubset(item.keys()), (
                f"{item.get('name', '?')}에 필수 필드 누락"
            )

    def test_macro_indicators_not_empty(self):
        """매크로 지표가 있어야 함"""
        from config import MACRO_INDICATORS

        assert len(MACRO_INDICATORS) > 0

    def test_get_market_kr(self):
        """한국 주식 마켓 분류"""
        from config import get_market

        assert get_market("005930.KS") == "KR"

    def test_get_market_us(self):
        """미국 주식 마켓 분류"""
        from config import get_market

        assert get_market("TSLA") == "US"

    def test_get_market_commodity(self):
        """상품 마켓 분류"""
        from config import get_market

        assert get_market("GOLD_KRW_G") == "COMMODITY"
        assert get_market("CL=F") == "COMMODITY"

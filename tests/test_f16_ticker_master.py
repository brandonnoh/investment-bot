"""Phase 4 DB 스키마 테스트 — ticker_master, agent_keywords, opportunities 테이블"""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_ticker_master_table_created(db_conn):
    """ticker_master 테이블이 생성되는지 확인"""
    cursor = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='ticker_master'"
    )
    assert cursor.fetchone() is not None


def test_agent_keywords_table_created(db_conn):
    """agent_keywords 테이블이 생성되는지 확인"""
    cursor = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_keywords'"
    )
    assert cursor.fetchone() is not None


def test_opportunities_table_created(db_conn):
    """opportunities 테이블이 생성되는지 확인"""
    cursor = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='opportunities'"
    )
    assert cursor.fetchone() is not None


def test_opportunities_columns(db_conn):
    """opportunities 테이블에 sub_scores 컬럼이 있는지"""
    cursor = db_conn.execute("PRAGMA table_info(opportunities)")
    columns = {row[1] for row in cursor.fetchall()}
    expected = {
        "id", "ticker", "name", "discovered_at", "discovered_via",
        "source", "composite_score", "score_return", "score_rsi",
        "score_sentiment", "score_macro", "price_at_discovery",
        "outcome_1w", "outcome_1m", "status",
    }
    assert expected.issubset(columns)


def test_ticker_master_crud(db_conn):
    """ticker_master 기본 CRUD"""
    db_conn.execute(
        "INSERT INTO ticker_master (ticker, name, market, sector, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("005930.KS", "삼성전자", "KOSPI", "반도체", "2026-03-26")
    )
    db_conn.commit()
    row = db_conn.execute("SELECT name FROM ticker_master WHERE ticker='005930.KS'").fetchone()
    assert row[0] == "삼성전자"


def test_agent_keywords_crud(db_conn):
    """agent_keywords 기본 CRUD"""
    db_conn.execute(
        "INSERT INTO agent_keywords (keyword, category, priority, generated_at) VALUES (?, ?, ?, ?)",
        ("방산 수주", "sector", 1, "2026-03-26T05:30:00+09:00")
    )
    db_conn.commit()
    row = db_conn.execute("SELECT keyword FROM agent_keywords WHERE category='sector'").fetchone()
    assert row[0] == "방산 수주"


def test_opportunities_crud(db_conn):
    """opportunities 기본 CRUD"""
    db_conn.execute(
        """INSERT INTO opportunities (ticker, name, discovered_at, discovered_via, source,
           composite_score, score_return, score_rsi, score_sentiment, score_macro, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("012450.KS", "한화에어로스페이스", "2026-03-26T06:00:00+09:00",
         "방산 수주", "brave", 0.82, 0.8, 0.7, 0.9, 0.85, "discovered")
    )
    db_conn.commit()
    row = db_conn.execute("SELECT composite_score FROM opportunities WHERE ticker='012450.KS'").fetchone()
    assert row[0] == 0.82

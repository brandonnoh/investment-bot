#!/usr/bin/env python3
"""
SQLite 데이터베이스 스키마 초기화
원시 테이블 (prices, macro, news, alerts) + 집계 테이블 (prices_daily, macro_daily) + 기록 테이블 (portfolio_history)
마이그레이션 안전: 기존 DB에서 실행해도 데이터 보존
"""

import sqlite3
import sys
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH


def _get_column_names(cursor, table_name):
    """테이블의 컬럼 이름 목록 반환"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def _table_exists(cursor, table_name):
    """테이블 존재 여부 확인"""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _migrate_add_column(cursor, table_name, column_name, column_def):
    """기존 테이블에 컬럼 추가 (없을 때만)"""
    if _table_exists(cursor, table_name):
        cols = _get_column_names(cursor, table_name)
        if column_name not in cols:
            cursor.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"
            )


def init_schema(conn):
    """DB 연결에 스키마 적용 (테이블 생성 + 마이그레이션)

    Args:
        conn: sqlite3.Connection 객체 (인메모리 또는 파일)
    """
    cursor = conn.cursor()

    # ── 원시 테이블 (10분 해상도, 3개월 보존) ──

    # 가격 히스토리 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            prev_close REAL,
            change_pct REAL,
            volume INTEGER,
            timestamp TEXT NOT NULL,
            market TEXT,
            data_source TEXT  -- kiwoom / naver / yahoo / calculated
        )
    """)

    # 매크로 지표 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS macro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            indicator TEXT NOT NULL,  -- KOSPI, USD_KRW, WTI, GOLD, VIX 등
            value REAL NOT NULL,
            change_pct REAL,
            timestamp TEXT NOT NULL
        )
    """)

    # 뉴스 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            summary TEXT,
            source TEXT,
            url TEXT,
            published_at TEXT,
            relevance_score REAL,
            sentiment REAL,  -- -1.0 ~ 1.0 감성 점수
            tickers TEXT,    -- JSON 배열
            category TEXT    -- stock / geopolitics / macro / sector / opportunity
        )
    """)

    # 알림 이력 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT NOT NULL,  -- RED / YELLOW / GREEN
            event_type TEXT NOT NULL,
            ticker TEXT,
            message TEXT NOT NULL,
            value REAL,
            threshold REAL,
            triggered_at TEXT NOT NULL,
            notified INTEGER DEFAULT 0
        )
    """)

    # ── 집계 테이블 (일봉, 영구 보존) ──

    # 가격 일봉 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prices_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            change_pct REAL,
            data_source TEXT  -- 원시 데이터 출처
        )
    """)

    # 매크로 일봉 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS macro_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            indicator TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            change_pct REAL
        )
    """)

    # ── 기록 테이블 ──

    # 포트폴리오 일별 스냅샷
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            total_value_krw REAL,
            total_invested_krw REAL,
            total_pnl_krw REAL,
            total_pnl_pct REAL,
            fx_rate REAL,
            fx_pnl_krw REAL,
            holdings_snapshot TEXT  -- JSON: 종목별 상세
        )
    """)

    # ── Phase 4: 종목 발굴 ──

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticker_master (
            ticker TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            name_en TEXT,
            market TEXT,
            sector TEXT,
            updated_at TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ticker_master_name
        ON ticker_master (name)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            category TEXT,
            priority INTEGER DEFAULT 5,
            reasoning TEXT,
            generated_at TEXT NOT NULL,
            used_at TEXT,
            results_count INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_agent_keywords_date
        ON agent_keywords (generated_at)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            name TEXT,
            discovered_at TEXT NOT NULL,
            discovered_via TEXT,
            source TEXT,
            composite_score REAL,
            score_return REAL,
            score_rsi REAL,
            score_sentiment REAL,
            score_macro REAL,
            price_at_discovery REAL,
            outcome_1w REAL,
            outcome_1m REAL,
            status TEXT DEFAULT 'discovered'
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_opp_ticker_date
        ON opportunities (ticker, discovered_at)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_opp_score
        ON opportunities (composite_score DESC)
    """)

    # ── Phase 4.1: 펀더멘탈 데이터 ──

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fundamentals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            name TEXT,
            market TEXT,
            per REAL,
            pbr REAL,
            roe REAL,
            debt_ratio REAL,
            revenue_growth REAL,
            operating_margin REAL,
            fcf REAL,
            eps REAL,
            dividend_yield REAL,
            market_cap REAL,
            data_source TEXT,
            updated_at TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_fundamentals_ticker
        ON fundamentals (ticker)
    """)

    # ── 마이그레이션: 기존 테이블에 새 컬럼 추가 ──
    _migrate_add_column(cursor, "prices", "data_source", "TEXT")
    _migrate_add_column(cursor, "news", "sentiment", "REAL")

    # ── 인덱스 생성 — 조회 성능 최적화 ──

    # 원시 테이블 인덱스
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_prices_ticker_ts ON prices (ticker, timestamp)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_macro_indicator_ts ON macro (indicator, timestamp)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_alerts_triggered ON alerts (triggered_at)"
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_news_title_source ON news (title, source)"
    )

    # 집계 테이블 인덱스 (유니크 — UPSERT 지원)
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_prices_daily_ticker_date ON prices_daily (ticker, date)"
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_macro_daily_indicator_date ON macro_daily (indicator, date)"
    )

    # 기록 테이블 인덱스 (일별 1행)
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_portfolio_history_date ON portfolio_history (date)"
    )

    conn.commit()


def init_db():
    """파일 기반 DB 스키마 초기화 (이미 존재하면 마이그레이션)"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    init_schema(conn)
    conn.close()
    print(f"✅ 데이터베이스 초기화 완료: {DB_PATH}")


if __name__ == "__main__":
    init_db()

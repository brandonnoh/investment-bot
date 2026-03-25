#!/usr/bin/env python3
"""
테스트 공통 설정 — pytest conftest.py
DB fixture, 샘플 데이터, 프로젝트 경로 설정
"""

import sqlite3
import sys
from pathlib import Path

import pytest

# 프로젝트 루트를 모듈 경로에 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def db_conn():
    """인메모리 SQLite DB — 전체 스키마 자동 생성"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # prices 테이블
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
            market TEXT
        )
    """)

    # macro 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS macro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            indicator TEXT NOT NULL,
            value REAL NOT NULL,
            change_pct REAL,
            timestamp TEXT NOT NULL
        )
    """)

    # news 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news (
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

    # alerts 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT NOT NULL,
            event_type TEXT NOT NULL,
            ticker TEXT,
            message TEXT NOT NULL,
            value REAL,
            threshold REAL,
            triggered_at TEXT NOT NULL,
            notified INTEGER DEFAULT 0
        )
    """)

    # 인덱스
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

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def sample_prices():
    """샘플 가격 데이터 (prices.json 형식)"""
    return {
        "prices": [
            {
                "name": "삼성전자",
                "ticker": "005930.KS",
                "price": 82000,
                "prev_close": 81500,
                "change_pct": 0.61,
                "volume": 15000000,
                "market": "KR",
                "timestamp": "2026-03-25T15:30:00+09:00",
            },
            {
                "name": "테슬라",
                "ticker": "TSLA",
                "price": 275.50,
                "prev_close": 270.00,
                "change_pct": 2.04,
                "volume": 80000000,
                "market": "US",
                "timestamp": "2026-03-25T04:00:00+09:00",
            },
        ],
        "updated_at": "2026-03-25T15:30:00+09:00",
    }


@pytest.fixture
def sample_macro():
    """샘플 매크로 지표 데이터 (macro.json 형식)"""
    return {
        "indicators": [
            {
                "name": "코스피",
                "ticker": "KOSPI",
                "value": 2650.32,
                "change_pct": -0.45,
                "category": "INDEX",
                "timestamp": "2026-03-25T15:30:00+09:00",
            },
            {
                "name": "원/달러",
                "ticker": "KRW=X",
                "value": 1380.50,
                "change_pct": 0.12,
                "category": "FX",
                "timestamp": "2026-03-25T15:30:00+09:00",
            },
            {
                "name": "VIX",
                "ticker": "^VIX",
                "value": 18.5,
                "change_pct": -2.1,
                "category": "VOLATILITY",
                "timestamp": "2026-03-25T04:00:00+09:00",
            },
        ],
        "updated_at": "2026-03-25T15:30:00+09:00",
    }


@pytest.fixture
def sample_news():
    """샘플 뉴스 데이터 (news.json 형식)"""
    return {
        "news": [
            {
                "title": "삼성전자, AI 반도체 투자 확대 발표",
                "summary": "삼성전자가 AI 반도체 생산 라인에 10조원 추가 투자를 발표했다.",
                "source": "Google RSS",
                "url": "https://example.com/news/1",
                "published_at": "2026-03-25T10:00:00+09:00",
                "relevance_score": 0.9,
                "tickers": ["005930.KS"],
                "category": "stock",
            },
            {
                "title": "Fed holds interest rates steady",
                "summary": "The Federal Reserve kept rates unchanged at 4.25-4.50%.",
                "source": "Brave",
                "url": "https://example.com/news/2",
                "published_at": "2026-03-25T03:00:00+09:00",
                "relevance_score": 0.7,
                "tickers": [],
                "category": "macro",
            },
        ],
        "updated_at": "2026-03-25T15:30:00+09:00",
    }


@pytest.fixture
def tmp_output_dir(tmp_path):
    """임시 output/intel/ 디렉토리"""
    intel_dir = tmp_path / "output" / "intel"
    intel_dir.mkdir(parents=True)
    return intel_dir


@pytest.fixture
def sample_prices_db_rows():
    """DB에 삽입할 샘플 prices 행"""
    return [
        (
            "005930.KS",
            "삼성전자",
            82000,
            81500,
            0.61,
            15000000,
            "2026-03-25T15:30:00+09:00",
            "KR",
        ),
        (
            "TSLA",
            "테슬라",
            275.50,
            270.00,
            2.04,
            80000000,
            "2026-03-25T04:00:00+09:00",
            "US",
        ),
    ]


@pytest.fixture
def sample_macro_db_rows():
    """DB에 삽입할 샘플 macro 행"""
    return [
        ("KOSPI", 2650.32, -0.45, "2026-03-25T15:30:00+09:00"),
        ("KRW=X", 1380.50, 0.12, "2026-03-25T15:30:00+09:00"),
        ("^VIX", 18.5, -2.1, "2026-03-25T04:00:00+09:00"),
    ]


@pytest.fixture
def sample_news_db_rows():
    """DB에 삽입할 샘플 news 행"""
    return [
        (
            "삼성전자, AI 반도체 투자 확대 발표",
            "삼성전자가 AI 반도체 생산 라인에 10조원 추가 투자를 발표했다.",
            "Google RSS",
            "https://example.com/news/1",
            "2026-03-25T10:00:00+09:00",
            0.9,
            '["005930.KS"]',
            "stock",
        ),
        (
            "Fed holds interest rates steady",
            "The Federal Reserve kept rates unchanged.",
            "Brave",
            "https://example.com/news/2",
            "2026-03-25T03:00:00+09:00",
            0.7,
            "[]",
            "macro",
        ),
    ]

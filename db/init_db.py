#!/usr/bin/env python3
"""
SQLite 데이터베이스 스키마 초기화
prices, macro, news, alerts 테이블 생성
"""
import sqlite3
import sys
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH


def init_db():
    """데이터베이스 스키마 초기화 (이미 존재하면 무시)"""
    # db 디렉토리 확인
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

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
            market TEXT  -- KR / US / COMMODITY
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

    # 뉴스 테이블 (Phase 2에서 사용)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            summary TEXT,
            source TEXT,
            url TEXT,
            published_at TEXT,
            relevance_score REAL,
            tickers TEXT  -- JSON 배열
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

    # 인덱스 생성 — 조회 성능 최적화
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_prices_ticker_ts ON prices (ticker, timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_macro_indicator_ts ON macro (indicator, timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_triggered ON alerts (triggered_at)")

    conn.commit()
    conn.close()
    print(f"✅ 데이터베이스 초기화 완료: {DB_PATH}")


if __name__ == "__main__":
    init_db()

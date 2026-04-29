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
from db.init_db_schema import (
    CREATE_INDEX_ADVISOR_STRATEGIES_DATE,
    CREATE_INDEX_AGENT_KEYWORDS_DATE,
    CREATE_INDEX_ALERTS_TRIGGERED,
    CREATE_INDEX_ANALYSIS_HISTORY_DATE,
    CREATE_INDEX_CORRECTION_NOTES_HISTORY_DATE,
    CREATE_INDEX_EXTRA_ASSETS_NAME,
    CREATE_INDEX_FUNDAMENTALS_TICKER,
    CREATE_INDEX_HOLDINGS_TICKER,
    CREATE_INDEX_INVESTMENT_ASSETS_CATEGORY,
    CREATE_INDEX_MACRO_DAILY_INDICATOR_DATE,
    CREATE_INDEX_MACRO_INDICATOR_TS,
    CREATE_INDEX_NEWS_CATEGORY,
    CREATE_INDEX_NEWS_PUBLISHED_AT,
    CREATE_INDEX_NEWS_TITLE_SOURCE,
    CREATE_INDEX_OPP_SCORE,
    CREATE_INDEX_OPP_TICKER_DATE,
    CREATE_INDEX_PERFORMANCE_REPORT_HISTORY_DATE,
    CREATE_INDEX_PORTFOLIO_HISTORY_DATE,
    CREATE_INDEX_PRICES_DAILY_TICKER_DATE,
    CREATE_INDEX_PRICES_TICKER_TS,
    CREATE_INDEX_REGIME_HISTORY_DATE,
    CREATE_INDEX_SECTOR_SCORES_HISTORY_DATE,
    CREATE_INDEX_SOLAR_LISTINGS_SOURCE,
    CREATE_INDEX_TICKER_MASTER_NAME,
    CREATE_INDEX_TOTAL_WEALTH_DATE,
    CREATE_INDEX_TRANSACTIONS_TICKER_DATE,
    CREATE_TABLE_ADVISOR_STRATEGIES,
    CREATE_TABLE_AGENT_KEYWORDS,
    CREATE_TABLE_ALERTS,
    CREATE_TABLE_ANALYSIS_HISTORY,
    CREATE_TABLE_COMPANY_PROFILES,
    CREATE_TABLE_CORRECTION_NOTES_HISTORY,
    CREATE_TABLE_EXTRA_ASSETS,
    CREATE_TABLE_FUNDAMENTALS,
    CREATE_TABLE_HOLDINGS,
    CREATE_TABLE_INVESTMENT_ASSETS,
    CREATE_TABLE_MACRO,
    CREATE_TABLE_MACRO_DAILY,
    CREATE_TABLE_NEWS,
    CREATE_TABLE_OPPORTUNITIES,
    CREATE_TABLE_PERFORMANCE_REPORT_HISTORY,
    CREATE_TABLE_PORTFOLIO_HISTORY,
    CREATE_TABLE_PRICES,
    CREATE_TABLE_PRICES_DAILY,
    CREATE_TABLE_REGIME_HISTORY,
    CREATE_TABLE_SECTOR_SCORES_HISTORY,
    CREATE_TABLE_SOLAR_LISTINGS,
    CREATE_TABLE_TICKER_MASTER,
    CREATE_TABLE_TOTAL_WEALTH_HISTORY,
    CREATE_TABLE_TRANSACTIONS,
    CREATE_UNIQUE_INDEX_MACRO_INDICATOR_TS,
    CREATE_UNIQUE_INDEX_PRICES_TICKER_TS,
    MIGRATION_COLUMNS,
)


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
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")


def init_schema(conn):
    """DB 연결에 스키마 적용 (테이블 생성 + 마이그레이션)

    Args:
        conn: sqlite3.Connection 객체 (인메모리 또는 파일)
    """
    cursor = conn.cursor()

    # ── 원시 테이블 (10분 해상도, 3개월 보존) ──
    cursor.execute(CREATE_TABLE_PRICES)
    cursor.execute(CREATE_TABLE_MACRO)
    cursor.execute(CREATE_TABLE_NEWS)
    cursor.execute(CREATE_TABLE_ALERTS)

    # ── 집계 테이블 (일봉, 영구 보존) ──
    cursor.execute(CREATE_TABLE_PRICES_DAILY)
    cursor.execute(CREATE_TABLE_MACRO_DAILY)

    # ── 기록 테이블 ──
    cursor.execute(CREATE_TABLE_PORTFOLIO_HISTORY)

    # ── Phase 4: 종목 발굴 ──
    cursor.execute(CREATE_TABLE_TICKER_MASTER)
    cursor.execute(CREATE_INDEX_TICKER_MASTER_NAME)
    cursor.execute(CREATE_TABLE_AGENT_KEYWORDS)
    cursor.execute(CREATE_INDEX_AGENT_KEYWORDS_DATE)
    cursor.execute(CREATE_TABLE_OPPORTUNITIES)
    cursor.execute(CREATE_INDEX_OPP_TICKER_DATE)
    cursor.execute(CREATE_INDEX_OPP_SCORE)

    # ── Phase 4.1: 펀더멘탈 데이터 ──
    cursor.execute(CREATE_TABLE_FUNDAMENTALS)
    cursor.execute(CREATE_INDEX_FUNDAMENTALS_TICKER)

    # ── SSoT (Single Source of Truth) — 자산 관리 중앙 집중화 ──
    cursor.execute(CREATE_TABLE_HOLDINGS)
    cursor.execute(CREATE_INDEX_HOLDINGS_TICKER)
    cursor.execute(CREATE_TABLE_TRANSACTIONS)
    cursor.execute(CREATE_INDEX_TRANSACTIONS_TICKER_DATE)
    cursor.execute(CREATE_TABLE_EXTRA_ASSETS)
    cursor.execute(CREATE_INDEX_EXTRA_ASSETS_NAME)
    cursor.execute(CREATE_TABLE_TOTAL_WEALTH_HISTORY)
    cursor.execute(CREATE_INDEX_TOTAL_WEALTH_DATE)

    # ── AI 분석 이력 ──
    cursor.execute(CREATE_TABLE_ANALYSIS_HISTORY)
    cursor.execute(CREATE_INDEX_ANALYSIS_HISTORY_DATE)

    # ── 태양광 발전소 매물 모니터링 ──
    cursor.execute(CREATE_TABLE_SOLAR_LISTINGS)
    cursor.execute(CREATE_INDEX_SOLAR_LISTINGS_SOURCE)

    # ── 투자 어드바이저 자산 정의 ──
    cursor.execute(CREATE_TABLE_INVESTMENT_ASSETS)
    cursor.execute(CREATE_INDEX_INVESTMENT_ASSETS_CATEGORY)

    # ── 어드바이저 저장 전략 이력 ──
    cursor.execute(CREATE_TABLE_ADVISOR_STRATEGIES)
    cursor.execute(CREATE_INDEX_ADVISOR_STRATEGIES_DATE)

    # ── 기업 프로필 (스크리너 추천 종목 상세) ──
    cursor.execute(CREATE_TABLE_COMPANY_PROFILES)

    # ── 파이프라인 분석 이력 (JSON 덮어쓰기 보완) ──
    cursor.execute(CREATE_TABLE_REGIME_HISTORY)
    cursor.execute(CREATE_INDEX_REGIME_HISTORY_DATE)
    cursor.execute(CREATE_TABLE_SECTOR_SCORES_HISTORY)
    cursor.execute(CREATE_INDEX_SECTOR_SCORES_HISTORY_DATE)
    cursor.execute(CREATE_TABLE_CORRECTION_NOTES_HISTORY)
    cursor.execute(CREATE_INDEX_CORRECTION_NOTES_HISTORY_DATE)
    cursor.execute(CREATE_TABLE_PERFORMANCE_REPORT_HISTORY)
    cursor.execute(CREATE_INDEX_PERFORMANCE_REPORT_HISTORY_DATE)

    # ── 마이그레이션: 기존 테이블에 새 컬럼 추가 ──
    for table_name, column_name, column_def in MIGRATION_COLUMNS:
        _migrate_add_column(cursor, table_name, column_name, column_def)

    # ── 인덱스 생성 — 조회 성능 최적화 ──

    # 원시 테이블 인덱스
    cursor.execute(CREATE_INDEX_PRICES_TICKER_TS)
    cursor.execute(CREATE_INDEX_MACRO_INDICATOR_TS)
    cursor.execute(CREATE_INDEX_ALERTS_TRIGGERED)
    cursor.execute(CREATE_INDEX_NEWS_TITLE_SOURCE)
    cursor.execute(CREATE_INDEX_NEWS_CATEGORY)
    cursor.execute(CREATE_INDEX_NEWS_PUBLISHED_AT)

    # 원시 테이블 중복 방지 UNIQUE 인덱스 — INSERT OR IGNORE 와 짝
    cursor.execute(CREATE_UNIQUE_INDEX_PRICES_TICKER_TS)
    cursor.execute(CREATE_UNIQUE_INDEX_MACRO_INDICATOR_TS)

    # 집계 테이블 인덱스 (유니크 — UPSERT 지원)
    cursor.execute(CREATE_INDEX_PRICES_DAILY_TICKER_DATE)
    cursor.execute(CREATE_INDEX_MACRO_DAILY_INDICATOR_DATE)

    # 기록 테이블 인덱스 (일별 1행)
    cursor.execute(CREATE_INDEX_PORTFOLIO_HISTORY_DATE)

    conn.commit()


def init_db():
    """파일 기반 DB 스키마 초기화 (이미 존재하면 마이그레이션)"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    # WAL 모드: 읽기/쓰기 동시성 향상, 파이프라인 병렬 접근 대비
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    init_schema(conn)
    conn.close()
    print(f"✅ 데이터베이스 초기화 완료: {DB_PATH}")


if __name__ == "__main__":
    init_db()

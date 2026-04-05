#!/usr/bin/env python3
"""
DB 스키마 SQL 상수 모음
init_db.py의 init_schema()가 실행하는 모든 DDL 문을 상수로 관리
"""

# ── 원시 테이블 (10분 해상도, 3개월 보존) ──

CREATE_TABLE_PRICES = """
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
"""

CREATE_TABLE_MACRO = """
    CREATE TABLE IF NOT EXISTS macro (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        indicator TEXT NOT NULL,  -- KOSPI, USD_KRW, WTI, GOLD, VIX 등
        value REAL NOT NULL,
        change_pct REAL,
        timestamp TEXT NOT NULL
    )
"""

CREATE_TABLE_NEWS = """
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
"""

CREATE_TABLE_ALERTS = """
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
"""

# ── 집계 테이블 (일봉, 영구 보존) ──

CREATE_TABLE_PRICES_DAILY = """
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
"""

CREATE_TABLE_MACRO_DAILY = """
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
"""

# ── 기록 테이블 ──

CREATE_TABLE_PORTFOLIO_HISTORY = """
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
"""

# ── Phase 4: 종목 발굴 ──

CREATE_TABLE_TICKER_MASTER = """
    CREATE TABLE IF NOT EXISTS ticker_master (
        ticker TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        name_en TEXT,
        market TEXT,
        sector TEXT,
        updated_at TEXT NOT NULL
    )
"""

CREATE_INDEX_TICKER_MASTER_NAME = """
    CREATE INDEX IF NOT EXISTS idx_ticker_master_name
    ON ticker_master (name)
"""

CREATE_TABLE_AGENT_KEYWORDS = """
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
"""

CREATE_INDEX_AGENT_KEYWORDS_DATE = """
    CREATE INDEX IF NOT EXISTS idx_agent_keywords_date
    ON agent_keywords (generated_at)
"""

CREATE_TABLE_OPPORTUNITIES = """
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
"""

CREATE_INDEX_OPP_TICKER_DATE = """
    CREATE INDEX IF NOT EXISTS idx_opp_ticker_date
    ON opportunities (ticker, discovered_at)
"""

CREATE_INDEX_OPP_SCORE = """
    CREATE INDEX IF NOT EXISTS idx_opp_score
    ON opportunities (composite_score DESC)
"""

# ── Phase 4.1: 펀더멘탈 데이터 ──

CREATE_TABLE_FUNDAMENTALS = """
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
"""

CREATE_INDEX_FUNDAMENTALS_TICKER = """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_fundamentals_ticker
    ON fundamentals (ticker)
"""

# ── SSoT (Single Source of Truth) — 자산 관리 중앙 집중화 ──

CREATE_TABLE_HOLDINGS = """
    CREATE TABLE IF NOT EXISTS holdings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        sector TEXT,
        currency TEXT DEFAULT 'KRW',
        qty REAL NOT NULL,
        avg_cost REAL NOT NULL,
        buy_fx_rate REAL,  -- USD 종목용 매입 환율
        acquired_at TEXT,  -- 최초 매수일
        account TEXT,      -- 계좌 구분 (예: 키움, 미래에셋, ISA 등)
        note TEXT,
        updated_at TEXT NOT NULL
    )
"""

CREATE_INDEX_HOLDINGS_TICKER = """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_holdings_ticker
    ON holdings (ticker)
"""

CREATE_TABLE_TRANSACTIONS = """
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        tx_type TEXT NOT NULL,  -- BUY / SELL
        qty REAL NOT NULL,
        price REAL NOT NULL,
        fx_rate REAL,  -- 거래 시점 환율
        fee REAL DEFAULT 0,
        note TEXT,
        executed_at TEXT NOT NULL
    )
"""

CREATE_INDEX_TRANSACTIONS_TICKER_DATE = """
    CREATE INDEX IF NOT EXISTS idx_transactions_ticker_date
    ON transactions (ticker, executed_at)
"""

CREATE_TABLE_EXTRA_ASSETS = """
    CREATE TABLE IF NOT EXISTS extra_assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        asset_type TEXT NOT NULL,  -- 부동산 / 적금 / 청약 / 연금 / 보험 / 기타
        current_value_krw REAL NOT NULL,
        monthly_deposit_krw REAL DEFAULT 0,
        is_fixed INTEGER DEFAULT 0,  -- 1: 고정자산 (전세 등)
        maturity_date TEXT,  -- 만기일
        note TEXT,
        updated_at TEXT NOT NULL
    )
"""

CREATE_INDEX_EXTRA_ASSETS_NAME = """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_extra_assets_name
    ON extra_assets (name)
"""

CREATE_TABLE_TOTAL_WEALTH_HISTORY = """
    CREATE TABLE IF NOT EXISTS total_wealth_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL UNIQUE,
        investment_value_krw REAL,  -- 투자 포트폴리오 평가
        extra_assets_krw REAL,  -- 비금융 자산 총계
        total_wealth_krw REAL,  -- 합계
        investment_pnl_krw REAL,
        investment_pnl_pct REAL,
        fx_rate REAL,
        note TEXT
    )
"""

CREATE_INDEX_TOTAL_WEALTH_DATE = """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_total_wealth_date
    ON total_wealth_history (date)
"""

# ── 인덱스 — 원시 테이블 조회 성능 최적화 ──

CREATE_INDEX_PRICES_TICKER_TS = (
    "CREATE INDEX IF NOT EXISTS idx_prices_ticker_ts ON prices (ticker, timestamp)"
)
CREATE_INDEX_MACRO_INDICATOR_TS = (
    "CREATE INDEX IF NOT EXISTS idx_macro_indicator_ts ON macro (indicator, timestamp)"
)
CREATE_INDEX_ALERTS_TRIGGERED = (
    "CREATE INDEX IF NOT EXISTS idx_alerts_triggered ON alerts (triggered_at)"
)
CREATE_INDEX_NEWS_TITLE_SOURCE = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_news_title_source ON news (title, source)"
)

# ── 인덱스 — 집계 테이블 (유니크 — UPSERT 지원) ──

CREATE_INDEX_PRICES_DAILY_TICKER_DATE = "CREATE UNIQUE INDEX IF NOT EXISTS idx_prices_daily_ticker_date ON prices_daily (ticker, date)"
CREATE_INDEX_MACRO_DAILY_INDICATOR_DATE = "CREATE UNIQUE INDEX IF NOT EXISTS idx_macro_daily_indicator_date ON macro_daily (indicator, date)"

# ── 인덱스 — 기록 테이블 (일별 1행) ──

CREATE_INDEX_PORTFOLIO_HISTORY_DATE = "CREATE UNIQUE INDEX IF NOT EXISTS idx_portfolio_history_date ON portfolio_history (date)"

# ── 마이그레이션: 기존 테이블에 추가된 컬럼 목록 ──
# (table_name, column_name, column_def) 튜플 리스트
MIGRATION_COLUMNS = [
    ("prices", "data_source", "TEXT"),
    ("news", "sentiment", "REAL"),
    # F22: 6팩터 서브 점수 컬럼
    ("opportunities", "score_value", "REAL"),
    ("opportunities", "score_quality", "REAL"),
    ("opportunities", "score_growth", "REAL"),
    # F23: 수급 데이터 컬럼
    ("fundamentals", "foreign_net", "INTEGER"),
    ("fundamentals", "inst_net", "INTEGER"),
    # holdings 계좌 구분 컬럼
    ("holdings", "account", "TEXT"),
]

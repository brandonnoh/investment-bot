"""Phase 4 DB 스키마 + ticker_master 모듈 테스트"""

import json
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture():
    """샘플 종목 사전 fixture 로드"""
    with open(FIXTURES / "sample_ticker_master.json") as f:
        return json.load(f)


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
        "id",
        "ticker",
        "name",
        "discovered_at",
        "discovered_via",
        "source",
        "composite_score",
        "score_return",
        "score_rsi",
        "score_sentiment",
        "score_macro",
        "price_at_discovery",
        "outcome_1w",
        "outcome_1m",
        "status",
    }
    assert expected.issubset(columns)


def test_ticker_master_crud(db_conn):
    """ticker_master 기본 CRUD"""
    db_conn.execute(
        "INSERT INTO ticker_master (ticker, name, market, sector, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("005930.KS", "삼성전자", "KOSPI", "반도체", "2026-03-26"),
    )
    db_conn.commit()
    row = db_conn.execute(
        "SELECT name FROM ticker_master WHERE ticker='005930.KS'"
    ).fetchone()
    assert row[0] == "삼성전자"


def test_agent_keywords_crud(db_conn):
    """agent_keywords 기본 CRUD"""
    db_conn.execute(
        "INSERT INTO agent_keywords (keyword, category, priority, generated_at) VALUES (?, ?, ?, ?)",
        ("방산 수주", "sector", 1, "2026-03-26T05:30:00+09:00"),
    )
    db_conn.commit()
    row = db_conn.execute(
        "SELECT keyword FROM agent_keywords WHERE category='sector'"
    ).fetchone()
    assert row[0] == "방산 수주"


def test_opportunities_crud(db_conn):
    """opportunities 기본 CRUD"""
    db_conn.execute(
        """INSERT INTO opportunities (ticker, name, discovered_at, discovered_via, source,
           composite_score, score_return, score_rsi, score_sentiment, score_macro, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "012450.KS",
            "한화에어로스페이스",
            "2026-03-26T06:00:00+09:00",
            "방산 수주",
            "brave",
            0.82,
            0.8,
            0.7,
            0.9,
            0.85,
            "discovered",
        ),
    )
    db_conn.commit()
    row = db_conn.execute(
        "SELECT composite_score FROM opportunities WHERE ticker='012450.KS'"
    ).fetchone()
    assert row[0] == 0.82


# ── ticker_master 모듈 테스트 ──


def test_exact_match():
    """정확한 종목명 매칭"""
    from data.ticker_master import find_tickers

    master = _load_fixture()
    results = find_tickers("삼성전자", master)
    assert len(results) >= 1
    assert results[0]["ticker"] == "005930.KS"


def test_fuzzy_match():
    """부분 종목명 퍼지 매칭"""
    from data.ticker_master import find_tickers

    master = _load_fixture()
    results = find_tickers("한화에어로", master)
    assert any(r["ticker"] == "012450.KS" for r in results)


def test_alias_match():
    """별칭 매칭 (삼전→삼성전자)"""
    from data.ticker_master import resolve_alias

    assert resolve_alias("삼전") == "삼성전자"
    assert resolve_alias("존재안함") == "존재안함"


def test_no_match():
    """매칭 불가 시 빈 리스트"""
    from data.ticker_master import find_tickers

    master = _load_fixture()
    results = find_tickers("완전히없는종목", master)
    assert results == []


def test_extract_codes_from_text():
    """뉴스 텍스트에서 종목코드 추출"""
    from data.ticker_master import extract_ticker_codes

    text = "한화에어로스페이스(012450)가 수주를 발표했다"
    codes = extract_ticker_codes(text)
    assert "012450" in codes


def test_extract_us_tickers():
    """영문 텍스트에서 미국 티커 추출"""
    from data.ticker_master import extract_us_tickers

    text = "NVDA surged 5% on AI demand, while TSLA dropped"
    tickers = extract_us_tickers(text)
    assert "NVDA" in tickers
    assert "TSLA" in tickers


def test_extract_companies_from_text():
    """텍스트에서 종목명 직접 매칭"""
    from data.ticker_master import extract_companies

    master = _load_fixture()
    text = "삼성전자와 SK하이닉스가 반도체 투자를 확대한다"
    found = extract_companies(text, master)
    tickers = [f["ticker"] for f in found]
    assert "005930.KS" in tickers
    assert "000660.KS" in tickers


def test_save_and_load_master(db_conn):
    """DB에 종목 사전 저장/로드"""
    from data.ticker_master import save_master_to_db, load_master_from_db

    master = _load_fixture()
    save_master_to_db(db_conn, master)
    loaded = load_master_from_db(db_conn)
    assert len(loaded) == len(master)
    loaded_tickers = {item["ticker"] for item in loaded}
    master_tickers = {item["ticker"] for item in master}
    assert loaded_tickers == master_tickers


def test_get_seed_master():
    """시드 종목 사전 생성 (PORTFOLIO + SCREENING_TARGETS)"""
    from data.ticker_master import get_seed_master

    master = get_seed_master()
    assert len(master) > 0
    # PORTFOLIO의 종목이 포함되어야 함
    tickers = [m["ticker"] for m in master]
    assert any(t.endswith(".KS") or t == "TSLA" for t in tickers)

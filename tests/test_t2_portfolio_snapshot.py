"""T2: 포트폴리오 히스토리 자동 저장 테스트"""

import json
import sqlite3
import sys
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

KST = timezone(timedelta(hours=9))

SAMPLE_PORTFOLIO = {
    "updated_at": "2026-04-02T15:40:00+09:00",
    "exchange_rate": 1503.68,
    "total": {
        "invested_krw": 45704937,
        "current_value_krw": 43803383,
        "pnl_krw": -1901554,
        "pnl_pct": -4.16,
        "stock_pnl_krw": -2048612,
        "fx_pnl_krw": 147057,
    },
    "holdings": [
        {"ticker": "005930.KS", "name": "삼성전자", "price": 167200, "qty": 42},
    ],
}


def _make_db() -> sqlite3.Connection:
    """인메모리 DB + portfolio_history 테이블 생성"""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE portfolio_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            total_value_krw REAL,
            total_invested_krw REAL,
            total_pnl_krw REAL,
            total_pnl_pct REAL,
            fx_rate REAL,
            fx_pnl_krw REAL,
            holdings_snapshot TEXT
        )
    """)
    conn.execute(
        "CREATE UNIQUE INDEX idx_portfolio_history_date ON portfolio_history (date)"
    )
    conn.commit()
    return conn


def test_save_snapshot_inserts_row():
    """save_portfolio_snapshot이 DB에 행을 삽입"""
    from reports.closing import save_portfolio_snapshot

    conn = _make_db()
    save_portfolio_snapshot(conn, SAMPLE_PORTFOLIO)

    row = conn.execute(
        "SELECT date, total_value_krw, total_invested_krw, total_pnl_krw, "
        "total_pnl_pct, fx_rate, fx_pnl_krw, holdings_snapshot "
        "FROM portfolio_history"
    ).fetchone()

    assert row is not None
    assert row[1] == 43803383   # total_value_krw
    assert row[2] == 45704937   # total_invested_krw
    assert row[3] == -1901554   # total_pnl_krw
    assert row[4] == -4.16      # total_pnl_pct
    assert row[5] == 1503.68    # fx_rate
    assert row[6] == 147057     # fx_pnl_krw
    conn.close()


def test_save_snapshot_upsert_same_date():
    """같은 날짜로 두 번 저장하면 UPDATE (행 1개 유지)"""
    from reports.closing import save_portfolio_snapshot

    conn = _make_db()
    save_portfolio_snapshot(conn, SAMPLE_PORTFOLIO)

    # 값을 변경해서 다시 저장
    updated = dict(SAMPLE_PORTFOLIO)
    updated["total"] = dict(SAMPLE_PORTFOLIO["total"])
    updated["total"]["current_value_krw"] = 44000000

    save_portfolio_snapshot(conn, updated)

    rows = conn.execute("SELECT total_value_krw FROM portfolio_history").fetchall()
    assert len(rows) == 1, "중복 행이 생성됨"
    assert rows[0][0] == 44000000, "UPDATE가 반영되지 않음"
    conn.close()


def test_save_snapshot_holdings_json():
    """holdings_snapshot이 JSON 문자열로 저장됨"""
    from reports.closing import save_portfolio_snapshot

    conn = _make_db()
    save_portfolio_snapshot(conn, SAMPLE_PORTFOLIO)

    snapshot_str = conn.execute(
        "SELECT holdings_snapshot FROM portfolio_history"
    ).fetchone()[0]

    holdings = json.loads(snapshot_str)
    assert isinstance(holdings, list)
    assert holdings[0]["ticker"] == "005930.KS"
    conn.close()


def test_save_snapshot_prints_value(capsys):
    """저장 후 콘솔에 날짜와 총 자산 출력"""
    from reports.closing import save_portfolio_snapshot

    conn = _make_db()
    save_portfolio_snapshot(conn, SAMPLE_PORTFOLIO)

    captured = capsys.readouterr()
    today = datetime.now(KST).strftime("%Y-%m-%d")
    assert today in captured.out
    assert "4,380" in captured.out or "만원" in captured.out
    conn.close()


def test_run_saves_snapshot(tmp_path):
    """run() 실행 후 portfolio_history에 행이 저장됨"""
    from reports import closing
    from db.init_db import init_schema
    import config

    # 임시 DB 및 출력 디렉토리 설정
    db_path = tmp_path / "history.db"
    orig_db = config.DB_PATH
    orig_out = config.OUTPUT_DIR
    config.DB_PATH = db_path
    config.OUTPUT_DIR = tmp_path
    closing.DB_PATH = db_path
    closing.OUTPUT_DIR = tmp_path

    # DB 초기화
    conn = sqlite3.connect(str(db_path))
    init_schema(conn)
    conn.close()

    # portfolio_summary.json 생성
    portfolio_path = tmp_path / "portfolio_summary.json"
    with open(portfolio_path, "w", encoding="utf-8") as f:
        json.dump(SAMPLE_PORTFOLIO, f, ensure_ascii=False)

    # run() 실행
    closing.run()

    # DB에서 확인
    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT * FROM portfolio_history").fetchone()
    conn.close()

    assert row is not None, "portfolio_history에 행이 없음"

    # 복구
    config.DB_PATH = orig_db
    config.OUTPUT_DIR = orig_out
    closing.DB_PATH = orig_db
    closing.OUTPUT_DIR = orig_out


def test_run_graceful_when_no_portfolio_json(tmp_path):
    """portfolio_summary.json 없어도 run()이 오류 없이 완료됨"""
    from reports import closing
    from db.init_db import init_schema
    import config

    db_path = tmp_path / "history.db"
    orig_db = config.DB_PATH
    orig_out = config.OUTPUT_DIR
    config.DB_PATH = db_path
    config.OUTPUT_DIR = tmp_path
    closing.DB_PATH = db_path
    closing.OUTPUT_DIR = tmp_path

    conn = sqlite3.connect(str(db_path))
    init_schema(conn)
    conn.close()

    # portfolio_summary.json 없이 run() 실행
    closing.run()  # 예외 없이 완료돼야 함

    # 복구
    config.DB_PATH = orig_db
    config.OUTPUT_DIR = orig_out
    closing.DB_PATH = orig_db
    closing.OUTPUT_DIR = orig_out

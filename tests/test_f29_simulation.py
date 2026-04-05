"""F29 — 포트폴리오 시뮬레이션: 가상 매매 손익 계산"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from db.init_db import init_schema


@pytest.fixture
def db_with_prices():
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    rows = [
        ("2026-03-01", "TSLA", 300.0),
        ("2026-03-08", "TSLA", 330.0),
        ("2026-03-01", "XOP",  170.0),
        ("2026-03-08", "XOP",  185.0),
        ("2026-03-01", "005930.KS", 55000.0),
        ("2026-03-08", "005930.KS", 51000.0),
    ]
    conn.executemany(
        "INSERT INTO prices_daily (date, ticker, close, open, high, low, volume, change_pct) VALUES (?,?,?,?,?,?,?,0)",
        [(r[0], r[1], r[2], r[2], r[2], r[2], 0) for r in rows]
    )
    conn.commit()
    return conn


def test_simulate_single_buy(db_with_prices):
    from analysis.simulation import simulate_trade
    result = simulate_trade(db_with_prices, "TSLA", buy_date="2026-03-01", sell_date="2026-03-08", qty=1, buy_price=300.0)
    assert result["pnl_pct"] == pytest.approx(10.0, abs=0.1)
    assert result["pnl"] == pytest.approx(30.0, abs=0.1)
    assert result["error"] is None


def test_simulate_loss(db_with_prices):
    from analysis.simulation import simulate_trade
    result = simulate_trade(db_with_prices, "005930.KS", buy_date="2026-03-01", sell_date="2026-03-08", qty=10, buy_price=55000.0)
    assert result["pnl_pct"] < 0
    assert result["error"] is None


def test_simulate_missing_price(db_with_prices):
    from analysis.simulation import simulate_trade
    result = simulate_trade(db_with_prices, "UNKNOWN", buy_date="2026-03-01", sell_date="2026-03-08", qty=1, buy_price=100.0)
    assert result["error"] is not None


def test_simulate_batch(db_with_prices):
    from analysis.simulation import simulate_batch
    trades = [
        {"ticker": "TSLA", "buy_date": "2026-03-01", "sell_date": "2026-03-08", "qty": 1, "buy_price": 300.0},
        {"ticker": "XOP",  "buy_date": "2026-03-01", "sell_date": "2026-03-08", "qty": 1, "buy_price": 170.0},
    ]
    results = simulate_batch(db_with_prices, trades)
    assert len(results) == 2
    assert all("pnl_pct" in r for r in results)


def test_simulate_uses_db_price_if_no_buy_price(db_with_prices):
    from analysis.simulation import simulate_trade
    result = simulate_trade(db_with_prices, "TSLA", buy_date="2026-03-01", sell_date="2026-03-08", qty=1)
    assert result["error"] is None
    assert result["buy_price"] == pytest.approx(300.0)


def test_run_generates_output(tmp_path):
    from analysis.simulation import run
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    run(conn=conn, output_dir=tmp_path)
    out = tmp_path / "simulation_report.json"
    assert out.exists()
    data = json.loads(out.read_text())
    assert "simulations" in data
    assert "summary" in data
    assert "generated_at" in data


def test_run_summary_fields(tmp_path):
    from analysis.simulation import run
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    result = run(conn=conn, output_dir=tmp_path)
    assert "total" in result["summary"]
    assert "avg_return_pct" in result["summary"]

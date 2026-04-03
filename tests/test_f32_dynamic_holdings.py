"""F32 — 동적 종목 관리: 추가/제거 제안"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from db.init_db import init_schema

KST = timezone(timedelta(hours=9))


@pytest.fixture
def db_with_opportunities():
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    today = datetime.now(KST).date()
    # 3일 연속 고점수 종목
    for i in range(3):
        date = (today - timedelta(days=i)).isoformat()
        conn.execute(
            """INSERT INTO opportunities
               (ticker, name, discovered_at, composite_score, status)
               VALUES (?, ?, ?, ?, 'new')""",
            ("NVDA", "엔비디아", date, 0.72)
        )
    # 1일만 있는 종목
    conn.execute(
        """INSERT INTO opportunities (ticker, name, discovered_at, composite_score, status)
           VALUES (?, ?, ?, ?, 'new')""",
        ("AMZN", "아마존", today.isoformat(), 0.70)
    )
    conn.commit()
    return conn


def test_identify_add_candidates(db_with_opportunities):
    from analysis.dynamic_holdings import identify_add_candidates
    candidates = identify_add_candidates(db_with_opportunities, min_score=0.65, min_days=3)
    tickers = [c["ticker"] for c in candidates]
    assert "NVDA" in tickers    # 3일 연속 0.72
    assert "AMZN" not in tickers  # 1일만


def test_identify_remove_candidates():
    from analysis.dynamic_holdings import identify_remove_candidates
    holdings = [
        {"ticker": "005930.KS", "name": "삼성전자", "pnl_pct": -20.0},
        {"ticker": "TSLA", "name": "테슬라", "pnl_pct": 5.0},
    ]
    correction = {"weak_factors": ["catalyst", "growth"]}
    candidates = identify_remove_candidates(holdings, correction, stop_loss_pct=-15.0)
    tickers = [c["ticker"] for c in candidates]
    assert "005930.KS" in tickers
    assert "TSLA" not in tickers


def test_proposal_has_required_fields(db_with_opportunities):
    from analysis.dynamic_holdings import identify_add_candidates
    candidates = identify_add_candidates(db_with_opportunities)
    for c in candidates:
        assert "ticker" in c
        assert "name" in c
        assert "avg_score" in c
        assert "days_appeared" in c
        assert "reason" in c


def test_run_generates_output(tmp_path, db_with_opportunities):
    from analysis.dynamic_holdings import run
    portfolio = {
        "holdings": [{"ticker": "005930.KS", "name": "삼성전자", "pnl_pct": -22.0}]
    }
    port_path = tmp_path / "portfolio_summary.json"
    port_path.write_text(json.dumps(portfolio))
    run(conn=db_with_opportunities, portfolio_path=port_path, output_dir=tmp_path)
    out = tmp_path / "holdings_proposal.json"
    assert out.exists()
    data = json.loads(out.read_text())
    assert "add_candidates" in data
    assert "remove_candidates" in data

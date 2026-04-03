"""F31 — 능동적 알림: Marcus 판단 기반 액션 알림 생성"""
from __future__ import annotations

import json


SAMPLE_PORTFOLIO = {
    "holdings": [
        {"ticker": "XOP", "name": "SPDR S&P Oil", "pnl_pct": 25.0, "sector": "에너지"},
        {"ticker": "005930.KS", "name": "삼성전자", "pnl_pct": -18.0, "sector": "반도체"},
        {"ticker": "GC=F", "name": "금 현물", "pnl_pct": 12.0, "sector": "원자재"},
    ],
    "total": {"pnl_pct": 3.5}
}

SAMPLE_REGIME = {"regime": "RISK_OFF", "confidence": 0.8, "panic_signal": False}
SAMPLE_CORRECTION = {
    "weak_factors": ["catalyst", "growth"],
    "strong_factors": ["value", "macro"],
    "summary": "지난 달 적중률 35% (부진). catalyst 팩터 신중히."
}


def test_check_take_profit(tmp_path):
    from analysis.proactive_alerts import check_portfolio_actions
    alerts = check_portfolio_actions(SAMPLE_PORTFOLIO, SAMPLE_REGIME, SAMPLE_CORRECTION)
    # XOP +25%는 익절 후보
    tickers = [a["ticker"] for a in alerts]
    assert "XOP" in tickers


def test_check_stop_loss(tmp_path):
    from analysis.proactive_alerts import check_portfolio_actions
    alerts = check_portfolio_actions(SAMPLE_PORTFOLIO, SAMPLE_REGIME, SAMPLE_CORRECTION)
    # 삼성전자 -18%는 손절 검토
    tickers = [a["ticker"] for a in alerts]
    assert "005930.KS" in tickers


def test_alert_has_required_fields(tmp_path):
    from analysis.proactive_alerts import check_portfolio_actions
    alerts = check_portfolio_actions(SAMPLE_PORTFOLIO, SAMPLE_REGIME, SAMPLE_CORRECTION)
    for alert in alerts:
        assert "ticker" in alert
        assert "action" in alert
        assert "reason" in alert
        assert "urgency" in alert  # HIGH / MEDIUM / LOW


def test_panic_regime_increases_urgency(tmp_path):
    from analysis.proactive_alerts import check_portfolio_actions
    panic_regime = {"regime": "RISK_OFF", "confidence": 0.9, "panic_signal": True}
    alerts = check_portfolio_actions(SAMPLE_PORTFOLIO, panic_regime, {})
    high_urgency = [a for a in alerts if a["urgency"] == "HIGH"]
    assert len(high_urgency) >= 1


def test_run_generates_output(tmp_path):
    from analysis.proactive_alerts import run
    port_path = tmp_path / "portfolio_summary.json"
    port_path.write_text(json.dumps(SAMPLE_PORTFOLIO))
    regime_path = tmp_path / "regime.json"
    regime_path.write_text(json.dumps(SAMPLE_REGIME))
    run(portfolio_path=port_path, regime_path=regime_path, output_dir=tmp_path)
    out = tmp_path / "proactive_alerts.json"
    assert out.exists()
    data = json.loads(out.read_text())
    assert "alerts" in data


def test_no_alerts_when_stable(tmp_path):
    """손익 정상 범위면 알림 없음."""
    from analysis.proactive_alerts import check_portfolio_actions
    stable_portfolio = {
        "holdings": [
            {"ticker": "TSLA", "name": "테슬라", "pnl_pct": 3.0, "sector": "전기차"},
        ],
        "total": {"pnl_pct": 3.0}
    }
    stable_regime = {"regime": "RISK_ON", "confidence": 0.6, "panic_signal": False}
    alerts = check_portfolio_actions(stable_portfolio, stable_regime, {})
    assert len(alerts) == 0

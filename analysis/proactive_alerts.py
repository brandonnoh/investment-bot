#!/usr/bin/env python3
"""
능동적 알림 — Marcus 판단 기반 포트폴리오 액션 알림
익절/손절 임계값 초과 + regime 위험 시 알림 생성
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output" / "intel"

TAKE_PROFIT_PCT = 20.0       # +20% 이상: 익절 검토
STOP_LOSS_PCT = -15.0         # -15% 이하: 손절 검토
PANIC_STOP_LOSS_PCT = -8.0   # PANIC 국면: -8%도 손절 검토


def check_portfolio_actions(
    portfolio: dict, regime: dict, correction: dict
) -> list[dict]:
    """포트폴리오 + 국면 + 교정 노트 기반 액션 알림 생성.

    Returns:
        [{ticker, name, action, reason, urgency, pnl_pct}] 리스트
    """
    alerts = []
    is_panic = regime.get("panic_signal", False)
    is_risk_off = regime.get("regime") in ("RISK_OFF", "STAGFLATION")
    regime_confidence = regime.get("confidence", 0.5)
    stop_loss_threshold = PANIC_STOP_LOSS_PCT if is_panic else STOP_LOSS_PCT
    weak_factors = set(correction.get("weak_factors", []))

    for holding in portfolio.get("holdings", []):
        ticker = holding.get("ticker", "")
        name = holding.get("name", ticker)
        pnl_pct = holding.get("pnl_pct", 0)

        if pnl_pct >= TAKE_PROFIT_PCT:
            urgency = "HIGH" if (is_risk_off and regime_confidence > 0.7) else "MEDIUM"
            reason_parts = [f"수익률 {pnl_pct:.1f}%로 익절 기준 초과."]
            if is_risk_off:
                reason_parts.append(f"현재 {regime.get('regime')} 국면 — 이익 실현 권고.")
            alerts.append({
                "ticker": ticker, "name": name,
                "action": "TAKE_PROFIT", "pnl_pct": pnl_pct,
                "reason": " ".join(reason_parts), "urgency": urgency,
            })

        elif pnl_pct <= stop_loss_threshold:
            urgency = "HIGH" if is_panic else "MEDIUM"
            reason_parts = [f"수익률 {pnl_pct:.1f}%로 손절 기준 이하."]
            if is_panic:
                reason_parts.append("패닉 국면 — 손실 제한 긴급.")
            if "catalyst" in weak_factors:
                reason_parts.append("촉매 팩터 신뢰도 낮음.")
            alerts.append({
                "ticker": ticker, "name": name,
                "action": "STOP_LOSS", "pnl_pct": pnl_pct,
                "reason": " ".join(reason_parts), "urgency": urgency,
            })

    return alerts


def run(
    portfolio_path: Path | None = None,
    regime_path: Path | None = None,
    correction_path: Path | None = None,
    output_dir: Path | None = None,
) -> dict:
    """능동적 알림 파이프라인."""
    out_dir = Path(output_dir) if output_dir else OUTPUT_DIR
    port_path = portfolio_path or OUTPUT_DIR / "portfolio_summary.json"
    reg_path = regime_path or OUTPUT_DIR / "regime.json"
    corr_path = correction_path or OUTPUT_DIR / "correction_notes.json"

    portfolio = json.loads(port_path.read_text()) if port_path.exists() else {}
    regime = json.loads(reg_path.read_text()) if reg_path.exists() else {}
    correction = json.loads(corr_path.read_text()) if corr_path.exists() else {}

    alerts = check_portfolio_actions(portfolio, regime, correction)

    report = {
        "generated_at": datetime.now(KST).isoformat(),
        "alerts": alerts,
        "count": len(alerts),
    }
    out_path = out_dir / "proactive_alerts.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    logger.info(f"능동적 알림 {len(alerts)}건 생성")
    return report

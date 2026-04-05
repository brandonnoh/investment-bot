#!/usr/bin/env python3
"""
동적 종목 관리 — 추가/제거 제안 생성
opportunities DB + 성과 + 교정 노트 기반으로 포트폴리오 변경 제안
"""
from __future__ import annotations

import json
import logging
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output" / "intel"

DEFAULT_MIN_SCORE = 0.65
DEFAULT_MIN_DAYS = 3
DEFAULT_STOP_LOSS_PCT = -15.0


def identify_add_candidates(
    conn: sqlite3.Connection,
    min_score: float = DEFAULT_MIN_SCORE,
    min_days: int = DEFAULT_MIN_DAYS,
) -> list[dict]:
    """opportunities DB에서 N일 이상 연속 고점수 종목 추출."""
    rows = conn.execute(
        """SELECT ticker, name,
                  COUNT(DISTINCT date(discovered_at)) AS days,
                  AVG(composite_score) AS avg_score,
                  MAX(composite_score) AS max_score
           FROM opportunities
           WHERE composite_score >= ?
             AND discovered_at >= date('now', '-14 days')
           GROUP BY ticker
           HAVING days >= ?
           ORDER BY avg_score DESC""",
        (min_score, min_days),
    ).fetchall()

    return [
        {
            "ticker": row[0],
            "name": row[1],
            "days_appeared": row[2],
            "avg_score": round(row[3], 4),
            "max_score": round(row[4], 4),
            "reason": f"{row[2]}일 연속 발굴, 평균 복합점수 {row[3]:.2f}",
            "action": "ADD_CANDIDATE",
        }
        for row in rows
    ]


def identify_remove_candidates(
    holdings: list[dict],
    correction: dict,
    stop_loss_pct: float = DEFAULT_STOP_LOSS_PCT,
) -> list[dict]:
    """보유 종목 중 손실 지속 + 약한 팩터 신호 종목 추출."""
    weak_factors = set(correction.get("weak_factors", []))
    candidates = []

    for h in holdings:
        pnl_pct = h.get("pnl_pct", 0)
        ticker = h.get("ticker", "")
        name = h.get("name", ticker)

        if pnl_pct <= stop_loss_pct:
            reason_parts = [f"수익률 {pnl_pct:.1f}% — 손절 기준 초과."]
            if weak_factors:
                reason_parts.append(f"약한 팩터({', '.join(weak_factors)}) 신호로 회복 불확실.")
            candidates.append({
                "ticker": ticker, "name": name,
                "pnl_pct": pnl_pct,
                "reason": " ".join(reason_parts),
                "action": "REMOVE_CANDIDATE",
            })

    return candidates


def run(
    conn: sqlite3.Connection | None = None,
    portfolio_path: Path | None = None,
    correction_path: Path | None = None,
    output_dir: Path | None = None,
) -> dict:
    """동적 종목 관리 파이프라인."""
    out_dir = Path(output_dir) if output_dir else OUTPUT_DIR
    port_path = portfolio_path or OUTPUT_DIR / "portfolio_summary.json"
    corr_path = correction_path or OUTPUT_DIR / "correction_notes.json"

    own_conn = False
    if conn is None:
        conn = sqlite3.connect(str(PROJECT_ROOT / "db" / "history.db"))
        own_conn = True

    try:
        portfolio = json.loads(port_path.read_text()) if port_path.exists() else {}
        correction = json.loads(corr_path.read_text()) if corr_path.exists() else {}

        holdings = portfolio.get("holdings", [])
        add_candidates = identify_add_candidates(conn)
        remove_candidates = identify_remove_candidates(holdings, correction)

        proposal = {
            "generated_at": datetime.now(KST).isoformat(),
            "add_candidates": add_candidates,
            "remove_candidates": remove_candidates,
            "summary": {
                "add_count": len(add_candidates),
                "remove_count": len(remove_candidates),
            },
        }
        out_path = out_dir / "holdings_proposal.json"
        out_path.write_text(json.dumps(proposal, ensure_ascii=False, indent=2))
        logger.info(
            "종목 제안: 추가 %d개, 제거 %d개",
            len(add_candidates),
            len(remove_candidates),
        )
        return proposal
    finally:
        if own_conn:
            conn.close()

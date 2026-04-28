#!/usr/bin/env python3
"""
investment_assets 테이블 시드 스크립트
web-next/src/data/investment-assets.json → DB 동기화 (UPSERT)
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from db.connection import get_db_conn

KST = timezone(timedelta(hours=9))
_ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = next(
    p
    for p in [
        _ROOT / "web-next" / "src" / "data" / "investment-assets.json",
        _ROOT / "db" / "investment-assets.json",
    ]
    if p.exists()
)


def seed():
    assets = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    now = datetime.now(KST).isoformat()
    conn = get_db_conn()

    upsert_sql = """
        INSERT INTO investment_assets (
            id, name, category, min_capital, min_capital_leveraged,
            expected_return_min, expected_return_max, risk_level, liquidity,
            leverage_available, leverage_ratio, leverage_type,
            tax_benefit, regulation_note, status, upcoming_date,
            beginner_friendly, description, caution, updated_at
        ) VALUES (
            :id, :name, :category, :min_capital, :min_capital_leveraged,
            :expected_return_min, :expected_return_max, :risk_level, :liquidity,
            :leverage_available, :leverage_ratio, :leverage_type,
            :tax_benefit, :regulation_note, :status, :upcoming_date,
            :beginner_friendly, :description, :caution, :updated_at
        )
        ON CONFLICT(id) DO UPDATE SET
            name                  = excluded.name,
            category              = excluded.category,
            min_capital           = excluded.min_capital,
            min_capital_leveraged = excluded.min_capital_leveraged,
            expected_return_min   = excluded.expected_return_min,
            expected_return_max   = excluded.expected_return_max,
            risk_level            = excluded.risk_level,
            liquidity             = excluded.liquidity,
            leverage_available    = excluded.leverage_available,
            leverage_ratio        = excluded.leverage_ratio,
            leverage_type         = excluded.leverage_type,
            tax_benefit           = excluded.tax_benefit,
            regulation_note       = excluded.regulation_note,
            status                = excluded.status,
            upcoming_date         = excluded.upcoming_date,
            beginner_friendly     = excluded.beginner_friendly,
            description           = excluded.description,
            caution               = excluded.caution,
            updated_at            = excluded.updated_at
    """

    rows = [
        {
            "id": a["id"],
            "name": a["name"],
            "category": a["category"],
            "min_capital": a.get("min_capital"),
            "min_capital_leveraged": a.get("min_capital_leveraged"),
            "expected_return_min": a.get("expected_return_min"),
            "expected_return_max": a.get("expected_return_max"),
            "risk_level": a.get("risk_level"),
            "liquidity": a.get("liquidity"),
            "leverage_available": 1 if a.get("leverage_available") else 0,
            "leverage_ratio": a.get("leverage_ratio"),
            "leverage_type": a.get("leverage_type"),
            "tax_benefit": a.get("tax_benefit"),
            "regulation_note": a.get("regulation_note"),
            "status": a.get("status", "available"),
            "upcoming_date": a.get("upcoming_date"),
            "beginner_friendly": 1 if a.get("beginner_friendly") else 0,
            "description": a.get("description"),
            "caution": a.get("caution"),
            "updated_at": now,
        }
        for a in assets
    ]

    conn.executemany(upsert_sql, rows)
    conn.commit()
    print(f"✅ investment_assets 시드 완료: {len(rows)}개")


if __name__ == "__main__":
    seed()

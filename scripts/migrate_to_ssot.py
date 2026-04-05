#!/usr/bin/env python3
"""
SSoT 마이그레이션 — config.py/JSON → DB 중앙 집중화
1. config.py PORTFOLIO → holdings 테이블
2. portfolio_extra.json → extra_assets 테이블
3. 기존 portfolio_history → total_wealth_history 통합
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import PORTFOLIO_LEGACY as PORTFOLIO, DB_PATH
from db.init_db import init_schema

KST = timezone(timedelta(hours=9))
PROJECT_ROOT = Path(__file__).parent.parent
EXTRA_JSON = PROJECT_ROOT / "output" / "intel" / "portfolio_extra.json"


def migrate_holdings(conn):
    """config.py PORTFOLIO → holdings 테이블"""
    cursor = conn.cursor()
    now = datetime.now(KST).isoformat()
    
    migrated = 0
    for info in PORTFOLIO:
        ticker = info.get("ticker", "")
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO holdings
                (ticker, name, sector, currency, qty, avg_cost, buy_fx_rate, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker,
                info.get("name", ticker),
                info.get("sector", ""),
                info.get("currency", "KRW"),
                info.get("qty", 0),
                info.get("avg_cost", 0),
                info.get("buy_fx_rate"),
                now,
            ))
            migrated += 1
        except Exception as e:
            print(f"  ❌ {ticker}: {e}")
    
    conn.commit()
    print(f"✅ holdings 마이그레이션 완료: {migrated}건")
    return migrated


def migrate_extra_assets(conn):
    """portfolio_extra.json → extra_assets 테이블"""
    cursor = conn.cursor()
    now = datetime.now(KST).isoformat()
    
    if not EXTRA_JSON.exists():
        print("⚠️ portfolio_extra.json 없음 — 건너뜀")
        return 0
    
    with open(EXTRA_JSON) as f:
        data = json.load(f)
    
    migrated = 0
    for asset in data.get("assets", []):
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO extra_assets
                (name, asset_type, current_value_krw, monthly_deposit_krw, is_fixed, note, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                asset.get("name", ""),
                asset.get("type", "기타"),
                asset.get("current_value_krw", 0),
                asset.get("monthly_deposit_krw", 0),
                1 if asset.get("fixed") else 0,
                asset.get("note", ""),
                now,
            ))
            migrated += 1
        except Exception as e:
            print(f"  ❌ {asset.get('name')}: {e}")
    
    conn.commit()
    print(f"✅ extra_assets 마이그레이션 완료: {migrated}건")
    return migrated


def sync_total_wealth_history(conn):
    """기존 portfolio_history + extra_assets → total_wealth_history"""
    cursor = conn.cursor()
    
    # extra_assets 총합 계산
    cursor.execute("SELECT SUM(current_value_krw) FROM extra_assets")
    extra_total = cursor.fetchone()[0] or 0
    
    # portfolio_history 데이터를 total_wealth_history로 복사
    cursor.execute("""
        SELECT date, total_value_krw, total_pnl_krw, total_pnl_pct, fx_rate
        FROM portfolio_history
        ORDER BY date
    """)
    rows = cursor.fetchall()
    
    migrated = 0
    for row in rows:
        date, inv_value, pnl_krw, pnl_pct, fx_rate = row
        total = (inv_value or 0) + extra_total
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO total_wealth_history
                (date, investment_value_krw, extra_assets_krw, total_wealth_krw,
                 investment_pnl_krw, investment_pnl_pct, fx_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (date, inv_value, extra_total, total, pnl_krw, pnl_pct, fx_rate))
            migrated += 1
        except Exception as e:
            print(f"  ❌ {date}: {e}")
    
    conn.commit()
    print(f"✅ total_wealth_history 동기화 완료: {migrated}건")
    return migrated


def run():
    """전체 마이그레이션 실행"""
    print("=" * 60)
    print("🚀 SSoT 마이그레이션 시작")
    print("=" * 60)
    
    conn = sqlite3.connect(str(DB_PATH))
    
    # 스키마 업데이트 (새 테이블 생성)
    init_schema(conn)
    print("✅ DB 스키마 업데이트 완료")
    
    # 마이그레이션
    migrate_holdings(conn)
    migrate_extra_assets(conn)
    sync_total_wealth_history(conn)
    
    # 검증
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM holdings")
    h_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM extra_assets")
    e_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM total_wealth_history")
    t_count = cursor.fetchone()[0]
    
    conn.close()
    
    print()
    print("=" * 60)
    print("✅ SSoT 마이그레이션 완료")
    print(f"   - holdings: {h_count}건")
    print(f"   - extra_assets: {e_count}건")
    print(f"   - total_wealth_history: {t_count}건")
    print("=" * 60)


if __name__ == "__main__":
    run()

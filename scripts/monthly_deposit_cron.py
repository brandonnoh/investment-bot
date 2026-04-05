#!/usr/bin/env python3
"""
월말 자동 적립 크론잡
매월 마지막 날 23:59에 monthly_deposit_krw > 0인 자산에 적립금 자동 추가
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from db.ssot import apply_monthly_deposits, get_extra_assets

KST = timezone(timedelta(hours=9))


def run():
    """월 적립금 적용"""
    print(f"🗓️ 월말 자동 적립 실행 — {datetime.now(KST).isoformat()}")
    
    # 적용 전 상태
    before = get_extra_assets()
    print("\n📊 적용 전:")
    for a in before:
        if a["monthly_deposit_krw"] > 0:
            print(f"  {a['name']}: {a['current_value_krw']:,.0f}원 (월 +{a['monthly_deposit_krw']:,.0f}원)")
    
    # 적립 적용
    updated = apply_monthly_deposits()
    print(f"\n✅ {updated}건 자산에 월 적립 적용")
    
    # 적용 후 상태
    after = get_extra_assets()
    print("\n📊 적용 후:")
    for a in after:
        if a["monthly_deposit_krw"] > 0:
            print(f"  {a['name']}: {a['current_value_krw']:,.0f}원")
    
    return updated


if __name__ == "__main__":
    run()

#!/usr/bin/env python3
"""
투자 인텔리전스 봇 — Phase 1 파이프라인 실행기
전체 수집 → 분석 → 리포트 생성 순서로 실행
"""
import sys
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db.init_db import init_db
from data.fetch_prices import run as fetch_prices
from data.fetch_macro import run as fetch_macro
from analysis.alerts import run as check_alerts
from reports.daily import run as generate_daily


def main():
    """Phase 1 전체 파이프라인 실행"""
    print("=" * 60)
    print("🏦 투자 인텔리전스 봇 — Phase 1 파이프라인")
    print("=" * 60)

    # 1. DB 초기화
    init_db()

    # 2. 데이터 수집
    fetch_prices()
    fetch_macro()

    # 3. 알림 감지
    check_alerts()

    # 4. 일일 리포트 생성
    generate_daily()

    print("=" * 60)
    print("✅ 파이프라인 완료")
    print("=" * 60)


if __name__ == "__main__":
    main()

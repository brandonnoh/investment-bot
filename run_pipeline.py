#!/usr/bin/env python3
"""
투자 인텔리전스 봇 — 파이프라인 실행기
Phase 1: 수집 → 분석 → 일일 리포트
Phase 2: 뉴스 수집 → 스크리너 → 포트폴리오 분석 → 주간 리포트
"""

import sys
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db.init_db import init_db
from data.fetch_prices import run as fetch_prices
from data.fetch_macro import run as fetch_macro
from data.fetch_news import run as fetch_news
from db.aggregate import run as aggregate_daily
from db.maintenance import run as maintain_db
from analysis.price_analysis import run as analyze_prices
from analysis.alerts import run as check_alerts
from analysis.screener import run as run_screener
from analysis.portfolio import run as analyze_portfolio
from reports.daily import run as generate_daily
from reports.weekly import run as generate_weekly


def main():
    """전체 파이프라인 실행"""
    weekly_mode = "--weekly" in sys.argv

    print("=" * 60)
    if weekly_mode:
        print("🏦 투자 인텔리전스 봇 — 전체 파이프라인 (주간 포함)")
    else:
        print("🏦 투자 인텔리전스 봇 — 일일 파이프라인")
    print("=" * 60)

    # 1. DB 초기화
    init_db()

    # 2. 데이터 수집
    fetch_prices()
    fetch_macro()
    fetch_news()

    # 3. 일봉 집계 (수집 후, 분석 전)
    aggregate_daily()

    # 3.5. DB 유지보수 (보존 정책 적용 + VACUUM)
    maintain_db()

    # 4. 분석
    analyze_prices()
    check_alerts()
    run_screener()
    analyze_portfolio()

    # 4. 일일 리포트 생성
    generate_daily()

    # 5. 주간 리포트 (--weekly 플래그 시)
    if weekly_mode:
        generate_weekly()

    print("=" * 60)
    print("✅ 파이프라인 완료")
    print("=" * 60)


if __name__ == "__main__":
    main()

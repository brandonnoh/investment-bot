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
from utils.schema import validate_all_outputs  # noqa: E402
from utils.engine_status import (  # noqa: E402
    EngineStatus,
    record_module_status,
    run as save_engine_status,
)


def main():
    """전체 파이프라인 실행"""
    weekly_mode = "--weekly" in sys.argv
    engine = EngineStatus()

    print("=" * 60)
    if weekly_mode:
        print("🏦 투자 인텔리전스 봇 — 전체 파이프라인 (주간 포함)")
    else:
        print("🏦 투자 인텔리전스 봇 — 일일 파이프라인")
    print("=" * 60)

    # 1. DB 초기화
    init_db()

    # 2. 데이터 수집 + 상태 기록
    price_records = fetch_prices()
    if price_records:
        record_module_status(engine, "fetch_prices", price_records, success_key="price")

    macro_records = fetch_macro()
    if macro_records:
        record_module_status(engine, "fetch_macro", macro_records, success_key="value")

    news_records = fetch_news()
    if news_records:
        record_module_status(engine, "fetch_news", news_records, success_key="title")

    # ── Phase 4.1: 펀더멘탈 수집 ──
    try:
        from data.fetch_fundamentals import run as fetch_fundamentals

        fund_results = fetch_fundamentals()
        if fund_results:
            record_module_status(
                engine, "fetch_fundamentals", fund_results, success_key="ticker"
            )
        print(f"  펀더멘탈: {len(fund_results)}개 종목")
    except Exception as e:
        print(f"  ⚠️ fetch_fundamentals 실패: {e}")

    # ── Phase 4.1: 수급 데이터 수집 ──
    try:
        from data.fetch_supply import run as fetch_supply

        supply_results = fetch_supply()
        if supply_results:
            print(
                f"  수급: KRX {len(supply_results.get('krx_supply', {}))}개, F&G={supply_results.get('fear_greed', {})}"
            )
    except Exception as e:
        print(f"  ⚠️ fetch_supply 실패: {e}")

    # ── Phase 4: 종목 발굴 ──
    try:
        from data.fetch_opportunities import run as fetch_opportunities

        opp_results = fetch_opportunities()
        if opp_results:
            record_module_status(
                engine, "fetch_opportunities", opp_results, success_key="ticker"
            )
        print(f"  종목 발굴: {len(opp_results)}개 후보")
    except Exception as e:
        print(f"  ⚠️ fetch_opportunities 실패: {e}")
        opp_results = []

    # 2.5. 시장 레짐 분류 (매크로 수집 후, 분석 전)
    try:
        from analysis.regime_classifier import run as classify_regime

        classify_regime()
    except Exception as e:
        print(f"  ⚠️ 레짐 분류 실패: {e}")

    # 3. 일봉 집계 (수집 후, 분석 전)
    aggregate_daily()

    # 3.5. DB 유지보수 (보존 정책 적용 + VACUUM)
    maintain_db()

    # 4. 분석
    analyze_prices()
    check_alerts()
    run_screener()
    analyze_portfolio()

    # 4.1. 성과 추적 (outcome 업데이트 + 월간 성적표)
    try:
        from analysis.performance import run as track_performance

        perf_result = track_performance()
        outcomes = perf_result.get("outcomes", {})
        print(
            f"  성과 추적: 1w={outcomes.get('updated_1w', 0)}건, "
            f"1m={outcomes.get('updated_1m', 0)}건 업데이트"
        )
    except Exception as e:
        print(f"  ⚠️ 성과 추적 실패: {e}")

    # 4.2. 자기 교정 (성과 분석 → correction_notes.json)
    try:
        from analysis.self_correction import run as run_self_correction

        correction = run_self_correction()
        if correction:
            print(
                f"  자기 교정: 약한 팩터={correction.get('weak_factors', [])}, "
                f"강한 팩터={correction.get('strong_factors', [])}"
            )
        else:
            print("  자기 교정: 성과 보고서 없음 — 건너뜀")
    except Exception as e:
        print(f"  ⚠️ 자기 교정 실패: {e}")

    # 4.5. JSON 출력 스키마 검증
    validate_all_outputs()

    # 4.6. 엔진 상태 저장
    save_engine_status(engine)

    # 5. 일일 리포트 생성
    generate_daily()

    # 6. 주간 리포트 (--weekly 플래그 시)
    if weekly_mode:
        generate_weekly()

    print("=" * 60)
    print("✅ 파이프라인 완료")
    print("=" * 60)


if __name__ == "__main__":
    main()

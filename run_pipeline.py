#!/usr/bin/env python3
"""
투자 인텔리전스 봇 — 파이프라인 실행기
Phase 1: 수집 → 분석 → 일일 리포트
Phase 2: 뉴스 수집 → 스크리너 → 포트폴리오 분석 → 주간 리포트
"""

import os
import sys
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent))

# .env 파일 자동 로드
_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    with _env_path.open() as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

from analysis.alerts import run as check_alerts  # noqa: E402
from analysis.portfolio import run as analyze_portfolio  # noqa: E402
from analysis.price_analysis import run as analyze_prices  # noqa: E402
from analysis.screener import run as run_screener  # noqa: E402
from data.fetch_macro import run as fetch_macro  # noqa: E402
from data.fetch_news import run as fetch_news  # noqa: E402
from data.fetch_prices import run as fetch_prices  # noqa: E402
from db.aggregate import run as aggregate_daily  # noqa: E402
from db.init_db import init_db  # noqa: E402
from db.maintenance import run as maintain_db  # noqa: E402
from reports.daily import run as generate_daily  # noqa: E402
from reports.weekly import run as generate_weekly  # noqa: E402
from utils.engine_status import (  # noqa: E402
    EngineStatus,
    record_module_status,
)
from utils.engine_status import (  # noqa: E402
    run as save_engine_status,
)
from utils.schema import validate_all_outputs  # noqa: E402


def _collect_data(engine: EngineStatus):
    """데이터 수집 단계 실행 (가격/매크로/뉴스/레짐/섹터/펀더멘탈/수급/발굴)"""
    price_records = fetch_prices()
    if price_records:
        record_module_status(engine, "fetch_prices", price_records, success_key="price")

    macro_records = fetch_macro()
    if macro_records:
        record_module_status(engine, "fetch_macro", macro_records, success_key="value")

    news_records = fetch_news()
    if news_records:
        record_module_status(engine, "fetch_news", news_records, success_key="title")

    # 레짐 분류 — sector_intel이 regime.json을 읽으므로 반드시 먼저 실행
    try:
        from analysis.regime_classifier import run as classify_regime

        classify_regime()
    except Exception as e:
        print(f"  ⚠️ 레짐 분류 실패: {e}")

    _collect_fundamentals(engine)
    _collect_supply()
    _run_sector_intel()
    _fetch_universe_daily(engine)  # 유니버스 일봉 사전 수집 (value_screener DB 스크리닝용)
    _collect_opportunities(engine)


def _collect_fundamentals(engine: EngineStatus):
    """Phase 4.1: 펀더멘탈 수집"""
    try:
        from data.fetch_fundamentals import run as fetch_fundamentals

        fund_results = fetch_fundamentals()
        if fund_results:
            record_module_status(engine, "fetch_fundamentals", fund_results, success_key="ticker")
        print(f"  펀더멘탈: {len(fund_results)}개 종목")
    except Exception as e:
        print(f"  ⚠️ fetch_fundamentals 실패: {e}")


def _collect_supply():
    """Phase 4.1: 수급 데이터 수집"""
    try:
        from data.fetch_supply import run as fetch_supply

        supply_results = fetch_supply()
        if supply_results:
            print(
                f"  수급: KRX {len(supply_results.get('krx_supply', {}))}개, F&G={supply_results.get('fear_greed', {})}"
            )
    except Exception as e:
        print(f"  ⚠️ fetch_supply 실패: {e}")


def _run_sector_intel():
    """섹터 인텔리전스: macro/news/regime → sector_scores.json"""
    try:
        from analysis.sector_intel import run as run_sector_intel

        result = run_sector_intel()
        top = result.get("sectors", [{}])[0]
        print(f"  섹터 점수화: top={top.get('name')}({top.get('score')})")
    except Exception as e:
        print(f"  ⚠️ sector_intel 실패: {e}")


def _fetch_universe_daily(engine: EngineStatus):
    """유니버스 전체(150개) 일봉 사전 수집 → prices_daily 저장"""
    try:
        from data.fetch_universe_daily import run as fetch_universe_daily

        result = fetch_universe_daily()
        print(
            f"  유니버스 일봉 수집: {result.get('success', 0)}개 성공, {result.get('fail', 0)}개 실패"
        )
    except Exception as e:
        print(f"  ⚠️ 유니버스 일봉 수집 실패: {e}")


def _collect_opportunities(engine: EngineStatus):
    """Phase 4: 종목 발굴"""
    try:
        from data.fetch_opportunities import run as fetch_opportunities

        opp_results = fetch_opportunities()
        if opp_results:
            record_module_status(engine, "fetch_opportunities", opp_results, success_key="ticker")
        print(f"  종목 발굴: {len(opp_results)}개 후보")
    except Exception as e:
        print(f"  ⚠️ fetch_opportunities 실패: {e}")

    # 발굴 종목 포함 ticker_master 갱신 (신규 종목 UPSERT)
    try:
        from data.ticker_master import run as update_ticker_master

        master = update_ticker_master()
        print(f"  종목 사전 갱신: {len(master)}개 종목")
    except Exception as e:
        print(f"  ⚠️ ticker_master 갱신 실패: {e}")


def _run_post_analysis():
    """분석 후처리 단계 실행 (성과추적/자기교정/능동알림/동적관리/시뮬레이션)"""
    _track_performance()
    _run_self_correction()
    _run_proactive_alerts()
    _run_dynamic_holdings()
    _run_simulation()


def _track_performance():
    """성과 추적 (outcome 업데이트 + 월간 성적표)"""
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


def _run_self_correction():
    """자기 교정 (성과 분석 → correction_notes.json)"""
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


def _run_proactive_alerts():
    """능동적 알림 (포트폴리오 P&L + regime + 교정 → proactive_alerts.json)"""
    try:
        from analysis.proactive_alerts import run as run_proactive_alerts

        alert_result = run_proactive_alerts()
        print(f"  능동적 알림: {alert_result.get('count', 0)}건 생성")
    except Exception as e:
        print(f"  ⚠️ 능동적 알림 실패: {e}")


def _run_dynamic_holdings():
    """동적 종목 관리 (추가/제거 후보 제안 → holdings_proposal.json)"""
    try:
        from analysis.dynamic_holdings import run as run_dynamic_holdings

        dh_result = run_dynamic_holdings()
        summary = dh_result.get("summary", {})
        print(
            f"  동적 종목 관리: 추가 후보 {summary.get('add_count', 0)}개, "
            f"제거 후보 {summary.get('remove_count', 0)}개"
        )
    except Exception as e:
        print(f"  ⚠️ 동적 종목 관리 실패: {e}")


def _run_simulation():
    """포트폴리오 시뮬레이션 (발굴 종목 가상 손익 → simulation_report.json)"""
    try:
        from analysis.simulation import run as run_simulation

        sim_result = run_simulation()
        summary = sim_result.get("summary", {})
        print(
            f"  시뮬레이션: {summary.get('total', 0)}건, "
            f"평균 수익률 {summary.get('avg_return_pct', 0.0):.1f}%"
        )
    except Exception as e:
        print(f"  ⚠️ 포트폴리오 시뮬레이션 실패: {e}")


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

    # 2. 데이터 수집 (내부에서 레짐 분류 → 섹터 인텔 순서로 실행)
    _collect_data(engine)

    # 3. 일봉 집계 + DB 유지보수
    aggregate_daily()
    maintain_db()

    # 4. 분석
    analyze_prices()
    check_alerts()
    run_screener()
    analyze_portfolio()

    # 4.1 ~ 4.3. 후처리 분석
    _run_post_analysis()

    # 4.6. JSON 출력 스키마 검증
    validate_all_outputs()

    # 4.7. 엔진 상태 저장
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

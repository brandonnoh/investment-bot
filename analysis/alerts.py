#!/usr/bin/env python3
"""
알림 감지 모듈 — 공통 감지 로직 + 배치 모드 실행
종목 급등/급락, 코스피 폭락, 환율 급등, 유가 급등, VIX 급등, 금 급변 감지
출력: output/intel/alerts.json (알림 있을 때만 생성)

- 이 모듈: 공통 감지/저장 함수 + JSON 기반 배치 실행 (run_pipeline.py용)
- alerts_watch.py: DB 기반 실시간 실행 + 중복 방지 + Discord 전송
- alerts_io.py: DB/JSON 저장 레이어
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as _config
from analysis.alerts_io import save_alerts_to_db, save_alerts_to_json  # noqa: F401 (re-export)
from config import ALERT_THRESHOLDS, DB_PATH, OUTPUT_DIR
from db.init_db import init_db

KST = timezone(timedelta(hours=9))

# 동적 임계값 함수 참조 (모듈 레벨에서 미리 바인딩해 린터 제거 방지)
_get_dynamic_thresholds = _config.get_dynamic_thresholds


# ── 데이터 로드 (JSON 기반, 배치 모드) ──


def load_latest_prices() -> list[dict]:
    """최신 주가 데이터 로드 (prices.json)"""
    prices_path = OUTPUT_DIR / "prices.json"
    if not prices_path.exists():
        print("  ⚠️  prices.json 없음 — fetch_prices.py를 먼저 실행하세요")
        return []
    with prices_path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data.get("prices", [])


def load_latest_macro() -> list[dict]:
    """최신 매크로 데이터 로드 (macro.json)"""
    macro_path = OUTPUT_DIR / "macro.json"
    if not macro_path.exists():
        print("  ⚠️  macro.json 없음 — fetch_macro.py를 먼저 실행하세요")
        return []
    with macro_path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data.get("indicators", [])


def get_current_vix(macro: list[dict]) -> float | None:
    """매크로 지표 리스트에서 현재 VIX 값 추출"""
    for m in macro:
        if m.get("indicator") == "VIX":
            return m.get("value")
    return None


# ── 공통 감지 로직 (alerts_watch.py에서도 사용) ──


def check_stock_alerts(
    prices: list[dict], thresholds: dict | None = None
) -> list[dict]:
    """종목별 급등/급락 감지.

    Args:
        prices: 주가 데이터 리스트
        thresholds: VIX 기반 동적 임계값 (None이면 고정 기본값 사용)
    """
    alerts = []
    if thresholds is not None:
        drop_threshold = thresholds.get(
            "stock_drop", ALERT_THRESHOLDS["stock_drop"]["threshold"]
        )
        surge_threshold = thresholds.get(
            "stock_surge", ALERT_THRESHOLDS["stock_surge"]["threshold"]
        )
    else:
        drop_threshold = ALERT_THRESHOLDS["stock_drop"]["threshold"]
        surge_threshold = ALERT_THRESHOLDS["stock_surge"]["threshold"]

    for p in prices:
        change = p.get("change_pct")
        if change is None:
            continue

        # 급락 감지
        if change <= drop_threshold:
            alerts.append(
                {
                    "level": "RED",
                    "event_type": "stock_drop",
                    "ticker": p["ticker"],
                    "message": f"🔴 긴급: {p['name']} {change:+.2f}% 급락 (현재가: {p['price']:,.2f})",
                    "value": change,
                    "threshold": drop_threshold,
                }
            )

        # 급등 감지
        elif change >= surge_threshold:
            alerts.append(
                {
                    "level": "GREEN",
                    "event_type": "stock_surge",
                    "ticker": p["ticker"],
                    "message": f"🟢 알림: {p['name']} {change:+.2f}% 급등 (현재가: {p['price']:,.2f})",
                    "value": change,
                    "threshold": surge_threshold,
                }
            )

    return alerts


def _check_kospi_alert(m: dict, thresholds: dict | None) -> dict | None:
    """코스피 폭락 알림 감지"""
    change = m.get("change_pct")
    value = m.get("value")
    if change is None:
        return None
    threshold = (
        thresholds.get("kospi_drop", ALERT_THRESHOLDS["kospi_drop"]["threshold"])
        if thresholds is not None
        else ALERT_THRESHOLDS["kospi_drop"]["threshold"]
    )
    if change <= threshold:
        return {
            "level": "RED",
            "event_type": "kospi_drop",
            "ticker": m.get("ticker"),
            "message": f"🔴 긴급: 코스피 {change:+.2f}% 폭락 (현재: {value:,.2f})",
            "value": change,
            "threshold": threshold,
        }
    return None


def _check_usd_krw_alert(m: dict) -> dict | None:
    """환율 급등 알림 감지 (절대값 기준)"""
    value = m.get("value")
    threshold = ALERT_THRESHOLDS["usd_krw_high"]["threshold"]
    if value >= threshold:
        return {
            "level": "RED",
            "event_type": "usd_krw_high",
            "ticker": m.get("ticker"),
            "message": f"🔴 긴급: 원/달러 환율 {value:,.2f}원 돌파 (임계값: {threshold:,.0f}원)",
            "value": value,
            "threshold": threshold,
        }
    return None


def _check_oil_alert(m: dict) -> dict | None:
    """WTI 유가 급등 알림 감지"""
    change = m.get("change_pct")
    value = m.get("value")
    if change is None:
        return None
    threshold = ALERT_THRESHOLDS["oil_surge"]["threshold"]
    if change >= threshold:
        return {
            "level": "YELLOW",
            "event_type": "oil_surge",
            "ticker": m.get("ticker"),
            "message": f"🟡 주의: WTI 유가 {change:+.2f}% 급등 (현재: ${value:,.2f})",
            "value": change,
            "threshold": threshold,
        }
    return None


def _check_vix_alert(m: dict) -> dict | None:
    """VIX 급등 알림 감지 (절대값 기준)"""
    value = m.get("value")
    if "vix_high" not in ALERT_THRESHOLDS:
        return None
    vix_threshold = ALERT_THRESHOLDS["vix_high"]["threshold"]
    if value >= vix_threshold:
        return {
            "level": "YELLOW",
            "event_type": "vix_high",
            "ticker": m.get("ticker"),
            "message": f"🟡 주의: VIX {value:.2f} 돌파 (임계값: {vix_threshold})",
            "value": value,
            "threshold": vix_threshold,
        }
    return None


def _check_gold_alert(m: dict) -> dict | None:
    """금 현물 급변 알림 감지 (±3%)"""
    change = m.get("change_pct")
    value = m.get("value")
    if change is None:
        return None
    threshold = ALERT_THRESHOLDS["gold_swing"]["threshold"]
    if abs(change) >= threshold:
        direction = "급등" if change > 0 else "급락"
        return {
            "level": "YELLOW",
            "event_type": "gold_swing",
            "ticker": m.get("ticker"),
            "message": f"🟡 주의: 금 현물 {change:+.2f}% {direction} (현재: ${value:,.2f})",
            "value": change,
            "threshold": threshold,
        }
    return None


def check_macro_alerts(macro: list[dict], thresholds: dict | None = None) -> list[dict]:
    """매크로 지표 알림 감지.

    Args:
        macro: 매크로 지표 리스트
        thresholds: VIX 기반 동적 임계값 (None이면 고정 기본값 사용)
    """
    alerts = []

    for m in macro:
        indicator = m.get("indicator")
        value = m.get("value")

        if value is None:
            continue

        # 지표별 체크 함수 호출
        alert = None
        if indicator == "코스피":
            alert = _check_kospi_alert(m, thresholds)
        elif indicator == "원/달러":
            alert = _check_usd_krw_alert(m)
        elif indicator == "WTI 유가":
            alert = _check_oil_alert(m)
        elif indicator == "VIX":
            alert = _check_vix_alert(m)
        elif indicator == "금 현물":
            alert = _check_gold_alert(m)

        if alert is not None:
            alerts.append(alert)

    return alerts


def check_portfolio_alert(prices: list[dict]) -> list[dict]:
    """포트폴리오 통화별 손실률 감지"""
    alerts = []
    threshold = ALERT_THRESHOLDS["portfolio_loss"]["threshold"]

    # 통화별로 분리 계산
    by_currency = {}
    for p in prices:
        if p.get("price") is None or p.get("avg_cost", 0) <= 0:
            continue
        cur = p.get("currency", "USD")
        if cur not in by_currency:
            by_currency[cur] = {"invested": 0, "current": 0}
        qty = p.get("qty", 0)
        by_currency[cur]["invested"] += p["avg_cost"] * qty
        by_currency[cur]["current"] += p["price"] * qty

    for cur, totals in by_currency.items():
        if totals["invested"] > 0:
            pnl_pct = (
                (totals["current"] - totals["invested"]) / totals["invested"] * 100
            )
            if pnl_pct <= threshold:
                alerts.append(
                    {
                        "level": "RED",
                        "event_type": "portfolio_loss",
                        "ticker": cur,
                        "message": f"🔴 긴급: 포트폴리오({cur}) {pnl_pct:+.2f}% 손실 (임계값: {threshold}%)",
                        "value": pnl_pct,
                        "threshold": threshold,
                    }
                )

    return alerts


# ── 배치 모드 실행 (run_pipeline.py용) ──


def run():
    """알림 감지 파이프라인 실행 (JSON 기반 배치 모드)"""
    print(f"\n🚨 알림 감지 시작 — {datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}")

    # DB 초기화 확인
    if not DB_PATH.exists():
        init_db()

    # 데이터 로드
    prices = load_latest_prices()
    macro = load_latest_macro()

    # VIX 기반 동적 임계값 결정
    vix = get_current_vix(macro)
    if vix is not None:
        dynamic = _get_dynamic_thresholds(vix)
        regime = dynamic["regime"]
        print(
            f"  📊 현재 레짐: {regime} (VIX {vix:.2f}) — 임계값 {dynamic['stock_drop']}% 적용"
        )
        thresholds = dynamic
    else:
        thresholds = None

    # 알림 감지
    all_alerts = []
    all_alerts.extend(check_stock_alerts(prices, thresholds))
    all_alerts.extend(check_macro_alerts(macro, thresholds))
    all_alerts.extend(check_portfolio_alert(prices))

    # 결과 출력
    if all_alerts:
        print(f"\n  ⚠️  {len(all_alerts)}건 알림 감지:")
        for a in all_alerts:
            print(f"    {a['message']}")
    else:
        print("\n  ✅ 이상 없음")

    # 저장
    save_alerts_to_db(all_alerts)
    save_alerts_to_json(all_alerts)

    print()
    return all_alerts


if __name__ == "__main__":
    run()

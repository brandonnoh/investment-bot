#!/usr/bin/env python3
"""
알림 감지 모듈 — 공통 감지 로직 + 배치 모드 실행
종목 급등/급락, 코스피 폭락, 환율 급등, 유가 급등, VIX 급등, 금 급변 감지
출력: output/intel/alerts.json (알림 있을 때만 생성)

- 이 모듈: 공통 감지/저장 함수 + JSON 기반 배치 실행 (run_pipeline.py용)
- alerts_watch.py: DB 기반 실시간 실행 + 중복 방지 + 텔레그램 전송
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import ALERT_THRESHOLDS, DB_PATH, OUTPUT_DIR
from db.init_db import init_db

KST = timezone(timedelta(hours=9))


# ── 데이터 로드 (JSON 기반, 배치 모드) ──


def load_latest_prices() -> list[dict]:
    """최신 주가 데이터 로드 (prices.json)"""
    prices_path = OUTPUT_DIR / "prices.json"
    if not prices_path.exists():
        print("  ⚠️  prices.json 없음 — fetch_prices.py를 먼저 실행하세요")
        return []
    with open(prices_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("prices", [])


def load_latest_macro() -> list[dict]:
    """최신 매크로 데이터 로드 (macro.json)"""
    macro_path = OUTPUT_DIR / "macro.json"
    if not macro_path.exists():
        print("  ⚠️  macro.json 없음 — fetch_macro.py를 먼저 실행하세요")
        return []
    with open(macro_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("indicators", [])


# ── 공통 감지 로직 (alerts_watch.py에서도 사용) ──


def check_stock_alerts(prices: list[dict]) -> list[dict]:
    """종목별 급등/급락 감지"""
    alerts = []
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


def check_macro_alerts(macro: list[dict]) -> list[dict]:
    """매크로 지표 알림 감지"""
    alerts = []

    for m in macro:
        indicator = m.get("indicator")
        value = m.get("value")
        change = m.get("change_pct")

        if value is None:
            continue

        # 코스피 폭락
        if indicator == "코스피" and change is not None:
            threshold = ALERT_THRESHOLDS["kospi_drop"]["threshold"]
            if change <= threshold:
                alerts.append(
                    {
                        "level": "RED",
                        "event_type": "kospi_drop",
                        "ticker": m.get("ticker"),
                        "message": f"🔴 긴급: 코스피 {change:+.2f}% 폭락 (현재: {value:,.2f})",
                        "value": change,
                        "threshold": threshold,
                    }
                )

        # 환율 급등 (절대값 기준)
        if indicator == "원/달러":
            threshold = ALERT_THRESHOLDS["usd_krw_high"]["threshold"]
            if value >= threshold:
                alerts.append(
                    {
                        "level": "RED",
                        "event_type": "usd_krw_high",
                        "ticker": m.get("ticker"),
                        "message": f"🔴 긴급: 원/달러 환율 {value:,.2f}원 돌파 (임계값: {threshold:,.0f}원)",
                        "value": value,
                        "threshold": threshold,
                    }
                )

        # 유가 급등 (WTI)
        if indicator == "WTI 유가" and change is not None:
            threshold = ALERT_THRESHOLDS["oil_surge"]["threshold"]
            if change >= threshold:
                alerts.append(
                    {
                        "level": "YELLOW",
                        "event_type": "oil_surge",
                        "ticker": m.get("ticker"),
                        "message": f"🟡 주의: WTI 유가 {change:+.2f}% 급등 (현재: ${value:,.2f})",
                        "value": change,
                        "threshold": threshold,
                    }
                )

        # VIX 급등 (절대값 기준)
        if indicator == "VIX" and "vix_high" in ALERT_THRESHOLDS:
            vix_threshold = ALERT_THRESHOLDS["vix_high"]["threshold"]
            if value >= vix_threshold:
                alerts.append(
                    {
                        "level": "YELLOW",
                        "event_type": "vix_high",
                        "ticker": m.get("ticker"),
                        "message": f"🟡 주의: VIX {value:.2f} 돌파 (임계값: {vix_threshold})",
                        "value": value,
                        "threshold": vix_threshold,
                    }
                )

        # 금 현물 급변 (±3%)
        if indicator == "금 현물" and change is not None:
            threshold = ALERT_THRESHOLDS["gold_swing"]["threshold"]
            if abs(change) >= threshold:
                direction = "급등" if change > 0 else "급락"
                alerts.append(
                    {
                        "level": "YELLOW",
                        "event_type": "gold_swing",
                        "ticker": m.get("ticker"),
                        "message": f"🟡 주의: 금 현물 {change:+.2f}% {direction} (현재: ${value:,.2f})",
                        "value": change,
                        "threshold": threshold,
                    }
                )

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


# ── 공통 저장 함수 ──


def save_alerts_to_db(alerts: list[dict], conn=None, notified: bool = False):
    """알림을 SQLite에 저장

    Args:
        alerts: 알림 리스트
        conn: DB 연결 (None이면 DB_PATH로 새 연결 생성)
        notified: True면 notified=1로 저장 (텔레그램 전송 시)
    """
    if not alerts:
        return

    own_conn = False
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH))
        own_conn = True

    try:
        cursor = conn.cursor()
        now = datetime.now(KST).isoformat()
        notified_val = 1 if notified else 0

        for a in alerts:
            cursor.execute(
                """INSERT INTO alerts (level, event_type, ticker, message, value, threshold, triggered_at, notified)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    a["level"],
                    a["event_type"],
                    a.get("ticker"),
                    a["message"],
                    a["value"],
                    a["threshold"],
                    now,
                    notified_val,
                ),
            )

        conn.commit()
        flag_msg = " (notified=1)" if notified else ""
        print(f"  💾 알림 DB 저장: {len(alerts)}건{flag_msg}")
    finally:
        if own_conn:
            conn.close()


def save_alerts_to_json(alerts: list[dict], output_dir=None):
    """알림을 JSON 파일로 출력 (알림 있을 때만 생성, 없으면 삭제)

    Args:
        alerts: 알림 리스트
        output_dir: 출력 디렉토리 (기본: config.OUTPUT_DIR)
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR
    output_dir = Path(output_dir)
    alerts_path = output_dir / "alerts.json"

    if not alerts:
        # 알림 없으면 기존 파일 제거
        if alerts_path.exists():
            alerts_path.unlink()
            print("  🟢 알림 없음 — alerts.json 제거")
        else:
            print("  🟢 알림 없음")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    output = {
        "triggered_at": datetime.now(KST).isoformat(),
        "count": len(alerts),
        "alerts": alerts,
    }
    with open(alerts_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  🚨 알림 JSON 저장: {alerts_path} ({len(alerts)}건)")


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

    # 알림 감지
    all_alerts = []
    all_alerts.extend(check_stock_alerts(prices))
    all_alerts.extend(check_macro_alerts(macro))
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

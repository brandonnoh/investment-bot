#!/usr/bin/env python3
"""
실시간 알림 감시 모듈 (Phase 2.5 핵심)
DB 최신 데이터 기반 임계값 체크 + 중복 방지 + OpenClaw system event 연동

- 알림 발생 시: DB 저장 → alerts.json 생성 → openclaw system event 실행
- 알림 없을 시: 조용히 종료 (system event 실행 금지 — 토큰 낭비 방지)
- 중복 방지: 같은 종목+같은 방향 알림은 1시간 내 재발송 금지
"""
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import ALERT_THRESHOLDS, PORTFOLIO, DB_PATH, OUTPUT_DIR
from db.init_db import init_db

KST = timezone(timedelta(hours=9))

# 중복 알림 방지 간격 (초)
DEDUP_INTERVAL_SECONDS = 3600  # 1시간


def get_latest_prices_from_db() -> list[dict]:
    """DB에서 각 종목의 최신 가격 조회"""
    if not DB_PATH.exists():
        return []

    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()
        # 각 종목별 가장 최근 레코드
        cursor.execute("""
            SELECT p.ticker, p.name, p.price, p.prev_close, p.change_pct, p.market, p.timestamp
            FROM prices p
            INNER JOIN (
                SELECT ticker, MAX(timestamp) AS max_ts
                FROM prices
                GROUP BY ticker
            ) latest ON p.ticker = latest.ticker AND p.timestamp = latest.max_ts
        """)
        rows = cursor.fetchall()
        results = []
        for row in rows:
            # PORTFOLIO에서 avg_cost, currency, qty 매칭
            stock_info = next((s for s in PORTFOLIO if s["ticker"] == row[0]), {})
            results.append({
                "ticker": row[0],
                "name": row[1],
                "price": row[2],
                "prev_close": row[3],
                "change_pct": row[4],
                "market": row[5],
                "timestamp": row[6],
                "avg_cost": stock_info.get("avg_cost", 0),
                "currency": stock_info.get("currency", "USD"),
                "qty": stock_info.get("qty", 0),
            })
        return results
    finally:
        conn.close()


def get_latest_macro_from_db() -> list[dict]:
    """DB에서 각 매크로 지표의 최신 값 조회"""
    if not DB_PATH.exists():
        return []

    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.indicator, m.value, m.change_pct, m.timestamp
            FROM macro m
            INNER JOIN (
                SELECT indicator, MAX(timestamp) AS max_ts
                FROM macro
                GROUP BY indicator
            ) latest ON m.indicator = latest.indicator AND m.timestamp = latest.max_ts
        """)
        rows = cursor.fetchall()
        return [
            {"indicator": r[0], "value": r[1], "change_pct": r[2], "timestamp": r[3]}
            for r in rows
        ]
    finally:
        conn.close()


def is_duplicate_alert(event_type: str, ticker: str | None, direction: str) -> bool:
    """같은 종목+같은 방향 알림이 최근 1시간 내에 이미 발송되었는지 확인"""
    if not DB_PATH.exists():
        return False

    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()
        cutoff = (datetime.now(KST) - timedelta(seconds=DEDUP_INTERVAL_SECONDS)).isoformat()

        if ticker:
            cursor.execute("""
                SELECT COUNT(*) FROM alerts
                WHERE event_type = ? AND ticker = ? AND triggered_at > ? AND notified = 1
            """, (event_type, ticker, cutoff))
        else:
            cursor.execute("""
                SELECT COUNT(*) FROM alerts
                WHERE event_type = ? AND ticker IS NULL AND triggered_at > ? AND notified = 1
            """, (event_type, cutoff))

        count = cursor.fetchone()[0]
        return count > 0
    finally:
        conn.close()


def check_stock_alerts(prices: list[dict]) -> list[dict]:
    """종목별 급등/급락 감지 (중복 방지 포함)"""
    alerts = []
    drop_threshold = ALERT_THRESHOLDS["stock_drop"]["threshold"]
    surge_threshold = ALERT_THRESHOLDS["stock_surge"]["threshold"]

    for p in prices:
        change = p.get("change_pct")
        if change is None:
            continue

        # 급락 감지
        if change <= drop_threshold:
            if not is_duplicate_alert("stock_drop", p["ticker"], "drop"):
                alerts.append({
                    "level": "RED",
                    "event_type": "stock_drop",
                    "ticker": p["ticker"],
                    "message": f"🔴 긴급: {p['name']} {change:+.2f}% 급락 (현재가: {p['price']:,.2f})",
                    "value": change,
                    "threshold": drop_threshold,
                })

        # 급등 감지
        elif change >= surge_threshold:
            if not is_duplicate_alert("stock_surge", p["ticker"], "surge"):
                alerts.append({
                    "level": "GREEN",
                    "event_type": "stock_surge",
                    "ticker": p["ticker"],
                    "message": f"🟢 알림: {p['name']} {change:+.2f}% 급등 (현재가: {p['price']:,.2f})",
                    "value": change,
                    "threshold": surge_threshold,
                })

    return alerts


def check_macro_alerts(macro: list[dict]) -> list[dict]:
    """매크로 지표 알림 감지 (중복 방지 포함)"""
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
            if change <= threshold and not is_duplicate_alert("kospi_drop", None, "drop"):
                alerts.append({
                    "level": "RED",
                    "event_type": "kospi_drop",
                    "ticker": None,
                    "message": f"🔴 긴급: 코스피 {change:+.2f}% 폭락 (현재: {value:,.2f})",
                    "value": change,
                    "threshold": threshold,
                })

        # 환율 급등 (절대값 기준)
        if indicator == "원/달러":
            threshold = ALERT_THRESHOLDS["usd_krw_high"]["threshold"]
            if value >= threshold and not is_duplicate_alert("usd_krw_high", None, "high"):
                alerts.append({
                    "level": "RED",
                    "event_type": "usd_krw_high",
                    "ticker": None,
                    "message": f"🔴 긴급: 원/달러 환율 {value:,.2f}원 돌파 (임계값: {threshold:,.0f}원)",
                    "value": value,
                    "threshold": threshold,
                })

        # 유가 급등 (WTI)
        if indicator == "WTI 유가" and change is not None:
            threshold = ALERT_THRESHOLDS["oil_surge"]["threshold"]
            if change >= threshold and not is_duplicate_alert("oil_surge", None, "surge"):
                alerts.append({
                    "level": "YELLOW",
                    "event_type": "oil_surge",
                    "ticker": None,
                    "message": f"🟡 주의: WTI 유가 {change:+.2f}% 급등 (현재: ${value:,.2f})",
                    "value": change,
                    "threshold": threshold,
                })

        # VIX 급등 (절대값 기준)
        if indicator == "VIX" and "vix_high" in ALERT_THRESHOLDS:
            vix_threshold = ALERT_THRESHOLDS["vix_high"]["threshold"]
            if value >= vix_threshold and not is_duplicate_alert("vix_high", None, "high"):
                alerts.append({
                    "level": "YELLOW",
                    "event_type": "vix_high",
                    "ticker": None,
                    "message": f"🟡 주의: VIX {value:.2f} 돌파 (임계값: {vix_threshold})",
                    "value": value,
                    "threshold": vix_threshold,
                })

        # 금 현물 급변 (±3%)
        if indicator == "금 현물" and change is not None:
            threshold = ALERT_THRESHOLDS["gold_swing"]["threshold"]
            if abs(change) >= threshold:
                direction = "surge" if change > 0 else "drop"
                direction_kr = "급등" if change > 0 else "급락"
                if not is_duplicate_alert("gold_swing", None, direction):
                    alerts.append({
                        "level": "YELLOW",
                        "event_type": "gold_swing",
                        "ticker": None,
                        "message": f"🟡 주의: 금 현물 {change:+.2f}% {direction_kr} (현재: ${value:,.2f})",
                        "value": change,
                        "threshold": threshold,
                    })

    return alerts


def check_portfolio_alert(prices: list[dict]) -> list[dict]:
    """포트폴리오 통화별 손실률 감지 (중복 방지 포함)"""
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
            pnl_pct = (totals["current"] - totals["invested"]) / totals["invested"] * 100
            if pnl_pct <= threshold:
                if not is_duplicate_alert("portfolio_loss", cur, "loss"):
                    alerts.append({
                        "level": "RED",
                        "event_type": "portfolio_loss",
                        "ticker": cur,
                        "message": f"🔴 긴급: 포트폴리오({cur}) {pnl_pct:+.2f}% 손실 (임계값: {threshold}%)",
                        "value": pnl_pct,
                        "threshold": threshold,
                    })

    return alerts


def save_alerts_to_db(alerts: list[dict]):
    """알림을 SQLite에 저장 (notified=1로 표시)"""
    if not alerts:
        return

    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()
        now = datetime.now(KST).isoformat()

        for a in alerts:
            cursor.execute(
                """INSERT INTO alerts (level, event_type, ticker, message, value, threshold, triggered_at, notified)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
                (a["level"], a["event_type"], a.get("ticker"), a["message"],
                 a["value"], a["threshold"], now),
            )

        conn.commit()
        print(f"  💾 알림 DB 저장: {len(alerts)}건 (notified=1)")
    finally:
        conn.close()


def save_alerts_to_json(alerts: list[dict]):
    """알림을 JSON 파일로 출력 (알림 있을 때만)"""
    alerts_path = OUTPUT_DIR / "alerts.json"

    if not alerts:
        # 알림 없으면 기존 파일 제거
        if alerts_path.exists():
            alerts_path.unlink()
            print("  🟢 알림 없음 — alerts.json 제거")
        else:
            print("  🟢 알림 없음")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = {
        "triggered_at": datetime.now(KST).isoformat(),
        "count": len(alerts),
        "alerts": alerts,
    }
    with open(alerts_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  🚨 알림 JSON 저장: {alerts_path} ({len(alerts)}건)")


def fire_system_event(alerts: list[dict]):
    """OpenClaw system event 실행 — 알림 있을 때만 (핵심 원칙)"""
    if not alerts:
        # 알림 없으면 절대 실행 금지 (토큰 낭비 방지)
        return

    # 알림 요약 메시지 생성
    summary_parts = []
    for a in alerts:
        level_emoji = {"RED": "🔴", "YELLOW": "🟡", "GREEN": "🟢"}.get(a["level"], "⚪")
        summary_parts.append(f"{level_emoji} {a['message']}")

    summary = "\n".join(summary_parts)
    event_text = f"🚨 투자 알림 ({len(alerts)}건):\n{summary}"

    try:
        result = subprocess.run(
            ["openclaw", "system", "event", "--text", event_text, "--mode", "now"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            print(f"  📡 system event 전송 완료 ({len(alerts)}건)")
        else:
            print(f"  ⚠️  system event 실패: {result.stderr.strip()}")
    except FileNotFoundError:
        print("  ⚠️  openclaw 명령어를 찾을 수 없음 — system event 건너뜀")
    except subprocess.TimeoutExpired:
        print("  ⚠️  system event 타임아웃 (30초)")
    except Exception as e:
        print(f"  ⚠️  system event 오류: {e}")


def run():
    """알림 감시 파이프라인 실행"""
    print(f"\n🚨 알림 감시 시작 — {datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}")

    # DB 초기화 확인
    if not DB_PATH.exists():
        init_db()

    # DB에서 최신 데이터 로드
    prices = get_latest_prices_from_db()
    macro = get_latest_macro_from_db()

    if not prices and not macro:
        print("  ⚠️  DB에 데이터 없음 — 수집 먼저 실행 필요")
        print()
        return []

    print(f"  📊 종목 {len(prices)}개, 매크로 {len(macro)}개 로드")

    # 알림 감지 (중복 방지 포함)
    all_alerts = []
    all_alerts.extend(check_stock_alerts(prices))
    all_alerts.extend(check_macro_alerts(macro))
    all_alerts.extend(check_portfolio_alert(prices))

    # 결과 출력
    if all_alerts:
        print(f"\n  ⚠️  {len(all_alerts)}건 신규 알림 감지:")
        for a in all_alerts:
            print(f"    {a['message']}")
    else:
        print("\n  ✅ 이상 없음 (또는 중복 알림 필터됨)")

    # 저장
    save_alerts_to_db(all_alerts)
    save_alerts_to_json(all_alerts)

    # system event 발사 — 알림 있을 때만!
    fire_system_event(all_alerts)

    print()
    return all_alerts


if __name__ == "__main__":
    run()

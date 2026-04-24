#!/usr/bin/env python3
"""
장 마감 리포트 생성 모듈 (Phase 2.5)
오늘 수집된 DB 이력으로 시가/고가/저가/종가 + 최종 손익 계산
출력: output/intel/closing_report.md
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, MACRO_INDICATORS, OUTPUT_DIR
from db.init_db import init_db

# 헬퍼 함수 임포트 (하위 호환 re-export 포함)
from reports.closing_helpers import (  # noqa: F401
    apply_monthly_deposits,
    fmt_change,
    fmt_price,
    get_today_alerts,
    get_today_macro_ohlc,
    get_today_ohlc,
    is_last_business_day_of_month,
    save_portfolio_snapshot,
)

KST = timezone(timedelta(hours=9))


def _render_price_section() -> tuple[list, dict]:
    """포트폴리오 종목 OHLC 섹션 렌더링.

    Returns:
        (lines, totals): 마크다운 라인 목록과 통화별 투자/평가 합계 딕셔너리
    """
    lines = [
        "## 💼 포트폴리오 종목 (오늘 OHLC)\n",
        "| 종목 | 시가 | 고가 | 저가 | 종가 | 전일比 | 평단比 | 수집 |",
        "|------|------|------|------|------|--------|--------|------|",
    ]
    totals = {
        "invested_krw": 0,
        "current_krw": 0,
        "invested_usd": 0,
        "current_usd": 0,
    }

    for stock in ssot.get_holdings():
        ticker = stock["ticker"]
        name = stock["name"]
        currency = stock["currency"]
        avg_cost = stock["avg_cost"]
        qty = stock["qty"]

        ohlc = get_today_ohlc(ticker)
        if ohlc is None:
            lines.append(f"| {name} | — | — | — | — | — | — | 0건 |")
            continue

        close = ohlc["close"]
        prev_close = ohlc["prev_close"]
        change_pct = round((close - prev_close) / prev_close * 100, 2) if prev_close else None
        pnl_pct = round((close - avg_cost) / avg_cost * 100, 2) if avg_cost > 0 else None

        if avg_cost > 0:
            if currency == "KRW":
                totals["invested_krw"] += avg_cost * qty
                totals["current_krw"] += close * qty
            else:
                totals["invested_usd"] += avg_cost * qty
                totals["current_usd"] += close * qty

        lines.append(
            f"| {name} | {fmt_price(ohlc['open'], currency)} "
            f"| {fmt_price(ohlc['high'], currency)} "
            f"| {fmt_price(ohlc['low'], currency)} "
            f"| {fmt_price(close, currency)} "
            f"| {fmt_change(change_pct)} "
            f"| {fmt_change(pnl_pct)} "
            f"| {ohlc['data_points']}건 |"
        )

    lines.append("")
    return lines, totals


def _render_pnl_section(totals: dict) -> list:
    """오늘 최종 손익 섹션 렌더링"""
    lines = ["## 💰 오늘 최종 손익\n"]
    invested_krw = totals["invested_krw"]
    current_krw = totals["current_krw"]
    invested_usd = totals["invested_usd"]
    current_usd = totals["current_usd"]

    if invested_krw > 0:
        pnl_krw = current_krw - invested_krw
        pnl_pct_krw = pnl_krw / invested_krw * 100
        emoji_krw = "🟢" if pnl_krw >= 0 else "🔴"
        lines.append(
            f"- **KRW 포트폴리오**: 투자 {invested_krw:,.0f}원 → 현재 {current_krw:,.0f}원"
        )
        lines.append(f"  - {emoji_krw} 손익: {pnl_krw:+,.0f}원 ({pnl_pct_krw:+.2f}%)")

    if invested_usd > 0:
        pnl_usd = current_usd - invested_usd
        pnl_pct_usd = pnl_usd / invested_usd * 100
        emoji_usd = "🟢" if pnl_usd >= 0 else "🔴"
        lines.append(f"- **USD 포트폴리오**: 투자 ${invested_usd:,.2f} → 현재 ${current_usd:,.2f}")
        lines.append(f"  - {emoji_usd} 손익: ${pnl_usd:+,.2f} ({pnl_pct_usd:+.2f}%)")

    if invested_krw == 0 and invested_usd == 0:
        lines.append("> 오늘 수집된 가격 데이터 없음")

    lines.append("")
    return lines


def _render_macro_section() -> list:
    """매크로 지표 마감 섹션 렌더링"""
    lines = [
        "---\n",
        "## 🌍 매크로 지표 마감\n",
        "| 지표 | 시가 | 고가 | 저가 | 종가 | 전일比 |",
        "|------|------|------|------|------|--------|",
    ]
    target_macros = {"코스피", "코스닥", "원/달러", "WTI 유가", "브렌트유", "VIX"}
    for ind in MACRO_INDICATORS:
        if ind["name"] not in target_macros:
            continue
        ohlc = get_today_macro_ohlc(ind["name"])
        if ohlc is None:
            lines.append(f"| {ind['name']} | — | — | — | — | — |")
            continue

        is_fx = ind["name"] == "원/달러"

        def fmt(v, _is_fx=is_fx):
            """매크로 값 포맷 (환율은 원 단위)"""
            if not v:
                return "—"
            return f"{v:,.2f}원" if _is_fx else f"{v:,.2f}"

        lines.append(
            f"| {ind['name']} | {fmt(ohlc['open'])} "
            f"| {fmt(ohlc['high'])} | {fmt(ohlc['low'])} "
            f"| {fmt(ohlc['close'])} | {fmt_change(ohlc['change_pct'])} |"
        )
    lines.append("")
    return lines


def _render_alerts_section() -> list:
    """오늘 알림 히스토리 섹션 렌더링 (알림 없으면 빈 리스트)"""
    today_alerts = get_today_alerts()
    if not today_alerts:
        return []
    lines = [
        "---\n",
        f"## 🚨 오늘 발생한 알림 ({len(today_alerts)}건)\n",
    ]
    for a in today_alerts:
        lines.append(f"- [{a['time']}] {a['message']}")
    lines.append("")
    return lines


def generate_closing_report() -> str:
    """장 마감 리포트 마크다운 생성"""
    now = datetime.now(KST)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M KST")

    header = [
        f"# 📈 장 마감 리포트 — {date_str}",
        f"> 생성 시각: {time_str}\n",
        "---\n",
    ]

    price_lines, totals = _render_price_section()
    pnl_lines = _render_pnl_section(totals)
    macro_lines = _render_macro_section()
    alerts_lines = _render_alerts_section()
    footer = ["---\n", f"*자동 생성 by investment-bot (closing) | {now.isoformat()}*\n"]

    lines = header + price_lines + pnl_lines + macro_lines + alerts_lines + footer
    return "\n".join(lines)


def run():
    """장 마감 리포트 생성 파이프라인"""
    print(f"\n📈 장 마감 리포트 생성 — {datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}")

    # DB 초기화 확인
    if not DB_PATH.exists():
        init_db()

    # ── 월말 자동이체 적립 반영 ──
    deposit_logs = apply_monthly_deposits()
    for log in deposit_logs:
        print(f"  {log}")
    if deposit_logs:
        print()

    report = generate_closing_report()

    # 저장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "closing_report.md"
    with output_path.open("w", encoding="utf-8") as f:
        f.write(report)

    print(f"  📄 마감 리포트 저장: {output_path}")
    print(f"  📏 크기: {len(report):,} bytes")

    # 포트폴리오 스냅샷 DB 저장
    portfolio_path = OUTPUT_DIR / "portfolio_summary.json"
    if portfolio_path.exists():
        try:
            with portfolio_path.open(encoding="utf-8") as f:
                portfolio_summary = json.load(f)
            conn = sqlite3.connect(str(DB_PATH))
            try:
                save_portfolio_snapshot(conn, portfolio_summary)
            finally:
                conn.close()
        except Exception as e:
            print(f"  ⚠️ 포트폴리오 스냅샷 저장 실패: {e}")
    else:
        print("  ⚠️ portfolio_summary.json 없음, 스냅샷 저장 건너뜀")

    print()
    return report


if __name__ == "__main__":
    run()

#!/usr/bin/env python3
"""
일일 리포트 마크다운 생성
포트폴리오 현황, 매크로 요약, 알림 요약을 통합
출력: output/intel/daily_report.md
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import OUTPUT_DIR

KST = timezone(timedelta(hours=9))


def load_json(filename: str) -> dict | None:
    """output/intel/ 에서 JSON 파일 로드"""
    path = OUTPUT_DIR / filename
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_price_section(prices_data: dict | None) -> str:
    """포트폴리오 현황 섹션 생성"""
    if not prices_data:
        return "## 📊 포트폴리오 현황\n\n> 데이터 없음 — fetch_prices.py 실행 필요\n"

    prices = prices_data.get("prices", [])
    lines = ["## 📊 포트폴리오 현황\n"]

    # 한국 종목
    kr_stocks = [p for p in prices if p.get("currency") == "KRW"]
    if kr_stocks:
        lines.append("### 🇰🇷 국내")
        lines.append("| 종목 | 현재가 | 전일比 | 평단比 | 계좌 |")
        lines.append("|------|--------|--------|--------|------|")
        for p in kr_stocks:
            if p.get("price") is None:
                lines.append(
                    f"| {p['name']} | ❌ 조회실패 | — | — | {p.get('account', '')} |"
                )
                continue
            chg = p.get("change_pct", 0)
            pnl = p.get("pnl_pct")
            flag = "🔴" if chg < -3 else ("🟡" if chg < 0 else "🟢")
            pnl_str = f"{pnl:+.2f}%" if pnl is not None else "—"
            lines.append(
                f"| {flag} {p['name']} | {p['price']:,.0f}원 | {chg:+.2f}% | {pnl_str} | {p.get('account', '')} |"
            )
        lines.append("")

    # 해외 종목
    us_stocks = [p for p in prices if p.get("currency") == "USD"]
    if us_stocks:
        lines.append("### 🇺🇸 해외")
        lines.append("| 종목 | 현재가 | 전일比 | 평단比 | 계좌 |")
        lines.append("|------|--------|--------|--------|------|")
        for p in us_stocks:
            if p.get("price") is None:
                lines.append(
                    f"| {p['name']} | ❌ 조회실패 | — | — | {p.get('account', '')} |"
                )
                continue
            chg = p.get("change_pct", 0)
            pnl = p.get("pnl_pct")
            flag = "🔴" if chg < -3 else ("🟡" if chg < 0 else "🟢")
            pnl_str = f"{pnl:+.2f}%" if pnl is not None else "—"
            lines.append(
                f"| {flag} {p['name']} | ${p['price']:,.2f} | {chg:+.2f}% | {pnl_str} | {p.get('account', '')} |"
            )
        lines.append("")

    return "\n".join(lines)


def format_portfolio_summary(prices_data: dict | None) -> str:
    """포트폴리오 통화별 요약 (KRW/USD 분리 계산)"""
    if not prices_data:
        return ""

    prices = prices_data.get("prices", [])

    # 통화별 분리 집계
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

    if not by_currency:
        return ""

    lines = ["### 💰 포트폴리오 요약\n"]
    for cur, totals in by_currency.items():
        invested = totals["invested"]
        current = totals["current"]
        pnl = current - invested
        pnl_pct = pnl / invested * 100 if invested > 0 else 0
        if cur == "KRW":
            lines.append(
                f"- **{cur}**: 투자 {invested:,.0f}원 → 현재 {current:,.0f}원 ({pnl_pct:+.2f}%)"
            )
        else:
            lines.append(
                f"- **{cur}**: 투자 ${invested:,.2f} → 현재 ${current:,.2f} ({pnl_pct:+.2f}%)"
            )

    lines.append("")
    return "\n".join(lines)


def format_macro_section(macro_data: dict | None) -> str:
    """매크로 지표 요약 섹션"""
    if not macro_data:
        return "## 🌍 매크로 지표\n\n> 데이터 없음 — fetch_macro.py 실행 필요\n"

    indicators = macro_data.get("indicators", [])
    lines = ["## 🌍 매크로 지표\n"]
    lines.append("| 지표 | 현재값 | 전일比 |")
    lines.append("|------|--------|--------|")

    for m in indicators:
        if m.get("value") is None:
            lines.append(f"| {m['indicator']} | ❌ 조회실패 | — |")
            continue
        chg = m.get("change_pct", 0)
        flag = "🔴" if chg < -2 else ("🟡" if chg < 0 else "🟢")

        # 지표 유형별 표시 형식
        if m["indicator"] == "원/달러":
            val_str = f"{m['value']:,.2f}원"
        elif m.get("category") in ("INDEX", "VOLATILITY", "FX"):
            val_str = f"{m['value']:,.2f}"
        else:
            val_str = f"${m['value']:,.2f}"

        lines.append(f"| {flag} {m['indicator']} | {val_str} | {chg:+.2f}% |")

    lines.append("")
    return "\n".join(lines)


def format_alerts_section(alerts_data: dict | None) -> str:
    """알림 요약 섹션"""
    if not alerts_data:
        return "## 🚨 알림\n\n✅ 현재 발생한 알림 없음\n"

    alerts = alerts_data.get("alerts", [])
    if not alerts:
        return "## 🚨 알림\n\n✅ 현재 발생한 알림 없음\n"

    lines = ["## 🚨 알림\n"]
    # 레벨순 정렬: RED > YELLOW > GREEN
    level_order = {"RED": 0, "YELLOW": 1, "GREEN": 2}
    sorted_alerts = sorted(
        alerts, key=lambda a: level_order.get(a.get("level", "GREEN"), 3)
    )

    for a in sorted_alerts:
        lines.append(f"- {a['message']}")

    lines.append("")
    return "\n".join(lines)


def generate_report() -> str:
    """일일 리포트 마크다운 생성"""
    now = datetime.now(KST)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M KST")

    # 데이터 로드
    prices_data = load_json("prices.json")
    macro_data = load_json("macro.json")
    alerts_data = load_json("alerts.json")

    # 리포트 조합
    report_parts = [
        f"# 📈 일일 투자 리포트 — {date_str}\n",
        f"> 생성 시각: {time_str}\n",
        "---\n",
        format_alerts_section(alerts_data),
        "---\n",
        format_price_section(prices_data),
        format_portfolio_summary(prices_data),
        "---\n",
        format_macro_section(macro_data),
        "---\n",
        f"*자동 생성 by investment-bot | {now.isoformat()}*\n",
    ]

    return "\n".join(report_parts)


def run():
    """일일 리포트 생성 파이프라인"""
    print(f"\n📝 일일 리포트 생성 — {datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}")

    report = generate_report()

    # 저장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "daily_report.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"  📄 리포트 저장: {output_path}")
    print(f"  📏 크기: {len(report):,} bytes")
    print()

    return report


if __name__ == "__main__":
    run()

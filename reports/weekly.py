#!/usr/bin/env python3
"""
주간 리포트 생성 — 매주 월요일 실행
포트폴리오 주간 성과, 섹터 로테이션, 신규 주목 종목
출력: output/intel/weekly_report.md
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, OUTPUT_DIR
from db.init_db import init_db

KST = timezone(timedelta(hours=9))


def load_json(filename: str) -> dict | None:
    """output/intel/ 에서 JSON 파일 로드"""
    path = OUTPUT_DIR / filename
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_weekly_price_history() -> dict:
    """DB에서 최근 7일 가격 히스토리 조회"""
    if not DB_PATH.exists():
        return {}

    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ticker, name, price, change_pct, timestamp
            FROM prices
            WHERE timestamp >= datetime('now', '-7 days')
            ORDER BY ticker, timestamp
        """)
        rows = cursor.fetchall()
    finally:
        conn.close()

    # 종목별로 그룹화
    history = {}
    for ticker, name, price, change_pct, ts in rows:
        if ticker not in history:
            history[ticker] = {"name": name, "records": []}
        history[ticker]["records"].append(
            {
                "price": price,
                "change_pct": change_pct,
                "timestamp": ts,
            }
        )

    return history


def calculate_weekly_performance(history: dict) -> list[dict]:
    """종목별 주간 수익률 계산"""
    performances = []

    for ticker, data in history.items():
        records = data["records"]
        if len(records) < 2:
            continue

        first_price = records[0]["price"]
        last_price = records[-1]["price"]

        if first_price > 0:
            weekly_return = round((last_price - first_price) / first_price * 100, 2)
        else:
            weekly_return = 0.0

        # 주간 최고/최저
        prices = [r["price"] for r in records if r["price"]]
        high = max(prices) if prices else last_price
        low = min(prices) if prices else last_price

        performances.append(
            {
                "ticker": ticker,
                "name": data["name"],
                "start_price": first_price,
                "end_price": last_price,
                "weekly_return": weekly_return,
                "high": high,
                "low": low,
                "data_points": len(records),
            }
        )

    performances.sort(key=lambda x: x["weekly_return"], reverse=True)
    return performances


def get_weekly_macro_history() -> list[dict]:
    """DB에서 매크로 지표 주간 히스토리 조회"""
    if not DB_PATH.exists():
        return []

    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()
        # 각 지표의 주초/주말 값 비교
        cursor.execute("""
            SELECT indicator, value, timestamp
            FROM macro
            WHERE timestamp >= datetime('now', '-7 days')
            ORDER BY indicator, timestamp
        """)
        rows = cursor.fetchall()
    finally:
        conn.close()

    # 지표별 주간 변동 계산
    by_indicator = {}
    for indicator, value, ts in rows:
        if indicator not in by_indicator:
            by_indicator[indicator] = []
        by_indicator[indicator].append({"value": value, "timestamp": ts})

    results = []
    for indicator, records in by_indicator.items():
        if len(records) < 2:
            continue
        first = records[0]["value"]
        last = records[-1]["value"]
        if first > 0:
            change = round((last - first) / first * 100, 2)
        else:
            change = 0.0
        results.append(
            {
                "indicator": indicator,
                "start_value": first,
                "end_value": last,
                "weekly_change": change,
            }
        )

    results.sort(key=lambda x: abs(x["weekly_change"]), reverse=True)
    return results


def format_weekly_performance(performances: list[dict]) -> str:
    """주간 포트폴리오 성과 섹션"""
    if not performances:
        return "## 📊 주간 포트폴리오 성과\n\n> DB 히스토리 부족 — 데이터 축적 후 사용 가능\n"

    lines = ["## 📊 주간 포트폴리오 성과\n"]
    lines.append("| 종목 | 주초 | 주말 | 주간 수익률 | 주간 고/저 |")
    lines.append("|------|------|------|-----------|----------|")

    for p in performances:
        flag = "🟢" if p["weekly_return"] >= 0 else "🔴"
        # 가격 형식 (한국 종목은 원, 해외는 $)
        is_kr = p["ticker"].endswith(".KS") or p["ticker"].endswith(".KQ")
        if is_kr:
            start_str = f"{p['start_price']:,.0f}원"
            end_str = f"{p['end_price']:,.0f}원"
            hl_str = f"{p['high']:,.0f} / {p['low']:,.0f}"
        else:
            start_str = f"${p['start_price']:,.2f}"
            end_str = f"${p['end_price']:,.2f}"
            hl_str = f"${p['high']:,.2f} / ${p['low']:,.2f}"

        lines.append(
            f"| {flag} {p['name']} | {start_str} | {end_str} | {p['weekly_return']:+.2f}% | {hl_str} |"
        )

    lines.append("")
    return "\n".join(lines)


def format_macro_weekly(macro_changes: list[dict]) -> str:
    """매크로 지표 주간 변동 섹션"""
    if not macro_changes:
        return "## 🌍 매크로 주간 변동\n\n> DB 히스토리 부족\n"

    lines = ["## 🌍 매크로 주간 변동\n"]
    lines.append("| 지표 | 주초 | 주말 | 주간 변동 |")
    lines.append("|------|------|------|---------|")

    for m in macro_changes:
        flag = "🟢" if m["weekly_change"] >= 0 else "🔴"
        if m["indicator"] == "원/달러":
            start_str = f"{m['start_value']:,.2f}원"
            end_str = f"{m['end_value']:,.2f}원"
        elif m["indicator"] in ("코스피", "코스닥", "VIX", "달러 인덱스"):
            start_str = f"{m['start_value']:,.2f}"
            end_str = f"{m['end_value']:,.2f}"
        else:
            start_str = f"${m['start_value']:,.2f}"
            end_str = f"${m['end_value']:,.2f}"

        lines.append(
            f"| {flag} {m['indicator']} | {start_str} | {end_str} | {m['weekly_change']:+.2f}% |"
        )

    lines.append("")
    return "\n".join(lines)


def format_portfolio_analysis(portfolio_data: dict | None) -> str:
    """포트폴리오 분석 결과 섹션"""
    if not portfolio_data:
        return "## 💼 포트폴리오 분석\n\n> portfolio_summary.json 없음 — portfolio.py 실행 필요\n"

    lines = ["## 💼 포트폴리오 분석\n"]

    # 총 수익률
    total = portfolio_data.get("total", {})
    if total.get("pnl_pct") is not None:
        flag = "🟢" if total["pnl_pct"] >= 0 else "🔴"
        lines.append(
            f"- {flag} **총 수익률**: {total['pnl_pct']:+.2f}% ({total['pnl_krw']:+,.0f}원)"
        )
        lines.append(
            f"- 투자금: {total['invested_krw']:,.0f}원 → 평가액: {total['current_value_krw']:,.0f}원"
        )
    lines.append(f"- 적용 환율: {portfolio_data.get('exchange_rate', 0):,.2f}원/USD")
    lines.append("")

    # 섹터 비중
    sectors = portfolio_data.get("sectors", [])
    if sectors:
        lines.append("### 섹터별 비중")
        lines.append("| 섹터 | 비중 | 수익률 | 종목 |")
        lines.append("|------|------|--------|------|")
        for s in sectors:
            pnl_str = f"{s['pnl_pct']:+.2f}%" if s.get("pnl_pct") is not None else "N/A"
            stocks_str = ", ".join(s.get("stocks", []))
            lines.append(
                f"| {s['sector']} | {s['weight_pct']}% | {pnl_str} | {stocks_str} |"
            )
        lines.append("")

    # 리스크 지표
    risk = portfolio_data.get("risk", {})
    if any(v is not None for v in risk.values()):
        lines.append("### 리스크 지표")
        if risk.get("volatility_daily") is not None:
            lines.append(f"- 일간 변동성: {risk['volatility_daily']}%")
        if risk.get("max_drawdown_pct") is not None:
            lines.append(f"- 최대 낙폭(MDD): -{risk['max_drawdown_pct']}%")
        if risk.get("worst_performer"):
            wp = risk["worst_performer"]
            lines.append(f"- 최악 종목: {wp['name']} ({wp['pnl_pct']:+.2f}%)")
        if risk.get("best_performer"):
            bp = risk["best_performer"]
            lines.append(f"- 최고 종목: {bp['name']} ({bp['pnl_pct']:+.2f}%)")
        lines.append("")

    return "\n".join(lines)


def format_screener_summary() -> str:
    """스크리너 결과 요약 (screener.md에서 주목 종목 추출)"""
    screener_path = OUTPUT_DIR / "screener.md"
    if not screener_path.exists():
        return "## 🔍 신규 주목 종목\n\n> screener.md 없음 — screener.py 실행 필요\n"

    with open(screener_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 스크리너 리포트에서 주목 종목 테이블 추출
    lines = ["## 🔍 신규 주목 종목\n"]

    # 주목 종목 섹션 찾기
    in_highlight = False
    for line in content.split("\n"):
        if "오늘의 주목 종목" in line:
            in_highlight = True
            continue
        if in_highlight:
            if line.startswith("---"):
                break
            if line.strip():
                lines.append(line)

    lines.append("")
    return "\n".join(lines)


def generate_weekly_report() -> str:
    """주간 리포트 마크다운 생성"""
    now = datetime.now(KST)
    # 이번주 월~일 범위
    monday = now - timedelta(days=now.weekday())
    sunday = monday + timedelta(days=6)
    week_range = f"{monday.strftime('%m/%d')}~{sunday.strftime('%m/%d')}"

    lines = [
        f"# 📊 주간 투자 리포트 — {now.strftime('%Y-%m-%d')}",
        f"> 기간: {week_range} | 생성: {now.strftime('%H:%M KST')}",
        "",
        "---",
        "",
    ]

    # 1. 주간 포트폴리오 성과
    history = get_weekly_price_history()
    performances = calculate_weekly_performance(history)
    lines.append(format_weekly_performance(performances))
    lines.append("---\n")

    # 2. 매크로 주간 변동
    macro_changes = get_weekly_macro_history()
    lines.append(format_macro_weekly(macro_changes))
    lines.append("---\n")

    # 3. 포트폴리오 분석 (portfolio_summary.json)
    portfolio_data = load_json("portfolio_summary.json")
    lines.append(format_portfolio_analysis(portfolio_data))
    lines.append("---\n")

    # 4. 신규 주목 종목 (screener.md)
    lines.append(format_screener_summary())
    lines.append("---\n")

    lines.append(f"*자동 생성 by investment-bot weekly | {now.isoformat()}*\n")

    return "\n".join(lines)


def run():
    """주간 리포트 생성 파이프라인"""
    print(f"\n📊 주간 리포트 생성 — {datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}")

    # DB 초기화 확인
    if not DB_PATH.exists():
        init_db()

    report = generate_weekly_report()

    # 저장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "weekly_report.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"  📄 주간 리포트 저장: {output_path}")
    print(f"  📏 크기: {len(report):,} bytes")
    print()

    return report


if __name__ == "__main__":
    run()

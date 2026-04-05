#!/usr/bin/env python3
"""
주간 리포트 생성 — 매주 월요일 실행
포트폴리오 주간 성과, 섹터 로테이션, 신규 주목 종목
출력: output/intel/weekly_report.md
"""

import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, OUTPUT_DIR
from db.init_db import init_db
from reports.weekly_formatters import (  # noqa: F401  re-export
    format_macro_weekly,
    format_portfolio_analysis,
    format_screener_summary,
    format_weekly_performance,
)

KST = timezone(timedelta(hours=9))


def load_json(filename: str) -> dict | None:
    """output/intel/ 에서 JSON 파일 로드"""
    path = OUTPUT_DIR / filename
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
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
    with output_path.open("w", encoding="utf-8") as f:
        f.write(report)

    print(f"  📄 주간 리포트 저장: {output_path}")
    print(f"  📏 크기: {len(report):,} bytes")
    print()

    return report


if __name__ == "__main__":
    run()

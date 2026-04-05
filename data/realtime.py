#!/usr/bin/env python3
"""
실시간 시세 조회 (stdout 마크다운 출력 전용)
자비스가 리포트 생성 시 호출하여 현재 수치를 즉석 확인하는 스크립트.
한국 주식: 키움증권 REST API (fallback: 네이버 금융 API) / 미국 주식·매크로: Yahoo Finance API
파일 저장 없음 — stdout에 마크다운 형식으로 출력.

사용법:
    python3 data/realtime.py

자비스 크론잡 프롬프트 통합 순서:
    1. DB 히스토리 읽기 → 최근 N일 추세 파악 (prices, macro 테이블)
    2. python3 data/realtime.py 실행 → 현재 실시간 수치 확보
    3. Brave Search API → 최신 뉴스/이벤트 수집
    4. 위 3가지를 조합하여 Discord 리포트 작성
"""

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, MACRO_INDICATORS

# 외부 수집 함수 re-export (하위 호환성)
from data.realtime_fetch import (  # noqa: F401
    NAVER_INDEX_CODES,
    _extract_kr_code,
    _fetch_kr_stock,
    _is_kr_ticker,
    fetch_gold_krw_per_gram,
    fetch_naver_index,
    fetch_naver_price,
    fetch_yahoo_quote,
)
from db.ssot import get_holdings

KST = timezone(timedelta(hours=9))

# 실시간 조회 대상 매크로 (요청된 6개)
REALTIME_MACRO_NAMES = {"코스피", "코스닥", "원/달러", "WTI 유가", "브렌트유", "VIX"}


def get_today_db_prices(ticker: str) -> list[dict]:
    """DB에서 오늘 수집된 해당 종목의 이력 조회"""
    if not DB_PATH.exists():
        return []
    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT price, timestamp FROM prices WHERE ticker = ? AND timestamp LIKE ? ORDER BY timestamp",
            (ticker, f"{today_str}%"),
        )
        return [{"price": row[0], "timestamp": row[1]} for row in cursor.fetchall()]
    finally:
        conn.close()


def get_today_db_macro(indicator: str) -> list[dict]:
    """DB에서 오늘 수집된 해당 매크로 지표 이력 조회"""
    if not DB_PATH.exists():
        return []
    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT value, timestamp FROM macro WHERE indicator = ? AND timestamp LIKE ? ORDER BY timestamp",
            (indicator, f"{today_str}%"),
        )
        return [{"value": row[0], "timestamp": row[1]} for row in cursor.fetchall()]
    finally:
        conn.close()


def fmt_change(pct):
    """변동률 포맷 (이모지 포함)"""
    if pct is None:
        return "N/A"
    arrow = "🔴" if pct < -1 else "🟢" if pct > 1 else "⚪"
    return f"{arrow} {pct:+.2f}%"


def fmt_price(val, currency="KRW"):
    """가격 포맷"""
    if val is None:
        return "N/A"
    if currency == "KRW":
        return f"{val:,.0f}"
    return f"{val:,.2f}"


def _fetch_stock_quote(ticker: str) -> tuple:
    """종목 티커에 맞는 API로 시세 조회.

    Returns:
        (price, prev_close, day_high, day_low) 튜플
    """
    if ticker == "GOLD_KRW_G":
        gold = fetch_gold_krw_per_gram()
        return gold["price"], gold["prev_close"], gold["high"], gold["low"]
    if _is_kr_ticker(ticker):
        kr = _fetch_kr_stock(_extract_kr_code(ticker))
        return kr["price"], kr["prev_close"], kr["high"], kr["low"]
    meta = fetch_yahoo_quote(ticker)
    price = meta["regularMarketPrice"]
    prev_close = meta.get("chartPreviousClose", meta.get("previousClose", price))
    return price, prev_close, meta.get("_dayHigh"), meta.get("_dayLow")


def _render_portfolio_section(holdings: list) -> list[str]:
    """포트폴리오 종목 섹션 마크다운 라인 목록 생성."""
    lines = []
    lines.append("## 💼 포트폴리오 종목")
    lines.append("")
    lines.append("> 오늘등락: 전일 대비 | 매입손익: 평균 매입가 대비\n")
    lines.append(
        "| 종목 | 현재가 | 오늘등락 | 매입손익 | 오늘 고가 | 오늘 저가 | 오전비 |"
    )
    lines.append(
        "|------|--------|----------|----------|-----------|-----------|--------|"
    )

    for stock in holdings:
        ticker = stock["ticker"]
        name = stock["name"]
        currency = stock.get("currency", "KRW")
        try:
            price, prev_close, day_high, day_low = _fetch_stock_quote(ticker)

            change_pct = (
                round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0
            )
            avg_cost = stock["avg_cost"]
            pnl_pct = (
                round((price - avg_cost) / avg_cost * 100, 2) if avg_cost > 0 else None
            )

            history = get_today_db_prices(ticker)
            if history:
                morning_price = history[0]["price"]
                morning_diff = round((price - morning_price) / morning_price * 100, 2)
                morning_str = fmt_change(morning_diff)
            else:
                morning_str = "—"

            lines.append(
                f"| {name} | {fmt_price(price, currency)} | {fmt_change(change_pct)} | {fmt_change(pnl_pct)} "
                f"| {fmt_price(day_high, currency)} | {fmt_price(day_low, currency)} | {morning_str} |"
            )
        except Exception as e:
            lines.append(f"| {name} | ❌ 조회실패 | — | — | — | — | — |")
            print(f"[오류] {name} ({ticker}): {e}", file=sys.stderr)

    return lines


def _render_macro_section() -> list[str]:
    """매크로 지표 섹션 마크다운 라인 목록 생성."""
    lines = []
    lines.append("## 🌍 매크로 지표")
    lines.append("")
    lines.append("| 지표 | 현재값 | 오늘등락 | 오전비 |")
    lines.append("|------|--------|----------|--------|")

    for ind in MACRO_INDICATORS:
        if ind["name"] not in REALTIME_MACRO_NAMES:
            continue
        ticker = ind["ticker"]
        name = ind["name"]
        try:
            if ticker in NAVER_INDEX_CODES:
                naver = fetch_naver_index(ticker)
                value = naver["price"]
                change_pct = naver["change_pct"]
            else:
                meta = fetch_yahoo_quote(ticker)
                value = meta["regularMarketPrice"]
                prev_close = meta.get(
                    "chartPreviousClose", meta.get("previousClose", value)
                )
                change_pct = (
                    round((value - prev_close) / prev_close * 100, 2)
                    if prev_close
                    else 0.0
                )

            history = get_today_db_macro(name)
            if history:
                morning_val = history[0]["value"]
                morning_diff = round((value - morning_val) / morning_val * 100, 2)
                morning_str = fmt_change(morning_diff)
            else:
                morning_str = "—"

            val_str = f"{value:,.2f}원" if ticker == "KRW=X" else f"{value:,.2f}"
            lines.append(
                f"| {name} | {val_str} | {fmt_change(change_pct)} | {morning_str} |"
            )

        except Exception as e:
            lines.append(f"| {name} | ❌ 조회실패 | — | — |")
            print(f"[오류] {name} ({ticker}): {e}", file=sys.stderr)

    return lines


def run():
    """실시간 시세 조회 후 마크다운 출력"""
    now = datetime.now(KST)
    lines = []
    lines.append(f"# 📡 실시간 시세 — {now.strftime('%H:%M')} KST")
    lines.append(f"> 조회 시각: {now.strftime('%Y-%m-%d %H:%M:%S')} KST\n")

    # ── 1. 포트폴리오 종목 ──
    holdings = get_holdings()
    lines.extend(_render_portfolio_section(holdings))

    # ── 2. 매크로 지표 ──
    lines.append("")
    lines.extend(_render_macro_section())

    lines.append("")
    lines.append(f"---\n_수집 완료: {datetime.now(KST).strftime('%H:%M')} KST_")

    # stdout으로 마크다운 출력
    print("\n".join(lines))


if __name__ == "__main__":
    run()

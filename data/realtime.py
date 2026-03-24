#!/usr/bin/env python3
"""
실시간 시세 조회 (stdout 마크다운 출력 전용)
자비스가 리포트 생성 시 호출하여 현재 수치를 즉석 확인하는 스크립트.
한국 주식: 네이버 금융 API / 미국 주식·매크로: Yahoo Finance API
파일 저장 없음 — stdout에 마크다운 형식으로 출력.

사용법:
    python3 data/realtime.py

자비스 크론잡 프롬프트 통합 순서:
    1. DB 히스토리 읽기 → 최근 N일 추세 파악 (prices, macro 테이블)
    2. python3 data/realtime.py 실행 → 현재 실시간 수치 확보
    3. Brave Search API → 최신 뉴스/이벤트 수집
    4. 위 3가지를 조합하여 텔레그램 리포트 작성
"""
import json
import sqlite3
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import PORTFOLIO, MACRO_INDICATORS, DB_PATH, YAHOO_HEADERS, YAHOO_TIMEOUT, get_market

KST = timezone(timedelta(hours=9))

# 실시간 조회 대상 매크로 (요청된 6개)
REALTIME_MACRO_NAMES = {"코스피", "코스닥", "원/달러", "WTI 유가", "브렌트유", "VIX"}


def _is_kr_ticker(ticker: str) -> bool:
    """한국 주식 티커 여부 (.KS 또는 .KQ)"""
    return ticker.endswith(".KS") or ticker.endswith(".KQ")


def _extract_kr_code(ticker: str) -> str:
    """티커에서 6자리 종목코드 추출 (005930.KS → 005930)"""
    return ticker.split(".")[0]


def fetch_naver_price(code: str) -> dict:
    """네이버 금융 실시간 주가 조회 (한국 주식 전용)"""
    url = f"https://polling.finance.naver.com/api/realtime/domestic/stock/{code}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://finance.naver.com"
    })
    with urllib.request.urlopen(req, timeout=8) as r:
        d = json.load(r)
    data = d["datas"][0]
    price = int(data["closePrice"].replace(",", ""))
    change = int(data["compareToPreviousClosePrice"].replace(",", ""))
    prev_close = price - change
    return {
        "price": price,
        "prev_close": prev_close,
        "change_pct": float(data["fluctuationsRatio"]),
        "volume": int(data["accumulatedTradingVolume"].replace(",", "")),
        "high": int(data["highPrice"].replace(",", "")),
        "low": int(data["lowPrice"].replace(",", "")),
    }


def fetch_yahoo_quote(ticker: str) -> dict:
    """Yahoo Finance에서 단일 종목/지표 시세 조회"""
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
    req = urllib.request.Request(url, headers=YAHOO_HEADERS)
    with urllib.request.urlopen(req, timeout=YAHOO_TIMEOUT) as resp:
        data = json.load(resp)
        result = data["chart"]["result"]
        if not result:
            raise ValueError(f"데이터 없음: {ticker}")
        meta = result[0]["meta"]
        # 장중 고가/저가 추출
        indicators = result[0].get("indicators", {}).get("quote", [{}])[0]
        if indicators.get("high"):
            meta["_dayHigh"] = max(h for h in indicators["high"] if h is not None) if any(h is not None for h in indicators["high"]) else None
        if indicators.get("low"):
            meta["_dayLow"] = min(l for l in indicators["low"] if l is not None) if any(l is not None for l in indicators["low"]) else None
        return meta


def fetch_gold_krw_per_gram() -> dict:
    """금 현물 원화/g 가격 계산"""
    gold_meta = fetch_yahoo_quote("GC=F")
    fx_meta = fetch_yahoo_quote("KRW=X")
    gold_usd = gold_meta["regularMarketPrice"]
    usd_krw = fx_meta["regularMarketPrice"]
    gold_prev = gold_meta.get("chartPreviousClose", gold_meta.get("previousClose", gold_usd))
    fx_prev = fx_meta.get("chartPreviousClose", fx_meta.get("previousClose", usd_krw))

    price = round(gold_usd * usd_krw / 31.1035, 0)
    prev_close = round(gold_prev * fx_prev / 31.1035, 0)
    return {"price": price, "prev_close": prev_close, "high": None, "low": None}


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


def run():
    """실시간 시세 조회 후 마크다운 출력"""
    now = datetime.now(KST)
    lines = []
    lines.append(f"# 📡 실시간 시세 — {now.strftime('%H:%M')} KST")
    lines.append(f"> 조회 시각: {now.strftime('%Y-%m-%d %H:%M:%S')} KST\n")

    # ── 1. 포트폴리오 종목 ──
    lines.append("## 💼 포트폴리오 종목")
    lines.append("")
    lines.append("| 종목 | 현재가 | 전일비 | 평단비 | 오늘 고가 | 오늘 저가 | 오전비 |")
    lines.append("|------|--------|--------|--------|-----------|-----------|--------|")

    for stock in PORTFOLIO:
        ticker = stock["ticker"]
        name = stock["name"]
        currency = stock["currency"]
        try:
            if ticker == "GOLD_KRW_G":
                gold = fetch_gold_krw_per_gram()
                price = gold["price"]
                prev_close = gold["prev_close"]
                day_high = gold["high"]
                day_low = gold["low"]
            elif _is_kr_ticker(ticker):
                # 한국 주식 → 네이버 금융 API
                naver = fetch_naver_price(_extract_kr_code(ticker))
                price = naver["price"]
                prev_close = naver["prev_close"]
                day_high = naver["high"]
                day_low = naver["low"]
            else:
                meta = fetch_yahoo_quote(ticker)
                price = meta["regularMarketPrice"]
                prev_close = meta.get("chartPreviousClose", meta.get("previousClose", price))
                day_high = meta.get("_dayHigh")
                day_low = meta.get("_dayLow")

            change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0
            avg_cost = stock["avg_cost"]
            pnl_pct = round((price - avg_cost) / avg_cost * 100, 2) if avg_cost > 0 else None

            # DB 이력 비교: 오전 첫 수집 대비 변화
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

    # ── 2. 매크로 지표 ──
    lines.append("")
    lines.append("## 🌍 매크로 지표")
    lines.append("")
    lines.append("| 지표 | 현재값 | 전일비 | 오전비 |")
    lines.append("|------|--------|--------|--------|")

    for ind in MACRO_INDICATORS:
        if ind["name"] not in REALTIME_MACRO_NAMES:
            continue
        ticker = ind["ticker"]
        name = ind["name"]
        try:
            meta = fetch_yahoo_quote(ticker)
            value = meta["regularMarketPrice"]
            prev_close = meta.get("chartPreviousClose", meta.get("previousClose", value))
            change_pct = round((value - prev_close) / prev_close * 100, 2) if prev_close else 0.0

            # DB 이력 비교
            history = get_today_db_macro(name)
            if history:
                morning_val = history[0]["value"]
                morning_diff = round((value - morning_val) / morning_val * 100, 2)
                morning_str = fmt_change(morning_diff)
            else:
                morning_str = "—"

            # 환율은 원 단위, 나머지는 소수점 2자리
            if ticker == "KRW=X":
                val_str = f"{value:,.2f}원"
            else:
                val_str = f"{value:,.2f}"

            lines.append(f"| {name} | {val_str} | {fmt_change(change_pct)} | {morning_str} |")

        except Exception as e:
            lines.append(f"| {name} | ❌ 조회실패 | — | — |")
            print(f"[오류] {name} ({ticker}): {e}", file=sys.stderr)

    lines.append("")
    lines.append(f"---\n_수집 완료: {datetime.now(KST).strftime('%H:%M')} KST_")

    # stdout으로 마크다운 출력
    print("\n".join(lines))


if __name__ == "__main__":
    run()

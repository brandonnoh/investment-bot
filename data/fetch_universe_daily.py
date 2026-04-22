#!/usr/bin/env python3
"""
유니버스 전체 일봉 & 펀더멘탈 사전 수집 모듈

KOSPI200 50개 + SP100 100개 = 총 150개 티커의
- prices_daily: 최근 90일 일봉 (UPSERT)
- fundamentals: PER/PBR/ROE/시총 (UPSERT)

파이프라인 실행(07:40) 전에 실행 권장.
value_screener 등이 DB 쿼리만으로 빠르게 스크리닝 가능.
"""

import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis.screener_universe import UNIVERSE_KOSPI200, UNIVERSE_SP100  # noqa: E402

# ── 상수 ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "history.db"
KST = timezone(timedelta(hours=9))
YAHOO_CHART_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=90d"
YAHOO_SUMMARY_URL = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules=financialData,defaultKeyStatistics,summaryDetail"
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
TIMEOUT = 10
RATE_LIMIT_BATCH = 20
RATE_LIMIT_SLEEP = 0.5


# ── HTTP 유틸 ──

def _fetch_json(url: str) -> dict:
    """URL에서 JSON 응답 반환 (urllib.request 사용)"""
    req = urllib.request.Request(url, headers=HTTP_HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── 일봉 수집 ──

def _parse_daily_rows(ticker: str, data: dict) -> list[dict]:
    """Yahoo Finance chart 응답 → prices_daily 행 리스트 변환"""
    result = data.get("chart", {}).get("result", [])
    if not result:
        return []
    r = result[0]
    timestamps = r.get("timestamp", [])
    quote = r.get("indicators", {}).get("quote", [{}])[0]
    opens = quote.get("open", [])
    highs = quote.get("high", [])
    lows = quote.get("low", [])
    closes = quote.get("close", [])
    volumes = quote.get("volume", [])

    rows = []
    prev_close = None
    for i, ts in enumerate(timestamps):
        close = closes[i] if i < len(closes) else None
        if close is None:
            prev_close = None
            continue
        date_str = datetime.fromtimestamp(ts, tz=KST).strftime("%Y-%m-%d")
        change_pct = round((close - prev_close) / prev_close * 100, 4) if prev_close else 0.0
        rows.append({
            "ticker": ticker,
            "date": date_str,
            "open": opens[i] if i < len(opens) else 0,
            "high": highs[i] if i < len(highs) else 0,
            "low": lows[i] if i < len(lows) else 0,
            "close": close,
            "volume": volumes[i] if i < len(volumes) else 0,
            "change_pct": change_pct,
        })
        prev_close = close
    return rows


def fetch_daily(ticker: str) -> list[dict]:
    """단일 티커 일봉 수집 (최근 90일)"""
    url = YAHOO_CHART_URL.format(ticker=urllib.request.quote(ticker, safe=""))
    data = _fetch_json(url)
    return _parse_daily_rows(ticker, data)


# ── 펀더멘탈 수집 ──

def _extract_val(module: dict, key: str) -> float | None:
    """모듈 딕셔너리에서 rawValue 추출 (없으면 None)"""
    entry = module.get(key, {})
    if isinstance(entry, dict):
        return entry.get("raw")
    return None


def fetch_fundamentals(ticker: str, name: str, market: str) -> dict | None:
    """단일 티커 펀더멘탈 수집 (PER/PBR/ROE/시총)"""
    url = YAHOO_SUMMARY_URL.format(ticker=urllib.request.quote(ticker, safe=""))
    data = _fetch_json(url)
    result = data.get("quoteSummary", {}).get("result", [])
    if not result:
        return None
    r = result[0]
    fd = r.get("financialData", {})
    ks = r.get("defaultKeyStatistics", {})
    sd = r.get("summaryDetail", {})

    roe_raw = _extract_val(fd, "returnOnEquity")
    return {
        "ticker": ticker,
        "name": name,
        "market": market,
        "per": _extract_val(ks, "trailingPE") or _extract_val(sd, "trailingPE"),
        "pbr": _extract_val(ks, "priceToBook"),
        "roe": round(roe_raw * 100, 4) if roe_raw is not None else None,
        "market_cap": _extract_val(ks, "marketCap") or _extract_val(sd, "marketCap"),
    }


# ── DB 저장 ──

def _upsert_daily_rows(conn: sqlite3.Connection, rows: list[dict]) -> None:
    """prices_daily 테이블에 UPSERT"""
    sql = """
        INSERT OR REPLACE INTO prices_daily
            (ticker, date, open, high, low, close, volume, change_pct, data_source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'yahoo_universe')
    """
    conn.executemany(sql, [
        (
            r["ticker"], r["date"],
            r["open"] or 0, r["high"] or 0, r["low"] or 0,
            r["close"], r["volume"] or 0,
            r["change_pct"],
        )
        for r in rows
    ])


def _upsert_fundamental(conn: sqlite3.Connection, f: dict) -> None:
    """fundamentals 테이블에 UPSERT (ticker 기준)"""
    now = datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    sql = """
        INSERT INTO fundamentals
            (ticker, name, market, per, pbr, roe, market_cap, data_source, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'yahoo_universe', ?)
        ON CONFLICT(ticker) DO UPDATE SET
            name=excluded.name,
            per=excluded.per,
            pbr=excluded.pbr,
            roe=excluded.roe,
            market_cap=excluded.market_cap,
            data_source='yahoo_universe',
            updated_at=excluded.updated_at
    """
    conn.execute(sql, (
        f["ticker"], f["name"], f["market"],
        f["per"], f["pbr"], f["roe"], f["market_cap"], now,
    ))


# ── 메인 ──

def _process_ticker(conn: sqlite3.Connection, info: dict) -> bool:
    """단일 티커 처리 (일봉 + 펀더멘탈). 성공 시 True 반환."""
    ticker = info["ticker"]
    name = info["name"]
    market = info["market"]
    try:
        rows = fetch_daily(ticker)
        if rows:
            _upsert_daily_rows(conn, rows)
        fund = fetch_fundamentals(ticker, name, market)
        if fund:
            _upsert_fundamental(conn, fund)
        return True
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        print(f"    [WARN] {ticker} 네트워크 오류 — {e}")
    except (KeyError, IndexError, ValueError, json.JSONDecodeError) as e:
        print(f"    [WARN] {ticker} 파싱 오류 — {e}")
    except Exception as e:  # noqa: BLE001
        print(f"    [WARN] {ticker} 알 수 없는 오류 — {e}")
    return False


def run() -> dict:
    """유니버스 전체 일봉 + 펀더멘탈 수집 실행"""
    universe = UNIVERSE_KOSPI200 + UNIVERSE_SP100
    total = len(universe)
    success = 0
    fail = 0

    print(f"[fetch_universe_daily] 유니버스 {total}개 수집 시작...")
    conn = sqlite3.connect(DB_PATH)
    try:
        for i, info in enumerate(universe):
            ok = _process_ticker(conn, info)
            if ok:
                success += 1
            else:
                fail += 1
            # 레이트 리밋 방지: 20개마다 0.5초 대기
            if (i + 1) % RATE_LIMIT_BATCH == 0:
                conn.commit()
                elapsed = i + 1
                print(f"    {elapsed}/{total} 처리 완료 (성공 {success} / 실패 {fail})...")
                time.sleep(RATE_LIMIT_SLEEP)
        conn.commit()
    finally:
        conn.close()

    print(f"[fetch_universe_daily] 완료 — 성공 {success} / 실패 {fail} / 전체 {total}")
    return {"success": success, "fail": fail, "total": total}


if __name__ == "__main__":
    result = run()
    print(result)

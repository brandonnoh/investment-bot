#!/usr/bin/env python3
"""
실시간 포트폴리오 주가 수집 + SQLite 저장
한국 주식: 네이버 금융 API / 미국 주식: Yahoo Finance API
출력: output/intel/prices.json
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
from config import PORTFOLIO, DB_PATH, OUTPUT_DIR, YAHOO_HEADERS, YAHOO_TIMEOUT, get_market
from db.init_db import init_db

# 한국 시간대
KST = timezone(timedelta(hours=9))


def fetch_yahoo_quote(ticker: str) -> dict:
    """Yahoo Finance에서 단일 종목 시세 조회"""
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
    req = urllib.request.Request(url, headers=YAHOO_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=YAHOO_TIMEOUT) as resp:
            data = json.load(resp)
            result = data["chart"]["result"]
            if not result:
                raise ValueError(f"데이터 없음: {ticker}")
            return result[0]["meta"]
    except urllib.error.URLError as e:
        raise ConnectionError(f"네트워크 오류 ({ticker}): {e}")
    except (KeyError, IndexError) as e:
        raise ValueError(f"응답 파싱 실패 ({ticker}): {e}")


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
    try:
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
    except urllib.error.URLError as e:
        raise ConnectionError(f"네이버 API 네트워크 오류 ({code}): {e}")
    except (KeyError, IndexError) as e:
        raise ValueError(f"네이버 API 응답 파싱 실패 ({code}): {e}")


def fetch_gold_krw_per_gram() -> tuple[float, float]:
    """금 현물 원화/g 가격 계산: GC=F(달러/트로이온스) × KRW=X(환율) ÷ 31.1035"""
    gold_meta = fetch_yahoo_quote("GC=F")
    fx_meta = fetch_yahoo_quote("KRW=X")
    gold_usd = gold_meta["regularMarketPrice"]
    usd_krw = fx_meta["regularMarketPrice"]
    gold_prev = gold_meta.get("chartPreviousClose", gold_meta.get("previousClose", gold_usd))
    fx_prev = fx_meta.get("chartPreviousClose", fx_meta.get("previousClose", usd_krw))

    price_krw_g = gold_usd * usd_krw / 31.1035
    prev_krw_g = gold_prev * fx_prev / 31.1035
    return round(price_krw_g, 0), round(prev_krw_g, 0)


def collect_prices() -> list[dict]:
    """포트폴리오 전 종목 시세 수집"""
    now = datetime.now(KST).isoformat()
    results = []

    for stock in PORTFOLIO:
        ticker = stock["ticker"]
        name = stock["name"]
        try:
            # 금 현물(원/g) 커스텀 처리
            if ticker == "GOLD_KRW_G":
                price, prev_close = fetch_gold_krw_per_gram()
                volume = 0
            elif _is_kr_ticker(ticker):
                # 한국 주식 → 네이버 금융 API
                naver = fetch_naver_price(_extract_kr_code(ticker))
                price = naver["price"]
                prev_close = naver["prev_close"]
                volume = naver["volume"]
            else:
                meta = fetch_yahoo_quote(ticker)
                price = meta["regularMarketPrice"]
                prev_close = meta.get("chartPreviousClose", meta.get("previousClose", price))
                volume = meta.get("regularMarketVolume", 0)

            # 전일 대비 변동률
            change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0

            # 평단 대비 손익률
            avg_cost = stock["avg_cost"]
            pnl_pct = round((price - avg_cost) / avg_cost * 100, 2) if avg_cost > 0 else None

            record = {
                "ticker": ticker,
                "name": name,
                "price": price,
                "prev_close": prev_close,
                "change_pct": change_pct,
                "volume": volume,
                "avg_cost": avg_cost,
                "pnl_pct": pnl_pct,
                "currency": stock["currency"],
                "qty": stock["qty"],
                "account": stock["account"],
                "market": get_market(ticker),
                "timestamp": now,
            }
            results.append(record)
            print(f"  ✅ {name} ({ticker}): {price:,.2f} ({change_pct:+.2f}%)")

        except Exception as e:
            print(f"  ❌ {name} ({ticker}): {e}")
            # 실패해도 나머지 종목은 계속 수집
            results.append({
                "ticker": ticker,
                "name": name,
                "price": None,
                "prev_close": None,
                "change_pct": None,
                "volume": None,
                "avg_cost": stock["avg_cost"],
                "pnl_pct": None,
                "currency": stock["currency"],
                "qty": stock["qty"],
                "account": stock["account"],
                "market": get_market(ticker),
                "timestamp": now,
                "error": str(e),
            })

    return results


def save_to_db(records: list[dict]):
    """수집된 시세를 SQLite에 저장"""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()
        inserted = 0

        for r in records:
            if r.get("price") is None:
                continue  # 에러 난 종목은 DB에 저장하지 않음
            cursor.execute(
                """INSERT INTO prices (ticker, name, price, prev_close, change_pct, volume, timestamp, market)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (r["ticker"], r["name"], r["price"], r["prev_close"],
                 r["change_pct"], r["volume"], r["timestamp"], r["market"]),
            )
            inserted += 1

        conn.commit()
        print(f"  💾 DB 저장 완료: {inserted}건")
    finally:
        conn.close()


def save_to_json(records: list[dict]):
    """수집된 시세를 JSON 파일로 출력"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "prices.json"

    output = {
        "updated_at": datetime.now(KST).isoformat(),
        "count": len([r for r in records if r.get("price") is not None]),
        "prices": records,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  📄 JSON 저장: {output_path}")


def run():
    """주가 수집 파이프라인 실행"""
    print(f"\n📊 주가 수집 시작 — {datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}")

    # DB 초기화 확인
    if not DB_PATH.exists():
        init_db()

    # 시세 수집
    records = collect_prices()

    # 저장
    save_to_db(records)
    save_to_json(records)

    success = len([r for r in records if r.get("price") is not None])
    fail = len(records) - success
    print(f"\n✅ 수집 완료: 성공 {success}건, 실패 {fail}건\n")

    return records


if __name__ == "__main__":
    run()

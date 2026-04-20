#!/usr/bin/env python3
"""
실시간 포트폴리오 주가 수집 + SQLite 저장
한국 주식: 키움증권 REST API (fallback: 네이버 금융 API) / 미국 주식: Yahoo Finance API
출력: output/intel/prices.json
"""

import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (
    DB_PATH,
    HTTP_RETRY_CONFIG,
    OUTPUT_DIR,
    YAHOO_HEADERS,
    YAHOO_TIMEOUT,
    get_market,
)
from data.fetch_prices_kr import (
    _extract_kr_code,
    _fetch_kr_stock,
    _is_kr_ticker,
    fetch_naver_price,  # noqa: F401 — 테스트 mock 네임스페이스 호환
)
from db.init_db import init_db
from db.ssot import get_holdings
from utils.http import retry_request, validate_price_data

# 한국 시간대
KST = timezone(timedelta(hours=9))


def fetch_yahoo_quote(ticker: str) -> dict:
    """Yahoo Finance에서 단일 종목 시세 조회 (자동 재시도)"""
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
    try:
        body = retry_request(
            url,
            headers=YAHOO_HEADERS,
            timeout=YAHOO_TIMEOUT,
            max_retries=HTTP_RETRY_CONFIG["max_retries"],
            base_delay=HTTP_RETRY_CONFIG["base_delay"],
        )
        data = json.loads(body)
        result = data["chart"]["result"]
        if not result:
            raise ValueError(f"데이터 없음: {ticker}")
        return result[0]["meta"]
    except urllib.error.URLError as e:
        raise ConnectionError(f"네트워크 오류 ({ticker}): {e}") from e
    except (KeyError, IndexError) as e:
        raise ValueError(f"응답 파싱 실패 ({ticker}): {e}") from e


def _fetch_gold_usd_per_oz() -> tuple[float, float, str]:
    """
    금 USD/oz 시세 수집.
    1순위: GC=F (금 선물), 2순위: GLD (금 ETF — 1/10 oz), 3순위: IAU (금 ETF — 1/100 oz)

    Returns:
        (price_usd_oz, prev_usd_oz, data_source)
    """
    # GC=F: 금 선물 (troy oz 기준)
    try:
        meta = fetch_yahoo_quote("GC=F")
        price = meta["regularMarketPrice"]
        prev = meta.get("chartPreviousClose", meta.get("previousClose", price))
        return price, prev, "GC=F"
    except Exception as e:
        print(f"  ⚠️ GC=F 조회 실패, GLD fallback: {e}")

    # GLD: SPDR Gold Shares (1주 = 0.0926 troy oz)
    GLD_OZ_PER_SHARE = 0.0926
    try:
        meta = fetch_yahoo_quote("GLD")
        price = meta["regularMarketPrice"] / GLD_OZ_PER_SHARE
        prev_raw = meta.get(
            "chartPreviousClose", meta.get("previousClose", meta["regularMarketPrice"])
        )
        prev = prev_raw / GLD_OZ_PER_SHARE
        return price, prev, "GLD"
    except Exception as e:
        print(f"  ⚠️ GLD 조회 실패, IAU fallback: {e}")

    # IAU: iShares Gold Trust (1주 = 0.01 troy oz)
    IAU_OZ_PER_SHARE = 0.01
    meta = fetch_yahoo_quote("IAU")
    price = meta["regularMarketPrice"] / IAU_OZ_PER_SHARE
    prev_raw = meta.get("chartPreviousClose", meta.get("previousClose", meta["regularMarketPrice"]))
    prev = prev_raw / IAU_OZ_PER_SHARE
    return price, prev, "IAU"


def fetch_gold_krw_per_gram() -> tuple[float, float, str, str | None]:
    """
    금 현물 원화/g 가격 계산.
    1순위: 키움증권 KRX 금 현물(4001) API
    2순위(fallback): GC=F(→GLD→IAU) × KRW=X ÷ 31.1035

    Returns:
        (price, prev_close, data_source, calc_method)
    """
    # 키움 API 사용 가능 시 KRX 금 현물 직접 조회
    if os.environ.get("KIWOOM_APPKEY"):
        try:
            from data.fetch_gold_krx import fetch_gold_krx

            krx = fetch_gold_krx()
            print("  🥇 KRX 금 현물(키움 API) 사용")
            return krx["price"], krx["prev_close"], "kiwoom", None
        except Exception as e:
            print(f"  ⚠️ 키움 API 실패, Yahoo fallback: {e}")

    # fallback: 금 USD/oz (GC=F→GLD→IAU) × 환율 ÷ 31.1035
    gold_usd, gold_prev, gold_src = _fetch_gold_usd_per_oz()
    fx_meta = fetch_yahoo_quote("KRW=X")
    usd_krw = fx_meta["regularMarketPrice"]
    fx_prev = fx_meta.get("chartPreviousClose", fx_meta.get("previousClose", usd_krw))

    price_krw_g = gold_usd * usd_krw / 31.1035
    prev_krw_g = gold_prev * fx_prev / 31.1035
    calc_method = f"{gold_src} × KRW=X ÷ 31.1035"
    print(f"  ℹ️ 금 시세 소스: {gold_src}")
    return (
        round(price_krw_g, 0),
        round(prev_krw_g, 0),
        "calculated",
        calc_method,
    )


def collect_prices() -> list[dict]:
    """포트폴리오 전 종목 시세 수집 (SSoT: DB holdings 테이블 사용)"""
    now = datetime.now(KST).isoformat()
    results = []

    # SSoT: DB에서 보유 종목 로드
    holdings = get_holdings()

    for stock in holdings:
        ticker = stock["ticker"]
        name = stock["name"]
        try:
            # 금 현물(원/g) 커스텀 처리
            data_source = None
            calc_method = None
            if ticker == "GOLD_KRW_G":
                price, prev_close, data_source, calc_method = fetch_gold_krw_per_gram()
                volume = 0
            elif _is_kr_ticker(ticker):
                # 한국 주식 → 키움증권 API (fallback: 네이버 금융)
                kr_code = _extract_kr_code(ticker)
                kr_data = _fetch_kr_stock(kr_code)
                price = kr_data["price"]
                prev_close = kr_data["prev_close"]
                volume = kr_data["volume"]
                data_source = kr_data["data_source"]
            else:
                meta = fetch_yahoo_quote(ticker)
                price = meta["regularMarketPrice"]
                prev_close = meta.get("chartPreviousClose", meta.get("previousClose", price))
                volume = meta.get("regularMarketVolume", 0)
                data_source = "yahoo"

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
                "currency": stock.get("currency", "KRW"),
                "qty": stock.get("qty", 0),
                "sector": stock.get("sector", ""),
                "market": get_market(ticker),
                "timestamp": now,
                "data_source": data_source,
            }
            # 매입 시점 환율 (환율 손익 분리용)
            if stock.get("buy_fx_rate"):
                record["buy_fx_rate"] = stock["buy_fx_rate"]
            if calc_method:
                record["calc_method"] = calc_method
            # 이상값 검증
            for warning in validate_price_data(price, prev_close, ticker):
                print(f"  ⚠️ {warning}")

            results.append(record)
            print(f"  ✅ {name} ({ticker}): {price:,.2f} ({change_pct:+.2f}%)")

        except Exception as e:
            print(f"  ❌ {name} ({ticker}): {e}")
            # 실패해도 나머지 종목은 계속 수집
            error_record = {
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
                "data_source": None,
                "error": str(e),
            }
            if stock.get("buy_fx_rate"):
                error_record["buy_fx_rate"] = stock["buy_fx_rate"]
            results.append(error_record)

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
                """INSERT OR IGNORE INTO prices (ticker, name, price, prev_close, change_pct, volume, timestamp, market, data_source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    r["ticker"],
                    r["name"],
                    r["price"],
                    r["prev_close"],
                    r["change_pct"],
                    r["volume"],
                    r["timestamp"],
                    r["market"],
                    r.get("data_source"),
                ),
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
    with output_path.open("w", encoding="utf-8") as f:
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

#!/usr/bin/env python3
"""
외부 데이터 수집 함수 모음 (realtime.py에서 분리)
네이버 금융, Yahoo Finance, 키움증권 API를 통해 실시간 시세를 조회한다.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import YAHOO_HEADERS, YAHOO_TIMEOUT

# 네이버 지수 조회 대상 (코스피/코스닥)
NAVER_INDEX_CODES = {"KOSPI", "KOSDAQ"}


def _is_kr_ticker(ticker: str) -> bool:
    """한국 주식 티커 여부 (.KS 또는 .KQ)"""
    return ticker.endswith(".KS") or ticker.endswith(".KQ")


def _extract_kr_code(ticker: str) -> str:
    """티커에서 6자리 종목코드 추출 (005930.KS → 005930)"""
    return ticker.split(".")[0]


def fetch_naver_price(code: str) -> dict:
    """네이버 금융 실시간 주가 조회 (한국 주식 전용)"""
    url = f"https://polling.finance.naver.com/api/realtime/domestic/stock/{code}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com"},
    )
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


def _fetch_kr_stock(code: str) -> dict:
    """
    한국 주식 현재가 조회.
    1순위: 키움증권 REST API (ka10007)
    2순위(fallback): 네이버 금융 API
    """
    if os.environ.get("KIWOOM_APPKEY"):
        try:
            from data.fetch_gold_krx import fetch_kiwoom_stock

            result = fetch_kiwoom_stock(code)
            return result
        except Exception as e:
            print(f"  ⚠️ 키움 API 실패 ({code}), 네이버 fallback: {e}", file=sys.stderr)

    return fetch_naver_price(code)


def fetch_naver_index(code: str) -> dict:
    """네이버 금융 실시간 지수 조회 (코스피/코스닥)"""
    url = f"https://polling.finance.naver.com/api/realtime/domestic/index/{code}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com"},
    )
    with urllib.request.urlopen(req, timeout=8) as r:
        d = json.load(r)
    data = d["datas"][0]
    price = float(data["closePrice"].replace(",", ""))
    change_pct = float(data["fluctuationsRatio"])
    return {"price": price, "change_pct": change_pct}


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
            meta["_dayHigh"] = (
                max(h for h in indicators["high"] if h is not None)
                if any(h is not None for h in indicators["high"])
                else None
            )
        if indicators.get("low"):
            meta["_dayLow"] = (
                min(v for v in indicators["low"] if v is not None)
                if any(v is not None for v in indicators["low"])
                else None
            )
        return meta


def fetch_gold_krw_per_gram() -> dict:
    """
    금 현물 원화/g 가격 계산.
    1순위: 키움증권 KRX 금 현물(4001) API
    2순위(fallback): GC=F × KRW=X ÷ 31.1035
    """
    if os.environ.get("KIWOOM_APPKEY"):
        try:
            from data.fetch_gold_krx import fetch_gold_krx

            krx = fetch_gold_krx()
            print("  🥇 KRX 금 현물(키움 API) 사용", file=sys.stderr)
            return {
                "price": krx["price"],
                "prev_close": krx["prev_close"],
                "high": krx["high"],
                "low": krx["low"],
            }
        except Exception as e:
            print(f"  ⚠️ 키움 API 실패, Yahoo fallback: {e}", file=sys.stderr)

    gold_meta = fetch_yahoo_quote("GC=F")
    fx_meta = fetch_yahoo_quote("KRW=X")
    gold_usd = gold_meta["regularMarketPrice"]
    usd_krw = fx_meta["regularMarketPrice"]
    gold_prev = gold_meta.get(
        "chartPreviousClose", gold_meta.get("previousClose", gold_usd)
    )
    fx_prev = fx_meta.get("chartPreviousClose", fx_meta.get("previousClose", usd_krw))

    price = round(gold_usd * usd_krw / 31.1035, 0)
    prev_close = round(gold_prev * fx_prev / 31.1035, 0)
    return {"price": price, "prev_close": prev_close, "high": None, "low": None}

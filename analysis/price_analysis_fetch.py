#!/usr/bin/env python3
"""
히스토리 수집 레이어 — Yahoo Finance / 네이버 금융
DB 데이터 부족 시 외부 API에서 일봉 역사 데이터를 보충한다.
"""

import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (
    YAHOO_HEADERS,
    YAHOO_TIMEOUT,
    HTTP_RETRY_CONFIG,
)
from utils.http import retry_request

KST = timezone(timedelta(hours=9))
logger = logging.getLogger(__name__)

# RSI/추세 분석에 필요한 최소 데이터 포인트
MIN_DATA_POINTS = 15


def fetch_yahoo_history(ticker):
    """Yahoo Finance에서 3개월 일봉 종가 리스트 가져오기

    Args:
        ticker: Yahoo Finance 티커 (예: TSLA, 005930.KS)
    Returns:
        list[dict]: [{"date": "2025-01-01", "close": 100.0, "high": 105.0, "low": 95.0}, ...]
                    오래된순 정렬, 실패 시 빈 리스트
    """
    url = (
        f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
        f"?interval=1d&range=3mo"
    )
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
            return []

        timestamps = result[0].get("timestamp", [])
        indicators = result[0].get("indicators", {})
        quotes = indicators.get("quote", [{}])[0]
        closes = quotes.get("close", [])
        highs = quotes.get("high", [])
        lows = quotes.get("low", [])

        history = []
        for i, ts in enumerate(timestamps):
            c = closes[i] if i < len(closes) else None
            h = highs[i] if i < len(highs) else None
            lo = lows[i] if i < len(lows) else None
            if c is not None:
                dt = datetime.fromtimestamp(ts, tz=KST)
                history.append(
                    {
                        "date": dt.strftime("%Y-%m-%d"),
                        "close": float(c),
                        "high": float(h) if h is not None else float(c),
                        "low": float(lo) if lo is not None else float(c),
                    }
                )
        return history

    except Exception as e:
        logger.warning(f"Yahoo 역사 데이터 실패 ({ticker}): {e}")
        return []


def fetch_naver_history(ticker):
    """네이버 금융에서 한국 종목 3개월 일봉 가져오기 (Yahoo 실패 시 대안)

    Args:
        ticker: Yahoo 티커 (예: 005930.KS)
    Returns:
        list[dict]: [{"date": ..., "close": ..., "high": ..., "low": ...}, ...]
                    오래된순 정렬, 실패 시 빈 리스트
    """
    if not (ticker.endswith(".KS") or ticker.endswith(".KQ")):
        return []

    code = ticker.split(".")[0]
    # 네이버 차트 API: 60일치 일봉 (count=90으로 3개월 커버)
    url = (
        f"https://fchart.stock.naver.com/siseJson.nhn"
        f"?symbol={code}&requestType=1&startTime=&endTime=&timeframe=day&count=90"
    )
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com"}
    try:
        body = retry_request(
            url,
            headers=headers,
            timeout=8,
            max_retries=HTTP_RETRY_CONFIG["max_retries"],
            base_delay=HTTP_RETRY_CONFIG["base_delay"],
        )
        # 네이버 응답: 문자열 배열 형태, 첫 줄은 헤더
        text = body.decode("cp949", errors="replace").strip()
        # JSON-like 파싱 — 각 줄이 ['날짜', 시가, 고가, 저가, 종가, 거래량]
        lines = text.strip().split("\n")
        history = []
        for line in lines[1:]:  # 첫 줄 헤더 건너뛰기
            line = line.strip().rstrip(",")
            if not line:
                continue
            try:
                # 문자열을 JSON으로 파싱
                row = json.loads(f"[{line}]")
                if len(row) >= 5:
                    date_str = str(row[0]).strip().strip("'\"")
                    # YYYYMMDD → YYYY-MM-DD
                    if len(date_str) == 8:
                        date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                    history.append(
                        {
                            "date": date_str,
                            "close": float(row[4]),
                            "high": float(row[2]),
                            "low": float(row[3]),
                        }
                    )
            except (json.JSONDecodeError, ValueError, IndexError):
                continue
        return history

    except Exception as e:
        logger.warning(f"네이버 역사 데이터 실패 ({ticker}): {e}")
        return []


def get_history_data(ticker):
    """종목의 역사 데이터를 Yahoo → 네이버 순서로 가져오기

    Returns:
        tuple: (list[dict], str) — (일봉 리스트, 데이터 소스명)
    """
    # Yahoo 먼저 시도
    history = fetch_yahoo_history(ticker)
    if len(history) >= MIN_DATA_POINTS:
        return history, "yahoo_history"

    # 한국 종목이면 네이버 대안
    if ticker.endswith(".KS") or ticker.endswith(".KQ"):
        naver_history = fetch_naver_history(ticker)
        if len(naver_history) >= MIN_DATA_POINTS:
            return naver_history, "naver_history"

    # 부분 데이터라도 반환
    if history:
        return history, "yahoo_history"
    return [], "none"

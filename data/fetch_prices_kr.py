#!/usr/bin/env python3
"""
한국 주식 시세 수집 모듈
키움증권 REST API (fallback: 네이버 금융 API)
"""

import json
import os
import sys
import urllib.error
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import HTTP_RETRY_CONFIG
from utils.http import retry_request


def _is_kr_ticker(ticker: str) -> bool:
    """한국 주식 티커 여부 (.KS 또는 .KQ)"""
    return ticker.endswith(".KS") or ticker.endswith(".KQ")


def _extract_kr_code(ticker: str) -> str:
    """티커에서 6자리 종목코드 추출 (005930.KS → 005930)"""
    return ticker.split(".")[0]


def fetch_naver_price(code: str) -> dict:
    """네이버 금융 실시간 주가 조회 (한국 주식 전용, 자동 재시도)"""
    url = f"https://polling.finance.naver.com/api/realtime/domestic/stock/{code}"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com"}
    try:
        body = retry_request(
            url,
            headers=headers,
            timeout=8,
            max_retries=HTTP_RETRY_CONFIG["max_retries"],
            base_delay=HTTP_RETRY_CONFIG["base_delay"],
        )
        d = json.loads(body)
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
        raise ConnectionError(f"네이버 API 네트워크 오류 ({code}): {e}") from e
    except (KeyError, IndexError) as e:
        raise ValueError(f"네이버 API 응답 파싱 실패 ({code}): {e}") from e


def _fetch_kr_stock(code: str) -> dict:
    """
    한국 주식 현재가 조회.
    1순위: 키움증권 REST API (ka10007)
    2순위(fallback): 네이버 금융 API

    Returns:
        dict: 시세 데이터 + data_source 키 포함
    """
    if os.environ.get("KIWOOM_APPKEY"):
        try:
            from data.fetch_gold_krx import fetch_kiwoom_stock

            result = fetch_kiwoom_stock(code)
            result["data_source"] = "kiwoom"
            print(f"    🔑 키움 API 사용 ({code})")
            return result
        except Exception as e:
            print(f"    ⚠️ 키움 API 실패 ({code}), 네이버 fallback: {e}")

    result = fetch_naver_price(code)
    result["data_source"] = "naver"
    return result

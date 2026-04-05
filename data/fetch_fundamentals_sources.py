#!/usr/bin/env python3
"""
펀더멘탈 외부 API 수집 레이어 — DART / 네이버금융 / Yahoo Finance
fetch_fundamentals.py에서 분리된 소스별 수집 함수 모음
"""

import json
import logging
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

KST = timezone(timedelta(hours=9))
logger = logging.getLogger(__name__)

# DART corp_code 매핑 (종목코드 6자리 → DART 고유번호)
# 주요 종목만 정적 매핑, 추후 corpCode.xml로 확장 가능
DART_CORP_CODES = {
    "005930": "00126380",  # 삼성전자
    "005380": "00164779",  # 현대차
    "000660": "00164742",  # SK하이닉스
    "035420": "00266961",  # NAVER
    "051910": "00174230",  # LG화학
    "006400": "00104040",  # 삼성SDI
    "012450": "00105765",  # 한화에어로스페이스
    "009150": "00107721",  # 삼성전기
    "066570": "00107374",  # LG전자
    "055550": "00382199",  # 신한지주
}


def _parse_dart_amount(amount_str: str) -> float:
    """DART 금액 문자열을 숫자로 변환 (콤마, 공백 제거)"""
    if not amount_str:
        return 0.0
    cleaned = amount_str.replace(",", "").replace(" ", "").strip()
    if not cleaned or cleaned == "-":
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def fetch_dart_financials(stock_code: str) -> Optional[dict]:
    """DART OpenAPI로 한국 종목 재무제표 수집.

    Args:
        stock_code: 종목코드 6자리 (예: '005930')

    Returns:
        재무 지표 딕셔너리 또는 None (실패 시)
    """
    api_key = os.environ.get("DART_API_KEY", "")
    if not api_key:
        logger.info("DART_API_KEY 미설정 — DART 수집 건너뜀")
        return None

    corp_code = DART_CORP_CODES.get(stock_code)
    if not corp_code:
        logger.info(f"DART corp_code 매핑 없음: {stock_code}")
        return None

    # 최근 사업연도 재무제표 (연결, 1년)
    now = datetime.now(KST)
    bsns_year = str(now.year - 1)

    url = (
        f"https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
        f"?crtfc_key={api_key}"
        f"&corp_code={corp_code}"
        f"&bsns_year={bsns_year}"
        f"&reprt_code=11011"  # 사업보고서
        f"&fs_div=CFS"  # 연결재무제표
    )

    try:
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=15)
        raw = resp.read()
        data = json.loads(raw)
    except Exception as e:
        logger.error(f"DART API 호출 실패 ({stock_code}): {e}")
        return None

    status = data.get("status", "")
    items = data.get("list", [])

    if status != "000" or not items:
        logger.info(f"DART 데이터 없음 ({stock_code}): status={status}")
        return None

    # 계정과목별 금액 추출
    accounts = {}
    for item in items:
        account_nm = item.get("account_nm", "")
        thstrm = _parse_dart_amount(item.get("thstrm_amount", ""))
        frmtrm = _parse_dart_amount(item.get("frmtrm_amount", ""))
        accounts[account_nm] = {"current": thstrm, "previous": frmtrm}

    def _get_account(*names):
        """여러 후보 계정과목명 중 존재하는 첫 번째 반환"""
        for name in names:
            if name in accounts:
                return accounts[name]
        return {}

    # 재무 지표 계산 (연결재무제표 계정과목명 다양성 대응)
    revenue = _get_account("매출액", "매출", "수익(매출액)")
    operating_profit = _get_account("영업이익", "영업이익(손실)")
    net_income = _get_account("당기순이익", "당기순이익(손실)", "연결당기순이익", "당기순손익")
    total_debt = _get_account("부채총계", "부채 총계")
    total_equity = _get_account("자본총계", "자본 총계", "지배기업 소유주지분")

    rev_current = revenue.get("current", 0)
    rev_previous = revenue.get("previous", 0)
    op_current = operating_profit.get("current", 0)
    ni_current = net_income.get("current", 0)
    debt_current = total_debt.get("current", 0)
    equity_current = total_equity.get("current", 0)

    result = {
        "revenue_growth": None,
        "operating_margin": None,
        "roe": None,
        "debt_ratio": None,
        "fcf": None,
    }

    # 매출 성장률
    if rev_previous and rev_previous != 0:
        result["revenue_growth"] = round(
            (rev_current - rev_previous) / abs(rev_previous) * 100, 2
        )

    # 영업이익률
    if rev_current and rev_current != 0:
        result["operating_margin"] = round(op_current / rev_current * 100, 2)

    # ROE
    if equity_current and equity_current != 0:
        result["roe"] = round(ni_current / equity_current * 100, 2)

    # 부채비율
    if equity_current and equity_current != 0:
        result["debt_ratio"] = round(debt_current / equity_current * 100, 2)

    # 비정상값 필터링
    if result.get("roe") is not None and abs(result["roe"]) > 200:
        logger.warning(f"DART ROE 비정상값 필터링: {stock_code} ROE={result['roe']:.1f}%")
        result["roe"] = None
    if result.get("debt_ratio") is not None and result["debt_ratio"] > 2000:
        logger.warning(f"DART 부채비율 비정상값 필터링: {stock_code} 부채비율={result['debt_ratio']:.1f}%")
        result["debt_ratio"] = None

    return result


def fetch_naver_per_pbr(stock_code: str) -> dict:
    """네이버 금융 API로 국내 종목 PER/PBR 수집.

    Args:
        stock_code: 종목코드 6자리 (예: '005930')

    Returns:
        {"per": float|None, "pbr": float|None}
    """
    url = f"https://m.stock.naver.com/api/stock/{stock_code}/integration"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        result = {"per": None, "pbr": None}
        for item in data.get("totalInfos", []):
            code = item.get("code", "")
            value_str = item.get("value", "")
            if code in ("per", "pbr") and value_str:
                # "28.37배" → 28.37
                cleaned = value_str.replace("배", "").replace(",", "").strip()
                try:
                    result[code] = float(cleaned)
                except ValueError:
                    pass
        return result
    except Exception as e:
        logger.debug(f"네이버 PER/PBR 수집 실패 ({stock_code}): {e}")
        return {"per": None, "pbr": None}


def _safe_raw(obj: dict, key: str, default=None):
    """Yahoo JSON에서 {key: {raw: value}} 패턴 안전 추출"""
    if not isinstance(obj, dict):
        return default
    nested = obj.get(key, {})
    if isinstance(nested, dict):
        return nested.get("raw", default)
    return default


def fetch_yahoo_financials(ticker: str) -> Optional[dict]:
    """yfinance로 재무 데이터 수집 (Yahoo Finance quoteSummary 대체).

    Args:
        ticker: Yahoo 티커 (예: 'TSLA', '005930.KS')

    Returns:
        재무 지표 딕셔너리 또는 None (실패 시)
    """
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.info
        if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
            logger.info(f"yfinance 데이터 없음: {ticker}")
            return None

        def _safe(key, multiplier=1):
            val = info.get(key)
            if val is None or val == "Infinity":
                return None
            try:
                return round(float(val) * multiplier, 2)
            except (TypeError, ValueError):
                return None

        roe_raw = info.get("returnOnEquity")
        roe = round(float(roe_raw) * 100, 2) if roe_raw is not None else None

        rev_growth_raw = info.get("revenueGrowth")
        revenue_growth = round(float(rev_growth_raw) * 100, 2) if rev_growth_raw is not None else None

        op_margin_raw = info.get("operatingMargins")
        operating_margin = round(float(op_margin_raw) * 100, 2) if op_margin_raw is not None else None

        div_yield_raw = info.get("dividendYield")
        dividend_yield = round(float(div_yield_raw) * 100, 2) if div_yield_raw is not None else None

        return {
            "per": _safe("trailingPE"),
            "pbr": _safe("priceToBook"),
            "roe": roe,
            "debt_ratio": _safe("debtToEquity"),
            "revenue_growth": revenue_growth,
            "operating_margin": operating_margin,
            "fcf": _safe("freeCashflow"),
            "eps": _safe("trailingEps"),
            "dividend_yield": dividend_yield,
            "market_cap": _safe("marketCap"),
        }
    except Exception as e:
        logger.error(f"yfinance 호출 실패 ({ticker}): {e}")
        return None

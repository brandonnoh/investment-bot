#!/usr/bin/env python3
"""
펀더멘탈 데이터 수집 — DART 재무제표 + Yahoo Finance quoteSummary
한국 종목: DART OpenAPI 우선, Yahoo로 PER/PBR 보완
미국 종목: Yahoo Finance quoteSummary 전용
"""

import json
import logging
import os
import sqlite3
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Union, List, Dict, Tuple

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

KST = timezone(timedelta(hours=9))
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "db" / "history.db"
OUTPUT_DIR = PROJECT_ROOT / "output" / "intel"

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


def save_fundamentals_to_db(conn: sqlite3.Connection, records: list):
    """펀더멘탈 데이터를 DB에 저장 (UPSERT).

    Args:
        conn: SQLite 연결 객체
        records: 펀더멘탈 레코드 리스트
    """
    now = datetime.now(KST).isoformat()
    for rec in records:
        conn.execute(
            """INSERT OR REPLACE INTO fundamentals
               (ticker, name, market, per, pbr, roe, debt_ratio,
                revenue_growth, operating_margin, fcf, eps,
                dividend_yield, market_cap, data_source, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rec.get("ticker"),
                rec.get("name"),
                rec.get("market"),
                rec.get("per"),
                rec.get("pbr"),
                rec.get("roe"),
                rec.get("debt_ratio"),
                rec.get("revenue_growth"),
                rec.get("operating_margin"),
                rec.get("fcf"),
                rec.get("eps"),
                rec.get("dividend_yield"),
                rec.get("market_cap"),
                rec.get("data_source"),
                now,
            ),
        )
    conn.commit()


def load_fundamentals(conn: sqlite3.Connection) -> list:
    """DB에서 펀더멘탈 데이터 조회.

    Returns:
        펀더멘탈 레코드 리스트
    """
    cursor = conn.execute(
        """SELECT ticker, name, market, per, pbr, roe, debt_ratio,
                  revenue_growth, operating_margin, fcf, eps,
                  dividend_yield, market_cap, data_source, updated_at
           FROM fundamentals ORDER BY ticker"""
    )
    columns = [
        "ticker", "name", "market", "per", "pbr", "roe", "debt_ratio",
        "revenue_growth", "operating_margin", "fcf", "eps",
        "dividend_yield", "market_cap", "data_source", "updated_at",
    ]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def generate_json(records: list) -> dict:
    """fundamentals.json 생성용 딕셔너리.

    Args:
        records: 펀더멘탈 레코드 리스트

    Returns:
        JSON 직렬화 가능한 딕셔너리
    """
    now = datetime.now(KST).isoformat()
    return {
        "updated_at": now,
        "count": len(records),
        "fundamentals": records,
    }


def _collect_for_ticker(ticker_info: dict) -> Optional[dict]:
    """개별 종목의 펀더멘탈 데이터 수집.

    한국 종목: DART 우선 → Yahoo 보완
    미국 종목: Yahoo 전용

    Args:
        ticker_info: {"ticker": ..., "name": ..., "market": ...}

    Returns:
        병합된 펀더멘탈 딕셔너리 또는 None
    """
    ticker = ticker_info["ticker"]
    market = ticker_info.get("market", "")
    name = ticker_info.get("name", "")

    result = {
        "ticker": ticker,
        "name": name,
        "market": market,
        "per": None,
        "pbr": None,
        "roe": None,
        "debt_ratio": None,
        "revenue_growth": None,
        "operating_margin": None,
        "fcf": None,
        "eps": None,
        "dividend_yield": None,
        "market_cap": None,
        "data_source": None,
    }

    dart_data = None
    yahoo_data = None

    # 한국 종목: DART + Yahoo
    if market == "KR" and ticker.endswith((".KS", ".KQ")):
        stock_code = ticker.split(".")[0]
        dart_data = fetch_dart_financials(stock_code)
        yahoo_data = fetch_yahoo_financials(ticker)

        if dart_data:
            # DART 데이터 우선 적용
            for key in ["revenue_growth", "operating_margin", "roe", "debt_ratio", "fcf"]:
                if dart_data.get(key) is not None:
                    result[key] = dart_data[key]
            result["data_source"] = "dart"

        if yahoo_data:
            # Yahoo로 나머지 보완 (DART에 없는 필드)
            for key in ["per", "pbr", "eps", "dividend_yield", "market_cap", "fcf"]:
                if result.get(key) is None and yahoo_data.get(key) is not None:
                    result[key] = yahoo_data[key]
            # DART가 없었으면 Yahoo 값으로 채움
            for key in ["roe", "debt_ratio", "revenue_growth", "operating_margin"]:
                if result.get(key) is None and yahoo_data.get(key) is not None:
                    result[key] = yahoo_data[key]
            if result["data_source"] is None:
                result["data_source"] = "yahoo"
            elif result["data_source"] == "dart":
                result["data_source"] = "dart+yahoo"

        # 국내 종목 PER/PBR 네이버에서 보완
        if market == "KR" and stock_code:
            naver_ratios = fetch_naver_per_pbr(stock_code)
            if result.get("per") is None:
                result["per"] = naver_ratios["per"]
            if result.get("pbr") is None:
                result["pbr"] = naver_ratios["pbr"]

    # 미국 종목: Yahoo 전용
    elif market == "US" or not ticker.endswith((".KS", ".KQ")):
        yahoo_data = fetch_yahoo_financials(ticker)
        if yahoo_data:
            for key, val in yahoo_data.items():
                if val is not None:
                    result[key] = val
            result["data_source"] = "yahoo"

    # 데이터가 하나도 없으면 None
    has_data = any(
        result.get(k) is not None
        for k in ["per", "pbr", "roe", "revenue_growth", "operating_margin"]
    )
    if not has_data:
        return None

    return result


def run(conn=None, output_dir=None) -> list:
    """펀더멘탈 데이터 수집 파이프라인.

    1. ticker_master에서 종목 목록 조회
    2. 종목별 DART/Yahoo 수집
    3. DB 저장 (UPSERT)
    4. fundamentals.json 출력

    Args:
        conn: SQLite 연결 (None이면 기본 DB)
        output_dir: 출력 디렉토리 (None이면 기본)

    Returns:
        수집된 펀더멘탈 레코드 리스트
    """
    out_dir = Path(output_dir) if output_dir else OUTPUT_DIR

    own_conn = False
    if conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH))
        own_conn = True

    # 1. 종목 목록 조회
    try:
        from data.ticker_master import load_master_from_db
        tickers = load_master_from_db(conn)
    except Exception as e:
        logger.warning(f"종목 사전 로드 실패: {e}")
        tickers = []

    if not tickers:
        logger.info("종목 사전 비어있음 — 펀더멘탈 수집 건너뜀")
        # 기존 DB 데이터로 JSON 생성
        existing = load_fundamentals(conn)
        if existing:
            _save_json(out_dir, existing)
        if own_conn:
            conn.close()
        return existing

    # 2. 종목별 수집
    collected = []
    for t in tickers:
        # COMMODITY, ETF 등 펀더멘탈 의미 없는 종목 스킵
        if t.get("market") == "COMMODITY":
            continue
        ticker = t["ticker"]
        # ETF 패턴 스킵 (6자리 코드가 아닌 경우 또는 특정 패턴)
        if ticker.startswith("GOLD_"):
            continue

        try:
            result = _collect_for_ticker(t)
            if result:
                collected.append(result)
                logger.info(f"  ✅ {ticker} 펀더멘탈 수집 완료 ({result['data_source']})")
            else:
                logger.info(f"  ⚠️ {ticker} 펀더멘탈 데이터 없음")
        except Exception as e:
            logger.error(f"  ❌ {ticker} 펀더멘탈 수집 실패: {e}")

    # 3. DB 저장 (수집된 것만 업데이트, 실패한 종목은 기존 데이터 유지)
    if collected:
        save_fundamentals_to_db(conn, collected)

    # 4. DB에서 전체 데이터 로드 (기존 + 신규)
    all_records = load_fundamentals(conn)

    # 5. JSON 저장
    _save_json(out_dir, all_records)

    print(f"  ✅ 펀더멘탈 수집 완료: {len(collected)}개 수집, 총 {len(all_records)}개")

    if own_conn:
        conn.close()

    return all_records


def _save_json(out_dir: Path, records: list):
    """fundamentals.json 파일 저장"""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_data = generate_json(records)
    json_path = out_dir / "fundamentals.json"
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"fundamentals.json 저장 실패: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(f"\n펀더멘탈 ({len(result)}개):")
    for rec in result:
        print(
            f"  {rec['ticker']:15s} {rec.get('name', ''):15s} "
            f"PER={rec.get('per')} PBR={rec.get('pbr')} ROE={rec.get('roe')}"
        )

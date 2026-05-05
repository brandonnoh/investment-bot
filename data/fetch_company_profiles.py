#!/usr/bin/env python3
"""스크리너 추천 종목 기업 프로필 사전 수집 — yfinance + DART + 네이버 → company_profiles DB"""

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from analysis.value_screener_strategies import (  # noqa: E402
    STRATEGY_META,
    get_opportunities_cached,
)
from data.fetch_fundamentals_sources import (  # noqa: E402
    fetch_dart_company_info,
    fetch_naver_analyst_reports,
)
from db.connection import get_db_conn  # noqa: E402
from web.claude_caller import call_claude  # noqa: E402

KST = timezone(timedelta(hours=9))
# 전략별 상위 N개만 수집
_TOP_N = 25
# yfinance rate limit 방지 (초)
_RATE_LIMIT = 0.3


def _translate_to_korean(text: str) -> str:
    """영문 기업 설명을 Claude로 한국어 번역. 실패 시 원문 반환."""
    if not text or not text.strip():
        return text
    try:
        result = call_claude(
            f"다음 영문 기업 설명을 자연스러운 한국어로 번역해줘. 번역문만 출력해:\n\n{text[:1500]}",
            system="기업 설명 번역 전문가. 번역문만 출력하고 다른 말은 하지 마.",
        )
        return result.strip() if result else text
    except Exception as e:
        print(f"  [warn] 번역 실패: {e}")
        return text


def _collect_target_tickers() -> dict[str, list[str]]:
    """5개 전략에서 상위 종목을 모아 {ticker: [strategy_ids...]} 매핑 반환."""
    ticker_strategies: dict[str, list[str]] = {}
    for strategy_id in STRATEGY_META:
        opps = get_opportunities_cached(strategy_id)
        for opp in opps[:_TOP_N]:
            ticker = opp.get("ticker", "")
            if not ticker:
                continue
            ticker_strategies.setdefault(ticker, [])
            if strategy_id not in ticker_strategies[ticker]:
                ticker_strategies[ticker].append(strategy_id)
    return ticker_strategies


def _is_kr_ticker(ticker: str) -> bool:
    """한국 주식 티커인지 판별 (.KS 또는 .KQ 접미사)."""
    return ticker.endswith(".KS") or ticker.endswith(".KQ")


def _extract_stock_code(ticker: str) -> str:
    """'005930.KS' → '005930' 종목코드 추출."""
    return ticker.split(".")[0]


def _fetch_yfinance_info(ticker: str) -> dict:
    """yfinance에서 기업 정보 조회. 실패 시 빈 dict 반환."""
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).info
        return info if info else {}
    except Exception as e:
        print(f"  [warn] {ticker}: yfinance 오류 — {e}")
        return {}


def _fetch_profile_kr(ticker: str) -> dict | None:
    """한국 주식 프로필: DART + 네이버 + yfinance 병합."""
    stock_code = _extract_stock_code(ticker)

    # DART 기업개황
    dart_info = fetch_dart_company_info(stock_code) or {}

    # 네이버 애널리스트 리포트 + 외국인 비율
    reports, foreign_rate = fetch_naver_analyst_reports(stock_code)

    # yfinance 보조 데이터 (실패해도 계속)
    yf_info = _fetch_yfinance_info(ticker)

    exchange = "KS" if ticker.endswith(".KS") else "KQ"
    name = yf_info.get("longName") or yf_info.get("shortName") or dart_info.get("name_kr")

    # 유효성 판단: 이름이나 리포트 중 하나라도 있으면 유효
    if not name and not dart_info.get("name_kr") and not reports:
        print(f"  [skip] {ticker}: 유효한 데이터 없음 (KR)")
        return None

    raw_desc = yf_info.get("longBusinessSummary", "") or ""
    return {
        "name": name,
        "name_kr": dart_info.get("name_kr"),
        "sector": yf_info.get("sector"),
        "industry": yf_info.get("industry"),
        "exchange": exchange,
        "country": "South Korea",
        "description_en": raw_desc,
        "description_kr": _translate_to_korean(raw_desc),
        "website": dart_info.get("website") or yf_info.get("website"),
        "employees": dart_info.get("employees") or yf_info.get("fullTimeEmployees"),
        "market_cap": yf_info.get("marketCap"),
        "current_price": yf_info.get("currentPrice"),
        "price_52w_high": yf_info.get("fiftyTwoWeekHigh"),
        "price_52w_low": yf_info.get("fiftyTwoWeekLow"),
        "ceo": dart_info.get("ceo"),
        "address": dart_info.get("address"),
        "founded": dart_info.get("founded"),
        "analyst_reports": json.dumps(reports, ensure_ascii=False) if reports else None,
        "foreign_rate": foreign_rate,
    }


def _fetch_profile_us(ticker: str) -> dict | None:
    """미국/해외 주식 프로필: yfinance 단독."""
    yf_info = _fetch_yfinance_info(ticker)
    if not yf_info or (not yf_info.get("currentPrice") and not yf_info.get("marketCap")):
        print(f"  [skip] {ticker}: 유효한 데이터 없음")
        return None

    raw_desc = yf_info.get("longBusinessSummary", "") or ""
    return {
        "name": yf_info.get("longName") or yf_info.get("shortName"),
        "name_kr": None,
        "sector": yf_info.get("sector"),
        "industry": yf_info.get("industry"),
        "exchange": yf_info.get("exchange"),
        "country": yf_info.get("country"),
        "description_en": raw_desc,
        "description_kr": _translate_to_korean(raw_desc),
        "website": yf_info.get("website"),
        "employees": yf_info.get("fullTimeEmployees"),
        "market_cap": yf_info.get("marketCap"),
        "current_price": yf_info.get("currentPrice"),
        "price_52w_high": yf_info.get("fiftyTwoWeekHigh"),
        "price_52w_low": yf_info.get("fiftyTwoWeekLow"),
        "ceo": None,
        "address": None,
        "founded": None,
        "analyst_reports": None,
        "foreign_rate": None,
    }


def _fetch_profile(ticker: str) -> dict | None:
    """기업 프로필 조회. KR/US 분기 처리."""
    if _is_kr_ticker(ticker):
        return _fetch_profile_kr(ticker)
    return _fetch_profile_us(ticker)


def _has_both_descriptions(conn, ticker: str) -> bool:
    """description_en, description_kr 모두 존재하면 True — 스킵 판단에 사용."""
    row = conn.execute(
        "SELECT description_en, description_kr FROM company_profiles WHERE ticker = ?",
        (ticker,),
    ).fetchone()
    if not row:
        return False
    return bool(row["description_en"]) and bool(row["description_kr"])


def _update_strategies_only(conn, ticker: str, strategies: list[str]) -> None:
    """screen_strategies와 updated_at만 갱신 (설명 수집 스킵 시)."""
    conn.execute(
        "UPDATE company_profiles SET screen_strategies = ?, updated_at = ? WHERE ticker = ?",
        (json.dumps(strategies, ensure_ascii=False), datetime.now(KST).isoformat(), ticker),
    )


def _upsert_profile(conn, ticker: str, profile: dict, strategies: list[str]):
    """company_profiles 테이블에 UPSERT — description_en/kr 별도 컬럼으로 저장."""
    now = datetime.now(KST).isoformat()
    conn.execute(
        """INSERT INTO company_profiles
           (ticker, name, name_kr, sector, industry, exchange, country,
            description_en, description_kr,
            website, employees, market_cap, current_price,
            price_52w_high, price_52w_low, ceo, address, founded,
            analyst_reports, foreign_rate, screen_strategies, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(ticker) DO UPDATE SET
             name=excluded.name, name_kr=excluded.name_kr,
             sector=excluded.sector, industry=excluded.industry,
             exchange=excluded.exchange, country=excluded.country,
             description_en=CASE WHEN excluded.description_en != ''
               THEN excluded.description_en ELSE company_profiles.description_en END,
             description_kr=CASE WHEN excluded.description_kr != ''
               THEN excluded.description_kr ELSE company_profiles.description_kr END,
             website=excluded.website,
             employees=excluded.employees, market_cap=excluded.market_cap,
             current_price=excluded.current_price,
             price_52w_high=excluded.price_52w_high,
             price_52w_low=excluded.price_52w_low,
             ceo=excluded.ceo, address=excluded.address,
             founded=excluded.founded,
             analyst_reports=excluded.analyst_reports,
             foreign_rate=excluded.foreign_rate,
             screen_strategies=excluded.screen_strategies,
             updated_at=excluded.updated_at""",
        (
            ticker,
            profile.get("name"),
            profile.get("name_kr"),
            profile.get("sector"),
            profile.get("industry"),
            profile.get("exchange"),
            profile.get("country"),
            profile.get("description_en") or "",
            profile.get("description_kr") or "",
            profile.get("website"),
            profile.get("employees"),
            profile.get("market_cap"),
            profile.get("current_price"),
            profile.get("price_52w_high"),
            profile.get("price_52w_low"),
            profile.get("ceo"),
            profile.get("address"),
            profile.get("founded"),
            profile.get("analyst_reports"),
            profile.get("foreign_rate"),
            json.dumps(strategies, ensure_ascii=False),
            now,
        ),
    )


def _is_english(text: str) -> bool:
    """한글 비율이 5% 미만이면 영문으로 판단."""
    if not text:
        return False
    kr = sum(1 for c in text if "가" <= c <= "힣")
    return kr / len(text) < 0.05


def _retranslate_failed(tickers: list[str]) -> None:
    """description_kr이 영문 그대로인 종목 재번역 시도."""
    placeholders = ",".join("?" * len(tickers))
    with get_db_conn() as conn:
        rows = conn.execute(
            f"SELECT ticker, description_en, description_kr FROM company_profiles WHERE ticker IN ({placeholders})",
            tickers,
        ).fetchall()
        failed = [
            (r["ticker"], r["description_en"])
            for r in rows
            if _is_english(r["description_kr"] or "")
            and (r["description_en"] or "")
        ]

    if not failed:
        return

    print(f"[company_profiles] 번역 실패 {len(failed)}개 재시도 중...")
    with get_db_conn() as conn:
        for ticker, desc_en in failed:
            translated = _translate_to_korean(desc_en)
            if translated and not _is_english(translated):
                conn.execute(
                    "UPDATE company_profiles SET description_kr = ? WHERE ticker = ?",
                    (translated, ticker),
                )
                print(f"  ✓ {ticker} 재번역 완료")
            else:
                print(f"  ✗ {ticker} 재번역 실패 — 영문 유지")
            time.sleep(_RATE_LIMIT)
        conn.commit()


def _migrate_legacy_description(conn) -> None:
    """기존 description 컬럼 데이터를 description_kr로 일회성 복사."""
    conn.execute(
        """UPDATE company_profiles
           SET description_kr = description
           WHERE description_kr IS NULL AND description IS NOT NULL AND description != ''"""
    )


def run():
    """스크리너 추천 종목 기업 프로필 수집 메인."""
    print("[company_profiles] 추천 종목 프로필 수집 시작")
    ticker_strategies = _collect_target_tickers()
    total = len(ticker_strategies)
    print(f"[company_profiles] 대상 종목 {total}개")

    success = 0
    skipped = 0
    with get_db_conn() as conn:
        _migrate_legacy_description(conn)
        for i, (ticker, strategies) in enumerate(ticker_strategies.items(), 1):
            if _has_both_descriptions(conn, ticker):
                print(f"  ({i}/{total}) {ticker} 스킵 (기수집)")
                _update_strategies_only(conn, ticker, strategies)
                skipped += 1
                continue
            print(f"  ({i}/{total}) {ticker} 수집 중...")
            profile = _fetch_profile(ticker)
            if profile:
                _upsert_profile(conn, ticker, profile, strategies)
                success += 1
            time.sleep(_RATE_LIMIT)
        conn.commit()

    print(f"[company_profiles] 완료: {success}개 저장, {skipped}개 스킵")
    _retranslate_failed(list(ticker_strategies.keys()))


if __name__ == "__main__":
    run()

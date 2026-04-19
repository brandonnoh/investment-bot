#!/usr/bin/env python3
"""
섹터 기반 가치 스크리닝 모듈

상위 섹터 종목에 대해 RSI/PER/PBR/52주 범위를 분석하여
매수 기회를 발굴한다.

스크리닝 조건:
  1. 과매도: RSI < 35
  2. 저평가: PBR < 1.2 AND ROE > 8.0
  3. 52주 저점 근접: position_52w < 15%
"""

import json
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 프로젝트 루트 경로 설정
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from analysis.price_analysis_indicators import calc_52w_range  # noqa: E402
from analysis.price_analysis_momentum import calc_rsi  # noqa: E402
from analysis.sector_map import _TICKER_NAMES, SECTOR_MAP  # noqa: E402
from data.fetch_fundamentals_sources import fetch_yahoo_financials  # noqa: E402

# ── 상수 ──

KST = timezone(timedelta(hours=9))
DB_PATH = PROJECT_ROOT / "db" / "history.db"
OUTPUT_DIR = PROJECT_ROOT / "output" / "intel"
FUNDAMENTALS_PATH = OUTPUT_DIR / "fundamentals.json"
SECTOR_SCORES_PATH = OUTPUT_DIR / "sector_scores.json"

MAX_TICKERS_PER_MARKET = 5
TOP_SECTOR_COUNT = 3


# ── 스크리닝 조건 ──


def _is_oversold(m: dict) -> bool:
    """RSI 과매도 판단"""
    rsi = m.get("rsi")
    return rsi is not None and rsi < 35


def _is_undervalued(m: dict) -> bool:
    """PBR+ROE 저평가 판단"""
    pbr = m.get("pbr")
    roe = m.get("roe")
    if pbr is None or roe is None:
        return False
    return pbr < 1.2 and roe > 8.0


def _is_near_52w_low(m: dict) -> bool:
    """52주 저점 근접 판단"""
    pos = m.get("pos_52w_pct")
    return pos is not None and pos < 15


SCREEN_CONDITIONS = [
    (_is_oversold, "과매도(RSI<35)"),
    (_is_undervalued, "저평가(PBR<1.2+ROE>8%)"),
    (_is_near_52w_low, "52주 저점근접(<15%)"),
]


# ── 복합 점수 ──


def _calc_composite_score(metrics: dict) -> float:
    """RSI 과매도 + PBR 저평가 + 52주 저점 기반 0~1 점수"""
    score = 0.5
    rsi = metrics.get("rsi")
    pbr = metrics.get("pbr")
    pos = metrics.get("pos_52w_pct")

    if rsi is not None:
        if rsi <= 30:
            score += 0.3
        elif rsi <= 35:
            score += 0.15

    if pbr is not None and pbr > 0:
        if pbr <= 1.0:
            score += 0.25
        elif pbr <= 1.5:
            score += 0.1

    if pos is not None and pos <= 15:
        score += 0.2

    return round(min(1.0, score), 4)


# ── 캐시 로드 ──

UNIVERSE_CACHE_PATH = OUTPUT_DIR / "universe_cache.json"


def _load_universe_cache() -> dict[str, dict]:
    """universe_cache.json 로드 (없으면 빈 dict)"""
    if not UNIVERSE_CACHE_PATH.exists():
        return {}
    try:
        data = json.loads(
            UNIVERSE_CACHE_PATH.read_text(encoding="utf-8"),
        )
        return data.get("stocks", {})
    except (json.JSONDecodeError, KeyError):
        return {}


def _load_fundamentals_cache() -> dict[str, dict]:
    """fundamentals.json에서 티커별 캐시 딕셔너리 반환"""
    if not FUNDAMENTALS_PATH.exists():
        return {}
    try:
        data = json.loads(
            FUNDAMENTALS_PATH.read_text(encoding="utf-8"),
        )
        items = data.get("fundamentals", [])
        return {item["ticker"]: item for item in items}
    except (json.JSONDecodeError, KeyError):
        return {}


def _load_sector_scores() -> list[dict]:
    """sector_scores.json에서 상위 섹터 리스트 반환"""
    if not SECTOR_SCORES_PATH.exists():
        print("  sector_scores.json 없음 — sector_intel 먼저 실행 필요")
        return []
    try:
        data = json.loads(
            SECTOR_SCORES_PATH.read_text(encoding="utf-8"),
        )
        sectors = data.get("sectors", [])
        eligible = [s for s in sectors if s.get("signal") in ("favorable", "neutral")]
        return eligible[:TOP_SECTOR_COUNT]
    except (json.JSONDecodeError, KeyError):
        return []


# ── 52주 위치 파싱 ──


def _parse_position_52w(pos_str: str | None) -> float | None:
    """'상단 94.9%' 같은 문자열에서 숫자 추출"""
    if not pos_str or pos_str == "변동 없음":
        return None
    match = re.search(r"([\d.]+)", pos_str)
    if not match:
        return None
    pct = float(match.group(1))
    # "하단 X%" → X가 작을수록 저점, 그대로 사용
    # "상단 X%" → X가 클수록 고점, 그대로 사용
    # position_52w는 0(저점)~100(고점) 범위
    return pct


# ── 종목별 지표 수집 ──


def _fetch_stock_metrics(
    conn,
    ticker: str,
    cache: dict[str, dict],
    uni_cache: dict[str, dict] | None = None,
) -> dict:
    """단일 종목 RSI + PER/PBR/ROE + 52주 범위 수집

    조회 우선순위: universe_cache → fundamentals 캐시 → Yahoo Finance
    """
    metrics: dict = {"ticker": ticker}

    # RSI (1순위: DB, 2순위: universe_cache)
    try:
        metrics["rsi"] = calc_rsi(conn, ticker)
    except Exception:
        metrics["rsi"] = None
    if metrics["rsi"] is None and uni_cache:
        cached = uni_cache.get(ticker)
        if cached:
            metrics["rsi"] = cached.get("rsi")

    # 52주 범위 (DB)
    try:
        range_data = calc_52w_range(conn, ticker)
        pos_str = range_data.get("position_52w")
        metrics["pos_52w_pct"] = _parse_position_52w(pos_str)
    except Exception:
        metrics["pos_52w_pct"] = None

    # PER/PBR/ROE (universe_cache → fundamentals → Yahoo)
    fund = _resolve_fundamentals(
        ticker,
        cache,
        uni_cache,
    )

    metrics["per"] = fund.get("per")
    metrics["pbr"] = fund.get("pbr")
    metrics["roe"] = fund.get("roe")
    metrics["name"] = fund.get(
        "name",
        _TICKER_NAMES.get(ticker, ticker),
    )

    return metrics


def _resolve_fundamentals(
    ticker: str,
    cache: dict[str, dict],
    uni_cache: dict[str, dict] | None,
) -> dict:
    """PER/PBR/ROE 조회: universe_cache → fundamentals → Yahoo"""
    # 1. universe_cache.json 우선
    if uni_cache:
        entry = uni_cache.get(ticker)
        if entry and entry.get("per") is not None:
            return entry

    # 2. fundamentals.json 캐시
    fund = cache.get(ticker)
    if fund and fund.get("per") is not None:
        return fund

    # 3. Yahoo Finance 직접 호출
    try:
        return fetch_yahoo_financials(ticker) or {}
    except Exception:
        return {}


# ── 대상 종목 수집 ──


def _collect_target_tickers(
    top_sectors: list[dict],
) -> list[dict]:
    """상위 섹터에서 KR/US 종목 리스트 수집"""
    targets: list[dict] = []
    seen: set[str] = set()
    for sector in top_sectors:
        name = sector["name"]
        smap = SECTOR_MAP.get(name, {})
        kr = smap.get("kr", [])[:MAX_TICKERS_PER_MARKET]
        us = smap.get("us", [])[:MAX_TICKERS_PER_MARKET]
        for t in kr + us:
            if t not in seen:
                seen.add(t)
                targets.append({"ticker": t, "sector": name})
    return targets


# ── 스크리닝 실행 ──


def _screen_ticker(
    metrics: dict,
    sector: str,
) -> dict | None:
    """단일 종목 스크리닝 → opportunity 또는 None"""
    reasons = []
    for cond_fn, cond_label in SCREEN_CONDITIONS:
        if cond_fn(metrics):
            reasons.append(cond_label)

    if not reasons:
        return None

    pos_52w = metrics.get("pos_52w_pct")
    return {
        "ticker": metrics["ticker"],
        "name": metrics.get("name", metrics["ticker"]),
        "sector": sector,
        "screen_reason": " + ".join(reasons),
        "rsi": metrics.get("rsi"),
        "per": metrics.get("per"),
        "pbr": metrics.get("pbr"),
        "roe": metrics.get("roe"),
        "pos_52w": round(pos_52w, 1) if pos_52w else None,
        "composite_score": _calc_composite_score(metrics),
        "discovered_via": f"섹터스크리닝:{sector}",
        "source": "value_screener",
    }


# ── 가장 빈번한 스크리닝 사유 ──


def _top_reason(opportunities: list[dict]) -> str:
    """가장 많이 등장한 screen_reason 키워드 반환"""
    if not opportunities:
        return "해당 없음"
    counts: dict[str, int] = {}
    for opp in opportunities:
        for part in opp.get("screen_reason", "").split(" + "):
            counts[part] = counts.get(part, 0) + 1
    return max(counts, key=counts.get) if counts else "해당 없음"


# ── 결과 저장 ──


def _build_output(
    opportunities: list[dict],
    top_sectors: list[dict],
) -> dict:
    """opportunities.json 출력 데이터 구성"""
    by_sector: dict[str, int] = {}
    for opp in opportunities:
        s = opp["sector"]
        by_sector[s] = by_sector.get(s, 0) + 1

    keywords = [
        {"keyword": s["name"], "category": "sector", "priority": i + 1}
        for i, s in enumerate(top_sectors)
    ]

    return {
        "updated_at": datetime.now(KST).isoformat(),
        "keywords": keywords,
        "opportunities": opportunities,
        "total_count": len(opportunities),
        "summary": {
            "total_count": len(opportunities),
            "by_sector": by_sector,
            "top_reason": _top_reason(opportunities),
        },
    }


def _save_output(output: dict) -> None:
    """opportunities.json 파일 저장"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "opportunities.json"
    path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── 메인 진입점 ──


def run() -> list:
    """섹터 기반 가치 스크리닝 실행 -> opportunities 리스트"""
    top_sectors = _load_sector_scores()
    if not top_sectors:
        return []

    targets = _collect_target_tickers(top_sectors)
    if not targets:
        print("  대상 종목 없음")
        return []

    uni_cache = _load_universe_cache()
    cache = _load_fundamentals_cache()
    conn = sqlite3.connect(str(DB_PATH))

    opportunities: list[dict] = []
    for item in targets:
        metrics = _fetch_stock_metrics(
            conn,
            item["ticker"],
            cache,
            uni_cache,
        )
        result = _screen_ticker(metrics, item["sector"])
        if result:
            opportunities.append(result)

    conn.close()

    # composite_score 내림차순 정렬
    opportunities.sort(
        key=lambda x: x.get("composite_score", 0),
        reverse=True,
    )

    output = _build_output(opportunities, top_sectors)
    _save_output(output)

    count = len(opportunities)
    print(f"  가치 스크리닝 완료: {count}건")
    return opportunities


if __name__ == "__main__":
    run()

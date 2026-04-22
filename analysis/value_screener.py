#!/usr/bin/env python3
"""섹터 기반 가치 스크리닝 — KOSPI200 200 + SP500 500 유니버스(700개).

스크리닝 조건: RSI<35 / PBR<1.2+ROE>8% / 52주 저점<15%
Marcus discovery_keywords.json 키워드로 섹터 필터 우선 적용.
섹터 할당: sector_map 우선 → fundamentals.sector(Yahoo) 폴백.
"""

import json
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from analysis.price_analysis_indicators import calc_52w_range  # noqa: E402
from analysis.price_analysis_momentum import calc_rsi  # noqa: E402
from analysis.screener_universe import UNIVERSE_KOSPI200, UNIVERSE_SP100  # noqa: E402
from analysis.sector_map import _TICKER_NAMES, get_ticker_sector  # noqa: E402
from analysis.value_screener_data import (  # noqa: E402
    load_fundamentals_cache,
    load_sector_scores,
    load_universe_cache,
    resolve_fundamentals,
)
from analysis.value_screener_marcus import load_marcus_sectors  # noqa: E402

# ── 상수 ──

KST = timezone(timedelta(hours=9))
DB_PATH = PROJECT_ROOT / "db" / "history.db"
OUTPUT_DIR = PROJECT_ROOT / "output" / "intel"


# ── 스크리닝 조건 ──


def _is_oversold(m: dict) -> bool:
    """RSI 과매도 판단"""
    rsi = m.get("rsi")
    return rsi is not None and rsi < 35


def _is_undervalued(m: dict) -> bool:
    """PBR+ROE 저평가 판단"""
    pbr, roe = m.get("pbr"), m.get("roe")
    return pbr is not None and roe is not None and pbr < 1.2 and roe > 8.0


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
    rsi, pbr, pos = metrics.get("rsi"), metrics.get("pbr"), metrics.get("pos_52w_pct")
    if rsi is not None:
        score += 0.3 if rsi <= 30 else (0.15 if rsi <= 35 else 0)
    if pbr is not None and pbr > 0:
        score += 0.25 if pbr <= 1.0 else (0.1 if pbr <= 1.5 else 0)
    if pos is not None and pos <= 15:
        score += 0.2
    return round(min(1.0, score), 4)


# ── 52주 위치 파싱 ──


def _parse_position_52w(pos_str: str | None) -> float | None:
    """'상단 94.9%' 같은 문자열에서 숫자 추출"""
    if not pos_str or pos_str == "변동 없음":
        return None
    match = re.search(r"([\d.]+)", pos_str)
    return float(match.group(1)) if match else None


# ── 종목별 지표 수집 ──


def _fetch_stock_metrics(
    conn,
    ticker: str,
    cache: dict[str, dict],
    uni_cache: dict[str, dict] | None = None,
) -> dict:
    """단일 종목 RSI + PER/PBR/ROE + 52주 범위 수집"""
    metrics: dict = {"ticker": ticker}

    # RSI: DB prices_daily → universe_cache 폴백
    try:
        metrics["rsi"] = calc_rsi(conn, ticker)
    except Exception:
        metrics["rsi"] = None
    if metrics["rsi"] is None and uni_cache:
        metrics["rsi"] = (uni_cache.get(ticker) or {}).get("rsi")

    # 52주 범위 (DB prices_daily)
    try:
        pos_str = calc_52w_range(conn, ticker).get("position_52w")
        metrics["pos_52w_pct"] = _parse_position_52w(pos_str)
    except Exception:
        metrics["pos_52w_pct"] = None

    # 펀더멘탈: DB → cache → Yahoo 폴백 (resolve_fundamentals)
    fund = resolve_fundamentals(ticker, conn, cache, uni_cache)
    metrics["per"] = fund.get("per")
    metrics["pbr"] = fund.get("pbr")
    metrics["roe"] = fund.get("roe")
    metrics["name"] = fund.get("name") or _TICKER_NAMES.get(ticker, ticker)

    return metrics


# ── 유니버스 기반 대상 종목 수집 ──


def _load_db_sectors(conn) -> dict[str, str]:
    """fundamentals 테이블에서 ticker→sector 매핑 로드"""
    try:
        cur = conn.cursor()
        cur.execute("SELECT ticker, sector FROM fundamentals WHERE sector IS NOT NULL")
        return {row[0]: row[1] for row in cur.fetchall()}
    except Exception:
        return {}


def _collect_target_tickers(conn=None) -> list[dict]:
    """KOSPI200 + SP500 전체 유니버스 기반 대상 종목 수집.

    섹터 할당: sector_map 우선 → fundamentals.sector(Yahoo) 폴백 → "기타"
    """
    db_sectors = _load_db_sectors(conn) if conn else {}
    targets: list[dict] = []
    seen: set[str] = set()
    for item in UNIVERSE_KOSPI200 + UNIVERSE_SP100:
        ticker = item["ticker"]
        if ticker in seen:
            continue
        seen.add(ticker)
        sector = get_ticker_sector(ticker) or db_sectors.get(ticker) or f"기타({item['market']})"
        targets.append({"ticker": ticker, "name": item["name"], "sector": sector})
    return targets


# ── 스크리닝 실행 ──


def _screen_ticker(metrics: dict, sector: str) -> dict | None:
    """단일 종목 스크리닝 → opportunity 또는 None"""
    reasons = [label for fn, label in SCREEN_CONDITIONS if fn(metrics)]
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
        "pos_52w": round(pos_52w, 1) if pos_52w is not None else None,
        "composite_score": _calc_composite_score(metrics),
        "discovered_via": f"섹터스크리닝:{sector}",
        "source": "value_screener",
    }


# ── 결과 저장 ──


def _top_reason(opportunities: list[dict]) -> str:
    """가장 많이 등장한 screen_reason 키워드 반환"""
    if not opportunities:
        return "해당 없음"
    counts: dict[str, int] = {}
    for opp in opportunities:
        for part in opp.get("screen_reason", "").split(" + "):
            counts[part] = counts.get(part, 0) + 1
    return max(counts, key=counts.get) if counts else "해당 없음"


def _build_output(
    opportunities: list[dict],
    top_sectors: list[dict],
    marcus_sectors: set[str],
) -> dict:
    """opportunities.json 출력 데이터 구성"""
    by_sector: dict[str, int] = {}
    for opp in opportunities:
        s = opp["sector"]
        by_sector[s] = by_sector.get(s, 0) + 1

    keywords = [
        {"keyword": s, "category": "marcus_sector", "priority": i + 1}
        for i, s in enumerate(sorted(marcus_sectors))
    ] + [
        {"keyword": s["name"], "category": "sector", "priority": len(marcus_sectors) + i + 1}
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
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 메인 진입점 ──


def run() -> list:
    """유니버스 기반 가치 스크리닝 실행 → opportunities 리스트"""
    top_sectors = load_sector_scores()
    marcus_sectors = load_marcus_sectors()

    uni_cache = load_universe_cache()
    cache = load_fundamentals_cache()
    conn = sqlite3.connect(str(DB_PATH))

    all_targets = _collect_target_tickers(conn)

    allowed_sectors = marcus_sectors | {s["name"] for s in top_sectors}
    if allowed_sectors:
        targets = [t for t in all_targets if t["sector"] in allowed_sectors]
        print(
            f"  섹터 필터 적용: {len(all_targets)}개 → {len(targets)}개 (허용 섹터: {len(allowed_sectors)}개)"
        )
    else:
        targets = all_targets
        print(f"  섹터 정보 없음 — 전체 {len(targets)}개 스크리닝")

    if not targets:
        conn.close()
        print("  대상 종목 없음")
        return []

    opportunities: list[dict] = []
    for item in targets:
        metrics = _fetch_stock_metrics(conn, item["ticker"], cache, uni_cache)
        result = _screen_ticker(metrics, item["sector"])
        if result:
            opportunities.append(result)

    conn.close()
    opportunities.sort(key=lambda x: x.get("composite_score", 0), reverse=True)

    output = _build_output(opportunities, top_sectors, marcus_sectors)
    _save_output(output)

    print(f"  가치 스크리닝 완료: {len(opportunities)}건 (대상 {len(targets)}개 중)")
    return opportunities


if __name__ == "__main__":
    run()

#!/usr/bin/env python3
"""거장 투자 전략 스크리너 — 전략별 종목 발굴

전략 목록:
  composite  — 5-팩터 복합 점수 (기본, value_screener 동일)
  graham     — 그레이엄 방어적 투자자 (저PER·PBR, 안전마진)
  buffett    — 버핏 우량주 (고ROE·영업이익률, 낮은 부채)
  lynch      — 린치 GARP (성장+합리적가격 PEG대용)
  greenblatt — 그린블랫 매직포뮬라 (1/PER + ROE 순위합산)
"""

import sqlite3
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from analysis.value_screener import (  # noqa: E402
    _collect_target_tickers,
    _fetch_stock_metrics,
)
from analysis.value_screener_data import (  # noqa: E402
    load_fundamentals_cache,
    load_sector_scores,
    load_universe_cache,
)
from analysis.value_screener_factors import calc_composite  # noqa: E402
from analysis.value_screener_marcus import load_marcus_sectors  # noqa: E402

DB_PATH = PROJECT_ROOT / "db" / "history.db"

# ── 전략 메타데이터 ──

STRATEGY_META: dict[str, dict] = {
    "composite": {
        "name": "퀀트",
        "description": "5개 팩터 종합 점수 (기본값)",
    },
    "graham": {
        "name": "그레이엄",
        "description": "저평가 자산, 강한 안전마진",
    },
    "buffett": {
        "name": "버핏",
        "description": "우량 기업, 장기 보유, 경제적 해자",
    },
    "lynch": {
        "name": "린치",
        "description": "성장+합리적 가격 (GARP)",
    },
    "greenblatt": {
        "name": "그린블랫",
        "description": "수익률+자본효율 상위 (매직포뮬라)",
    },
}


# ── 전략별 스크리너 ──


def _screen_graham(m: dict) -> dict | None:
    """그레이엄 방어적 투자자 기준"""
    per = m.get("per")
    pbr = m.get("pbr")
    debt = m.get("debt_ratio")
    div = m.get("dividend_yield")

    if per is None or pbr is None:
        return None
    if not (per > 0 and pbr > 0):
        return None
    if per > 15:
        return None
    if pbr > 1.5:
        return None
    if per * pbr > 22.5:
        return None
    if debt is not None and debt > 100:
        return None

    reasons = [f"PER {per:.0f}", f"PBR {pbr:.1f}"]
    if div and div > 0:
        reasons.append(f"배당 {div:.1f}%")
    if debt:
        reasons.append(f"부채 {debt:.0f}%")

    result = calc_composite(m)
    result["score"] = min(1.0, result["score"] + 0.05)
    return {**result, "reason": " + ".join(reasons)}


def _screen_buffett(m: dict) -> dict | None:
    """버핏 우량주 기준"""
    roe = m.get("roe")
    opm = m.get("operating_margin")
    debt = m.get("debt_ratio")
    rev = m.get("revenue_growth")

    if roe is None or opm is None:
        return None
    if roe < 15:
        return None
    if opm < 15:
        return None
    if debt is not None and debt > 50:
        return None

    reasons = [f"ROE {roe:.0f}%", f"영업이익률 {opm:.0f}%"]
    if rev and rev > 0:
        reasons.append("매출 성장 중")

    result = calc_composite(m)
    result["score"] = min(1.0, result["score"] + 0.05)
    return {**result, "reason": " + ".join(reasons)}


def _screen_lynch(m: dict) -> dict | None:
    """린치 GARP — PEG 대용 (PER/매출성장률)"""
    per = m.get("per")
    rev = m.get("revenue_growth")
    debt = m.get("debt_ratio")

    if per is None or rev is None:
        return None
    if per <= 0 or rev <= 0:
        return None
    if not (15 <= rev <= 50):
        return None
    if debt is not None and debt > 60:
        return None

    peg_proxy = per / rev
    if peg_proxy > 1.5:
        return None

    reasons = [f"매출 {rev:.0f}% 성장", f"PEG대용 {peg_proxy:.2f}"]
    result = calc_composite(m)
    result["score"] = min(1.0, result["score"] + 0.05)
    return {**result, "reason": " + ".join(reasons)}


def _rank_greenblatt(all_metrics: list[dict]) -> list[dict]:
    """그린블랫 매직포뮬라 — 1/PER 순위 + ROE 순위 합산"""
    eligible = [
        m for m in all_metrics if m.get("per") and m["per"] > 0 and m.get("roe") and m["roe"] > 0
    ]
    if not eligible:
        return []

    # 각 지표 순위 계산 (낮은 PER = 좋음, 높은 ROE = 좋음)
    sorted_per = sorted(eligible, key=lambda x: x["per"])
    sorted_roe = sorted(eligible, key=lambda x: x["roe"], reverse=True)

    per_rank = {m["ticker"]: i for i, m in enumerate(sorted_per)}
    roe_rank = {m["ticker"]: i for i, m in enumerate(sorted_roe)}

    for m in eligible:
        m["_gf_rank"] = per_rank[m["ticker"]] + roe_rank[m["ticker"]]

    top = sorted(eligible, key=lambda x: x["_gf_rank"])[:30]

    results = []
    for m in top:
        result = calc_composite(m)
        per = m.get("per")
        roe = m.get("roe")
        result["reason"] = f"PER {per:.0f} + ROE {roe:.0f}% 복합순위"
        results.append((m, result))
    return results


# ── 메인 실행 함수 ──


def run_strategy(strategy_id: str) -> list[dict]:
    """전략별 발굴 실행 → opportunities 리스트"""
    uni_cache = load_universe_cache()
    cache = load_fundamentals_cache()
    conn = sqlite3.connect(str(DB_PATH))

    all_targets = _collect_target_tickers(conn)

    top_sectors = load_sector_scores()
    marcus_sectors = load_marcus_sectors()
    allowed_sectors = marcus_sectors | {s["name"] for s in top_sectors}

    if allowed_sectors:
        targets = [t for t in all_targets if t["sector"] in allowed_sectors]
    else:
        targets = all_targets

    all_metrics = []
    for item in targets:
        m = _fetch_stock_metrics(conn, item["ticker"], cache, uni_cache)
        m["_sector"] = item["sector"]
        m["_name"] = item.get("name", m.get("name", item["ticker"]))
        all_metrics.append(m)

    conn.close()

    opportunities: list[dict] = []

    if strategy_id == "greenblatt":
        ranked = _rank_greenblatt(all_metrics)
        for m, result in ranked:
            opportunities.append(_build_opp(m, result))
    else:
        screener = {
            "graham": _screen_graham,
            "buffett": _screen_buffett,
            "lynch": _screen_lynch,
            "composite": _screen_composite,
        }.get(strategy_id, _screen_composite)

        for m in all_metrics:
            result = screener(m)
            if result:
                opportunities.append(_build_opp(m, result))

    opportunities.sort(key=lambda x: x.get("composite_score", 0), reverse=True)
    return opportunities


def _screen_composite(m: dict) -> dict | None:
    """기본 5-팩터 복합 점수 (threshold 0.60)"""
    result = calc_composite(m)
    if result["score"] < 0.60:
        return None
    return result


def _build_opp(m: dict, result: dict) -> dict:
    """metrics + 전략 결과 → opportunity dict"""
    pos = m.get("pos_52w_pct")
    return {
        "ticker": m["ticker"],
        "name": m.get("name") or m.get("_name", m["ticker"]),
        "sector": m.get("_sector", "—"),
        "screen_reason": result.get("reason", result.get("screen_reason", "—")),
        "grade": result.get("grade", "—"),
        "composite_score": result.get("score", 0),
        "factors": result.get("factors", {}),
        "rsi": m.get("rsi"),
        "per": m.get("per"),
        "pbr": m.get("pbr"),
        "roe": m.get("roe"),
        "pos_52w": round(pos, 1) if pos is not None else None,
        "source": f"strategy_{m.get('_strategy_id', 'unknown')}",
    }


# ── 캐시 (메모리, TTL 5분) ──

_cache: dict[str, dict] = {}
_CACHE_TTL = 300


def get_opportunities_cached(strategy_id: str) -> list[dict]:
    entry = _cache.get(strategy_id)
    if entry and time.time() - entry["ts"] < _CACHE_TTL:
        return entry["data"]
    data = run_strategy(strategy_id)
    _cache[strategy_id] = {"ts": time.time(), "data": data}
    return data

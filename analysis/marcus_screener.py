#!/usr/bin/env python3
"""마커스 스크리닝 풀 — B+ 이상(70점) 통과 종목 추출

5개 전략(퀀트·그레이엄·버핏·린치·그린블랫)을 순서대로 실행하고,
composite_score >= 0.70인 종목만 수집해 compact pool을 반환한다.
같은 종목이 여러 전략을 통과하면 strategies 필드에 모두 기록.

TTL 3600초 메모리 캐시로 반복 호출 비용 절감.
"""

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from analysis.value_screener_strategies import STRATEGY_META, run_strategy  # noqa: E402

# ── 상수 ──

STRATEGY_IDS = ["composite", "graham", "buffett", "lynch", "greenblatt"]
B_PLUS_THRESHOLD = 0.70  # B+ 기준 점수

# ── 메모리 캐시 ──

_CACHE: dict = {}
_CACHE_TTL = 3600  # 1시간


def _extract_financials(opp: dict) -> dict:
    """opportunity dict에서 핵심 재무 지표만 추출"""
    factors = opp.get("factors", {})
    return {
        "per": opp.get("per"),
        "roe": opp.get("roe"),
        # factors에 없는 필드는 opp 루트에서 시도 (run_strategy가 _build_opp으로 생성)
        "operating_margin": opp.get("operating_margin"),
        "revenue_growth": opp.get("revenue_growth"),
        "debt_ratio": opp.get("debt_ratio"),
    }


def _strategy_name(strategy_id: str) -> str:
    """전략 ID → 한글 이름 (STRATEGY_META 사용)"""
    return STRATEGY_META.get(strategy_id, {}).get("name", strategy_id)


def _run_all_strategies() -> list[dict]:
    """5개 전략 실행 후 B+ 이상 종목 수집 및 중복 제거"""
    # ticker → 누적 결과 dict
    pool: dict[str, dict] = {}

    for strategy_id in STRATEGY_IDS:
        try:
            results = run_strategy(strategy_id)
        except Exception as e:
            print(f"  ⚠️  전략 '{strategy_id}' 실행 실패: {e}")
            continue

        strategy_name = _strategy_name(strategy_id)

        for opp in results:
            score = opp.get("composite_score", 0)
            if score < B_PLUS_THRESHOLD:
                continue

            ticker = opp.get("ticker")
            if not ticker:
                continue

            if ticker in pool:
                # 이미 등록된 종목 — strategies 추가, 최고 점수 갱신
                existing = pool[ticker]
                if strategy_name not in existing["strategies"]:
                    existing["strategies"].append(strategy_name)
                if score > existing["composite_score"]:
                    existing["composite_score"] = score
                    existing["grade"] = opp.get("grade", existing["grade"])
            else:
                financials = _extract_financials(opp)
                pool[ticker] = {
                    "ticker": ticker,
                    "name": opp.get("name", ticker),
                    "grade": opp.get("grade", "—"),
                    "strategies": [strategy_name],
                    "composite_score": score,
                    **financials,
                }

    # composite_score 내림차순 정렬
    return sorted(pool.values(), key=lambda x: x["composite_score"], reverse=True)


def get_marcus_screened_pool() -> list[dict]:
    """B+(70점 이상) 스크리닝 풀 반환. TTL 캐시 적용 (1시간).

    실패 시 빈 리스트 반환 (graceful degradation).
    """
    entry = _CACHE.get("pool")
    if entry and time.time() - entry["ts"] < _CACHE_TTL:
        return entry["data"]

    try:
        data = _run_all_strategies()
        _CACHE["pool"] = {"ts": time.time(), "data": data}
        return data
    except Exception as e:
        print(f"  ⚠️  marcus_screener 전체 실패: {e}")
        return []

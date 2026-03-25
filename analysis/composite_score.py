"""복합 점수 계산 엔진 — 6팩터 Percentile Rank 기반 스코어링

팩터 구성:
  1. 밸류 (Value): PER/PBR 업종평균 대비 역순 Percentile
  2. 퀄리티 (Quality): ROE/부채비율(역순)/FCF
  3. 성장 (Growth): 매출성장률/EPS성장률
  4. 타이밍 (Timing): 모멘텀(수익률) + RSI 과매도 기회
  5. 촉매 (Catalyst): 뉴스 감성 점수
  6. 매크로 (Macro): 시장 환경 방향 지수
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


def percentile_rank(values: list, value: float) -> float:
    """0~1 사이 백분위 순위. 이상치에 강건."""
    if not values:
        return 0.5
    count_below = sum(1 for v in values if v < value)
    count_equal = sum(1 for v in values if v == value)
    n = len(values)
    if n == 0:
        return 0.5
    return (count_below + 0.5 * count_equal) / n


def calculate_macro_direction(macro: dict) -> float:
    """매크로 환경을 -1.0~1.0 지수로 변환.

    5개 팩터: 코스피, 환율, 유가, VIX, Fear & Greed(선택)
    Fear & Greed가 없으면 기존 4팩터만 사용.
    """
    scores = []

    # 코스피: 상승 → 긍정
    kospi = macro.get("KOSPI", {}).get("change_pct", 0) or 0
    scores.append(max(-1, min(1, kospi / 5)))

    # 환율: 하락 → 긍정
    krw = macro.get("KRW=X", {}).get("change_pct", 0) or 0
    scores.append(max(-1, min(1, -krw / 3)))

    # 유가
    oil = macro.get("CL=F", {}).get("change_pct", 0) or 0
    scores.append(max(-1, min(1, oil / 10)))

    # VIX: 하락 → 긍정
    vix = macro.get("^VIX", {}).get("change_pct", 0) or 0
    scores.append(max(-1, min(1, -vix / 15)))

    # Fear & Greed Index (0~100 → -1.0~1.0)
    fg_data = macro.get("fear_greed")
    if fg_data and isinstance(fg_data, dict):
        fg_score = fg_data.get("score")
        if fg_score is not None:
            scores.append(max(-1, min(1, (fg_score - 50) / 50)))

    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 4)


# ── 개별 팩터 점수 계산 함수 ──


def calculate_value_score(
    per: float | None,
    pbr: float | None,
    universe_per: list,
    universe_pbr: list,
) -> float:
    """밸류에이션 점수 — PER/PBR이 낮을수록 높은 점수 (역순 percentile).

    Args:
        per: 종목 PER (None이면 중립 0.5)
        pbr: 종목 PBR (None이면 중립 0.5)
        universe_per: 유니버스 전체 PER 리스트
        universe_pbr: 유니버스 전체 PBR 리스트

    Returns:
        0~1 사이 밸류 점수 (높을수록 저평가)
    """
    scores = []

    if per is not None and universe_per:
        # 역순: 낮은 PER이 높은 점수
        scores.append(1.0 - percentile_rank(universe_per, per))
    if pbr is not None and universe_pbr:
        scores.append(1.0 - percentile_rank(universe_pbr, pbr))

    if not scores:
        return 0.5
    return sum(scores) / len(scores)


def calculate_quality_score(
    roe: float | None,
    debt_ratio: float | None,
    fcf: float | None,
    universe_roe: list,
    universe_debt: list,
    universe_fcf: list,
) -> float:
    """퀄리티 점수 — ROE 높을수록, 부채비율 낮을수록, FCF 높을수록 좋음.

    Args:
        roe: 자기자본이익률 (%)
        debt_ratio: 부채비율 (%)
        fcf: 잉여현금흐름 (원/달러)
        universe_*: 유니버스 전체 리스트

    Returns:
        0~1 사이 퀄리티 점수
    """
    scores = []

    if roe is not None and universe_roe:
        scores.append(percentile_rank(universe_roe, roe))
    if debt_ratio is not None and universe_debt:
        # 역순: 낮은 부채비율이 높은 점수
        scores.append(1.0 - percentile_rank(universe_debt, debt_ratio))
    if fcf is not None and universe_fcf:
        scores.append(percentile_rank(universe_fcf, fcf))

    if not scores:
        return 0.5
    return sum(scores) / len(scores)


def calculate_growth_score(
    revenue_growth: float | None,
    eps_growth: float | None,
    universe_rev_growth: list,
    universe_eps_growth: list,
) -> float:
    """성장 점수 — 매출/EPS 성장률 Percentile Rank.

    Args:
        revenue_growth: 매출 성장률 (%)
        eps_growth: EPS 성장률 (%)
        universe_*: 유니버스 전체 리스트

    Returns:
        0~1 사이 성장 점수
    """
    scores = []

    if revenue_growth is not None and universe_rev_growth:
        scores.append(percentile_rank(universe_rev_growth, revenue_growth))
    if eps_growth is not None and universe_eps_growth:
        scores.append(percentile_rank(universe_eps_growth, eps_growth))

    if not scores:
        return 0.5
    return sum(scores) / len(scores)


def calculate_eps_growth(
    current_eps: float | None, previous_eps: float | None
) -> float | None:
    """EPS 성장률 계산.

    Args:
        current_eps: 현재 EPS
        previous_eps: 이전 EPS

    Returns:
        성장률 (%) 또는 None
    """
    if current_eps is None or previous_eps is None or previous_eps == 0:
        return None
    return round((current_eps - previous_eps) / abs(previous_eps) * 100, 1)


def build_universe_stats(fundamentals: list) -> dict:
    """펀더멘탈 데이터에서 유니버스 통계 추출.

    Args:
        fundamentals: 펀더멘탈 레코드 리스트

    Returns:
        각 팩터별 유니버스 값 리스트 딕셔너리
    """
    keys = ["per", "pbr", "roe", "debt_ratio", "fcf", "revenue_growth", "eps"]
    stats = {k: [] for k in keys}

    for rec in fundamentals:
        for k in keys:
            val = rec.get(k)
            if val is not None:
                stats[k].append(val)

    return stats


# ── 6팩터 통합 점수 ──


def calculate_composite_score_v2(
    candidate: dict,
    universe: dict,
    macro_direction: float,
) -> tuple:
    """6팩터 복합 점수 계산.

    Args:
        candidate: {month_return, rsi_14, sentiment, per, pbr, roe,
                    debt_ratio, fcf, revenue_growth, eps_growth}
        universe: {returns, rsi, per, pbr, roe, debt_ratio, fcf,
                   revenue_growth, eps_growth}
        macro_direction: -1.0 ~ 1.0

    Returns:
        (score: float 0~1, sub_scores: dict)
    """
    weights = config.OPPORTUNITY_CONFIG["composite_weights"]

    # 1. 밸류 (Value)
    score_value = calculate_value_score(
        candidate.get("per"),
        candidate.get("pbr"),
        universe.get("per", []),
        universe.get("pbr", []),
    )

    # 2. 퀄리티 (Quality)
    score_quality = calculate_quality_score(
        candidate.get("roe"),
        candidate.get("debt_ratio"),
        candidate.get("fcf"),
        universe.get("roe", []),
        universe.get("debt_ratio", []),
        universe.get("fcf", []),
    )

    # 3. 성장 (Growth)
    score_growth = calculate_growth_score(
        candidate.get("revenue_growth"),
        candidate.get("eps_growth"),
        universe.get("revenue_growth", []),
        universe.get("eps_growth", []),
    )

    # 4. 타이밍 (Timing) — 기존 모멘텀 + RSI 로직
    ret_val = candidate.get("month_return") or 0
    score_return = percentile_rank(universe.get("returns", []), ret_val)
    rsi_val = candidate.get("rsi_14") or 50
    rsi_inverted = 100 - rsi_val
    universe_rsi = universe.get("rsi", [])
    score_rsi = (
        percentile_rank([100 - r for r in universe_rsi], rsi_inverted)
        if universe_rsi
        else 0.5
    )
    score_timing = (score_return + score_rsi) / 2.0

    # 5. 촉매 (Catalyst) — 감성 점수
    sentiment_val = candidate.get("sentiment") or 0
    score_catalyst = (sentiment_val + 1.0) / 2.0

    # 6. 매크로 (Macro)
    score_macro = (macro_direction + 1.0) / 2.0

    # 가중 합산
    composite = (
        score_value * weights["value"]
        + score_quality * weights["quality"]
        + score_growth * weights["growth"]
        + score_timing * weights["timing"]
        + score_catalyst * weights["catalyst"]
        + score_macro * weights["macro"]
    )

    sub_scores = {
        "value": round(score_value, 4),
        "quality": round(score_quality, 4),
        "growth": round(score_growth, 4),
        "timing": round(score_timing, 4),
        "catalyst": round(score_catalyst, 4),
        "macro": round(score_macro, 4),
    }

    return round(composite, 4), sub_scores


# ── 기존 4팩터 하위 호환 ──


def calculate_composite_score(
    candidate: dict,
    universe_returns: list,
    universe_rsi: list,
    macro_direction: float,
) -> tuple:
    """기존 4팩터 복합 점수 (하위 호환 유지).

    Args:
        candidate: {"month_return": float, "rsi_14": float, "sentiment": float}
        universe_returns: 유니버스 전체의 1개월 수익률 리스트
        universe_rsi: 유니버스 전체의 RSI 리스트
        macro_direction: -1.0 ~ 1.0

    Returns:
        (score: float 0~1, sub_scores: dict)
    """
    # 레거시 가중치 (균등)
    w = {"return": 0.25, "rsi": 0.25, "sentiment": 0.25, "macro": 0.25}

    # 1. 수익률 점수 (모멘텀)
    ret_val = candidate.get("month_return") or 0
    score_return = percentile_rank(universe_returns, ret_val)

    # 2. RSI 점수 (과매도일수록 매수 기회 → 역전)
    rsi_val = candidate.get("rsi_14") or 50
    rsi_inverted = 100 - rsi_val
    score_rsi = percentile_rank([100 - r for r in universe_rsi], rsi_inverted)

    # 3. 감성 점수 (-1~1 → 0~1)
    sentiment_val = candidate.get("sentiment") or 0
    score_sentiment = (sentiment_val + 1.0) / 2.0

    # 4. 매크로 방향 (-1~1 → 0~1)
    score_macro = (macro_direction + 1.0) / 2.0

    # 가중 합산
    composite = (
        score_return * w["return"]
        + score_rsi * w["rsi"]
        + score_sentiment * w["sentiment"]
        + score_macro * w["macro"]
    )

    sub_scores = {
        "return": round(score_return, 4),
        "rsi": round(score_rsi, 4),
        "sentiment": round(score_sentiment, 4),
        "macro": round(score_macro, 4),
    }

    return round(composite, 4), sub_scores

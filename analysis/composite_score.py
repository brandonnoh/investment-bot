"""복합 점수 계산 엔진 — 4팩터 Percentile Rank 기반 스코어링"""

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
    """매크로 환경을 -1.0~1.0 지수로 변환"""
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

    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 4)


def calculate_composite_score(
    candidate: dict,
    universe_returns: list,
    universe_rsi: list,
    macro_direction: float,
) -> tuple:
    """
    복합 점수 계산.

    Args:
        candidate: {"month_return": float, "rsi_14": float, "sentiment": float}
        universe_returns: 유니버스 전체의 1개월 수익률 리스트
        universe_rsi: 유니버스 전체의 RSI 리스트
        macro_direction: -1.0 ~ 1.0

    Returns:
        (score: float 0~1, sub_scores: dict)
    """
    weights = config.OPPORTUNITY_CONFIG["composite_weights"]

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
        score_return * weights["return"]
        + score_rsi * weights["rsi"]
        + score_sentiment * weights["sentiment"]
        + score_macro * weights["macro"]
    )

    sub_scores = {
        "return": round(score_return, 4),
        "rsi": round(score_rsi, 4),
        "sentiment": round(score_sentiment, 4),
        "macro": round(score_macro, 4),
    }

    return round(composite, 4), sub_scores

"""Phase 4 복합 점수 엔진 테스트"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_percentile_rank_basic():
    """기본 percentile rank 계산"""
    from analysis.composite_score import percentile_rank

    values = [10, 20, 30, 40, 50]
    assert percentile_rank(values, 50) == 0.9
    assert percentile_rank(values, 10) == 0.1
    assert percentile_rank(values, 30) == 0.5


def test_percentile_rank_empty():
    """빈 리스트일 때 0.5 반환"""
    from analysis.composite_score import percentile_rank

    assert percentile_rank([], 42) == 0.5


def test_percentile_rank_all_same():
    """모든 값이 같을 때"""
    from analysis.composite_score import percentile_rank

    assert percentile_rank([5, 5, 5], 5) == 0.5


def test_percentile_rank_single():
    """단일 값"""
    from analysis.composite_score import percentile_rank

    assert percentile_rank([10], 10) == 0.5


def test_calculate_macro_direction_positive():
    """매크로 방향 긍정 (코스피 상승, VIX 하락)"""
    from analysis.composite_score import calculate_macro_direction

    macro = {
        "KOSPI": {"change_pct": 2.0},
        "KRW=X": {"change_pct": -1.0},
        "CL=F": {"change_pct": 1.0},
        "^VIX": {"change_pct": -5.0},
    }
    direction = calculate_macro_direction(macro)
    assert -1.0 <= direction <= 1.0
    assert direction > 0


def test_calculate_macro_direction_negative():
    """매크로 방향 부정 (코스피 하락, VIX 급등)"""
    from analysis.composite_score import calculate_macro_direction

    macro = {
        "KOSPI": {"change_pct": -3.0},
        "KRW=X": {"change_pct": 2.0},
        "CL=F": {"change_pct": -2.0},
        "^VIX": {"change_pct": 10.0},
    }
    direction = calculate_macro_direction(macro)
    assert direction < 0


def test_calculate_macro_direction_empty():
    """빈 매크로 데이터"""
    from analysis.composite_score import calculate_macro_direction

    assert calculate_macro_direction({}) == 0.0


def test_calculate_composite_score():
    """복합 점수 계산"""
    from analysis.composite_score import calculate_composite_score

    candidate = {"month_return": 10.0, "rsi_14": 55.0, "sentiment": 0.5}
    universe_returns = [-5, 0, 5, 10, 15]
    universe_rsi = [30, 40, 50, 55, 70]
    macro_direction = 0.3
    score, sub = calculate_composite_score(
        candidate, universe_returns, universe_rsi, macro_direction
    )
    assert 0 <= score <= 1
    assert "return" in sub
    assert "rsi" in sub
    assert "sentiment" in sub
    assert "macro" in sub


def test_composite_score_weights_sum():
    """가중치 합이 1.0"""
    import config

    weights = config.OPPORTUNITY_CONFIG["composite_weights"]
    assert abs(sum(weights.values()) - 1.0) < 0.001


def test_score_all_extremes():
    """최고/최저 극단값 테스트"""
    from analysis.composite_score import calculate_composite_score

    best = {"month_return": 50.0, "rsi_14": 99.0, "sentiment": 1.0}
    worst = {"month_return": -50.0, "rsi_14": 1.0, "sentiment": -1.0}
    returns = [-50, 0, 50]
    rsis = [1, 50, 99]

    best_score, _ = calculate_composite_score(best, returns, rsis, 1.0)
    worst_score, _ = calculate_composite_score(worst, returns, rsis, -1.0)
    assert best_score > worst_score


def test_composite_score_none_handling():
    """None 값 처리"""
    from analysis.composite_score import calculate_composite_score

    candidate = {"month_return": None, "rsi_14": None, "sentiment": None}
    score, sub = calculate_composite_score(candidate, [0, 10], [30, 70], 0.0)
    assert 0 <= score <= 1

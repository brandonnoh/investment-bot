"""F22 퀀트 스코어링 고도화 — 6팩터 복합 점수 테스트"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── 1. config 가중치 테스트 ──


def test_six_factor_weights_exist():
    """config.py에 6팩터 가중치 설정 존재"""
    import config

    weights = config.OPPORTUNITY_CONFIG["composite_weights"]
    for key in ["value", "quality", "growth", "timing", "catalyst", "macro"]:
        assert key in weights, f"가중치 키 없음: {key}"


def test_six_factor_weights_sum_to_one():
    """6팩터 가중치 합이 1.0"""
    import config

    weights = config.OPPORTUNITY_CONFIG["composite_weights"]
    total = sum(weights.values())
    assert abs(total - 1.0) < 0.001, f"가중치 합: {total}"


# ── 2. 밸류에이션 점수 테스트 ──


def test_calculate_value_score_low_per():
    """낮은 PER → 높은 밸류 점수 (역순 percentile)"""
    from analysis.composite_score import calculate_value_score

    # PER 10은 유니버스 [5, 10, 20, 30, 50] 중 낮은 편
    score = calculate_value_score(
        per=10.0, pbr=1.0,
        universe_per=[5, 10, 20, 30, 50],
        universe_pbr=[0.5, 1.0, 2.0, 3.0, 5.0],
    )
    assert 0 <= score <= 1
    assert score > 0.5  # 낮은 PER → 높은 점수


def test_calculate_value_score_high_per():
    """높은 PER → 낮은 밸류 점수"""
    from analysis.composite_score import calculate_value_score

    score = calculate_value_score(
        per=50.0, pbr=5.0,
        universe_per=[5, 10, 20, 30, 50],
        universe_pbr=[0.5, 1.0, 2.0, 3.0, 5.0],
    )
    assert 0 <= score <= 1
    assert score < 0.5


def test_calculate_value_score_none_handling():
    """PER/PBR이 None일 때 0.5 반환"""
    from analysis.composite_score import calculate_value_score

    score = calculate_value_score(
        per=None, pbr=None,
        universe_per=[10, 20, 30],
        universe_pbr=[1.0, 2.0, 3.0],
    )
    assert score == 0.5


def test_calculate_value_score_empty_universe():
    """유니버스 비어있을 때"""
    from analysis.composite_score import calculate_value_score

    score = calculate_value_score(per=15.0, pbr=1.5, universe_per=[], universe_pbr=[])
    assert score == 0.5


# ── 3. 퀄리티 점수 테스트 ──


def test_calculate_quality_score_high():
    """높은 ROE + 낮은 부채비율 + 양수 FCF → 높은 퀄리티"""
    from analysis.composite_score import calculate_quality_score

    score = calculate_quality_score(
        roe=25.0, debt_ratio=30.0, fcf=1e9,
        universe_roe=[5, 10, 15, 20, 25],
        universe_debt=[30, 50, 80, 100, 150],
        universe_fcf=[-1e8, 0, 5e8, 1e9, 2e9],
    )
    assert 0 <= score <= 1
    assert score > 0.5


def test_calculate_quality_score_low():
    """낮은 ROE + 높은 부채비율 + 음수 FCF → 낮은 퀄리티"""
    from analysis.composite_score import calculate_quality_score

    score = calculate_quality_score(
        roe=5.0, debt_ratio=150.0, fcf=-1e8,
        universe_roe=[5, 10, 15, 20, 25],
        universe_debt=[30, 50, 80, 100, 150],
        universe_fcf=[-1e8, 0, 5e8, 1e9, 2e9],
    )
    assert 0 <= score <= 1
    assert score < 0.5


def test_calculate_quality_score_none():
    """모든 값 None일 때"""
    from analysis.composite_score import calculate_quality_score

    score = calculate_quality_score(
        roe=None, debt_ratio=None, fcf=None,
        universe_roe=[10, 20], universe_debt=[50, 100], universe_fcf=[0, 1e9],
    )
    assert score == 0.5


# ── 4. 성장 점수 테스트 ──


def test_calculate_growth_score_high():
    """높은 매출 성장률 + EPS 성장 → 높은 성장 점수"""
    from analysis.composite_score import calculate_growth_score

    score = calculate_growth_score(
        revenue_growth=30.0, eps_growth=25.0,
        universe_rev_growth=[0, 5, 10, 20, 30],
        universe_eps_growth=[-10, 0, 10, 20, 25],
    )
    assert 0 <= score <= 1
    assert score > 0.5


def test_calculate_growth_score_negative():
    """역성장 → 낮은 성장 점수"""
    from analysis.composite_score import calculate_growth_score

    score = calculate_growth_score(
        revenue_growth=-10.0, eps_growth=-20.0,
        universe_rev_growth=[-10, 0, 10, 20, 30],
        universe_eps_growth=[-20, -10, 0, 10, 20],
    )
    assert 0 <= score <= 1
    assert score < 0.5


def test_calculate_growth_score_none():
    """성장률 None 처리"""
    from analysis.composite_score import calculate_growth_score

    score = calculate_growth_score(
        revenue_growth=None, eps_growth=None,
        universe_rev_growth=[10, 20], universe_eps_growth=[5, 15],
    )
    assert score == 0.5


# ── 5. 6팩터 통합 점수 테스트 ──


def test_calculate_composite_score_v2_basic():
    """6팩터 복합 점수 기본 계산"""
    from analysis.composite_score import calculate_composite_score_v2

    candidate = {
        "month_return": 10.0,
        "rsi_14": 55.0,
        "sentiment": 0.5,
        "per": 15.0,
        "pbr": 1.5,
        "roe": 20.0,
        "debt_ratio": 50.0,
        "fcf": 1e9,
        "revenue_growth": 15.0,
        "eps_growth": 10.0,
    }
    universe = {
        "returns": [-5, 0, 5, 10, 15],
        "rsi": [30, 40, 50, 55, 70],
        "per": [5, 10, 15, 20, 50],
        "pbr": [0.5, 1.0, 1.5, 3.0, 5.0],
        "roe": [5, 10, 15, 20, 25],
        "debt_ratio": [30, 50, 80, 100, 150],
        "fcf": [-1e8, 0, 5e8, 1e9, 2e9],
        "revenue_growth": [0, 5, 10, 15, 30],
        "eps_growth": [-10, 0, 5, 10, 25],
    }

    score, sub_scores = calculate_composite_score_v2(
        candidate, universe, macro_direction=0.3
    )
    assert 0 <= score <= 1
    # 6팩터 서브 점수 키 확인
    for key in ["value", "quality", "growth", "timing", "catalyst", "macro"]:
        assert key in sub_scores, f"서브 점수 키 없음: {key}"
        assert 0 <= sub_scores[key] <= 1


def test_composite_v2_best_vs_worst():
    """최고 후보 > 최악 후보"""
    from analysis.composite_score import calculate_composite_score_v2

    best = {
        "month_return": 30.0, "rsi_14": 95.0, "sentiment": 1.0,
        "per": 5.0, "pbr": 0.5, "roe": 30.0, "debt_ratio": 20.0,
        "fcf": 5e9, "revenue_growth": 50.0, "eps_growth": 40.0,
    }
    worst = {
        "month_return": -30.0, "rsi_14": 5.0, "sentiment": -1.0,
        "per": 100.0, "pbr": 10.0, "roe": 1.0, "debt_ratio": 300.0,
        "fcf": -1e9, "revenue_growth": -30.0, "eps_growth": -50.0,
    }
    universe = {
        "returns": [-30, 0, 30], "rsi": [5, 50, 95],
        "per": [5, 30, 100], "pbr": [0.5, 3, 10],
        "roe": [1, 15, 30], "debt_ratio": [20, 100, 300],
        "fcf": [-1e9, 0, 5e9], "revenue_growth": [-30, 10, 50],
        "eps_growth": [-50, 0, 40],
    }

    best_score, _ = calculate_composite_score_v2(best, universe, 1.0)
    worst_score, _ = calculate_composite_score_v2(worst, universe, -1.0)
    assert best_score > worst_score


def test_composite_v2_none_candidate():
    """모든 값 None인 후보"""
    from analysis.composite_score import calculate_composite_score_v2

    candidate = {
        "month_return": None, "rsi_14": None, "sentiment": None,
        "per": None, "pbr": None, "roe": None, "debt_ratio": None,
        "fcf": None, "revenue_growth": None, "eps_growth": None,
    }
    universe = {
        "returns": [0, 10], "rsi": [30, 70],
        "per": [10, 30], "pbr": [1, 3],
        "roe": [10, 20], "debt_ratio": [50, 100],
        "fcf": [0, 1e9], "revenue_growth": [5, 15],
        "eps_growth": [0, 10],
    }

    score, sub = calculate_composite_score_v2(candidate, universe, 0.0)
    assert 0 <= score <= 1


# ── 6. 기존 4팩터 하위 호환 테스트 ──


def test_legacy_calculate_composite_score_still_works():
    """기존 calculate_composite_score 함수 유지"""
    from analysis.composite_score import calculate_composite_score

    candidate = {"month_return": 10.0, "rsi_14": 55.0, "sentiment": 0.5}
    score, sub = calculate_composite_score(
        candidate, [-5, 0, 5, 10, 15], [30, 40, 50, 55, 70], 0.3
    )
    assert 0 <= score <= 1
    assert "return" in sub


# ── 7. DB 마이그레이션 테스트 ──


def test_opportunities_table_has_new_columns():
    """opportunities 테이블에 신규 sub_scores 컬럼 존재"""
    from db.init_db import init_schema

    conn = sqlite3.connect(":memory:")
    init_schema(conn)

    cursor = conn.execute("PRAGMA table_info(opportunities)")
    columns = {row[1] for row in cursor.fetchall()}

    for col in ["score_value", "score_quality", "score_growth"]:
        assert col in columns, f"컬럼 없음: {col}"

    conn.close()


# ── 8. 유니버스 데이터 빌드 테스트 ──


def test_build_universe_stats():
    """펀더멘탈 데이터에서 유니버스 통계 추출"""
    from analysis.composite_score import build_universe_stats

    fundamentals = [
        {"ticker": "A", "per": 10, "pbr": 1.0, "roe": 15, "debt_ratio": 50, "fcf": 1e9, "revenue_growth": 10, "eps": 5000},
        {"ticker": "B", "per": 20, "pbr": 2.0, "roe": 20, "debt_ratio": 80, "fcf": 2e9, "revenue_growth": 20, "eps": 8000},
        {"ticker": "C", "per": 30, "pbr": 3.0, "roe": 10, "debt_ratio": 100, "fcf": -1e8, "revenue_growth": 5, "eps": 3000},
    ]

    stats = build_universe_stats(fundamentals)
    assert len(stats["per"]) == 3
    assert len(stats["roe"]) == 3
    assert len(stats["revenue_growth"]) == 3
    assert 10 in stats["per"]
    assert 20 in stats["per"]


def test_build_universe_stats_skips_none():
    """None 값은 유니버스 통계에서 제외"""
    from analysis.composite_score import build_universe_stats

    fundamentals = [
        {"ticker": "A", "per": 10, "pbr": 1.0, "roe": None, "debt_ratio": 50, "fcf": None, "revenue_growth": 10, "eps": None},
        {"ticker": "B", "per": None, "pbr": None, "roe": 20, "debt_ratio": None, "fcf": 1e9, "revenue_growth": None, "eps": 5000},
    ]

    stats = build_universe_stats(fundamentals)
    assert stats["per"] == [10]
    assert stats["roe"] == [20]
    assert stats["fcf"] == [1e9]


def test_build_universe_stats_empty():
    """빈 리스트"""
    from analysis.composite_score import build_universe_stats

    stats = build_universe_stats([])
    assert stats["per"] == []
    assert stats["roe"] == []


# ── 9. EPS 성장률 계산 테스트 ──


def test_calculate_eps_growth():
    """EPS 성장률 계산 (이전 EPS 대비)"""
    from analysis.composite_score import calculate_eps_growth

    # 5000 → 8000: +60%
    assert calculate_eps_growth(8000, 5000) == 60.0
    # None 처리
    assert calculate_eps_growth(None, 5000) is None
    assert calculate_eps_growth(8000, None) is None
    assert calculate_eps_growth(8000, 0) is None


# ── 10. 극단값 테스트 ──


def test_value_score_negative_per():
    """음수 PER (적자 기업) 처리"""
    from analysis.composite_score import calculate_value_score

    score = calculate_value_score(
        per=-5.0, pbr=0.5,
        universe_per=[-5, 10, 20, 30],
        universe_pbr=[0.5, 1.0, 2.0, 3.0],
    )
    assert 0 <= score <= 1


def test_quality_score_extreme_debt():
    """극단적 부채비율"""
    from analysis.composite_score import calculate_quality_score

    score = calculate_quality_score(
        roe=5.0, debt_ratio=500.0, fcf=-1e10,
        universe_roe=[5, 15, 25],
        universe_debt=[50, 100, 500],
        universe_fcf=[-1e10, 0, 1e10],
    )
    assert 0 <= score <= 1
    assert score < 0.5  # 나쁜 퀄리티

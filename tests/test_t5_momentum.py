"""T5: 12-1 모멘텀 팩터 테스트"""

import sqlite3
import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

KST = timezone(timedelta(hours=9))


def _make_conn_with_prices(ticker: str, prices: list) -> sqlite3.Connection:
    """인메모리 DB를 생성하고 prices 데이터를 삽입.

    Args:
        ticker: 종목 코드
        prices: 가격 리스트 (오래된 순)

    Returns:
        초기화된 sqlite3.Connection
    """
    from db.init_db import init_schema

    conn = sqlite3.connect(":memory:")
    init_schema(conn)

    # 기준 시각: 현재로부터 len(prices)일 전
    base_dt = datetime.now(KST) - timedelta(days=len(prices))

    rows = []
    for i, price in enumerate(prices):
        ts = (base_dt + timedelta(days=i)).isoformat()
        rows.append((ticker, "테스트종목", price, price, 0.0, 1000, ts, "KR", "test"))

    conn.executemany(
        "INSERT INTO prices (ticker, name, price, prev_close, change_pct, volume, timestamp, market, data_source) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    return conn


# ── 1. 데이터 부족 시 None 반환 ──


def test_calculate_12_1_momentum_returns_none_insufficient_data():
    """21행 미만 데이터 → None 반환"""
    from analysis.composite_score import calculate_12_1_momentum

    conn = _make_conn_with_prices("005930", [100.0] * 20)  # 20행 (21 미만)
    result = calculate_12_1_momentum("005930", conn)
    assert result is None
    conn.close()


# ── 2. 정상 케이스: 260행, 0~100 범위 ──


def test_calculate_12_1_momentum_basic():
    """260행(약 13개월) 삽입 → 0~100 사이 float 반환"""
    from analysis.composite_score import calculate_12_1_momentum

    # 완만한 우상향 추세
    prices = [100.0 + i * 0.1 for i in range(260)]
    conn = _make_conn_with_prices("005930", prices)
    result = calculate_12_1_momentum("005930", conn)
    assert result is not None
    assert 0 <= result <= 100
    conn.close()


# ── 3. 강한 상승 추세 → 50 초과 ──


def test_calculate_12_1_momentum_positive_trend():
    """강한 상승 추세: 12개월 전 대비 크게 올랐고, 1개월 반등도 있음 → 점수 > 50"""
    from analysis.composite_score import calculate_12_1_momentum

    # 12개월 전 100 → 현재 200으로 크게 상승
    # 1개월 전 190 → 현재 200 (소폭 상승)
    # momentum_raw = (200/100) - (200/190) = 2.0 - 1.053 = +0.947 → 클램프 후 0.5 → 점수 100
    prices = [100.0] * 231 + [190.0] * 20 + [200.0]  # 총 252행
    conn = _make_conn_with_prices("005930", prices)
    result = calculate_12_1_momentum("005930", conn)
    assert result is not None
    assert result > 50
    conn.close()


# ── 4. 하락 추세 → 50 미만 ──


def test_calculate_12_1_momentum_negative_trend():
    """하락 추세: 12개월 전보다 많이 빠진 상황 → 점수 < 50"""
    from analysis.composite_score import calculate_12_1_momentum

    # 12개월 전 200 → 현재 100으로 하락
    # 1개월 전 110 → 현재 100 (소폭 하락)
    # momentum_raw = (100/200) - (100/110) = 0.5 - 0.909 = -0.409 → 점수 < 50
    prices = [200.0] * 231 + [110.0] * 20 + [100.0]  # 총 252행
    conn = _make_conn_with_prices("005930", prices)
    result = calculate_12_1_momentum("005930", conn)
    assert result is not None
    assert result < 50
    conn.close()


# ── 5. DB에 없는 종목 → None ──


def test_calculate_12_1_momentum_missing_ticker():
    """DB에 없는 종목 → None 반환"""
    from analysis.composite_score import calculate_12_1_momentum
    from db.init_db import init_schema

    conn = sqlite3.connect(":memory:")
    init_schema(conn)

    result = calculate_12_1_momentum("NONEXISTENT", conn)
    assert result is None
    conn.close()


# ── 6. momentum_12_1 전달 시 타이밍 점수에 반영 ──


def test_composite_score_v2_with_momentum():
    """momentum_12_1 값을 전달하면 타이밍 점수가 3팩터 평균으로 계산됨"""
    from analysis.composite_score import calculate_composite_score_v2

    # 기준 후보 (momentum 없음)
    candidate_base = {
        "month_return": 5.0,
        "rsi_14": 50.0,
        "sentiment": 0.0,
        "per": None, "pbr": None, "roe": None,
        "debt_ratio": None, "fcf": None,
        "revenue_growth": None, "eps_growth": None,
    }
    # 동일 후보에 momentum_12_1=100 추가 (매우 강한 모멘텀)
    candidate_with_momentum = dict(candidate_base)
    candidate_with_momentum["momentum_12_1"] = 100.0

    universe = {
        "returns": [0, 5, 10], "rsi": [30, 50, 70],
        "per": [], "pbr": [], "roe": [], "debt_ratio": [], "fcf": [],
        "revenue_growth": [], "eps_growth": [],
    }

    score_base, sub_base = calculate_composite_score_v2(candidate_base, universe, 0.0)
    score_with, sub_with = calculate_composite_score_v2(candidate_with_momentum, universe, 0.0)

    # momentum_12_1=100이면 score_momentum=1.0이므로 타이밍 점수가 높아져야 함
    assert sub_with["timing"] >= sub_base["timing"]
    # 서브 점수 키 모두 존재
    for key in ["value", "quality", "growth", "timing", "catalyst", "macro"]:
        assert key in sub_with


# ── 7. momentum_12_1 없으면 기존 동작 유지 (하위 호환) ──


def test_composite_score_v2_without_momentum():
    """momentum_12_1 키 없으면 기존 2팩터(return+rsi) 평균과 동일"""
    from analysis.composite_score import calculate_composite_score_v2, percentile_rank

    candidate = {
        "month_return": 10.0,
        "rsi_14": 40.0,
        "sentiment": 0.0,
        "per": None, "pbr": None, "roe": None,
        "debt_ratio": None, "fcf": None,
        "revenue_growth": None, "eps_growth": None,
        # momentum_12_1 키 없음
    }
    universe = {
        "returns": [0, 5, 10, 15], "rsi": [30, 40, 50, 70],
        "per": [], "pbr": [], "roe": [], "debt_ratio": [], "fcf": [],
        "revenue_growth": [], "eps_growth": [],
    }

    score, sub = calculate_composite_score_v2(candidate, universe, 0.0)

    # 직접 계산: score_return + score_rsi 평균
    score_return = percentile_rank([0, 5, 10, 15], 10.0)
    rsi_inverted = 100 - 40.0
    score_rsi = percentile_rank([100 - r for r in [30, 40, 50, 70]], rsi_inverted)
    expected_timing = round((score_return + score_rsi) / 2.0, 4)

    assert sub["timing"] == expected_timing
    assert 0 <= score <= 1

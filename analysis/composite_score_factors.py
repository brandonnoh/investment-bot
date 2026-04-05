"""팩터 계산 레이어 — 개별 팩터 점수 함수 모음

composite_score.py에서 분리된 팩터 계산 전용 모듈.
밸류/퀄리티/성장/모멘텀 등 개별 팩터 점수를 산출하는 함수만 포함.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# percentile_rank는 composite_score.py에 있으나, 팩터 계산에 필요하므로 직접 구현
# (순환 임포트 방지)


def _percentile_rank(values: list, value: float) -> float:
    """0~1 사이 백분위 순위. 이상치에 강건. (내부 전용)"""
    if not values:
        return 0.5
    count_below = sum(1 for v in values if v < value)
    count_equal = sum(1 for v in values if v == value)
    n = len(values)
    if n == 0:
        return 0.5
    return (count_below + 0.5 * count_equal) / n


def calculate_12_1_momentum(ticker: str, conn) -> float | None:
    """12-1 모멘텀 팩터 계산.

    DB의 prices 테이블에서 해당 종목의 가격 이력을 조회하여
    중기 모멘텀(12개월 전 대비 수익률에서 1개월 전 대비 수익률을 차감)을 산출.

    Args:
        ticker: 종목 코드
        conn: sqlite3.Connection 객체

    Returns:
        0~100 사이 모멘텀 점수. 데이터 부족(21행 미만)이면 None.
    """
    cursor = conn.cursor()

    # 해당 종목의 가격 이력을 시간순으로 조회
    cursor.execute(
        "SELECT price FROM prices WHERE ticker = ? ORDER BY timestamp ASC",
        (ticker,),
    )
    rows = cursor.fetchall()

    # 최소 21행(약 1개월) 미만이면 None 반환
    if len(rows) < 21:
        return None

    prices = [row[0] for row in rows]
    current_price = prices[-1]

    # 1개월 전(약 21거래일): 인덱스 -21 (21번째 마지막 행)
    price_1m = prices[-21]

    # 12개월 전(약 252거래일): 데이터가 252개 이상이면 252번째, 아니면 가장 오래된 값 사용
    price_12m_idx = max(0, len(prices) - 252)
    price_12m = prices[price_12m_idx]

    # 0으로 나누기 방지
    if price_12m == 0 or price_1m == 0:
        return None

    # 12-1 모멘텀: 장기 수익률 - 단기 수익률
    momentum_raw = (current_price / price_12m) - (current_price / price_1m)

    # [-0.5, 0.5] 범위로 클램핑 후 [0, 100]으로 정규화
    clamped = max(-0.5, min(0.5, momentum_raw))
    score = (clamped + 0.5) * 100.0

    return round(score, 2)


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
        scores.append(1.0 - _percentile_rank(universe_per, per))
    if pbr is not None and universe_pbr:
        scores.append(1.0 - _percentile_rank(universe_pbr, pbr))

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
        scores.append(_percentile_rank(universe_roe, roe))
    if debt_ratio is not None and universe_debt:
        # 역순: 낮은 부채비율이 높은 점수
        scores.append(1.0 - _percentile_rank(universe_debt, debt_ratio))
    if fcf is not None and universe_fcf:
        scores.append(_percentile_rank(universe_fcf, fcf))

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
        scores.append(_percentile_rank(universe_rev_growth, revenue_growth))
    if eps_growth is not None and universe_eps_growth:
        scores.append(_percentile_rank(universe_eps_growth, eps_growth))

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

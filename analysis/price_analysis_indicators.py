#!/usr/bin/env python3
"""
변동성/추세/범위 기술 지표 계산 모듈
52주 고저, 변동성, 추세, 지지/저항

price_analysis.py에서 분리된 서브모듈.
모멘텀 지표(MA, RSI)는 price_analysis_momentum.py에서 관리.

하위 호환 re-export: 이 파일에서 모든 지표 함수를 임포트 가능.
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis.price_analysis_calc import _calc_trend_duration

# 모멘텀 지표 re-export (하위 호환)
from analysis.price_analysis_momentum import (  # noqa: F401
    calc_moving_averages,
    calc_rsi,
    get_ma_signal,
    get_rsi_signal,
)
from config import ANALYSIS_PARAMS

# ── 52주 고저 ──


def calc_52w_range(conn, ticker):
    """52주 최고/최저 + 현재 위치 계산

    Returns:
        dict: {"high_52w", "low_52w", "position_52w", "current"}
    """
    days = ANALYSIS_PARAMS["week_52_days"]

    rows = conn.execute(
        """SELECT high, low, close FROM prices_daily
           WHERE ticker = ? ORDER BY date DESC LIMIT ?""",
        (ticker, days),
    ).fetchall()

    if not rows:
        return {
            "high_52w": None,
            "low_52w": None,
            "position_52w": None,
            "current": None,
        }

    current = rows[0][2]  # 최신 close
    high_52w = max(r[0] for r in rows)
    low_52w = min(r[1] for r in rows)

    # 현재 위치 (%)
    range_52w = high_52w - low_52w
    if range_52w > 0:
        position_pct = ((current - low_52w) / range_52w) * 100
        position_pct = round(position_pct, 1)
        if position_pct <= 25:
            position_str = f"하단 {position_pct}%"
        elif position_pct >= 75:
            position_str = f"상단 {position_pct}%"
        else:
            position_str = f"중단 {position_pct}%"
    else:
        position_str = "변동 없음"

    return {
        "high_52w": round(high_52w, 2),
        "low_52w": round(low_52w, 2),
        "position_52w": position_str,
        "current": round(current, 2),
    }


# ── 변동성 ──


def calc_volatility(conn, ticker, period=None):
    """30일 변동성 계산 (일간 수익률 표준편차, 연환산 %)

    Returns:
        float|None: 변동성 (%), 데이터 부족 시 None
    """
    if period is None:
        period = ANALYSIS_PARAMS["volatility_period"]

    # period+1개 데이터 필요 (수익률 = period개)
    rows = conn.execute(
        """SELECT close FROM prices_daily
           WHERE ticker = ? ORDER BY date DESC LIMIT ?""",
        (ticker, period + 1),
    ).fetchall()

    if len(rows) < period + 1:
        return None

    closes = [r[0] for r in reversed(rows)]

    # 일간 수익률
    returns = []
    for i in range(1, len(closes)):
        if closes[i - 1] != 0:
            daily_return = (closes[i] - closes[i - 1]) / closes[i - 1]
            returns.append(daily_return)

    if not returns:
        return None

    # 표준편차 계산
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / len(returns)
    std_dev = math.sqrt(variance)

    # 연환산 변동성 (%) = 일간 표준편차 × √252 × 100
    annualized = std_dev * math.sqrt(252) * 100
    return round(annualized, 2)


# ── 추세 판단 ──


def calc_trend(conn, ticker):
    """추세 판단 (uptrend/downtrend/sideways) + 지속 일수

    MA20 기울기 기반 판단:
    - MA20이 3일 연속 상승 → uptrend
    - MA20이 3일 연속 하락 → downtrend
    - 그 외 → sideways

    Returns:
        dict: {"trend": str|None, "trend_duration_days": int}
    """
    period = ANALYSIS_PARAMS["trend_period"]

    rows = conn.execute(
        """SELECT close FROM prices_daily
           WHERE ticker = ? ORDER BY date DESC LIMIT ?""",
        (ticker, period + 5),  # 여유분
    ).fetchall()

    if len(rows) < 5:
        return {"trend": None, "trend_duration_days": 0}

    closes = [r[0] for r in reversed(rows)]

    # 최근 5일 MA5 추세로 판단
    if len(closes) < 10:
        # 단순 가격 기울기로 판단
        recent = closes[-5:]
        change_pct = (recent[-1] - recent[0]) / recent[0] * 100 if recent[0] != 0 else 0

        if change_pct > 1:
            trend = "uptrend"
        elif change_pct < -1:
            trend = "downtrend"
        else:
            trend = "sideways"
    else:
        # MA5 시리즈 계산
        ma5_series = []
        for i in range(4, len(closes)):
            ma5 = sum(closes[i - 4: i + 1]) / 5
            ma5_series.append(ma5)

        # 최근 MA5 추세 판단
        recent_ma = ma5_series[-5:]
        up_count = sum(
            1 for i in range(1, len(recent_ma)) if recent_ma[i] > recent_ma[i - 1]
        )
        down_count = sum(
            1 for i in range(1, len(recent_ma)) if recent_ma[i] < recent_ma[i - 1]
        )

        if up_count >= 3:
            trend = "uptrend"
        elif down_count >= 3:
            trend = "downtrend"
        else:
            trend = "sideways"

    # 추세 지속 일수 계산
    duration = _calc_trend_duration(closes, trend)

    return {"trend": trend, "trend_duration_days": duration}


# ── 지지/저항 ──


def calc_support_resistance(conn, ticker, period=None):
    """지지선/저항선 추정 (최근 N일 고/저 기반)

    Returns:
        dict: {"support": float|None, "resistance": float|None}
    """
    if period is None:
        period = ANALYSIS_PARAMS["support_resistance_period"]

    rows = conn.execute(
        """SELECT high, low FROM prices_daily
           WHERE ticker = ? ORDER BY date DESC LIMIT ?""",
        (ticker, period),
    ).fetchall()

    if not rows:
        return {"support": None, "resistance": None}

    # 지지선: 최근 N일 저가 중 하위 25% 평균
    # 저항선: 최근 N일 고가 중 상위 25% 평균
    lows = sorted(r[1] for r in rows)
    highs = sorted((r[0] for r in rows), reverse=True)

    q1_count = max(1, len(lows) // 4)
    support = sum(lows[:q1_count]) / q1_count
    resistance = sum(highs[:q1_count]) / q1_count

    return {
        "support": round(support, 2),
        "resistance": round(resistance, 2),
    }

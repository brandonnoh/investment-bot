#!/usr/bin/env python3
"""
리스트 기반 순수 계산 함수 — 역사 데이터(list[dict]) 입력
DB 없이 Yahoo/네이버에서 받은 일봉 리스트만으로 기술 지표를 계산한다.
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import ANALYSIS_PARAMS


def calc_ma_from_list(closes, periods=None):
    """종가 리스트에서 이동평균 계산

    Args:
        closes: 오래된순 종가 리스트
        periods: MA 기간 리스트 (기본 [5, 20, 60])
    Returns:
        dict: {"ma5": float|None, "ma20": float|None, "ma60": float|None}
    """
    if periods is None:
        periods = ANALYSIS_PARAMS["ma_periods"]
    result = {}
    for p in periods:
        key = f"ma{p}"
        if len(closes) >= p:
            result[key] = round(sum(closes[-p:]) / p, 2)
        else:
            result[key] = None
    return result


def calc_rsi_from_list(closes, period=None):
    """종가 리스트에서 RSI 계산

    Args:
        closes: 오래된순 종가 리스트
        period: RSI 기간 (기본 14)
    Returns:
        float|None
    """
    if period is None:
        period = ANALYSIS_PARAMS["rsi_period"]

    if len(closes) < period + 1:
        return None

    recent = closes[-(period + 1):]
    gains = []
    losses = []
    for i in range(1, len(recent)):
        change = recent[i] - recent[i - 1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _calc_trend_duration(closes, trend):
    """현재 추세가 몇 일째 지속되는지 계산"""
    if trend is None or len(closes) < 2:
        return 0

    duration = 0
    for i in range(len(closes) - 1, 0, -1):
        if trend == "uptrend" and closes[i] >= closes[i - 1] or trend == "downtrend" and closes[i] <= closes[i - 1]:
            duration += 1
        elif trend == "sideways":
            change = (
                abs(closes[i] - closes[i - 1]) / closes[i - 1] * 100
                if closes[i - 1] != 0
                else 0
            )
            if change < 1:
                duration += 1
            else:
                break
        else:
            break

    return max(duration, 1)


def calc_trend_from_list(closes):
    """종가 리스트에서 추세 판단

    Returns:
        dict: {"trend": str|None, "trend_duration_days": int}
    """
    if len(closes) < 5:
        return {"trend": None, "trend_duration_days": 0}

    if len(closes) < 10:
        recent = closes[-5:]
        change_pct = (recent[-1] - recent[0]) / recent[0] * 100 if recent[0] != 0 else 0
        if change_pct > 1:
            trend = "uptrend"
        elif change_pct < -1:
            trend = "downtrend"
        else:
            trend = "sideways"
    else:
        ma5_series = []
        for i in range(4, len(closes)):
            ma5 = sum(closes[i - 4: i + 1]) / 5
            ma5_series.append(ma5)
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

    duration = _calc_trend_duration(closes, trend)
    return {"trend": trend, "trend_duration_days": duration}


def calc_volatility_from_list(closes, period=None):
    """종가 리스트에서 변동성 계산

    Returns:
        float|None: 연환산 변동성 (%)
    """
    if period is None:
        period = ANALYSIS_PARAMS["volatility_period"]

    if len(closes) < period + 1:
        return None

    recent = closes[-(period + 1):]
    returns = []
    for i in range(1, len(recent)):
        if recent[i - 1] != 0:
            returns.append((recent[i] - recent[i - 1]) / recent[i - 1])

    if not returns:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / len(returns)
    std_dev = math.sqrt(variance)
    return round(std_dev * math.sqrt(252) * 100, 2)


def calc_support_resistance_from_list(history):
    """역사 데이터에서 지지/저항선 계산

    Args:
        history: [{"high": ..., "low": ...}, ...] 리스트
    Returns:
        dict: {"support": float|None, "resistance": float|None}
    """
    period = ANALYSIS_PARAMS["support_resistance_period"]
    recent = history[-period:] if len(history) >= period else history
    if not recent:
        return {"support": None, "resistance": None}

    lows = sorted(r["low"] for r in recent)
    highs = sorted((r["high"] for r in recent), reverse=True)
    q1_count = max(1, len(lows) // 4)
    support = sum(lows[:q1_count]) / q1_count
    resistance = sum(highs[:q1_count]) / q1_count
    return {"support": round(support, 2), "resistance": round(resistance, 2)}


def analyze_from_history(history, get_ma_signal_fn, get_rsi_signal_fn):
    """역사 데이터(리스트)로 전체 기술 분석 수행

    Args:
        history: [{"date": ..., "close": ..., "high": ..., "low": ...}, ...]
        get_ma_signal_fn: MA 신호 판단 함수 (price_analysis에서 주입)
        get_rsi_signal_fn: RSI 신호 판단 함수 (price_analysis에서 주입)
    Returns:
        dict: 분석 결과
    """
    closes = [h["close"] for h in history]
    ma = calc_ma_from_list(closes)
    rsi = calc_rsi_from_list(closes)
    vol = calc_volatility_from_list(closes)
    trend = calc_trend_from_list(closes)
    sr = calc_support_resistance_from_list(history)

    current = closes[-1] if closes else None
    high_52w = max(h["high"] for h in history) if history else None
    low_52w = min(h["low"] for h in history) if history else None

    position_str = None
    if high_52w is not None and low_52w is not None:
        range_52w = high_52w - low_52w
        if range_52w > 0 and current is not None:
            position_pct = round(((current - low_52w) / range_52w) * 100, 1)
            if position_pct <= 25:
                position_str = f"하단 {position_pct}%"
            elif position_pct >= 75:
                position_str = f"상단 {position_pct}%"
            else:
                position_str = f"중단 {position_pct}%"
        else:
            position_str = "변동 없음"

    return {
        "current": round(current, 2) if current else None,
        "ma5": ma.get("ma5"),
        "ma20": ma.get("ma20"),
        "ma60": ma.get("ma60"),
        "ma_signal": get_ma_signal_fn(ma.get("ma5"), ma.get("ma20"), ma.get("ma60")),
        "rsi_14": rsi,
        "rsi_signal": get_rsi_signal_fn(rsi),
        "high_52w": round(high_52w, 2) if high_52w else None,
        "low_52w": round(low_52w, 2) if low_52w else None,
        "position_52w": position_str,
        "volatility_30d": vol,
        "trend": trend["trend"],
        "trend_duration_days": trend["trend_duration_days"],
        "support": sr["support"],
        "resistance": sr["resistance"],
        "data_points": len(history),
    }

#!/usr/bin/env python3
"""
모멘텀 기술 지표 계산 모듈
MA(이동평균), RSI 계산 및 신호 판단

price_analysis_indicators.py에서 분리된 서브모듈.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import ANALYSIS_PARAMS


# ── 이동평균 ──


def calc_moving_averages(conn, ticker, data_points):
    """MA5, MA20, MA60 이동평균 계산 (prices_daily 기반)

    Args:
        conn: sqlite3.Connection
        ticker: 종목 코드
        data_points: 가용 데이터 수 (최적화용, 실제 쿼리로 확인)
    Returns:
        dict: {"ma5": float|None, "ma20": float|None, "ma60": float|None}
    """
    result = {"ma5": None, "ma20": None, "ma60": None}
    periods = ANALYSIS_PARAMS["ma_periods"]  # [5, 20, 60]

    for period in periods:
        key = f"ma{period}"
        rows = conn.execute(
            """SELECT close FROM prices_daily
               WHERE ticker = ? ORDER BY date DESC LIMIT ?""",
            (ticker, period),
        ).fetchall()

        if len(rows) >= period:
            avg = sum(r[0] for r in rows) / period
            result[key] = round(avg, 2)

    return result


def get_ma_signal(ma5, ma20, ma60):
    """MA 배열 기반 신호 판단

    Returns:
        str: 상승/하락/혼조/데이터 부족
    """
    values = [ma5, ma20, ma60]
    if any(v is None for v in values):
        return "데이터 부족"

    if ma5 > ma20 > ma60:
        return "상승 (5일선 > 20일선 > 60일선)"
    elif ma5 < ma20 < ma60:
        return "하락 (5일선 < 20일선 < 60일선)"
    else:
        return "혼조 (정배열/역배열 아님)"


# ── RSI ──


def calc_rsi(conn, ticker, period=None):
    """RSI (Relative Strength Index) 계산

    Args:
        conn: sqlite3.Connection
        ticker: 종목 코드
        period: RSI 기간 (기본 14)
    Returns:
        float|None: RSI 값 (0~100), 데이터 부족 시 None
    """
    if period is None:
        period = ANALYSIS_PARAMS["rsi_period"]

    # period+1개 데이터 필요 (변화량 = period개)
    rows = conn.execute(
        """SELECT close FROM prices_daily
           WHERE ticker = ? ORDER BY date DESC LIMIT ?""",
        (ticker, period + 1),
    ).fetchall()

    if len(rows) < period + 1:
        return None

    # 최신순 → 오래된순으로 뒤집기
    closes = [r[0] for r in reversed(rows)]

    # 일간 변화량 계산
    gains = []
    losses = []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
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
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)


def get_rsi_signal(rsi):
    """RSI 구간별 신호

    Returns:
        str: 과매수/과매도/중립 등
    """
    if rsi is None:
        return "데이터 부족"
    if rsi >= 70:
        return "과매수"
    elif rsi >= 60:
        return "과매수 접근"
    elif rsi <= 30:
        return "과매도"
    elif rsi <= 40:
        return "과매도 접근"
    else:
        return "중립"

#!/usr/bin/env python3
"""
기술 분석 엔진 — prices_daily 기반
MA5/20/60, RSI, 52주 고저, 변동성, 추세, 지지/저항 계산
출력: output/intel/price_analysis.json
"""

import json
import math
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import PORTFOLIO, DB_PATH, OUTPUT_DIR, ANALYSIS_PARAMS

KST = timezone(timedelta(hours=9))


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
            ma5 = sum(closes[i - 4 : i + 1]) / 5
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


def _calc_trend_duration(closes, trend):
    """현재 추세가 몇 일째 지속되는지 계산"""
    if trend is None or len(closes) < 2:
        return 0

    duration = 0
    for i in range(len(closes) - 1, 0, -1):
        if trend == "uptrend" and closes[i] >= closes[i - 1]:
            duration += 1
        elif trend == "downtrend" and closes[i] <= closes[i - 1]:
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


# ── 종목별 분석 통합 ──


def analyze_ticker(conn, ticker):
    """단일 종목 기술 분석 실행

    Returns:
        dict: 모든 분석 결과 통합
    """
    # 데이터 포인트 수 확인
    row = conn.execute(
        "SELECT COUNT(*) FROM prices_daily WHERE ticker = ?",
        (ticker,),
    ).fetchone()
    data_points = row[0] if row else 0

    if data_points == 0:
        return {
            "current": None,
            "ma5": None,
            "ma20": None,
            "ma60": None,
            "ma_signal": "데이터 부족",
            "rsi_14": None,
            "rsi_signal": "데이터 부족",
            "high_52w": None,
            "low_52w": None,
            "position_52w": None,
            "volatility_30d": None,
            "trend": None,
            "trend_duration_days": 0,
            "support": None,
            "resistance": None,
            "data_points": 0,
        }

    # 각 분석 함수 호출
    ma = calc_moving_averages(conn, ticker, data_points)
    rsi = calc_rsi(conn, ticker)
    range_52w = calc_52w_range(conn, ticker)
    vol = calc_volatility(conn, ticker)
    trend = calc_trend(conn, ticker)
    sr = calc_support_resistance(conn, ticker)

    return {
        "current": range_52w["current"],
        "ma5": ma["ma5"],
        "ma20": ma["ma20"],
        "ma60": ma["ma60"],
        "ma_signal": get_ma_signal(ma["ma5"], ma["ma20"], ma["ma60"]),
        "rsi_14": rsi,
        "rsi_signal": get_rsi_signal(rsi),
        "high_52w": range_52w["high_52w"],
        "low_52w": range_52w["low_52w"],
        "position_52w": range_52w["position_52w"],
        "volatility_30d": vol,
        "trend": trend["trend"],
        "trend_duration_days": trend["trend_duration_days"],
        "support": sr["support"],
        "resistance": sr["resistance"],
        "data_points": data_points,
    }


# ── run() 진입점 ──


def run(conn=None, output_dir=None, tickers=None):
    """기술 분석 실행 + price_analysis.json 출력

    Args:
        conn: sqlite3.Connection (None이면 파일 DB 사용)
        output_dir: 출력 디렉토리 (None이면 config.OUTPUT_DIR)
        tickers: 분석 대상 종목 리스트 [{"ticker": ..., "name": ...}]
                 None이면 config.PORTFOLIO 사용
    """
    print("📈 기술 분석 시작...")

    if output_dir is None:
        output_dir = OUTPUT_DIR
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if tickers is None:
        tickers = [{"ticker": p["ticker"], "name": p["name"]} for p in PORTFOLIO]

    own_conn = False
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        own_conn = True

    try:
        analysis = {}
        for t in tickers:
            ticker = t["ticker"]
            name = t.get("name", ticker)
            try:
                result = analyze_ticker(conn, ticker)
                result["name"] = name
                analysis[ticker] = result
            except Exception as e:
                print(f"  ⚠️ {ticker} 분석 실패: {e}")
                analysis[ticker] = {
                    "name": name,
                    "current": None,
                    "ma5": None,
                    "ma20": None,
                    "ma60": None,
                    "ma_signal": "분석 실패",
                    "rsi_14": None,
                    "rsi_signal": "분석 실패",
                    "high_52w": None,
                    "low_52w": None,
                    "position_52w": None,
                    "volatility_30d": None,
                    "trend": None,
                    "trend_duration_days": 0,
                    "support": None,
                    "resistance": None,
                    "data_points": 0,
                }

        now = datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S+09:00")
        output = {
            "updated_at": now,
            "analysis": analysis,
        }

        output_file = output_dir / "price_analysis.json"
        output_file.write_text(json.dumps(output, ensure_ascii=False, indent=2))
        print(f"  ✅ {len(analysis)}개 종목 분석 완료 → {output_file}")

    finally:
        if own_conn:
            conn.close()

    return output


if __name__ == "__main__":
    run()

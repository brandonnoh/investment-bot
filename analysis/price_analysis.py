#!/usr/bin/env python3
"""
기술 분석 엔진 — prices_daily 기반
MA5/20/60, RSI, 52주 고저, 변동성, 추세, 지지/저항 계산
출력: output/intel/price_analysis.json
"""

import json
import logging
import math
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (
    PORTFOLIO,
    DB_PATH,
    OUTPUT_DIR,
    ANALYSIS_PARAMS,
    YAHOO_HEADERS,
    YAHOO_TIMEOUT,
    HTTP_RETRY_CONFIG,
)
from utils.http import retry_request

KST = timezone(timedelta(hours=9))
logger = logging.getLogger(__name__)

# RSI/추세 분석에 필요한 최소 데이터 포인트
MIN_DATA_POINTS = 15


# ── Yahoo/네이버 역사 데이터 보충 ──


def fetch_yahoo_history(ticker):
    """Yahoo Finance에서 3개월 일봉 종가 리스트 가져오기

    Args:
        ticker: Yahoo Finance 티커 (예: TSLA, 005930.KS)
    Returns:
        list[dict]: [{"date": "2025-01-01", "close": 100.0, "high": 105.0, "low": 95.0}, ...]
                    오래된순 정렬, 실패 시 빈 리스트
    """
    url = (
        f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
        f"?interval=1d&range=3mo"
    )
    try:
        body = retry_request(
            url,
            headers=YAHOO_HEADERS,
            timeout=YAHOO_TIMEOUT,
            max_retries=HTTP_RETRY_CONFIG["max_retries"],
            base_delay=HTTP_RETRY_CONFIG["base_delay"],
        )
        data = json.loads(body)
        result = data["chart"]["result"]
        if not result:
            return []

        timestamps = result[0].get("timestamp", [])
        indicators = result[0].get("indicators", {})
        quotes = indicators.get("quote", [{}])[0]
        closes = quotes.get("close", [])
        highs = quotes.get("high", [])
        lows = quotes.get("low", [])

        history = []
        for i, ts in enumerate(timestamps):
            c = closes[i] if i < len(closes) else None
            h = highs[i] if i < len(highs) else None
            lo = lows[i] if i < len(lows) else None
            if c is not None:
                dt = datetime.fromtimestamp(ts, tz=KST)
                history.append(
                    {
                        "date": dt.strftime("%Y-%m-%d"),
                        "close": float(c),
                        "high": float(h) if h is not None else float(c),
                        "low": float(lo) if lo is not None else float(c),
                    }
                )
        return history

    except Exception as e:
        logger.warning(f"Yahoo 역사 데이터 실패 ({ticker}): {e}")
        return []


def fetch_naver_history(ticker):
    """네이버 금융에서 한국 종목 3개월 일봉 가져오기 (Yahoo 실패 시 대안)

    Args:
        ticker: Yahoo 티커 (예: 005930.KS)
    Returns:
        list[dict]: [{"date": ..., "close": ..., "high": ..., "low": ...}, ...]
                    오래된순 정렬, 실패 시 빈 리스트
    """
    if not (ticker.endswith(".KS") or ticker.endswith(".KQ")):
        return []

    code = ticker.split(".")[0]
    # 네이버 차트 API: 60일치 일봉 (count=90으로 3개월 커버)
    url = (
        f"https://fchart.stock.naver.com/siseJson.nhn"
        f"?symbol={code}&requestType=1&startTime=&endTime=&timeframe=day&count=90"
    )
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com"}
    try:
        body = retry_request(
            url,
            headers=headers,
            timeout=8,
            max_retries=HTTP_RETRY_CONFIG["max_retries"],
            base_delay=HTTP_RETRY_CONFIG["base_delay"],
        )
        # 네이버 응답: 문자열 배열 형태, 첫 줄은 헤더
        text = body.decode("cp949", errors="replace").strip()
        # JSON-like 파싱 — 각 줄이 ['날짜', 시가, 고가, 저가, 종가, 거래량]
        lines = text.strip().split("\n")
        history = []
        for line in lines[1:]:  # 첫 줄 헤더 건너뛰기
            line = line.strip().rstrip(",")
            if not line:
                continue
            try:
                # 문자열을 JSON으로 파싱
                row = json.loads(f"[{line}]")
                if len(row) >= 5:
                    date_str = str(row[0]).strip().strip("'\"")
                    # YYYYMMDD → YYYY-MM-DD
                    if len(date_str) == 8:
                        date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                    history.append(
                        {
                            "date": date_str,
                            "close": float(row[4]),
                            "high": float(row[2]),
                            "low": float(row[3]),
                        }
                    )
            except (json.JSONDecodeError, ValueError, IndexError):
                continue
        return history

    except Exception as e:
        logger.warning(f"네이버 역사 데이터 실패 ({ticker}): {e}")
        return []


def get_history_data(ticker):
    """종목의 역사 데이터를 Yahoo → 네이버 순서로 가져오기

    Returns:
        tuple: (list[dict], str) — (일봉 리스트, 데이터 소스명)
    """
    # Yahoo 먼저 시도
    history = fetch_yahoo_history(ticker)
    if len(history) >= MIN_DATA_POINTS:
        return history, "yahoo_history"

    # 한국 종목이면 네이버 대안
    if ticker.endswith(".KS") or ticker.endswith(".KQ"):
        naver_history = fetch_naver_history(ticker)
        if len(naver_history) >= MIN_DATA_POINTS:
            return naver_history, "naver_history"

    # 부분 데이터라도 반환
    if history:
        return history, "yahoo_history"
    return [], "none"


# ── 리스트 기반 계산 함수 (역사 데이터 보충용) ──


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

    recent = closes[-(period + 1) :]
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
            ma5 = sum(closes[i - 4 : i + 1]) / 5
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

    recent = closes[-(period + 1) :]
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


def analyze_from_history(history):
    """역사 데이터(리스트)로 전체 기술 분석 수행

    Args:
        history: [{"date": ..., "close": ..., "high": ..., "low": ...}, ...]
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
        "ma_signal": get_ma_signal(ma.get("ma5"), ma.get("ma20"), ma.get("ma60")),
        "rsi_14": rsi,
        "rsi_signal": get_rsi_signal(rsi),
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

    DB에 충분한 데이터가 있으면 DB 기반 분석, 부족하면 Yahoo/네이버에서 보충.

    Returns:
        dict: 모든 분석 결과 통합
    """
    # 데이터 포인트 수 확인
    row = conn.execute(
        "SELECT COUNT(*) FROM prices_daily WHERE ticker = ?",
        (ticker,),
    ).fetchone()
    data_points = row[0] if row else 0

    # DB 데이터가 충분하면 기존 DB 기반 분석
    if data_points >= MIN_DATA_POINTS:
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
            "data_source": "db_history",
        }

    # DB 데이터 부족 → Yahoo/네이버에서 역사 데이터 보충
    # 금 현물(GOLD_KRW_G)은 Yahoo 티커가 아니므로 건너뜀
    if ticker.startswith("GOLD_KRW"):
        print(f"  ⚠️ {ticker}: DB {data_points}일, 외부 소스 미지원 → 부분 분석")
        return _empty_result(data_points)

    print(
        f"  📡 {ticker}: DB {data_points}일 < {MIN_DATA_POINTS}일, Yahoo에서 보충 중..."
    )
    history, source = get_history_data(ticker)

    if not history:
        print(f"  ⚠️ {ticker}: 외부 데이터도 가져오기 실패")
        return _empty_result(data_points)

    print(f"  ✅ {ticker}: {source}에서 {len(history)}일치 확보")
    result = analyze_from_history(history)
    result["data_source"] = source
    return result


def _empty_result(data_points=0):
    """데이터 부족 시 빈 결과 반환"""
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
        "data_points": data_points,
        "data_source": "none",
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
                    "data_source": "error",
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

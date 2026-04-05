#!/usr/bin/env python3
"""
기술 분석 엔진 — prices_daily 기반
MA5/20/60, RSI, 52주 고저, 변동성, 추세, 지지/저항 계산
출력: output/intel/price_analysis.json
"""

import json
import logging
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import analysis.price_analysis_calc as _calc_mod
from analysis.price_analysis_calc import (  # noqa: F401
    _calc_trend_duration,
    calc_ma_from_list,
    calc_rsi_from_list,
    calc_support_resistance_from_list,
    calc_trend_from_list,
    calc_volatility_from_list,
)

# ── 하위 호환: 수집/계산 서브모듈 re-export ──
from analysis.price_analysis_fetch import (  # noqa: F401
    fetch_naver_history,
    fetch_yahoo_history,
    get_history_data,
)

# ── 하위 호환: 지표 계산 서브모듈 re-export ──
from analysis.price_analysis_indicators import (  # noqa: F401
    calc_52w_range,
    calc_moving_averages,
    calc_rsi,
    calc_support_resistance,
    calc_trend,
    calc_volatility,
    get_ma_signal,
    get_rsi_signal,
)
from config import (
    DB_PATH,
    OUTPUT_DIR,
)
from db.ssot import get_holdings

KST = timezone(timedelta(hours=9))
logger = logging.getLogger(__name__)

# RSI/추세 분석에 필요한 최소 데이터 포인트
MIN_DATA_POINTS = 15


# ── 역사 데이터 기반 통합 분석 (calc 모듈 래퍼) ──


def analyze_from_history(history):
    """역사 데이터(리스트)로 전체 기술 분석 수행

    Args:
        history: [{"date": ..., "close": ..., "high": ..., "low": ...}, ...]
    Returns:
        dict: 분석 결과
    """
    return _calc_mod.analyze_from_history(history, get_ma_signal, get_rsi_signal)


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
    # 금 현물(GOLD_KRW_G)은 Yahoo GC=F(금 선물 달러)로 대체
    if ticker.startswith("GOLD_KRW"):
        print(
            f"  📡 {ticker}: DB {data_points}일 < {MIN_DATA_POINTS}일, Yahoo GC=F로 보충 중..."
        )
        history = fetch_yahoo_history("GC=F")
        if history:
            # 달러/온스 → 원/그램 환산 (대략적)
            # 1 온스 = 31.1035g, 환율 ~1500원 가정 (정확도는 제한적)
            fx_rate = 1500.0  # 환율 근사값
            oz_to_gram = 31.1035
            for h in history:
                h["close"] = round(h["close"] / oz_to_gram * fx_rate, 0)
                h["high"] = (
                    round(h["high"] / oz_to_gram * fx_rate, 0)
                    if h.get("high")
                    else h["close"]
                )
                h["low"] = (
                    round(h["low"] / oz_to_gram * fx_rate, 0)
                    if h.get("low")
                    else h["close"]
                )
            print(f"  ✅ {ticker}: Yahoo GC=F에서 {len(history)}일치 (KRW 환산)")
            result = analyze_from_history(history)
            result["data_source"] = "yahoo_gold_converted"
            return result
        else:
            print(f"  ⚠️ {ticker}: Yahoo GC=F 데이터도 실패 → 부분 분석")
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
        # SSoT: DB에서 보유 종목 로드
        holdings = get_holdings()
        tickers = [{"ticker": p["ticker"], "name": p["name"]} for p in holdings]

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

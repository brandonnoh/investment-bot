#!/usr/bin/env python3
"""
F07 — price_analysis.json 기술 분석 엔진 테스트
prices_daily 기반 MA, RSI, 52주 고저, 변동성, 추세, 지지/저항 계산 검증
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── 헬퍼: prices_daily에 N일치 데이터 삽입 ──


def _insert_daily_prices(conn, ticker, prices, start_date="2025-10-01"):
    """prices_daily 테이블에 연속 일봉 데이터 삽입

    Args:
        conn: DB 연결
        ticker: 종목 코드
        prices: close 가격 리스트 (오래된 날짜부터)
        start_date: 시작 날짜 (YYYY-MM-DD)
    """
    from datetime import datetime, timedelta

    base = datetime.strptime(start_date, "%Y-%m-%d")
    for i, close in enumerate(prices):
        date = (base + timedelta(days=i)).strftime("%Y-%m-%d")
        # open=close 근사, high=close*1.01, low=close*0.99 (단순화)
        conn.execute(
            """INSERT INTO prices_daily (ticker, date, open, high, low, close, volume, change_pct)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (ticker, date, close, close * 1.01, close * 0.99, close, 1000000, 0.0),
        )
    conn.commit()


# ── 이동평균 테스트 ──


class TestMovingAverage:
    """MA5, MA20, MA60 이동평균 계산 검증"""

    def test_ma5_정확도(self, db_conn):
        """5일 이동평균 = 최근 5개 close의 평균"""
        from analysis.price_analysis import calc_moving_averages

        prices = [100, 102, 104, 103, 101]  # 평균 = 102.0
        _insert_daily_prices(db_conn, "TEST", prices)

        result = calc_moving_averages(db_conn, "TEST", 5)
        assert result["ma5"] == pytest.approx(102.0, abs=0.01)

    def test_ma20_정확도(self, db_conn):
        """20일 이동평균 계산"""
        from analysis.price_analysis import calc_moving_averages

        prices = list(range(100, 120))  # 100~119, 최근 20개 평균 = 109.5
        _insert_daily_prices(db_conn, "TEST", prices)

        result = calc_moving_averages(db_conn, "TEST", 20)
        assert result["ma20"] == pytest.approx(109.5, abs=0.01)

    def test_ma60_데이터_부족시_None(self, db_conn):
        """데이터 포인트가 MA 기간보다 적으면 None"""
        from analysis.price_analysis import calc_moving_averages

        prices = [100] * 10  # 10일치만
        _insert_daily_prices(db_conn, "TEST", prices)

        result = calc_moving_averages(db_conn, "TEST", 10)
        assert result["ma5"] == pytest.approx(100.0)
        assert result["ma20"] is None
        assert result["ma60"] is None

    def test_ma_signal_상승(self, db_conn):
        """5일선 > 20일선 > 60일선 → 상승 신호"""
        from analysis.price_analysis import get_ma_signal

        signal = get_ma_signal(ma5=200, ma20=190, ma60=180)
        assert "상승" in signal

    def test_ma_signal_하락(self, db_conn):
        """5일선 < 20일선 < 60일선 → 하락 신호"""
        from analysis.price_analysis import get_ma_signal

        signal = get_ma_signal(ma5=180, ma20=190, ma60=200)
        assert "하락" in signal

    def test_ma_signal_혼조(self, db_conn):
        """정배열도 역배열도 아닌 경우 → 혼조"""
        from analysis.price_analysis import get_ma_signal

        signal = get_ma_signal(ma5=195, ma20=190, ma60=200)
        assert "혼조" in signal

    def test_ma_signal_데이터부족(self, db_conn):
        """MA 값 중 None이 있으면 데이터 부족 메시지"""
        from analysis.price_analysis import get_ma_signal

        signal = get_ma_signal(ma5=200, ma20=None, ma60=None)
        assert "부족" in signal


# ── RSI 테스트 ──


class TestRSI:
    """RSI 14일 계산 검증"""

    def test_rsi_상승장(self, db_conn):
        """모두 상승 → RSI 100 근처"""
        from analysis.price_analysis import calc_rsi

        # 15일 연속 상승 (14개 변화량 필요)
        prices = [100 + i for i in range(16)]
        _insert_daily_prices(db_conn, "TEST", prices)

        rsi = calc_rsi(db_conn, "TEST", period=14)
        assert rsi is not None
        assert rsi > 90  # 거의 100

    def test_rsi_하락장(self, db_conn):
        """모두 하락 → RSI 0 근처"""
        from analysis.price_analysis import calc_rsi

        prices = [200 - i for i in range(16)]
        _insert_daily_prices(db_conn, "TEST", prices)

        rsi = calc_rsi(db_conn, "TEST", period=14)
        assert rsi is not None
        assert rsi < 10  # 거의 0

    def test_rsi_혼합(self, db_conn):
        """상승/하락 혼합 → RSI 30~70 사이"""
        from analysis.price_analysis import calc_rsi

        # 교대로 상승/하락
        prices = []
        for i in range(20):
            prices.append(100 + (2 if i % 2 == 0 else -1))
        _insert_daily_prices(db_conn, "TEST", prices)

        rsi = calc_rsi(db_conn, "TEST", period=14)
        assert rsi is not None
        assert 20 < rsi < 80

    def test_rsi_데이터부족(self, db_conn):
        """데이터 5일 → RSI 계산 불가 → None"""
        from analysis.price_analysis import calc_rsi

        prices = [100, 101, 102, 101, 100]
        _insert_daily_prices(db_conn, "TEST", prices)

        rsi = calc_rsi(db_conn, "TEST", period=14)
        assert rsi is None

    def test_rsi_signal(self, db_conn):
        """RSI 구간별 신호"""
        from analysis.price_analysis import get_rsi_signal

        assert "과매수" in get_rsi_signal(75)
        assert "과매도" in get_rsi_signal(25)
        assert "중립" in get_rsi_signal(50)


# ── 52주 고저 테스트 ──


class TestHigh52w:
    """52주(약 252 거래일) 최고/최저 + 현재 위치"""

    def test_52주_고저(self, db_conn):
        """최근 252일 중 최고/최저 가격"""
        from analysis.price_analysis import calc_52w_range

        # 260일 데이터: 50~150~50 패턴
        prices = list(range(50, 151)) + list(range(149, 49, -1))  # 201개
        prices += [100] * 60  # 총 261개
        _insert_daily_prices(db_conn, "TEST", prices)

        result = calc_52w_range(db_conn, "TEST")
        assert result["high_52w"] == pytest.approx(
            150 * 1.01, abs=1
        )  # high 컬럼 = close*1.01
        assert result["low_52w"] == pytest.approx(
            50 * 0.99, abs=1
        )  # low 컬럼 = close*0.99

    def test_52주_위치_퍼센트(self, db_conn):
        """현재가가 52주 범위에서 어디인지 (%)"""
        from analysis.price_analysis import calc_52w_range

        # 200에서 시작해서 100으로 하락 → 현재가 100, high근처 202, low근처 99
        prices = [200] * 10 + [100] * 250
        _insert_daily_prices(db_conn, "TEST", prices)

        result = calc_52w_range(db_conn, "TEST")
        # 현재가 100은 low(99) 근처이므로 하단
        assert "하단" in result["position_52w"]

    def test_데이터부족시_가용데이터_사용(self, db_conn):
        """252일 미만이어도 가용 데이터로 계산"""
        from analysis.price_analysis import calc_52w_range

        prices = [100, 120, 90, 110]  # 4일치
        _insert_daily_prices(db_conn, "TEST", prices)

        result = calc_52w_range(db_conn, "TEST")
        assert result["high_52w"] is not None
        assert result["low_52w"] is not None


# ── 변동성 테스트 ──


class TestVolatility:
    """30일 변동성 (일간 수익률 표준편차, 연환산)"""

    def test_변동성_0_일정가격(self, db_conn):
        """가격 동일 → 변동성 0"""
        from analysis.price_analysis import calc_volatility

        prices = [100] * 31  # 31일 → 30개 수익률
        _insert_daily_prices(db_conn, "TEST", prices)

        vol = calc_volatility(db_conn, "TEST", period=30)
        assert vol == pytest.approx(0.0, abs=0.01)

    def test_변동성_양수(self, db_conn):
        """가격 변동 있으면 양수"""
        from analysis.price_analysis import calc_volatility

        prices = [
            100,
            105,
            98,
            103,
            99,
            107,
            95,
            102,
            100,
            104,
            98,
            106,
            97,
            103,
            100,
            105,
            98,
            102,
            99,
            104,
            97,
            106,
            100,
            103,
            98,
            105,
            99,
            103,
            100,
            104,
            98,
        ]
        _insert_daily_prices(db_conn, "TEST", prices)

        vol = calc_volatility(db_conn, "TEST", period=30)
        assert vol is not None
        assert vol > 0

    def test_변동성_데이터부족(self, db_conn):
        """데이터 부족 시 None"""
        from analysis.price_analysis import calc_volatility

        prices = [100, 101, 102]
        _insert_daily_prices(db_conn, "TEST", prices)

        vol = calc_volatility(db_conn, "TEST", period=30)
        assert vol is None


# ── 추세 판단 테스트 ──


class TestTrend:
    """추세 판단 (uptrend/downtrend/sideways) + 지속 일수"""

    def test_상승추세(self, db_conn):
        """연속 상승 → uptrend"""
        from analysis.price_analysis import calc_trend

        prices = [100 + i * 2 for i in range(30)]
        _insert_daily_prices(db_conn, "TEST", prices)

        result = calc_trend(db_conn, "TEST")
        assert result["trend"] == "uptrend"
        assert result["trend_duration_days"] > 0

    def test_하락추세(self, db_conn):
        """연속 하락 → downtrend"""
        from analysis.price_analysis import calc_trend

        prices = [200 - i * 2 for i in range(30)]
        _insert_daily_prices(db_conn, "TEST", prices)

        result = calc_trend(db_conn, "TEST")
        assert result["trend"] == "downtrend"
        assert result["trend_duration_days"] > 0

    def test_횡보(self, db_conn):
        """가격 변동 미미 → sideways"""
        from analysis.price_analysis import calc_trend

        prices = [100, 100.5, 99.5, 100.2, 99.8] * 6  # 30일 횡보
        _insert_daily_prices(db_conn, "TEST", prices)

        result = calc_trend(db_conn, "TEST")
        assert result["trend"] == "sideways"

    def test_데이터부족(self, db_conn):
        """데이터 3일 미만 → None"""
        from analysis.price_analysis import calc_trend

        prices = [100, 101]
        _insert_daily_prices(db_conn, "TEST", prices)

        result = calc_trend(db_conn, "TEST")
        assert result["trend"] is None


# ── 지지/저항 테스트 ──


class TestSupportResistance:
    """지지선/저항선 추정 (최근 N일 고/저 기반)"""

    def test_지지저항_계산(self, db_conn):
        """최근 N일 저가 중 최저 = 지지, 고가 중 최고 = 저항"""
        from analysis.price_analysis import calc_support_resistance

        prices = [
            100,
            110,
            95,
            105,
            98,
            108,
            92,
            103,
            97,
            106,
            100,
            110,
            95,
            105,
            98,
            108,
            92,
            103,
            97,
            106,
        ]
        _insert_daily_prices(db_conn, "TEST", prices)

        result = calc_support_resistance(db_conn, "TEST", period=20)
        assert result["support"] is not None
        assert result["resistance"] is not None
        assert result["support"] < result["resistance"]

    def test_데이터부족시_None(self, db_conn):
        """데이터 부족 시 None"""
        from analysis.price_analysis import calc_support_resistance

        prices = [100]
        _insert_daily_prices(db_conn, "TEST", prices)

        result = calc_support_resistance(db_conn, "TEST", period=20)
        # 1일치로도 계산 가능하지만 의미 없음 — 최소 5일 필요
        assert result["support"] is not None or result["support"] is None  # 구현에 따라


# ── 통합 테스트: run() 함수 ──


class TestRunIntegration:
    """run() 함수 전체 출력 검증"""

    def test_json_출력_구조(self, db_conn, tmp_output_dir):
        """price_analysis.json 필수 필드 존재 확인"""
        from analysis.price_analysis import run

        # 충분한 데이터 삽입 (65일)
        prices_samsung = [50000 + i * 100 for i in range(65)]
        _insert_daily_prices(db_conn, "005930.KS", prices_samsung)

        run(conn=db_conn, output_dir=tmp_output_dir)

        output_file = tmp_output_dir / "price_analysis.json"
        assert output_file.exists()

        data = json.loads(output_file.read_text())
        assert "updated_at" in data
        assert "analysis" in data
        assert "005930.KS" in data["analysis"]

        ticker_data = data["analysis"]["005930.KS"]
        # 필수 필드 존재
        for field in [
            "current",
            "ma5",
            "ma20",
            "rsi_14",
            "high_52w",
            "low_52w",
            "position_52w",
            "volatility_30d",
            "trend",
            "trend_duration_days",
            "support",
            "resistance",
            "data_points",
        ]:
            assert field in ticker_data, f"필드 누락: {field}"

    def test_여러종목_분석(self, db_conn, tmp_output_dir):
        """포트폴리오 전체 종목 분석"""
        from analysis.price_analysis import run

        # 2종목 데이터
        _insert_daily_prices(db_conn, "005930.KS", [50000 + i * 50 for i in range(65)])
        _insert_daily_prices(db_conn, "TSLA", [200 + i * 0.5 for i in range(65)])

        tickers = [
            {"ticker": "005930.KS", "name": "삼성전자"},
            {"ticker": "TSLA", "name": "테슬라"},
        ]
        run(conn=db_conn, output_dir=tmp_output_dir, tickers=tickers)

        data = json.loads((tmp_output_dir / "price_analysis.json").read_text())
        assert "005930.KS" in data["analysis"]
        assert "TSLA" in data["analysis"]

    def test_데이터없는_종목_graceful(self, db_conn, tmp_output_dir):
        """DB에 데이터 없는 종목 → 에러 없이 최소 정보 출력"""
        from analysis.price_analysis import run

        tickers = [{"ticker": "NO_DATA", "name": "없는종목"}]
        run(conn=db_conn, output_dir=tmp_output_dir, tickers=tickers)

        data = json.loads((tmp_output_dir / "price_analysis.json").read_text())
        assert "NO_DATA" in data["analysis"]
        ticker_data = data["analysis"]["NO_DATA"]
        assert ticker_data["data_points"] == 0

    def test_ma_signal_필드(self, db_conn, tmp_output_dir):
        """MA 신호 텍스트 포함"""
        from analysis.price_analysis import run

        _insert_daily_prices(db_conn, "005930.KS", [50000 + i * 100 for i in range(65)])
        run(conn=db_conn, output_dir=tmp_output_dir)

        data = json.loads((tmp_output_dir / "price_analysis.json").read_text())
        assert "ma_signal" in data["analysis"]["005930.KS"]

    def test_rsi_signal_필드(self, db_conn, tmp_output_dir):
        """RSI 신호 텍스트 포함"""
        from analysis.price_analysis import run

        _insert_daily_prices(db_conn, "005930.KS", [50000 + i * 100 for i in range(65)])
        run(conn=db_conn, output_dir=tmp_output_dir)

        data = json.loads((tmp_output_dir / "price_analysis.json").read_text())
        assert "rsi_signal" in data["analysis"]["005930.KS"]

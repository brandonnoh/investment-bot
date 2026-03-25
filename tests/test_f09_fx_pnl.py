#!/usr/bin/env python3
"""
F09 테스트 — 환율 손익 분리 계산
주식 손익 vs 환율 손익 분리, fx_pnl 별도 계산, portfolio_history 기록 검증
"""

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── 픽스처 ──


@pytest.fixture
def prices_with_fx():
    """USD 종목 포함 가격 데이터 (buy_fx_rate 포함)"""
    return [
        {
            "name": "삼성전자",
            "ticker": "005930.KS",
            "price": 82000,
            "prev_close": 81500,
            "change_pct": 0.61,
            "volume": 15000000,
            "market": "KR",
            "currency": "KRW",
            "avg_cost": 80000,
            "qty": 42,
        },
        {
            "name": "테슬라",
            "ticker": "TSLA",
            "price": 400.0,
            "prev_close": 390.0,
            "change_pct": 2.56,
            "volume": 80000000,
            "market": "US",
            "currency": "USD",
            "avg_cost": 394.32,
            "qty": 1,
            "buy_fx_rate": 1350.0,
        },
        {
            "name": "알파벳",
            "ticker": "GOOGL",
            "price": 320.0,
            "prev_close": 310.0,
            "change_pct": 3.23,
            "volume": 30000000,
            "market": "US",
            "currency": "USD",
            "avg_cost": 308.27,
            "qty": 2,
            "buy_fx_rate": 1380.0,
        },
        {
            "name": "SPDR S&P Oil",
            "ticker": "XOP",
            "price": 180.0,
            "prev_close": 178.0,
            "change_pct": 1.12,
            "volume": 5000000,
            "market": "US",
            "currency": "USD",
            "avg_cost": 178.26,
            "qty": 1,
            "buy_fx_rate": 1400.0,
        },
    ]


# ── config.py buy_fx_rate 필드 테스트 ──


class TestConfigBuyFxRate:
    """config.py PORTFOLIO에 buy_fx_rate 필드 존재 검증"""

    def test_usd_stocks_have_buy_fx_rate(self):
        """USD 종목에 buy_fx_rate 필드 존재"""
        from config import PORTFOLIO

        usd_stocks = [p for p in PORTFOLIO if p["currency"] == "USD"]
        assert len(usd_stocks) > 0, "USD 종목이 없음"
        for stock in usd_stocks:
            assert "buy_fx_rate" in stock, f"{stock['name']}에 buy_fx_rate 없음"
            assert isinstance(stock["buy_fx_rate"], (int, float))
            assert stock["buy_fx_rate"] > 0

    def test_krw_stocks_no_buy_fx_rate(self):
        """KRW 종목에는 buy_fx_rate 불필요"""
        from config import PORTFOLIO

        krw_stocks = [p for p in PORTFOLIO if p["currency"] == "KRW"]
        for stock in krw_stocks:
            # buy_fx_rate 없거나 있어도 무관 (KRW는 무시됨)
            pass  # KRW 종목은 환율 손익 해당 없음


# ── calculate_holdings 환율 손익 분리 테스트 ──


class TestFxPnlSeparation:
    """주식 손익 vs 환율 손익 분리 계산 검증"""

    def test_usd_stock_invested_uses_buy_fx_rate(self, prices_with_fx):
        """USD 종목 투자금은 매입 환율로 계산"""
        from analysis.portfolio import calculate_holdings

        exchange_rate = 1450.0  # 현재 환율
        holdings = calculate_holdings(prices_with_fx, exchange_rate)

        tsla = next(h for h in holdings if h["ticker"] == "TSLA")
        # invested_krw = avg_cost * qty * buy_fx_rate = 394.32 * 1 * 1350
        expected_invested = round(394.32 * 1 * 1350.0)
        assert tsla["invested_krw"] == expected_invested

    def test_usd_stock_current_value_uses_current_rate(self, prices_with_fx):
        """USD 종목 현재가치는 현재 환율로 계산"""
        from analysis.portfolio import calculate_holdings

        exchange_rate = 1450.0
        holdings = calculate_holdings(prices_with_fx, exchange_rate)

        tsla = next(h for h in holdings if h["ticker"] == "TSLA")
        # current_value_krw = price * qty * exchange_rate = 400 * 1 * 1450
        expected_value = round(400.0 * 1 * 1450.0)
        assert tsla["current_value_krw"] == expected_value

    def test_usd_stock_has_stock_pnl_krw(self, prices_with_fx):
        """USD 종목에 stock_pnl_krw 필드 존재"""
        from analysis.portfolio import calculate_holdings

        exchange_rate = 1450.0
        holdings = calculate_holdings(prices_with_fx, exchange_rate)

        tsla = next(h for h in holdings if h["ticker"] == "TSLA")
        assert "stock_pnl_krw" in tsla
        # stock_pnl = (price - avg_cost) * qty * buy_fx_rate
        # = (400 - 394.32) * 1 * 1350 = 5.68 * 1350 = 7668
        expected = round((400.0 - 394.32) * 1 * 1350.0)
        assert tsla["stock_pnl_krw"] == expected

    def test_usd_stock_has_fx_pnl_krw(self, prices_with_fx):
        """USD 종목에 fx_pnl_krw 필드 존재"""
        from analysis.portfolio import calculate_holdings

        exchange_rate = 1450.0
        holdings = calculate_holdings(prices_with_fx, exchange_rate)

        tsla = next(h for h in holdings if h["ticker"] == "TSLA")
        assert "fx_pnl_krw" in tsla
        # fx_pnl = price * qty * (exchange_rate - buy_fx_rate)
        # = 400 * 1 * (1450 - 1350) = 400 * 100 = 40000
        expected = round(400.0 * 1 * (1450.0 - 1350.0))
        assert tsla["fx_pnl_krw"] == expected

    def test_stock_pnl_plus_fx_pnl_equals_total_pnl(self, prices_with_fx):
        """stock_pnl + fx_pnl = total pnl 항등식 검증"""
        from analysis.portfolio import calculate_holdings

        exchange_rate = 1450.0
        holdings = calculate_holdings(prices_with_fx, exchange_rate)

        for h in holdings:
            if h["currency"] == "USD" and h.get("pnl_krw") is not None:
                total = h["pnl_krw"]
                stock = h["stock_pnl_krw"]
                fx = h["fx_pnl_krw"]
                assert abs(stock + fx - total) <= 1, (
                    f"{h['name']}: stock({stock}) + fx({fx}) != total({total})"
                )

    def test_krw_stock_fx_pnl_zero(self, prices_with_fx):
        """KRW 종목의 fx_pnl_krw는 0"""
        from analysis.portfolio import calculate_holdings

        exchange_rate = 1450.0
        holdings = calculate_holdings(prices_with_fx, exchange_rate)

        samsung = next(h for h in holdings if h["ticker"] == "005930.KS")
        assert samsung["fx_pnl_krw"] == 0
        assert samsung["stock_pnl_krw"] == samsung["pnl_krw"]

    def test_fx_rate_decrease_negative_fx_pnl(self, prices_with_fx):
        """환율 하락 시 fx_pnl이 음수"""
        from analysis.portfolio import calculate_holdings

        # 현재 환율 < 매입 환율 (테슬라 buy_fx_rate=1350)
        exchange_rate = 1300.0
        holdings = calculate_holdings(prices_with_fx, exchange_rate)

        tsla = next(h for h in holdings if h["ticker"] == "TSLA")
        assert tsla["fx_pnl_krw"] < 0

    def test_multiple_usd_stocks_fx_pnl(self, prices_with_fx):
        """여러 USD 종목의 fx_pnl 각각 계산"""
        from analysis.portfolio import calculate_holdings

        exchange_rate = 1450.0
        holdings = calculate_holdings(prices_with_fx, exchange_rate)

        googl = next(h for h in holdings if h["ticker"] == "GOOGL")
        # fx_pnl = 320 * 2 * (1450 - 1380) = 640 * 70 = 44800
        expected_fx = round(320.0 * 2 * (1450.0 - 1380.0))
        assert googl["fx_pnl_krw"] == expected_fx

        xop = next(h for h in holdings if h["ticker"] == "XOP")
        # fx_pnl = 180 * 1 * (1450 - 1400) = 180 * 50 = 9000
        expected_fx = round(180.0 * 1 * (1450.0 - 1400.0))
        assert xop["fx_pnl_krw"] == expected_fx


# ── build_summary 환율 손익 합계 테스트 ──


class TestBuildSummaryFxPnl:
    """build_summary에 fx_pnl_krw, stock_pnl_krw 합계 포함"""

    def test_summary_total_has_fx_pnl_krw(self, prices_with_fx):
        """summary.total에 fx_pnl_krw 필드 포함"""
        from analysis.portfolio import calculate_holdings, build_summary

        exchange_rate = 1450.0
        holdings = calculate_holdings(prices_with_fx, exchange_rate)
        summary = build_summary(holdings, [], {}, exchange_rate)

        assert "fx_pnl_krw" in summary["total"]
        assert isinstance(summary["total"]["fx_pnl_krw"], (int, float))

    def test_summary_total_has_stock_pnl_krw(self, prices_with_fx):
        """summary.total에 stock_pnl_krw 필드 포함"""
        from analysis.portfolio import calculate_holdings, build_summary

        exchange_rate = 1450.0
        holdings = calculate_holdings(prices_with_fx, exchange_rate)
        summary = build_summary(holdings, [], {}, exchange_rate)

        assert "stock_pnl_krw" in summary["total"]
        assert isinstance(summary["total"]["stock_pnl_krw"], (int, float))

    def test_summary_fx_pnl_is_sum_of_holdings(self, prices_with_fx):
        """summary.total.fx_pnl_krw = 각 종목 fx_pnl_krw 합계"""
        from analysis.portfolio import calculate_holdings, build_summary

        exchange_rate = 1450.0
        holdings = calculate_holdings(prices_with_fx, exchange_rate)
        summary = build_summary(holdings, [], {}, exchange_rate)

        expected_fx = sum(
            h.get("fx_pnl_krw", 0) for h in holdings
            if h.get("pnl_label") is None
        )
        assert summary["total"]["fx_pnl_krw"] == expected_fx

    def test_summary_stock_plus_fx_equals_total(self, prices_with_fx):
        """stock_pnl_krw + fx_pnl_krw = pnl_krw 항등식"""
        from analysis.portfolio import calculate_holdings, build_summary

        exchange_rate = 1450.0
        holdings = calculate_holdings(prices_with_fx, exchange_rate)
        summary = build_summary(holdings, [], {}, exchange_rate)

        total = summary["total"]
        assert abs(total["stock_pnl_krw"] + total["fx_pnl_krw"] - total["pnl_krw"]) <= 1


# ── save_snapshot fx_pnl_krw 저장 테스트 ──


class TestSnapshotFxPnl:
    """portfolio_history에 fx_pnl_krw 저장 검증"""

    def test_snapshot_saves_fx_pnl_krw(self, db_conn):
        """스냅샷 저장 시 fx_pnl_krw 값 기록"""
        from analysis.portfolio import save_snapshot

        summary = {
            "exchange_rate": 1450.0,
            "total": {
                "invested_krw": 5000000,
                "current_value_krw": 5500000,
                "pnl_krw": 500000,
                "pnl_pct": 10.0,
                "fx_pnl_krw": 150000,
                "stock_pnl_krw": 350000,
            },
            "holdings": [],
        }

        save_snapshot(db_conn, summary, "2026-03-25")

        cursor = db_conn.cursor()
        cursor.execute("SELECT fx_pnl_krw FROM portfolio_history WHERE date = '2026-03-25'")
        row = cursor.fetchone()
        assert row["fx_pnl_krw"] == 150000

    def test_snapshot_fx_pnl_none_when_missing(self, db_conn):
        """fx_pnl_krw 없는 summary에서도 정상 저장 (하위 호환)"""
        from analysis.portfolio import save_snapshot

        summary = {
            "exchange_rate": 1450.0,
            "total": {
                "invested_krw": 5000000,
                "current_value_krw": 5500000,
                "pnl_krw": 500000,
                "pnl_pct": 10.0,
            },
            "holdings": [],
        }

        save_snapshot(db_conn, summary, "2026-03-25")

        cursor = db_conn.cursor()
        cursor.execute("SELECT fx_pnl_krw FROM portfolio_history WHERE date = '2026-03-25'")
        row = cursor.fetchone()
        # fx_pnl_krw가 없으면 None 저장
        assert row["fx_pnl_krw"] is None


# ── run() 통합 테스트 ──


class TestRunFxPnlIntegration:
    """run() 실행 시 환율 손익 분리 포함 검증"""

    def test_run_output_has_fx_pnl_fields(self, tmp_path):
        """run() 출력 JSON에 fx_pnl_krw, stock_pnl_krw 필드 포함"""
        from analysis import portfolio
        from db.init_db import init_schema

        # 파일 기반 DB 생성
        db_path = tmp_path / "test.db"
        file_conn = sqlite3.connect(str(db_path))
        file_conn.row_factory = sqlite3.Row
        init_schema(file_conn)
        file_conn.close()

        intel_dir = tmp_path / "output" / "intel"
        intel_dir.mkdir(parents=True)

        prices_data = {
            "prices": [
                {
                    "name": "테슬라",
                    "ticker": "TSLA",
                    "price": 400.0,
                    "prev_close": 390.0,
                    "change_pct": 2.56,
                    "volume": 80000000,
                    "market": "US",
                    "currency": "USD",
                    "avg_cost": 394.32,
                    "qty": 1,
                    "buy_fx_rate": 1350.0,
                    "timestamp": "2026-03-25T04:00:00+09:00",
                },
                {
                    "name": "삼성전자",
                    "ticker": "005930.KS",
                    "price": 82000,
                    "prev_close": 81500,
                    "change_pct": 0.61,
                    "volume": 15000000,
                    "market": "KR",
                    "currency": "KRW",
                    "avg_cost": 80000,
                    "qty": 42,
                    "timestamp": "2026-03-25T15:30:00+09:00",
                },
            ],
            "updated_at": "2026-03-25T15:30:00+09:00",
        }
        macro_data = {
            "indicators": [
                {"name": "원/달러", "indicator": "원/달러", "value": 1450.0, "change_pct": 0.5},
            ],
            "updated_at": "2026-03-25T15:30:00+09:00",
        }

        with open(intel_dir / "prices.json", "w") as f:
            json.dump(prices_data, f)
        with open(intel_dir / "macro.json", "w") as f:
            json.dump(macro_data, f)

        with (
            patch.object(portfolio, "OUTPUT_DIR", intel_dir),
            patch.object(portfolio, "DB_PATH", db_path),
        ):
            result = portfolio.run()

        assert result is not None
        total = result["total"]
        assert "fx_pnl_krw" in total
        assert "stock_pnl_krw" in total
        assert abs(total["stock_pnl_krw"] + total["fx_pnl_krw"] - total["pnl_krw"]) <= 1

        # 저장된 JSON에도 포함
        with open(intel_dir / "portfolio_summary.json") as f:
            saved = json.load(f)
        assert "fx_pnl_krw" in saved["total"]
        assert "stock_pnl_krw" in saved["total"]

        # holdings에도 fx_pnl_krw 포함
        tsla = next(h for h in saved["holdings"] if h["ticker"] == "TSLA")
        assert "fx_pnl_krw" in tsla
        assert "stock_pnl_krw" in tsla

    def test_run_saves_fx_pnl_to_db(self, tmp_path):
        """run() 실행 시 portfolio_history에 fx_pnl_krw 저장"""
        from analysis import portfolio
        from db.init_db import init_schema

        db_path = tmp_path / "test.db"
        file_conn = sqlite3.connect(str(db_path))
        file_conn.row_factory = sqlite3.Row
        init_schema(file_conn)
        file_conn.close()

        intel_dir = tmp_path / "output" / "intel"
        intel_dir.mkdir(parents=True)

        prices_data = {
            "prices": [
                {
                    "name": "테슬라",
                    "ticker": "TSLA",
                    "price": 400.0,
                    "prev_close": 390.0,
                    "change_pct": 2.56,
                    "volume": 80000000,
                    "market": "US",
                    "currency": "USD",
                    "avg_cost": 394.32,
                    "qty": 1,
                    "buy_fx_rate": 1350.0,
                    "timestamp": "2026-03-25T04:00:00+09:00",
                },
            ],
            "updated_at": "2026-03-25T15:30:00+09:00",
        }
        macro_data = {
            "indicators": [
                {"name": "원/달러", "indicator": "원/달러", "value": 1450.0, "change_pct": 0.5},
            ],
        }

        with open(intel_dir / "prices.json", "w") as f:
            json.dump(prices_data, f)
        with open(intel_dir / "macro.json", "w") as f:
            json.dump(macro_data, f)

        with (
            patch.object(portfolio, "OUTPUT_DIR", intel_dir),
            patch.object(portfolio, "DB_PATH", db_path),
        ):
            portfolio.run()

        # DB 검증
        verify_conn = sqlite3.connect(str(db_path))
        verify_conn.row_factory = sqlite3.Row
        cursor = verify_conn.cursor()
        cursor.execute("SELECT fx_pnl_krw FROM portfolio_history")
        row = cursor.fetchone()
        assert row is not None
        assert row["fx_pnl_krw"] is not None
        assert row["fx_pnl_krw"] != 0  # 환율 차이 있으니 0 아님
        verify_conn.close()

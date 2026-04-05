#!/usr/bin/env python3
"""
F06 — data_source 필드 테스트
prices.json에 데이터 출처 (kiwoom/naver/yahoo/calculated) 명시 검증
"""

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# 프로젝트 루트를 모듈 경로에 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════
# data_source 필드 테스트 — collect_prices
# ═══════════════════════════════════════════════════════


def _make_yahoo_response(price, prev_close, volume=1000):
    """Yahoo Finance 응답 JSON 바이트 생성"""
    return json.dumps(
        {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "regularMarketPrice": price,
                            "chartPreviousClose": prev_close,
                            "regularMarketVolume": volume,
                        }
                    }
                ]
            }
        }
    ).encode()


def _mock_urlopen_factory(responses):
    """URL별 응답을 매핑하는 urlopen 모킹 팩토리"""
    call_count = [0]

    def mock_urlopen(req, timeout=None):
        idx = call_count[0]
        call_count[0] += 1
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        if idx < len(responses):
            data = responses[idx]
        else:
            data = responses[-1]

        import io

        resp.read = MagicMock(return_value=data)
        # json.load 호환: file-like 객체처럼 동작
        buffer = io.BytesIO(data)
        resp.read = buffer.read
        resp.readline = buffer.readline
        resp.readlines = buffer.readlines
        resp.__iter__ = buffer.__iter__
        return resp

    return mock_urlopen


class TestDataSourceYahoo:
    """미국 주식 → data_source='yahoo' 검증"""

    @patch(
        "data.fetch_prices.get_holdings",
        return_value=[
            {
                "name": "테슬라",
                "ticker": "TSLA",
                "avg_cost": 300,
                "currency": "USD",
                "qty": 1,
                "account": "미국",
                "sector": None,
                "buy_fx_rate": None,
                "note": None,
            },
        ],
    )
    @patch("data.fetch_prices.urllib.request.urlopen")
    def test_미국_주식_yahoo_소스(self, mock_urlopen, mock_holdings):
        """미국 주식은 data_source='yahoo'"""
        from data.fetch_prices import collect_prices

        resp = _make_yahoo_response(275.50, 270.00, 80000)
        mock_urlopen.return_value = MagicMock(
            __enter__=lambda s: s,
            __exit__=MagicMock(return_value=False),
        )
        import io

        buf = io.BytesIO(resp)
        mock_urlopen.return_value.read = buf.read
        mock_urlopen.return_value.readline = buf.readline
        mock_urlopen.return_value.readlines = buf.readlines
        mock_urlopen.return_value.__iter__ = buf.__iter__

        records = collect_prices()
        assert len(records) == 1
        assert records[0]["data_source"] == "yahoo"


class TestDataSourceNaver:
    """한국 주식 (네이버 폴백) → data_source='naver' 검증"""

    @patch(
        "data.fetch_prices.get_holdings",
        return_value=[
            {
                "name": "삼성전자",
                "ticker": "005930.KS",
                "avg_cost": 70000,
                "currency": "KRW",
                "qty": 10,
                "account": "ISA",
                "sector": None,
                "buy_fx_rate": None,
                "note": None,
            },
        ],
    )
    @patch("data.fetch_prices.os.environ.get", return_value=None)
    @patch("data.fetch_prices.fetch_naver_price")
    def test_한국_주식_네이버_소스(self, mock_naver, mock_env, mock_holdings):
        """키움 API 없이 네이버 폴백 → data_source='naver'"""
        from data.fetch_prices import collect_prices

        mock_naver.return_value = {
            "price": 75000,
            "prev_close": 74000,
            "change_pct": 1.35,
            "volume": 10000000,
            "high": 76000,
            "low": 74500,
        }

        records = collect_prices()
        assert len(records) == 1
        assert records[0]["data_source"] == "naver"


class TestDataSourceKiwoom:
    """한국 주식 (키움 API) → data_source='kiwoom' 검증"""

    @patch(
        "data.fetch_prices.get_holdings",
        return_value=[
            {
                "name": "삼성전자",
                "ticker": "005930.KS",
                "avg_cost": 70000,
                "currency": "KRW",
                "qty": 10,
                "account": "ISA",
                "sector": None,
                "buy_fx_rate": None,
                "note": None,
            },
        ],
    )
    @patch("data.fetch_prices.os.environ.get", return_value="test_appkey")
    def test_한국_주식_키움_소스(self, mock_env, mock_holdings):
        """키움 API 성공 시 data_source='kiwoom'"""
        from data.fetch_prices import collect_prices

        mock_kiwoom = MagicMock(
            return_value={
                "price": 75000,
                "prev_close": 74000,
                "change_pct": 1.35,
                "volume": 10000000,
            }
        )

        with patch("data.fetch_prices.fetch_kiwoom_stock", mock_kiwoom, create=True):
            with patch.dict(
                "sys.modules",
                {"data.fetch_gold_krx": MagicMock(fetch_kiwoom_stock=mock_kiwoom)},
            ):
                records = collect_prices()

        assert len(records) == 1
        assert records[0]["data_source"] == "kiwoom"


class TestDataSourceKiwoomFallbackNaver:
    """한국 주식 — 키움 실패 → 네이버 폴백 시 data_source='naver'"""

    @patch(
        "data.fetch_prices.get_holdings",
        return_value=[
            {
                "name": "삼성전자",
                "ticker": "005930.KS",
                "avg_cost": 70000,
                "currency": "KRW",
                "qty": 10,
                "account": "ISA",
                "sector": None,
                "buy_fx_rate": None,
                "note": None,
            },
        ],
    )
    @patch("data.fetch_prices.os.environ.get", return_value="test_appkey")
    @patch("data.fetch_prices.fetch_naver_price")
    def test_키움_실패_네이버_폴백_소스(self, mock_naver, mock_env, mock_holdings):
        """키움 실패 후 네이버 폴백 → data_source='naver'"""
        from data.fetch_prices import collect_prices

        mock_naver.return_value = {
            "price": 75000,
            "prev_close": 74000,
            "change_pct": 1.35,
            "volume": 10000000,
            "high": 76000,
            "low": 74500,
        }

        # 키움 import 실패 시뮬레이션
        with patch.dict("sys.modules", {"data.fetch_gold_krx": None}):
            records = collect_prices()

        assert len(records) == 1
        assert records[0]["data_source"] == "naver"


class TestDataSourceGold:
    """금 현물 → data_source 검증"""

    @patch(
        "data.fetch_prices.get_holdings",
        return_value=[
            {
                "name": "금 현물",
                "ticker": "GOLD_KRW_G",
                "avg_cost": 200000,
                "currency": "KRW",
                "qty": 128,
                "account": "실물",
                "sector": None,
                "buy_fx_rate": None,
                "note": None,
            },
        ],
    )
    @patch("data.fetch_prices.os.environ.get", return_value=None)
    @patch("data.fetch_prices.fetch_yahoo_quote")
    def test_금_현물_yahoo_계산_소스(self, mock_yahoo, mock_env, mock_holdings):
        """금 현물 Yahoo 폴백 → data_source='calculated'"""
        from data.fetch_prices import collect_prices

        # GC=F (금 선물), KRW=X (환율) 순서
        mock_yahoo.side_effect = [
            {"regularMarketPrice": 2000.0, "chartPreviousClose": 1990.0},
            {"regularMarketPrice": 1350.0, "chartPreviousClose": 1345.0},
        ]

        records = collect_prices()
        assert len(records) == 1
        assert records[0]["data_source"] == "calculated"
        assert "calc_method" in records[0]
        assert "GC=F" in records[0]["calc_method"]

    @patch(
        "data.fetch_prices.get_holdings",
        return_value=[
            {
                "name": "금 현물",
                "ticker": "GOLD_KRW_G",
                "avg_cost": 200000,
                "currency": "KRW",
                "qty": 128,
                "account": "실물",
                "sector": None,
                "buy_fx_rate": None,
                "note": None,
            },
        ],
    )
    @patch("data.fetch_prices.os.environ.get", return_value="test_appkey")
    def test_금_현물_키움_소스(self, mock_env, mock_holdings):
        """금 현물 키움 KRX API → data_source='kiwoom'"""
        from data.fetch_prices import collect_prices

        mock_gold_krx = MagicMock(
            return_value={
                "price": 130000.0,
                "prev_close": 129500.0,
            }
        )

        with patch.dict(
            "sys.modules",
            {
                "data.fetch_gold_krx": MagicMock(fetch_gold_krx=mock_gold_krx),
            },
        ):
            records = collect_prices()

        assert len(records) == 1
        assert records[0]["data_source"] == "kiwoom"


class TestDataSourceErrorRecord:
    """에러 레코드에도 data_source 필드 포함 (None)"""

    @patch(
        "data.fetch_prices.get_holdings",
        return_value=[
            {
                "name": "테슬라",
                "ticker": "TSLA",
                "avg_cost": 300,
                "currency": "USD",
                "qty": 1,
                "account": "미국",
                "sector": None,
                "buy_fx_rate": None,
                "note": None,
            },
        ],
    )
    @patch(
        "data.fetch_prices.fetch_yahoo_quote", side_effect=ConnectionError("timeout")
    )
    def test_에러_시_data_source_none(self, mock_yahoo, mock_holdings):
        """수집 실패 시 data_source=None"""
        from data.fetch_prices import collect_prices

        records = collect_prices()
        assert len(records) == 1
        assert records[0]["data_source"] is None


class TestDataSourceDB저장:
    """data_source가 DB에 올바르게 저장되는지 검증"""

    def test_save_to_db_data_source_포함(self, db_conn):
        """save_to_db가 data_source를 DB에 저장"""
        # 인메모리 DB 사용 — save_to_db는 파일 DB를 사용하므로 직접 INSERT 테스트
        db_conn.execute(
            """INSERT INTO prices (ticker, name, price, prev_close, change_pct, volume, timestamp, market, data_source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "TSLA",
                "테슬라",
                275.50,
                270.00,
                2.04,
                80000,
                "2026-03-25T10:00:00+09:00",
                "US",
                "yahoo",
            ),
        )
        db_conn.commit()

        row = db_conn.execute(
            "SELECT data_source FROM prices WHERE ticker = 'TSLA'"
        ).fetchone()
        assert row[0] == "yahoo"

    def test_save_to_db_data_source_집계_보존(self, db_conn):
        """집계 시 data_source가 prices_daily에 보존됨"""
        from db.aggregate import aggregate_daily

        # 원시 데이터 삽입 (data_source 포함)
        db_conn.execute(
            """INSERT INTO prices (ticker, name, price, prev_close, change_pct, volume, timestamp, market, data_source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "TSLA",
                "테슬라",
                275.50,
                270.00,
                2.04,
                80000,
                "2026-03-25T09:00:00+09:00",
                "US",
                "yahoo",
            ),
        )
        db_conn.execute(
            """INSERT INTO prices (ticker, name, price, prev_close, change_pct, volume, timestamp, market, data_source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "TSLA",
                "테슬라",
                278.00,
                270.00,
                2.96,
                90000,
                "2026-03-25T15:00:00+09:00",
                "US",
                "yahoo",
            ),
        )
        db_conn.commit()

        aggregate_daily(db_conn, target_date="2026-03-25")

        row = db_conn.execute(
            "SELECT data_source FROM prices_daily WHERE ticker = 'TSLA' AND date = '2026-03-25'"
        ).fetchone()
        assert row[0] == "yahoo"


class TestDataSourceJSON하위호환:
    """기존 prices.json 필드 유지 + data_source 추가 검증"""

    @patch(
        "data.fetch_prices.get_holdings",
        return_value=[
            {
                "name": "테슬라",
                "ticker": "TSLA",
                "avg_cost": 300,
                "currency": "USD",
                "qty": 1,
                "account": "미국",
                "sector": None,
                "buy_fx_rate": None,
                "note": None,
            },
        ],
    )
    @patch("data.fetch_prices.urllib.request.urlopen")
    def test_기존_필드_유지_data_source_추가(self, mock_urlopen, mock_holdings):
        """prices.json에 기존 필드 모두 유지 + data_source 추가"""
        from data.fetch_prices import collect_prices

        resp = _make_yahoo_response(275.50, 270.00, 80000)
        import io

        buf = io.BytesIO(resp)
        mock_urlopen.return_value = MagicMock(
            __enter__=lambda s: s,
            __exit__=MagicMock(return_value=False),
        )
        mock_urlopen.return_value.read = buf.read
        mock_urlopen.return_value.readline = buf.readline
        mock_urlopen.return_value.readlines = buf.readlines
        mock_urlopen.return_value.__iter__ = buf.__iter__

        records = collect_prices()
        record = records[0]

        # 기존 필수 필드 유지 (account는 SSoT 마이그레이션 후 성공 레코드에서 제외됨)
        기존_필드 = [
            "ticker",
            "name",
            "price",
            "prev_close",
            "change_pct",
            "volume",
            "avg_cost",
            "pnl_pct",
            "currency",
            "qty",
            "market",
            "timestamp",
        ]
        for field in 기존_필드:
            assert field in record, f"기존 필드 '{field}' 누락"

        # data_source 추가
        assert "data_source" in record
        assert record["data_source"] in ("yahoo", "naver", "kiwoom", "calculated")


class TestDataSourceSaveToDbIntegration:
    """save_to_db가 data_source 컬럼에 실제로 저장하는지 통합 테스트"""

    @patch("data.fetch_prices.DB_PATH")
    def test_save_to_db_실제_저장(self, mock_db_path, tmp_path):
        """save_to_db가 data_source를 prices 테이블에 저장"""
        from data.fetch_prices import save_to_db
        from db.init_db import init_schema

        db_file = tmp_path / "test.db"
        mock_db_path.__str__ = lambda s: str(db_file)
        # Path 비교 연산 지원
        mock_db_path.__fspath__ = lambda s: str(db_file)

        # DB 초기화
        conn = sqlite3.connect(str(db_file))
        init_schema(conn)
        conn.close()

        records = [
            {
                "ticker": "TSLA",
                "name": "테슬라",
                "price": 275.50,
                "prev_close": 270.00,
                "change_pct": 2.04,
                "volume": 80000,
                "timestamp": "2026-03-25T10:00:00+09:00",
                "market": "US",
                "data_source": "yahoo",
            }
        ]

        save_to_db(records)

        conn = sqlite3.connect(str(db_file))
        row = conn.execute(
            "SELECT data_source FROM prices WHERE ticker = 'TSLA'"
        ).fetchone()
        conn.close()
        assert row[0] == "yahoo"

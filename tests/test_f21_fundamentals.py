#!/usr/bin/env python3
"""
F21 — 펀더멘탈 데이터 수집 테스트
DART 재무제표 + Yahoo Finance quoteSummary + fundamentals DB + JSON 출력
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── 1. DB 스키마 테스트 ──


class TestFundamentalsSchema:
    """fundamentals 테이블 스키마 검증"""

    def test_table_exists(self, db_conn):
        """fundamentals 테이블이 존재하는지 확인"""
        cursor = db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='fundamentals'"
        )
        assert cursor.fetchone() is not None

    def test_table_columns(self, db_conn):
        """필수 컬럼이 모두 존재하는지 확인"""
        cursor = db_conn.execute("PRAGMA table_info(fundamentals)")
        columns = {row[1] for row in cursor.fetchall()}
        required = {
            "id",
            "ticker",
            "name",
            "market",
            "per",
            "pbr",
            "roe",
            "debt_ratio",
            "revenue_growth",
            "operating_margin",
            "fcf",
            "eps",
            "dividend_yield",
            "market_cap",
            "data_source",
            "updated_at",
        }
        assert required.issubset(columns)

    def test_unique_index_on_ticker(self, db_conn):
        """ticker에 유니크 인덱스가 있는지 확인"""
        db_conn.execute(
            "INSERT INTO fundamentals (ticker, name, updated_at) VALUES (?, ?, ?)",
            ("005930.KS", "삼성전자", "2026-03-26T00:00:00+09:00"),
        )
        db_conn.commit()
        # 같은 ticker 삽입 시 에러
        with pytest.raises(Exception):
            db_conn.execute(
                "INSERT INTO fundamentals (ticker, name, updated_at) VALUES (?, ?, ?)",
                ("005930.KS", "삼성전자", "2026-03-26T01:00:00+09:00"),
            )


# ── 2. DART API 모킹 테스트 ──


class TestDartFetch:
    """DART OpenAPI 재무제표 수집 테스트"""

    def _make_dart_response(self):
        """DART API 응답 샘플"""
        return {
            "status": "000",
            "message": "정상",
            "list": [
                {
                    "corp_code": "00126380",
                    "corp_name": "삼성전자",
                    "stock_code": "005930",
                    "account_nm": "매출액",
                    "thstrm_amount": "279,000,000,000,000",
                    "frmtrm_amount": "258,000,000,000,000",
                },
                {
                    "corp_code": "00126380",
                    "corp_name": "삼성전자",
                    "stock_code": "005930",
                    "account_nm": "영업이익",
                    "thstrm_amount": "36,000,000,000,000",
                    "frmtrm_amount": "6,000,000,000,000",
                },
                {
                    "corp_code": "00126380",
                    "corp_name": "삼성전자",
                    "stock_code": "005930",
                    "account_nm": "당기순이익",
                    "thstrm_amount": "25,000,000,000,000",
                    "frmtrm_amount": "15,000,000,000,000",
                },
                {
                    "corp_code": "00126380",
                    "corp_name": "삼성전자",
                    "stock_code": "005930",
                    "account_nm": "부채총계",
                    "thstrm_amount": "100,000,000,000,000",
                    "frmtrm_amount": "95,000,000,000,000",
                },
                {
                    "corp_code": "00126380",
                    "corp_name": "삼성전자",
                    "stock_code": "005930",
                    "account_nm": "자본총계",
                    "thstrm_amount": "300,000,000,000,000",
                    "frmtrm_amount": "280,000,000,000,000",
                },
            ],
        }

    @patch("data.fetch_fundamentals.urllib.request.urlopen")
    @patch.dict("os.environ", {"DART_API_KEY": "test_key"})
    def test_fetch_dart_success(self, mock_urlopen):
        """DART API 정상 응답 시 재무 데이터 파싱"""
        from data.fetch_fundamentals import fetch_dart_financials

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(self._make_dart_response()).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = fetch_dart_financials("005930")
        assert result is not None
        assert result["revenue_growth"] is not None
        assert result["operating_margin"] is not None
        assert result["roe"] is not None
        assert result["debt_ratio"] is not None

    @patch("data.fetch_fundamentals.urllib.request.urlopen")
    @patch.dict("os.environ", {"DART_API_KEY": "test_key"})
    def test_fetch_dart_revenue_growth(self, mock_urlopen):
        """매출 성장률 계산 정확도"""
        from data.fetch_fundamentals import fetch_dart_financials

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(self._make_dart_response()).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = fetch_dart_financials("005930")
        # (279조 - 258조) / 258조 * 100 ≈ 8.14%
        assert abs(result["revenue_growth"] - 8.14) < 0.1

    @patch("data.fetch_fundamentals.urllib.request.urlopen")
    @patch.dict("os.environ", {"DART_API_KEY": "test_key"})
    def test_fetch_dart_operating_margin(self, mock_urlopen):
        """영업이익률 계산 정확도"""
        from data.fetch_fundamentals import fetch_dart_financials

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(self._make_dart_response()).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = fetch_dart_financials("005930")
        # 36조 / 279조 * 100 ≈ 12.9%
        assert abs(result["operating_margin"] - 12.9) < 0.1

    @patch("data.fetch_fundamentals.urllib.request.urlopen")
    @patch.dict("os.environ", {"DART_API_KEY": "test_key"})
    def test_fetch_dart_roe(self, mock_urlopen):
        """ROE 계산 정확도"""
        from data.fetch_fundamentals import fetch_dart_financials

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(self._make_dart_response()).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = fetch_dart_financials("005930")
        # 25조 / 300조 * 100 ≈ 8.33%
        assert abs(result["roe"] - 8.33) < 0.1

    def test_fetch_dart_no_api_key(self):
        """DART_API_KEY 미설정 시 None 반환"""
        from data.fetch_fundamentals import fetch_dart_financials

        with patch.dict("os.environ", {}, clear=True):
            result = fetch_dart_financials("005930")
            assert result is None

    @patch("data.fetch_fundamentals.urllib.request.urlopen")
    @patch.dict("os.environ", {"DART_API_KEY": "test_key"})
    def test_fetch_dart_api_error(self, mock_urlopen):
        """DART API 에러 시 None 반환 (graceful degradation)"""
        from data.fetch_fundamentals import fetch_dart_financials

        mock_urlopen.side_effect = Exception("Connection timeout")
        result = fetch_dart_financials("005930")
        assert result is None

    @patch("data.fetch_fundamentals.urllib.request.urlopen")
    @patch.dict("os.environ", {"DART_API_KEY": "test_key"})
    def test_fetch_dart_empty_list(self, mock_urlopen):
        """DART API 빈 응답 시 None 반환"""
        from data.fetch_fundamentals import fetch_dart_financials

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"status": "013", "message": "조회된 데이터가 없습니다.", "list": []}
        ).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = fetch_dart_financials("999999")
        assert result is None


# ── 3. Yahoo Finance 모킹 테스트 ──


class TestYahooFetch:
    """Yahoo Finance quoteSummary 수집 테스트"""

    def _make_yahoo_response(self):
        """Yahoo Finance quoteSummary 응답 샘플"""
        return {
            "quoteSummary": {
                "result": [
                    {
                        "defaultKeyStatistics": {
                            "trailingPE": {"raw": 25.3},
                            "priceToBook": {"raw": 3.2},
                            "returnOnEquity": {"raw": 0.285},
                            "enterpriseToEbitda": {"raw": 18.5},
                            "trailingEps": {"raw": 10.85},
                        },
                        "financialData": {
                            "totalDebt": {"raw": 5000000000},
                            "totalRevenue": {"raw": 95000000000},
                            "revenueGrowth": {"raw": 0.12},
                            "operatingMargins": {"raw": 0.185},
                            "freeCashflow": {"raw": 8500000000},
                            "debtToEquity": {"raw": 45.2},
                            "returnOnEquity": {"raw": 0.285},
                        },
                        "summaryDetail": {
                            "marketCap": {"raw": 850000000000},
                            "dividendYield": {"raw": 0.005},
                            "trailingPE": {"raw": 25.3},
                        },
                    }
                ],
                "error": None,
            }
        }

    @patch("yfinance.Ticker")
    def test_fetch_yahoo_success(self, MockTicker):
        """yfinance로 재무 데이터 파싱"""
        from data.fetch_fundamentals import fetch_yahoo_financials

        mock_t = MagicMock()
        mock_t.info = {
            "regularMarketPrice": 200.0,
            "trailingPE": 25.3,
            "priceToBook": 3.2,
            "returnOnEquity": 0.285,
            "revenueGrowth": 0.12,
            "operatingMargins": 0.185,
            "debtToEquity": 45.2,
            "marketCap": 850000000000,
        }
        MockTicker.return_value = mock_t

        result = fetch_yahoo_financials("TSLA")
        assert result is not None
        assert result["per"] == 25.3
        assert result["pbr"] == 3.2
        assert abs(result["roe"] - 28.5) < 0.1
        assert result["revenue_growth"] == 12.0
        assert abs(result["operating_margin"] - 18.5) < 0.1
        assert result["debt_ratio"] == 45.2

    @patch("yfinance.Ticker")
    def test_fetch_yahoo_market_cap(self, MockTicker):
        """시가총액 파싱"""
        from data.fetch_fundamentals import fetch_yahoo_financials

        mock_t = MagicMock()
        mock_t.info = {
            "regularMarketPrice": 200.0,
            "trailingPE": 25.3,
            "marketCap": 850000000000,
        }
        MockTicker.return_value = mock_t

        result = fetch_yahoo_financials("TSLA")
        assert result["market_cap"] == 850000000000

    @patch("data.fetch_fundamentals.urllib.request.urlopen")
    def test_fetch_yahoo_api_error(self, mock_urlopen):
        """Yahoo API 에러 시 None 반환"""
        from data.fetch_fundamentals import fetch_yahoo_financials

        mock_urlopen.side_effect = Exception("HTTP Error 404")
        result = fetch_yahoo_financials("INVALID")
        assert result is None

    @patch("data.fetch_fundamentals.urllib.request.urlopen")
    def test_fetch_yahoo_empty_result(self, mock_urlopen):
        """Yahoo API 빈 결과 시 None 반환"""
        from data.fetch_fundamentals import fetch_yahoo_financials

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"quoteSummary": {"result": [], "error": None}}
        ).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = fetch_yahoo_financials("INVALID")
        assert result is None

    @patch("yfinance.Ticker")
    def test_fetch_yahoo_partial_data(self, MockTicker):
        """yfinance 일부 필드 누락 시 graceful 처리"""
        from data.fetch_fundamentals import fetch_yahoo_financials

        mock_t = MagicMock()
        mock_t.info = {
            "regularMarketPrice": 200.0,
            "trailingPE": 15.0,
        }
        MockTicker.return_value = mock_t

        result = fetch_yahoo_financials("TSLA")
        assert result is not None
        assert result["per"] == 15.0
        assert result["pbr"] is None  # 누락 필드는 None


# ── 4. DB CRUD 테스트 ──


class TestFundamentalsDB:
    """fundamentals 테이블 DB 저장/조회 테스트"""

    def test_save_fundamentals(self, db_conn):
        """펀더멘탈 데이터 저장"""
        from data.fetch_fundamentals import save_fundamentals_to_db

        records = [
            {
                "ticker": "005930.KS",
                "name": "삼성전자",
                "market": "KR",
                "per": 12.5,
                "pbr": 1.2,
                "roe": 8.33,
                "debt_ratio": 33.3,
                "revenue_growth": 8.14,
                "operating_margin": 12.9,
                "fcf": None,
                "eps": 5000,
                "dividend_yield": 2.1,
                "market_cap": 490000000000000,
                "data_source": "dart",
            }
        ]
        save_fundamentals_to_db(db_conn, records)

        cursor = db_conn.execute("SELECT * FROM fundamentals WHERE ticker='005930.KS'")
        row = cursor.fetchone()
        assert row is not None
        assert row["per"] == 12.5
        assert row["roe"] == 8.33

    def test_upsert_fundamentals(self, db_conn):
        """같은 ticker 재저장 시 UPSERT"""
        from data.fetch_fundamentals import save_fundamentals_to_db

        records = [
            {
                "ticker": "TSLA",
                "name": "테슬라",
                "market": "US",
                "per": 25.0,
                "pbr": 3.0,
                "roe": 28.0,
                "debt_ratio": 45.0,
                "revenue_growth": 12.0,
                "operating_margin": 18.0,
                "fcf": 8500000000,
                "eps": 10.85,
                "dividend_yield": 0.0,
                "market_cap": 850000000000,
                "data_source": "yahoo",
            }
        ]
        save_fundamentals_to_db(db_conn, records)

        # 업데이트
        records[0]["per"] = 30.0
        save_fundamentals_to_db(db_conn, records)

        cursor = db_conn.execute(
            "SELECT COUNT(*) FROM fundamentals WHERE ticker='TSLA'"
        )
        assert cursor.fetchone()[0] == 1

        cursor = db_conn.execute("SELECT per FROM fundamentals WHERE ticker='TSLA'")
        assert cursor.fetchone()[0] == 30.0

    def test_load_fundamentals(self, db_conn):
        """펀더멘탈 데이터 조회"""
        from data.fetch_fundamentals import save_fundamentals_to_db, load_fundamentals

        records = [
            {
                "ticker": "005930.KS",
                "name": "삼성전자",
                "market": "KR",
                "per": 12.5,
                "pbr": 1.2,
                "roe": 8.33,
                "debt_ratio": 33.3,
                "revenue_growth": 8.14,
                "operating_margin": 12.9,
                "fcf": None,
                "eps": 5000,
                "dividend_yield": 2.1,
                "market_cap": 490000000000000,
                "data_source": "dart",
            },
            {
                "ticker": "TSLA",
                "name": "테슬라",
                "market": "US",
                "per": 25.0,
                "pbr": 3.0,
                "roe": 28.0,
                "debt_ratio": 45.0,
                "revenue_growth": 12.0,
                "operating_margin": 18.0,
                "fcf": 8500000000,
                "eps": 10.85,
                "dividend_yield": 0.0,
                "market_cap": 850000000000,
                "data_source": "yahoo",
            },
        ]
        save_fundamentals_to_db(db_conn, records)

        result = load_fundamentals(db_conn)
        assert len(result) == 2
        tickers = {r["ticker"] for r in result}
        assert "005930.KS" in tickers
        assert "TSLA" in tickers

    def test_load_fundamentals_empty(self, db_conn):
        """빈 DB에서 조회 시 빈 리스트"""
        from data.fetch_fundamentals import load_fundamentals

        result = load_fundamentals(db_conn)
        assert result == []


# ── 5. JSON 출력 테스트 ──


class TestFundamentalsJSON:
    """fundamentals.json 출력 검증"""

    def test_generate_json(self):
        """JSON 생성 포맷 검증"""
        from data.fetch_fundamentals import generate_json

        records = [
            {
                "ticker": "005930.KS",
                "name": "삼성전자",
                "market": "KR",
                "per": 12.5,
                "pbr": 1.2,
                "roe": 8.33,
                "debt_ratio": 33.3,
                "revenue_growth": 8.14,
                "operating_margin": 12.9,
                "fcf": None,
                "eps": 5000,
                "dividend_yield": 2.1,
                "market_cap": 490000000000000,
                "data_source": "dart",
            }
        ]
        result = generate_json(records)
        assert "updated_at" in result
        assert "count" in result
        assert "fundamentals" in result
        assert result["count"] == 1
        assert result["fundamentals"][0]["ticker"] == "005930.KS"

    def test_json_file_output(self, db_conn, tmp_output_dir):
        """파일 저장 검증"""
        from data.fetch_fundamentals import generate_json

        records = [
            {
                "ticker": "TSLA",
                "name": "테슬라",
                "market": "US",
                "per": 25.0,
                "pbr": 3.0,
                "roe": 28.0,
                "debt_ratio": 45.0,
                "revenue_growth": 12.0,
                "operating_margin": 18.0,
                "fcf": 8500000000,
                "eps": 10.85,
                "dividend_yield": 0.0,
                "market_cap": 850000000000,
                "data_source": "yahoo",
            }
        ]
        json_data = generate_json(records)
        json_path = tmp_output_dir / "fundamentals.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        with open(json_path, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["count"] == 1
        assert loaded["fundamentals"][0]["per"] == 25.0


# ── 6. run() 통합 테스트 ──


class TestFundamentalsRun:
    """run() 함수 통합 테스트"""

    def _seed_ticker_master(self, db_conn):
        """ticker_master에 시드 데이터 삽입"""
        db_conn.execute(
            "INSERT INTO ticker_master (ticker, name, name_en, market, sector, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("005930.KS", "삼성전자", "Samsung Electronics", "KR", "", "2026-03-26"),
        )
        db_conn.execute(
            "INSERT INTO ticker_master (ticker, name, name_en, market, sector, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("TSLA", "테슬라", "Tesla", "US", "", "2026-03-26"),
        )
        db_conn.commit()

    @patch("data.fetch_fundamentals.fetch_dart_financials")
    @patch("data.fetch_fundamentals.fetch_yahoo_financials")
    def test_run_basic(self, mock_yahoo, mock_dart, db_conn, tmp_output_dir):
        """run() 기본 동작 — DART + Yahoo 수집 후 DB/JSON 저장"""
        from data.fetch_fundamentals import run

        self._seed_ticker_master(db_conn)

        mock_dart.return_value = {
            "revenue_growth": 8.14,
            "operating_margin": 12.9,
            "roe": 8.33,
            "debt_ratio": 33.3,
            "fcf": None,
        }
        mock_yahoo.return_value = {
            "per": 12.5,
            "pbr": 1.2,
            "roe": 10.0,
            "debt_ratio": 30.0,
            "revenue_growth": 7.0,
            "operating_margin": 11.0,
            "fcf": 5000000000,
            "eps": 5000,
            "dividend_yield": 2.1,
            "market_cap": 490000000000000,
        }

        result = run(conn=db_conn, output_dir=str(tmp_output_dir))
        assert len(result) >= 1

        # DB 저장 확인
        cursor = db_conn.execute("SELECT COUNT(*) FROM fundamentals")
        assert cursor.fetchone()[0] >= 1

        # JSON 파일 확인
        json_path = tmp_output_dir / "fundamentals.json"
        assert json_path.exists()

    @patch("data.fetch_fundamentals.fetch_naver_per_pbr")
    @patch("data.fetch_fundamentals.fetch_dart_financials")
    @patch("data.fetch_fundamentals.fetch_yahoo_financials")
    def test_run_graceful_degradation(
        self, mock_yahoo, mock_dart, mock_naver, db_conn, tmp_output_dir
    ):
        """모든 API 실패 시에도 기존 데이터 유지"""
        from data.fetch_fundamentals import run, save_fundamentals_to_db

        self._seed_ticker_master(db_conn)

        # 기존 데이터 삽입
        existing = [
            {
                "ticker": "005930.KS",
                "name": "삼성전자",
                "market": "KR",
                "per": 10.0,
                "pbr": 1.0,
                "roe": 7.0,
                "debt_ratio": 30.0,
                "revenue_growth": 5.0,
                "operating_margin": 10.0,
                "fcf": None,
                "eps": 4000,
                "dividend_yield": 2.0,
                "market_cap": 400000000000000,
                "data_source": "yahoo",
            }
        ]
        save_fundamentals_to_db(db_conn, existing)

        # 모든 API 실패
        mock_dart.return_value = None
        mock_yahoo.return_value = None
        mock_naver.return_value = {"per": None, "pbr": None}

        run(conn=db_conn, output_dir=str(tmp_output_dir))

        # 기존 데이터가 유지되어야 함
        cursor = db_conn.execute(
            "SELECT per FROM fundamentals WHERE ticker='005930.KS'"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == 10.0  # 기존 값 유지

    @patch("data.fetch_fundamentals.fetch_dart_financials")
    @patch("data.fetch_fundamentals.fetch_yahoo_financials")
    def test_run_kr_uses_dart_priority(
        self, mock_yahoo, mock_dart, db_conn, tmp_output_dir
    ):
        """한국 종목: DART 데이터 우선, Yahoo로 보완"""
        from data.fetch_fundamentals import run

        self._seed_ticker_master(db_conn)

        mock_dart.return_value = {
            "revenue_growth": 8.14,
            "operating_margin": 12.9,
            "roe": 8.33,
            "debt_ratio": 33.3,
            "fcf": None,
        }
        mock_yahoo.return_value = {
            "per": 12.5,
            "pbr": 1.2,
            "roe": 10.0,
            "debt_ratio": 30.0,
            "revenue_growth": 7.0,
            "operating_margin": 11.0,
            "fcf": 5000000000,
            "eps": 5000,
            "dividend_yield": 2.1,
            "market_cap": 490000000000000,
        }

        result = run(conn=db_conn, output_dir=str(tmp_output_dir))

        # 한국 종목 찾기
        kr = [r for r in result if r["ticker"] == "005930.KS"]
        assert len(kr) == 1
        # DART 데이터 우선 (revenue_growth는 DART 값)
        assert abs(kr[0]["revenue_growth"] - 8.14) < 0.1
        # Yahoo에서 보완 (per, pbr은 Yahoo)
        assert kr[0]["per"] == 12.5

    @patch("data.fetch_fundamentals.fetch_dart_financials")
    @patch("data.fetch_fundamentals.fetch_yahoo_financials")
    def test_run_us_uses_yahoo_only(
        self, mock_yahoo, mock_dart, db_conn, tmp_output_dir
    ):
        """미국 종목: Yahoo만 사용"""
        from data.fetch_fundamentals import run

        self._seed_ticker_master(db_conn)

        mock_dart.return_value = None
        mock_yahoo.return_value = {
            "per": 25.0,
            "pbr": 3.0,
            "roe": 28.0,
            "debt_ratio": 45.0,
            "revenue_growth": 12.0,
            "operating_margin": 18.0,
            "fcf": 8500000000,
            "eps": 10.85,
            "dividend_yield": 0.0,
            "market_cap": 850000000000,
        }

        result = run(conn=db_conn, output_dir=str(tmp_output_dir))

        us = [r for r in result if r["ticker"] == "TSLA"]
        assert len(us) == 1
        assert us[0]["per"] == 25.0
        assert us[0]["data_source"] == "yahoo"


# ── 7. 스키마 검증 테스트 ──


class TestFundamentalsSchemaValidation:
    """fundamentals.json 스키마 검증"""

    def test_schema_exists(self):
        """utils/schema.py에 fundamentals.json 스키마 등록 확인"""
        from utils.schema import SCHEMAS

        assert "fundamentals.json" in SCHEMAS

    def test_schema_validation_pass(self):
        """정상 데이터 검증 통과"""
        from utils.schema import validate_json

        data = {
            "updated_at": "2026-03-26T00:00:00+09:00",
            "count": 1,
            "fundamentals": [
                {
                    "ticker": "005930.KS",
                    "name": "삼성전자",
                    "market": "KR",
                    "per": 12.5,
                    "data_source": "dart",
                }
            ],
        }
        warnings = validate_json("fundamentals.json", data)
        assert len(warnings) == 0

    def test_schema_validation_missing_field(self):
        """필수 필드 누락 시 경고"""
        from utils.schema import validate_json

        data = {
            "count": 1,
            "fundamentals": [],
        }
        warnings = validate_json("fundamentals.json", data)
        assert any("updated_at" in w for w in warnings)

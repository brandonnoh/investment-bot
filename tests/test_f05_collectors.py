#!/usr/bin/env python3
"""
F05 — 수집 모듈 단위 테스트
fetch_prices, fetch_macro, fetch_news API 모킹, 폴백, graceful degradation 검증
"""

import json
import sqlite3
import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# 프로젝트 루트를 모듈 경로에 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════
# fetch_prices 테스트
# ═══════════════════════════════════════════════════════


class TestFetchYahooQuote:
    """Yahoo Finance API 응답 모킹 + 파싱 검증"""

    def _make_yahoo_response(self, price, prev_close, volume=1000):
        """Yahoo Finance 응답 JSON 생성 헬퍼"""
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

    @patch("data.fetch_prices.urllib.request.urlopen")
    def test_yahoo_정상_응답(self, mock_urlopen):
        """Yahoo API 정상 응답 시 meta 딕셔너리 반환"""
        from data.fetch_prices import fetch_yahoo_quote

        resp = MagicMock()
        resp.read.return_value = self._make_yahoo_response(275.50, 270.00, 80000000)
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        # json.load가 file-like 객체 필요
        resp.read = MagicMock(
            return_value=self._make_yahoo_response(275.50, 270.00, 80000000)
        )
        mock_urlopen.return_value = resp

        # json.load는 file-like 객체에서 읽으므로 BytesIO 사용
        mock_urlopen.return_value = MagicMock()
        mock_urlopen.return_value.__enter__ = lambda s: BytesIO(
            self._make_yahoo_response(275.50, 270.00, 80000000)
        )
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        result = fetch_yahoo_quote("TSLA")
        assert result["regularMarketPrice"] == 275.50
        assert result["chartPreviousClose"] == 270.00

    @patch("data.fetch_prices.urllib.request.urlopen")
    def test_yahoo_빈_결과(self, mock_urlopen):
        """Yahoo API가 빈 result 반환 시 ValueError"""
        from data.fetch_prices import fetch_yahoo_quote

        empty_resp = json.dumps({"chart": {"result": []}}).encode()
        mock_urlopen.return_value = MagicMock()
        mock_urlopen.return_value.__enter__ = lambda s: BytesIO(empty_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises(ValueError, match="데이터 없음"):
            fetch_yahoo_quote("INVALID")

    @patch("data.fetch_prices.urllib.request.urlopen")
    def test_yahoo_네트워크_오류(self, mock_urlopen):
        """Yahoo API 네트워크 오류 시 ConnectionError"""
        import urllib.error
        from data.fetch_prices import fetch_yahoo_quote

        mock_urlopen.side_effect = urllib.error.URLError("timeout")

        with pytest.raises(ConnectionError, match="네트워크 오류"):
            fetch_yahoo_quote("TSLA")


class TestFetchNaverPrice:
    """네이버 금융 API 모킹 + 한국 주식 시세 파싱"""

    def _make_naver_response(self, close, change, ratio, volume, high, low):
        """네이버 금융 응답 JSON 생성 헬퍼"""
        return json.dumps(
            {
                "datas": [
                    {
                        "closePrice": str(close),
                        "compareToPreviousClosePrice": str(change),
                        "fluctuationsRatio": str(ratio),
                        "accumulatedTradingVolume": str(volume),
                        "highPrice": str(high),
                        "lowPrice": str(low),
                    }
                ]
            }
        ).encode()

    @patch("data.fetch_prices.urllib.request.urlopen")
    def test_naver_정상_응답(self, mock_urlopen):
        """네이버 API 정상 응답 파싱 — price, prev_close, change_pct"""
        from data.fetch_prices import fetch_naver_price

        resp_data = self._make_naver_response(82000, 500, 0.61, 15000000, 82500, 81000)
        mock_urlopen.return_value = MagicMock()
        mock_urlopen.return_value.__enter__ = lambda s: BytesIO(resp_data)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        result = fetch_naver_price("005930")
        assert result["price"] == 82000
        assert result["prev_close"] == 82000 - 500
        assert result["change_pct"] == 0.61
        assert result["volume"] == 15000000

    @patch("data.fetch_prices.urllib.request.urlopen")
    def test_naver_네트워크_오류(self, mock_urlopen):
        """네이버 API 네트워크 오류 시 ConnectionError"""
        import urllib.error
        from data.fetch_prices import fetch_naver_price

        mock_urlopen.side_effect = urllib.error.URLError("timeout")
        with pytest.raises(ConnectionError, match="네이버 API 네트워크 오류"):
            fetch_naver_price("005930")

    @patch("data.fetch_prices.urllib.request.urlopen")
    def test_naver_파싱_실패(self, mock_urlopen):
        """네이버 API 응답 구조가 잘못된 경우 ValueError"""
        from data.fetch_prices import fetch_naver_price

        bad_resp = json.dumps({"datas": [{}]}).encode()
        mock_urlopen.return_value = MagicMock()
        mock_urlopen.return_value.__enter__ = lambda s: BytesIO(bad_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises((ValueError, KeyError)):
            fetch_naver_price("005930")


class TestKrStockFallback:
    """한국 주식 키움→네이버 폴백 로직 검증"""

    @patch("data.fetch_prices.fetch_naver_price")
    def test_키움_없으면_네이버_사용(self, mock_naver):
        """KIWOOM_APPKEY 없으면 네이버 API로 폴백"""
        from data.fetch_prices import _fetch_kr_stock

        mock_naver.return_value = {
            "price": 82000,
            "prev_close": 81500,
            "change_pct": 0.61,
            "volume": 15000000,
        }

        with patch.dict("os.environ", {}, clear=True):
            result = _fetch_kr_stock("005930")

        assert result["price"] == 82000
        mock_naver.assert_called_once_with("005930")

    @patch("data.fetch_prices.fetch_naver_price")
    def test_키움_실패시_네이버_폴백(self, mock_naver):
        """키움 API 실패 시 네이버로 자동 폴백"""
        from data.fetch_prices import _fetch_kr_stock

        mock_naver.return_value = {
            "price": 82000,
            "prev_close": 81500,
            "change_pct": 0.61,
            "volume": 15000000,
        }

        with patch.dict("os.environ", {"KIWOOM_APPKEY": "test_key"}):
            with patch(
                "data.fetch_gold_krx.fetch_kiwoom_stock",
                side_effect=Exception("키움 장애"),
            ):
                result = _fetch_kr_stock("005930")

        assert result["price"] == 82000
        mock_naver.assert_called_once()


class TestCollectPrices:
    """collect_prices() 통합 테스트 — 전종목 수집 + graceful degradation"""

    @patch(
        "data.fetch_prices.PORTFOLIO",
        [
            {
                "name": "테슬라",
                "ticker": "TSLA",
                "avg_cost": 300.0,
                "currency": "USD",
                "qty": 1,
                "account": "미국",
            },
        ],
    )
    @patch("data.fetch_prices.fetch_yahoo_quote")
    def test_정상_수집(self, mock_yahoo):
        """단일 종목 정상 수집 — 스키마 필드 검증"""
        from data.fetch_prices import collect_prices

        mock_yahoo.return_value = {
            "regularMarketPrice": 275.50,
            "chartPreviousClose": 270.00,
            "regularMarketVolume": 80000000,
        }

        results = collect_prices()
        assert len(results) == 1
        r = results[0]
        # 필수 필드 존재 확인
        assert r["ticker"] == "TSLA"
        assert r["name"] == "테슬라"
        assert r["price"] == 275.50
        assert r["prev_close"] == 270.00
        assert r["volume"] == 80000000
        assert r["currency"] == "USD"
        assert r["market"] == "US"
        assert "timestamp" in r
        assert "change_pct" in r
        assert "pnl_pct" in r

    @patch(
        "data.fetch_prices.PORTFOLIO",
        [
            {
                "name": "테슬라",
                "ticker": "TSLA",
                "avg_cost": 300.0,
                "currency": "USD",
                "qty": 1,
                "account": "미국",
            },
            {
                "name": "알파벳",
                "ticker": "GOOGL",
                "avg_cost": 308.0,
                "currency": "USD",
                "qty": 2,
                "account": "미국",
            },
        ],
    )
    @patch("data.fetch_prices.fetch_yahoo_quote")
    def test_일부_실패시_나머지_정상(self, mock_yahoo):
        """한 종목 실패해도 나머지 정상 수집 (graceful degradation)"""
        from data.fetch_prices import collect_prices

        def side_effect(ticker):
            if ticker == "TSLA":
                raise ConnectionError("네트워크 오류")
            return {
                "regularMarketPrice": 160.00,
                "chartPreviousClose": 158.00,
                "regularMarketVolume": 30000000,
            }

        mock_yahoo.side_effect = side_effect
        results = collect_prices()

        assert len(results) == 2
        # TSLA는 실패 → price가 None
        tsla = next(r for r in results if r["ticker"] == "TSLA")
        assert tsla["price"] is None
        assert "error" in tsla
        # GOOGL은 정상
        googl = next(r for r in results if r["ticker"] == "GOOGL")
        assert googl["price"] == 160.00

    @patch(
        "data.fetch_prices.PORTFOLIO",
        [
            {
                "name": "테슬라",
                "ticker": "TSLA",
                "avg_cost": 300.0,
                "currency": "USD",
                "qty": 1,
                "account": "미국",
            },
        ],
    )
    @patch("data.fetch_prices.fetch_yahoo_quote")
    def test_전체_실패시에도_빈_리스트_아닌_에러_레코드(self, mock_yahoo):
        """전체 실패 시에도 에러 레코드가 포함된 리스트 반환"""
        from data.fetch_prices import collect_prices

        mock_yahoo.side_effect = Exception("전체 장애")
        results = collect_prices()

        assert len(results) == 1
        assert results[0]["price"] is None
        assert "error" in results[0]


class TestPricesSaveToDb:
    """prices DB 저장 검증"""

    @patch("data.fetch_prices.DB_PATH")
    def test_에러_레코드는_DB_저장_안함(self, mock_db_path, db_conn, tmp_path):
        """price가 None인 에러 레코드는 DB에 삽입하지 않음"""
        from data.fetch_prices import save_to_db

        db_file = tmp_path / "test.db"
        # 실제 파일 DB에 스키마 생성
        from db.init_db import init_schema

        file_conn = sqlite3.connect(str(db_file))
        init_schema(file_conn)
        file_conn.close()

        mock_db_path.__str__ = lambda s: str(db_file)

        records = [
            {
                "ticker": "TSLA",
                "name": "테슬라",
                "price": 275.50,
                "prev_close": 270.00,
                "change_pct": 2.04,
                "volume": 80000000,
                "timestamp": "2026-03-25T15:00:00+09:00",
                "market": "US",
            },
            {
                "ticker": "GOOGL",
                "name": "알파벳",
                "price": None,
                "error": "네트워크 오류",
            },
        ]

        save_to_db(records)

        conn = sqlite3.connect(str(db_file))
        rows = conn.execute("SELECT * FROM prices").fetchall()
        conn.close()
        assert len(rows) == 1  # TSLA만 저장


class TestPricesSaveToJson:
    """prices JSON 저장 검증"""

    @patch("data.fetch_prices.OUTPUT_DIR")
    def test_json_출력_스키마(self, mock_output_dir, tmp_path):
        """JSON 출력에 updated_at, count, prices 필드 존재"""
        from data.fetch_prices import save_to_json

        mock_output_dir.__truediv__ = lambda s, name: tmp_path / name
        mock_output_dir.mkdir = MagicMock()

        records = [
            {
                "ticker": "TSLA",
                "name": "테슬라",
                "price": 275.50,
                "prev_close": 270.00,
                "change_pct": 2.04,
                "volume": 80000000,
                "timestamp": "2026-03-25T15:00:00+09:00",
                "market": "US",
            },
        ]

        save_to_json(records)

        output = json.loads((tmp_path / "prices.json").read_text())
        assert "updated_at" in output
        assert output["count"] == 1
        assert len(output["prices"]) == 1


class TestGoldKrwPerGram:
    """금 현물 원화/g 계산 로직 검증"""

    @patch("data.fetch_prices.fetch_yahoo_quote")
    def test_yahoo_폴백_계산(self, mock_yahoo):
        """키움 없이 Yahoo GC=F × KRW=X ÷ 31.1035 계산"""
        from data.fetch_prices import fetch_gold_krw_per_gram

        def side_effect(ticker):
            if ticker == "GC=F":
                return {"regularMarketPrice": 2000.0, "chartPreviousClose": 1990.0}
            elif ticker == "KRW=X":
                return {"regularMarketPrice": 1380.0, "chartPreviousClose": 1375.0}

        mock_yahoo.side_effect = side_effect

        with patch.dict("os.environ", {}, clear=True):
            price, prev_close = fetch_gold_krw_per_gram()

        expected_price = round(2000.0 * 1380.0 / 31.1035, 0)
        assert price == expected_price


class TestIsKrTicker:
    """한국 주식 티커 판별"""

    def test_ks_티커(self):
        from data.fetch_prices import _is_kr_ticker

        assert _is_kr_ticker("005930.KS") is True

    def test_kq_티커(self):
        from data.fetch_prices import _is_kr_ticker

        assert _is_kr_ticker("035420.KQ") is True

    def test_미국_티커(self):
        from data.fetch_prices import _is_kr_ticker

        assert _is_kr_ticker("TSLA") is False


# ═══════════════════════════════════════════════════════
# fetch_macro 테스트
# ═══════════════════════════════════════════════════════


class TestFetchNaverIndex:
    """네이버 금융 지수 API (코스피/코스닥) 모킹"""

    @patch("data.fetch_macro.urllib.request.urlopen")
    def test_코스피_정상_응답(self, mock_urlopen):
        """코스피 지수 정상 파싱"""
        from data.fetch_macro import fetch_naver_index

        resp_data = json.dumps(
            {
                "datas": [
                    {
                        "closePrice": "2,650.32",
                        "fluctuationsRatio": "-0.45",
                    }
                ]
            }
        ).encode()
        mock_urlopen.return_value = MagicMock()
        mock_urlopen.return_value.__enter__ = lambda s: BytesIO(resp_data)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        result = fetch_naver_index("KOSPI")
        assert result["price"] == 2650.32
        assert result["change_pct"] == -0.45


class TestMacroYahooQuote:
    """매크로 Yahoo Finance API 모킹"""

    @patch("data.fetch_macro.urllib.request.urlopen")
    def test_yahoo_정상(self, mock_urlopen):
        """Yahoo 지표 시세 정상 파싱"""
        from data.fetch_macro import fetch_yahoo_quote

        resp_data = json.dumps(
            {
                "chart": {
                    "result": [
                        {
                            "meta": {
                                "regularMarketPrice": 72.50,
                                "chartPreviousClose": 71.00,
                            }
                        }
                    ]
                }
            }
        ).encode()
        mock_urlopen.return_value = MagicMock()
        mock_urlopen.return_value.__enter__ = lambda s: BytesIO(resp_data)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        result = fetch_yahoo_quote("CL=F")
        assert result["regularMarketPrice"] == 72.50


class TestCollectMacro:
    """collect_macro() 통합 테스트"""

    @patch(
        "data.fetch_macro.MACRO_INDICATORS",
        [
            {"name": "코스피", "ticker": "KOSPI", "category": "INDEX"},
            {"name": "WTI 유가", "ticker": "CL=F", "category": "COMMODITY"},
        ],
    )
    @patch("data.fetch_macro.fetch_yahoo_quote")
    @patch("data.fetch_macro.fetch_naver_index")
    def test_정상_수집_스키마(self, mock_naver, mock_yahoo):
        """매크로 지표 정상 수집 — 출력 스키마 필드 검증"""
        from data.fetch_macro import collect_macro

        mock_naver.return_value = {"price": 2650.32, "change_pct": -0.45}
        mock_yahoo.return_value = {
            "regularMarketPrice": 72.50,
            "chartPreviousClose": 71.00,
        }

        results = collect_macro()
        assert len(results) == 2

        kospi = next(r for r in results if r["indicator"] == "코스피")
        assert kospi["value"] == 2650.32
        assert kospi["change_pct"] == -0.45
        assert kospi["category"] == "INDEX"
        assert "timestamp" in kospi

        wti = next(r for r in results if r["indicator"] == "WTI 유가")
        assert wti["value"] == 72.50

    @patch(
        "data.fetch_macro.MACRO_INDICATORS",
        [
            {"name": "코스피", "ticker": "KOSPI", "category": "INDEX"},
            {"name": "WTI 유가", "ticker": "CL=F", "category": "COMMODITY"},
            {"name": "VIX", "ticker": "^VIX", "category": "VOLATILITY"},
        ],
    )
    @patch("data.fetch_macro.fetch_yahoo_quote")
    @patch("data.fetch_macro.fetch_naver_index")
    def test_개별_실패시_나머지_정상(self, mock_naver, mock_yahoo):
        """하나의 지표 실패해도 나머지 정상 수집"""
        from data.fetch_macro import collect_macro

        mock_naver.return_value = {"price": 2650.32, "change_pct": -0.45}

        def yahoo_side_effect(ticker):
            if ticker == "CL=F":
                raise ConnectionError("네트워크 오류")
            return {"regularMarketPrice": 18.5, "chartPreviousClose": 19.0}

        mock_yahoo.side_effect = yahoo_side_effect

        results = collect_macro()
        assert len(results) == 3

        # 코스피 정상
        kospi = next(r for r in results if r["indicator"] == "코스피")
        assert kospi["value"] == 2650.32

        # WTI 실패
        wti = next(r for r in results if r["indicator"] == "WTI 유가")
        assert wti["value"] is None
        assert "error" in wti

        # VIX 정상
        vix = next(r for r in results if r["indicator"] == "VIX")
        assert vix["value"] == 18.5

    @patch(
        "data.fetch_macro.MACRO_INDICATORS",
        [
            {"name": "코스피", "ticker": "KOSPI", "category": "INDEX"},
        ],
    )
    @patch("data.fetch_macro.fetch_naver_index")
    def test_전체_실패시에도_에러_레코드_반환(self, mock_naver):
        """전체 실패 시에도 에러 레코드 포함 리스트 반환"""
        from data.fetch_macro import collect_macro

        mock_naver.side_effect = Exception("장애")
        results = collect_macro()

        assert len(results) == 1
        assert results[0]["value"] is None
        assert "error" in results[0]


class TestMacroSaveToDb:
    """macro DB 저장 검증"""

    @patch("data.fetch_macro.DB_PATH")
    def test_에러_레코드_DB_미저장(self, mock_db_path, tmp_path):
        """value가 None인 에러 레코드는 DB에 삽입 안 됨"""
        from data.fetch_macro import save_to_db
        from db.init_db import init_schema

        db_file = tmp_path / "test.db"
        file_conn = sqlite3.connect(str(db_file))
        init_schema(file_conn)
        file_conn.close()

        mock_db_path.__str__ = lambda s: str(db_file)

        records = [
            {
                "indicator": "코스피",
                "value": 2650.32,
                "change_pct": -0.45,
                "timestamp": "2026-03-25T15:00:00+09:00",
            },
            {"indicator": "WTI 유가", "value": None, "error": "네트워크 오류"},
        ]

        save_to_db(records)

        conn = sqlite3.connect(str(db_file))
        rows = conn.execute("SELECT * FROM macro").fetchall()
        conn.close()
        assert len(rows) == 1


class TestMacroSaveToJson:
    """macro JSON 저장 검증"""

    @patch("data.fetch_macro.OUTPUT_DIR")
    def test_json_출력_스키마(self, mock_output_dir, tmp_path):
        """JSON 출력에 updated_at, count, indicators 필드 존재"""
        from data.fetch_macro import save_to_json

        mock_output_dir.__truediv__ = lambda s, name: tmp_path / name
        mock_output_dir.mkdir = MagicMock()

        records = [
            {
                "indicator": "코스피",
                "value": 2650.32,
                "change_pct": -0.45,
                "category": "INDEX",
                "timestamp": "2026-03-25T15:00:00+09:00",
            },
        ]

        save_to_json(records)

        output = json.loads((tmp_path / "macro.json").read_text())
        assert "updated_at" in output
        assert output["count"] == 1
        assert len(output["indicators"]) == 1


# ═══════════════════════════════════════════════════════
# fetch_news 테스트
# ═══════════════════════════════════════════════════════


class TestFetchGoogleNewsRss:
    """Google News RSS 파싱 테스트"""

    SAMPLE_RSS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Samsung stock rises on AI chip news</title>
          <link>https://example.com/news/1</link>
          <pubDate>Tue, 25 Mar 2026 10:00:00 GMT</pubDate>
          <source>Reuters</source>
        </item>
        <item>
          <title>Samsung quarterly earnings preview</title>
          <link>https://example.com/news/2</link>
          <pubDate>Tue, 25 Mar 2026 08:00:00 GMT</pubDate>
          <source>Bloomberg</source>
        </item>
      </channel>
    </rss>"""

    @patch("data.fetch_news.urllib.request.urlopen")
    def test_rss_정상_파싱(self, mock_urlopen):
        """RSS XML에서 title, url, source, published_at 파싱"""
        from data.fetch_news import fetch_google_news_rss

        mock_urlopen.return_value = MagicMock()
        mock_urlopen.return_value.__enter__ = lambda s: BytesIO(self.SAMPLE_RSS_XML)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        results = fetch_google_news_rss("삼성전자", count=5)
        assert len(results) == 2
        assert results[0]["title"] == "Samsung stock rises on AI chip news"
        assert results[0]["url"] == "https://example.com/news/1"
        assert results[0]["source"] == "Reuters"

    @patch("data.fetch_news.urllib.request.urlopen")
    def test_rss_count_제한(self, mock_urlopen):
        """count 파라미터로 결과 수 제한"""
        from data.fetch_news import fetch_google_news_rss

        mock_urlopen.return_value = MagicMock()
        mock_urlopen.return_value.__enter__ = lambda s: BytesIO(self.SAMPLE_RSS_XML)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        results = fetch_google_news_rss("삼성전자", count=1)
        assert len(results) == 1

    @patch("data.fetch_news.urllib.request.urlopen")
    def test_rss_빈_피드(self, mock_urlopen):
        """빈 RSS 피드 시 빈 리스트 반환"""
        from data.fetch_news import fetch_google_news_rss

        empty_rss = (
            b"""<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>"""
        )
        mock_urlopen.return_value = MagicMock()
        mock_urlopen.return_value.__enter__ = lambda s: BytesIO(empty_rss)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        results = fetch_google_news_rss("없는키워드", count=5)
        assert results == []


class TestSearchBraveNews:
    """Brave Search API 모킹"""

    @patch("data.fetch_news.urllib.request.urlopen")
    @patch("data.fetch_news.BRAVE_API_KEY", "test_key_123")
    def test_brave_정상_응답(self, mock_urlopen):
        """Brave API 정상 응답 파싱"""
        from data.fetch_news import search_brave_news

        resp_data = json.dumps(
            {
                "results": [
                    {
                        "title": "저평가 종목 발굴 전략",
                        "url": "https://example.com/brave/1",
                        "description": "투자 전략 기사",
                        "meta_url": {"hostname": "example.com"},
                        "age": "2h ago",
                    },
                ]
            }
        ).encode()
        mock_urlopen.return_value = MagicMock()
        mock_urlopen.return_value.__enter__ = lambda s: BytesIO(resp_data)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        results = search_brave_news("저평가 종목", count=2)
        assert len(results) == 1
        assert results[0]["title"] == "저평가 종목 발굴 전략"

    def test_brave_api키_없으면_에러(self):
        """BRAVE_API_KEY 없으면 ValueError"""
        from data.fetch_news import search_brave_news

        with patch("data.fetch_news.BRAVE_API_KEY", ""):
            with pytest.raises(ValueError, match="BRAVE_API_KEY"):
                search_brave_news("test")


class TestCalculateRelevance:
    """관련도 스코어 계산 검증"""

    def test_전부_매칭(self):
        from data.fetch_news import calculate_relevance

        score = calculate_relevance("삼성전자 주가 급등", ["삼성전자", "주가"])
        assert score == 1.0

    def test_부분_매칭(self):
        from data.fetch_news import calculate_relevance

        score = calculate_relevance("삼성전자 뉴스", ["삼성전자", "주가"])
        assert score == 0.5

    def test_매칭_없음(self):
        from data.fetch_news import calculate_relevance

        score = calculate_relevance("무관한 기사", ["삼성전자", "주가"])
        assert score == 0.0

    def test_빈_키워드(self):
        from data.fetch_news import calculate_relevance

        score = calculate_relevance("아무 기사", [])
        assert score == 0.5


class TestCollectNews:
    """collect_news() 통합 테스트"""

    @patch(
        "data.fetch_news.PORTFOLIO",
        [
            {
                "name": "삼성전자",
                "ticker": "005930.KS",
                "avg_cost": 80000,
                "currency": "KRW",
                "qty": 10,
                "account": "ISA",
            },
        ],
    )
    @patch("data.fetch_news.TICKER_KEYWORDS", {"005930.KS": ["삼성전자 주가"]})
    @patch("data.fetch_news.MACRO_KEYWORDS", {})
    @patch("data.fetch_news.fetch_google_news_rss")
    def test_종목_뉴스_수집(self, mock_rss):
        """종목별 RSS 뉴스 수집 — 기본 스키마 검증"""
        from data.fetch_news import collect_news

        mock_rss.return_value = [
            {
                "title": "삼성전자 AI 투자",
                "url": "https://ex.com/1",
                "source": "Reuters",
                "published_at": "2026-03-25",
            },
        ]

        news, rss_count, brave_count = collect_news()
        assert len(news) == 1
        assert rss_count == 1
        assert brave_count == 0

        item = news[0]
        assert item["title"] == "삼성전자 AI 투자"
        assert item["tickers"] == ["005930.KS"]
        assert item["category"] == "stock"
        assert item["fetch_method"] == "rss"

    @patch("data.fetch_news.PORTFOLIO", [])
    @patch("data.fetch_news.TICKER_KEYWORDS", {})
    @patch(
        "data.fetch_news.MACRO_KEYWORDS",
        {
            "macro": {"relevance": 0.8, "method": "rss", "keywords": ["코스피"]},
        },
    )
    @patch("data.fetch_news.fetch_google_news_rss")
    def test_매크로_rss_수집(self, mock_rss):
        """매크로 키워드 RSS 수집"""
        from data.fetch_news import collect_news

        mock_rss.return_value = [
            {
                "title": "코스피 상승",
                "url": "https://ex.com/macro1",
                "source": "MBN",
                "published_at": "2026-03-25",
            },
        ]

        news, rss_count, brave_count = collect_news()
        assert len(news) == 1
        assert news[0]["category"] == "macro"
        assert news[0]["relevance_score"] == 0.8

    @patch(
        "data.fetch_news.PORTFOLIO",
        [
            {
                "name": "삼성전자",
                "ticker": "005930.KS",
                "avg_cost": 80000,
                "currency": "KRW",
                "qty": 10,
                "account": "ISA",
            },
        ],
    )
    @patch("data.fetch_news.TICKER_KEYWORDS", {"005930.KS": ["삼성전자 주가"]})
    @patch("data.fetch_news.MACRO_KEYWORDS", {})
    @patch("data.fetch_news.fetch_google_news_rss")
    def test_중복_url_제거(self, mock_rss):
        """같은 URL이 여러 번 나오면 중복 제거"""
        from data.fetch_news import collect_news

        mock_rss.return_value = [
            {
                "title": "기사1",
                "url": "https://ex.com/dup",
                "source": "A",
                "published_at": "2026-03-25",
            },
            {
                "title": "기사2",
                "url": "https://ex.com/dup",
                "source": "B",
                "published_at": "2026-03-25",
            },
            {
                "title": "기사3",
                "url": "https://ex.com/unique",
                "source": "C",
                "published_at": "2026-03-25",
            },
        ]

        news, rss_count, _ = collect_news()
        assert rss_count == 2  # 중복 1건 제거
        urls = [n["url"] for n in news]
        assert urls.count("https://ex.com/dup") == 1

    @patch(
        "data.fetch_news.PORTFOLIO",
        [
            {
                "name": "삼성전자",
                "ticker": "005930.KS",
                "avg_cost": 80000,
                "currency": "KRW",
                "qty": 10,
                "account": "ISA",
            },
        ],
    )
    @patch("data.fetch_news.TICKER_KEYWORDS", {"005930.KS": ["삼성전자 주가"]})
    @patch("data.fetch_news.MACRO_KEYWORDS", {})
    @patch("data.fetch_news.fetch_google_news_rss")
    def test_rss_실패시_graceful(self, mock_rss):
        """RSS 실패 시에도 빈 리스트 반환 (파이프라인 중단 안 됨)"""
        from data.fetch_news import collect_news

        mock_rss.side_effect = Exception("RSS 장애")
        news, rss_count, brave_count = collect_news()

        assert len(news) == 0
        assert rss_count == 0


class TestNewsSaveToDb:
    """news DB 저장 + 중복 방지 검증"""

    def test_중복_뉴스_INSERT_OR_IGNORE(self, db_conn):
        """같은 title+source 뉴스는 중복 삽입 무시"""
        # UNIQUE 인덱스 생성
        db_conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_news_title_source ON news (title, source)"
        )

        record = (
            "뉴스 제목",
            "요약",
            "Reuters",
            "https://ex.com/1",
            "2026-03-25",
            0.9,
            "[]",
            "stock",
        )

        db_conn.execute(
            "INSERT INTO news (title, summary, source, url, published_at, relevance_score, tickers, category) VALUES (?,?,?,?,?,?,?,?)",
            record,
        )
        db_conn.commit()

        # 같은 title+source로 재삽입 시도
        db_conn.execute(
            "INSERT OR IGNORE INTO news (title, summary, source, url, published_at, relevance_score, tickers, category) VALUES (?,?,?,?,?,?,?,?)",
            record,
        )
        db_conn.commit()

        count = db_conn.execute("SELECT COUNT(*) FROM news").fetchone()[0]
        assert count == 1  # 중복 무시


class TestNewsSaveToJson:
    """news JSON 저장 검증"""

    @patch("data.fetch_news.OUTPUT_DIR")
    def test_json_출력_스키마(self, mock_output_dir, tmp_path):
        """JSON 출력에 updated_at, count, news 필드"""
        from data.fetch_news import save_to_json

        mock_output_dir.__truediv__ = lambda s, name: tmp_path / name
        mock_output_dir.mkdir = MagicMock()

        records = [
            {
                "title": "테스트 뉴스",
                "summary": "",
                "source": "Test",
                "url": "https://ex.com/1",
                "published_at": "2026-03-25",
                "relevance_score": 0.9,
                "category": "stock",
                "tickers": [],
            },
        ]

        save_to_json(records)

        output = json.loads((tmp_path / "news.json").read_text())
        assert "updated_at" in output
        assert output["count"] == 1
        assert len(output["news"]) == 1


# ═══════════════════════════════════════════════════════
# 공통 Graceful Degradation 테스트
# ═══════════════════════════════════════════════════════


class TestGracefulDegradation:
    """공통: 일부 항목 실패 시 나머지 정상 수집 확인"""

    @patch(
        "data.fetch_prices.PORTFOLIO",
        [
            {
                "name": "삼성전자",
                "ticker": "005930.KS",
                "avg_cost": 80000,
                "currency": "KRW",
                "qty": 10,
                "account": "ISA",
            },
            {
                "name": "테슬라",
                "ticker": "TSLA",
                "avg_cost": 300.0,
                "currency": "USD",
                "qty": 1,
                "account": "미국",
            },
            {
                "name": "알파벳",
                "ticker": "GOOGL",
                "avg_cost": 308.0,
                "currency": "USD",
                "qty": 2,
                "account": "미국",
            },
        ],
    )
    @patch("data.fetch_prices.fetch_yahoo_quote")
    @patch("data.fetch_prices._fetch_kr_stock")
    def test_prices_혼합_성공실패(self, mock_kr, mock_yahoo):
        """prices: KR 1건 성공, US 1건 실패, US 1건 성공"""
        from data.fetch_prices import collect_prices

        mock_kr.return_value = {
            "price": 82000,
            "prev_close": 81500,
            "change_pct": 0.61,
            "volume": 15000000,
        }

        def yahoo_side(ticker):
            if ticker == "TSLA":
                raise Exception("TSLA 오류")
            return {
                "regularMarketPrice": 160.00,
                "chartPreviousClose": 158.00,
                "regularMarketVolume": 30000000,
            }

        mock_yahoo.side_effect = yahoo_side

        results = collect_prices()
        assert len(results) == 3

        success = [r for r in results if r["price"] is not None]
        fail = [r for r in results if r["price"] is None]
        assert len(success) == 2
        assert len(fail) == 1
        assert fail[0]["ticker"] == "TSLA"

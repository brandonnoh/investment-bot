"""T1: 유니버스 확장 테스트 — 코스피 200 + S&P 100"""

import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_universe_kospi200_defined():
    """UNIVERSE_KOSPI200 리스트가 정의되어 있고 최소 50개 이상"""
    from analysis.screener import UNIVERSE_KOSPI200

    assert len(UNIVERSE_KOSPI200) >= 50
    # 모든 항목이 ticker, name, market 키를 가짐
    for item in UNIVERSE_KOSPI200:
        assert "ticker" in item
        assert "name" in item
        assert item["market"] == "KR"
    # 한국 종목 형식 확인 (.KS 또는 .KQ)
    kr_count = sum(1 for i in UNIVERSE_KOSPI200 if ".KS" in i["ticker"] or ".KQ" in i["ticker"])
    assert kr_count >= 50


def test_universe_sp100_defined():
    """UNIVERSE_SP100 리스트가 정의되어 있고 최소 80개 이상"""
    from analysis.screener import UNIVERSE_SP100

    assert len(UNIVERSE_SP100) >= 80
    for item in UNIVERSE_SP100:
        assert "ticker" in item
        assert "name" in item
        assert item["market"] == "US"
    # 주요 S&P 100 종목 포함 여부
    tickers = {i["ticker"] for i in UNIVERSE_SP100}
    for expected in ["AAPL", "MSFT", "NVDA", "AMZN", "META"]:
        assert expected in tickers


def test_universe_no_duplicates():
    """유니버스 내 중복 티커 없음"""
    from analysis.screener import UNIVERSE_KOSPI200, UNIVERSE_SP100

    kospi_tickers = [i["ticker"] for i in UNIVERSE_KOSPI200]
    sp_tickers = [i["ticker"] for i in UNIVERSE_SP100]
    assert len(kospi_tickers) == len(set(kospi_tickers)), "코스피 유니버스 중복 존재"
    assert len(sp_tickers) == len(set(sp_tickers)), "S&P 유니버스 중복 존재"


def _make_mock_result(ticker_info: dict) -> dict:
    """analyze_ticker 모킹용 결과 생성"""
    return {
        "ticker": ticker_info["ticker"],
        "name": ticker_info["name"],
        "market": ticker_info["market"],
        "price": 100.0,
        "day_change": 1.0,
        "month_return": float(hash(ticker_info["ticker"]) % 20 - 10),
        "volume": 1000000,
        "currency": "USD" if ticker_info["market"] == "US" else "KRW",
    }


def test_screen_universe_returns_top_n():
    """screen_universe가 상위 top_n개 반환 (month_return 기준 내림차순)"""
    from analysis.screener import UNIVERSE_KOSPI200, screen_universe

    sample = UNIVERSE_KOSPI200[:15]
    with patch("analysis.screener.analyze_ticker", side_effect=_make_mock_result):
        results = screen_universe(sample, top_n=5)

    assert len(results) == 5
    # month_return 내림차순 정렬 확인
    returns = [r["month_return"] for r in results if r.get("month_return") is not None]
    assert returns == sorted(returns, reverse=True)


def test_screen_universe_handles_failures():
    """일부 종목 실패해도 graceful degradation"""
    from analysis.screener import UNIVERSE_SP100, screen_universe

    def mock_analyze(ticker_info):
        # 홀수 인덱스는 None 반환 (실패 시뮬레이션)
        if hash(ticker_info["ticker"]) % 2 == 0:
            return None
        return _make_mock_result(ticker_info)

    sample = UNIVERSE_SP100[:10]
    with patch("analysis.screener.analyze_ticker", side_effect=mock_analyze):
        results = screen_universe(sample, top_n=10)

    # 실패 종목 제외하고 결과 반환됨
    assert isinstance(results, list)
    assert all(r is not None for r in results)


def test_generate_universe_section_format():
    """유니버스 섹션 마크다운 형식 확인"""
    from analysis.screener import generate_universe_section

    kospi_top = [
        {
            "ticker": "005930.KS",
            "name": "삼성전자",
            "market": "KR",
            "price": 62000,
            "day_change": 1.2,
            "month_return": 5.3,
            "volume": 5000000,
            "currency": "KRW",
        }
    ]
    sp_top = [
        {
            "ticker": "AAPL",
            "name": "Apple",
            "market": "US",
            "price": 200.5,
            "day_change": -0.5,
            "month_return": 8.1,
            "volume": 50000000,
            "currency": "USD",
        }
    ]

    section = generate_universe_section(kospi_top, sp_top, 50, 100)
    assert "삼성전자" in section
    assert "Apple" in section
    assert "코스피 200" in section
    assert "S&P 100" in section
    assert "5.30%" in section or "+5.30%" in section


def test_run_saves_screener_results_json(tmp_path):
    """run() 실행 후 screener_results.json 저장 확인"""
    import config
    from analysis import screener

    orig_output = config.OUTPUT_DIR
    config.OUTPUT_DIR = tmp_path
    screener.OUTPUT_DIR = tmp_path

    def mock_analyze(ticker_info):
        return _make_mock_result(ticker_info)

    with patch("analysis.screener.analyze_ticker", side_effect=mock_analyze):
        screener.run()

    results_path = tmp_path / "screener_results.json"
    assert results_path.exists(), "screener_results.json 미생성"

    with open(results_path, encoding="utf-8") as f:
        data = json.load(f)

    assert "kospi200_top10" in data
    assert "sp100_top10" in data
    assert "generated_at" in data
    assert data["total_kospi_scanned"] == len(screener.UNIVERSE_KOSPI200)
    assert data["total_sp_scanned"] == len(screener.UNIVERSE_SP100)

    # 복구
    config.OUTPUT_DIR = orig_output
    screener.OUTPUT_DIR = orig_output

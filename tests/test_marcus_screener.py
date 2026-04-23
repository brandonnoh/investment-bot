"""marcus_screener 단위 테스트"""

import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import analysis.marcus_screener as screener_mod
from analysis.marcus_screener import get_marcus_screened_pool

# ── 테스트용 더미 opportunity ──

def _make_opp(ticker: str, score: float, grade: str = "B+") -> dict:
    return {
        "ticker": ticker,
        "name": f"Company {ticker}",
        "grade": grade,
        "composite_score": score,
        "per": 10.0,
        "roe": 15.0,
        "operating_margin": None,
        "revenue_growth": None,
        "debt_ratio": 50.0,
        "factors": {},
    }


def _mock_run_strategy(strategy_id: str) -> list[dict]:
    """전략별 더미 결과 반환"""
    if strategy_id == "composite":
        return [_make_opp("AAPL", 0.85, "A"), _make_opp("MSFT", 0.72, "B+"), _make_opp("XYZ", 0.55, "C")]
    if strategy_id == "buffett":
        return [_make_opp("AAPL", 0.90, "A+"), _make_opp("KO", 0.75, "B+")]
    return []


class TestGetMarcusScreenedPool:
    def setup_method(self):
        # 매 테스트 전 캐시 초기화
        screener_mod._CACHE.clear()

    def test_returns_list(self):
        with patch("analysis.marcus_screener.run_strategy", side_effect=_mock_run_strategy):
            result = get_marcus_screened_pool()
        assert isinstance(result, list)

    def test_all_b_plus(self):
        """모든 종목이 B+(0.70) 이상이어야 한다"""
        with patch("analysis.marcus_screener.run_strategy", side_effect=_mock_run_strategy):
            result = get_marcus_screened_pool()
        for item in result:
            assert item["composite_score"] >= 0.70, f"{item['ticker']} score {item['composite_score']} < 0.70"

    def test_has_required_fields(self):
        """필수 필드 존재 확인"""
        with patch("analysis.marcus_screener.run_strategy", side_effect=_mock_run_strategy):
            result = get_marcus_screened_pool()
        assert len(result) > 0
        for item in result:
            for field in ("ticker", "name", "grade", "strategies", "composite_score"):
                assert field in item, f"'{field}' 필드 누락: {item}"

    def test_strategies_is_list(self):
        """strategies 필드가 리스트여야 한다"""
        with patch("analysis.marcus_screener.run_strategy", side_effect=_mock_run_strategy):
            result = get_marcus_screened_pool()
        for item in result:
            assert isinstance(item["strategies"], list)

    def test_deduplication_merges_strategies(self):
        """AAPL이 composite + buffett 두 전략에서 통과 → strategies에 둘 다 기록"""
        with patch("analysis.marcus_screener.run_strategy", side_effect=_mock_run_strategy):
            result = get_marcus_screened_pool()
        aapl = next((x for x in result if x["ticker"] == "AAPL"), None)
        assert aapl is not None
        assert len(aapl["strategies"]) >= 2

    def test_cache_returns_same_object(self):
        """두 번 호출 시 캐시된 동일 객체 반환"""
        with patch("analysis.marcus_screener.run_strategy", side_effect=_mock_run_strategy) as mock:
            first = get_marcus_screened_pool()
            second = get_marcus_screened_pool()
        assert first is second
        # 캐시 덕분에 run_strategy 호출 횟수가 전략 수(5)로 제한됨
        assert mock.call_count == len(screener_mod.STRATEGY_IDS)

    def test_returns_empty_on_failure(self):
        """run_strategy 전체 실패 시 빈 리스트 반환 (graceful degradation)"""
        with patch("analysis.marcus_screener.run_strategy", side_effect=Exception("DB 없음")):
            result = get_marcus_screened_pool()
        assert result == []

    def test_sorted_by_score_desc(self):
        """composite_score 내림차순 정렬 확인"""
        with patch("analysis.marcus_screener.run_strategy", side_effect=_mock_run_strategy):
            result = get_marcus_screened_pool()
        scores = [x["composite_score"] for x in result]
        assert scores == sorted(scores, reverse=True)

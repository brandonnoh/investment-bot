"""Phase 4 screener 고도화 테스트"""
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_merge_universe():
    """기존 스크리닝 + opportunities 통합"""
    from analysis.screener import merge_universe
    existing = [{"ticker": "NVDA", "name": "NVIDIA", "sector": "AI"}]
    opps = [{"ticker": "012450.KS", "name": "한화에어로스페이스",
             "discovered_via": "방산 수주"}]
    merged = merge_universe(existing, opps)
    tickers = [m["ticker"] for m in merged]
    assert "NVDA" in tickers
    assert "012450.KS" in tickers


def test_merge_universe_dedup():
    """중복 종목 제거"""
    from analysis.screener import merge_universe
    existing = [{"ticker": "NVDA", "name": "NVIDIA"}]
    opps = [{"ticker": "NVDA", "name": "NVIDIA", "discovered_via": "AI"}]
    merged = merge_universe(existing, opps)
    assert len(merged) == 1


def test_merge_universe_empty():
    """빈 리스트 병합"""
    from analysis.screener import merge_universe
    assert merge_universe([], []) == []
    assert len(merge_universe([{"ticker": "A"}], [])) == 1


def test_screener_report_format():
    """리포트에 종목 정보가 포함되는지"""
    from analysis.screener import generate_screener_report
    highlights = [
        {"ticker": "012450.KS", "name": "한화에어로스페이스",
         "sector": "방산", "market": "KR", "price": 350000,
         "change_pct": 2.5, "day_change": 2.5,
         "composite_score": 0.82,
         "sub_scores": {"return": 0.8, "rsi": 0.7, "sentiment": 0.9, "macro": 0.85},
         "month_return": 12.5, "volume": 1000000}
    ]
    report = generate_screener_report({}, highlights)
    assert "한화에어로스페이스" in report
    assert isinstance(report, str)
    assert len(report) > 50


def test_composite_score_in_report():
    """리포트에 복합 점수 관련 정보가 포함되는지"""
    from analysis.screener import generate_screener_report
    highlights = [
        {"ticker": "012450.KS", "name": "한화에어로스페이스",
         "sector": "방산", "market": "KR", "price": 350000,
         "change_pct": 2.5, "day_change": 2.5,
         "composite_score": 0.82,
         "sub_scores": {"return": 0.8, "rsi": 0.7, "sentiment": 0.9, "macro": 0.85},
         "month_return": 12.5, "volume": 1000000}
    ]
    report = generate_screener_report({}, highlights)
    # 점수 관련 텍스트가 어떤 형태로든 포함
    has_score = ("82" in report or "0.82" in report or "점수" in report or "score" in report.lower())
    assert has_score, f"리포트에 점수 정보 없음: {report[:200]}"

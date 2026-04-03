#!/usr/bin/env python3
"""F27 — 문맥 기반 감성: relevance_score 가중 평균 검증"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from analysis.sentiment import aggregate_sentiment_by_ticker_weighted


def test_weighted_sentiment_high_relevance():
    """높은 relevance는 낮은 relevance보다 더 많이 반영된다."""
    news = [
        {"tickers": ["005930.KS"], "sentiment": 1.0, "relevance_score": 1.0},
        {"tickers": ["005930.KS"], "sentiment": -1.0, "relevance_score": 0.1},
    ]
    result = aggregate_sentiment_by_ticker_weighted(news)
    # 1.0*1.0 + (-1.0)*0.1 / (1.0+0.1) ≈ 0.818 > 0
    assert result["005930.KS"]["avg_sentiment"] > 0


def test_weighted_sentiment_equal_relevance():
    """동일 relevance면 단순 평균과 같다."""
    news = [
        {"tickers": ["TSLA"], "sentiment": 0.8, "relevance_score": 0.5},
        {"tickers": ["TSLA"], "sentiment": 0.4, "relevance_score": 0.5},
    ]
    result = aggregate_sentiment_by_ticker_weighted(news)
    assert abs(result["TSLA"]["avg_sentiment"] - 0.6) < 0.01


def test_weighted_sentiment_zero_relevance():
    """relevance_score=0인 뉴스는 무시된다."""
    news = [
        {"tickers": ["GOOGL"], "sentiment": 1.0, "relevance_score": 0.8},
        {"tickers": ["GOOGL"], "sentiment": -1.0, "relevance_score": 0.0},
    ]
    result = aggregate_sentiment_by_ticker_weighted(news)
    assert result["GOOGL"]["avg_sentiment"] == pytest.approx(1.0)


def test_weighted_sentiment_missing_relevance():
    """relevance_score 없으면 0.5로 기본값 처리."""
    news = [
        {"tickers": ["XOP"], "sentiment": 0.6},
        {"tickers": ["XOP"], "sentiment": 0.4},
    ]
    result = aggregate_sentiment_by_ticker_weighted(news)
    assert abs(result["XOP"]["avg_sentiment"] - 0.5) < 0.01


def test_weighted_sentiment_multi_ticker():
    """한 뉴스가 여러 종목에 연결된 경우 각각 반영."""
    news = [
        {"tickers": ["005930.KS", "TSLA"], "sentiment": 0.9, "relevance_score": 1.0},
    ]
    result = aggregate_sentiment_by_ticker_weighted(news)
    assert "005930.KS" in result
    assert "TSLA" in result
    assert result["005930.KS"]["avg_sentiment"] == pytest.approx(0.9)


def test_weighted_sentiment_empty():
    """빈 레코드 리스트"""
    result = aggregate_sentiment_by_ticker_weighted([])
    assert result == {}


def test_weighted_count():
    """count 필드가 정확히 기록된다."""
    news = [
        {"tickers": ["005930.KS"], "sentiment": 0.5, "relevance_score": 0.8},
        {"tickers": ["005930.KS"], "sentiment": -0.2, "relevance_score": 0.3},
    ]
    result = aggregate_sentiment_by_ticker_weighted(news)
    assert result["005930.KS"]["count"] == 2


def test_tickers_as_json_string():
    """tickers가 JSON 문자열로 저장된 경우도 처리."""
    news = [
        {"tickers": json.dumps(["NVDA"]), "sentiment": 0.7, "relevance_score": 0.9},
    ]
    result = aggregate_sentiment_by_ticker_weighted(news)
    assert "NVDA" in result


def test_weighted_sentiment_comparison_with_unweighted():
    """가중 평균이 단순 평균과 다르게 계산된다."""
    from analysis.sentiment import aggregate_sentiment_by_ticker

    news = [
        {"tickers": ["TEST"], "sentiment": 0.9, "relevance_score": 0.9},
        {"tickers": ["TEST"], "sentiment": 0.1, "relevance_score": 0.1},
    ]
    weighted = aggregate_sentiment_by_ticker_weighted(news)
    unweighted = aggregate_sentiment_by_ticker(news)

    # 가중치가 다르므로 다른 결과
    assert weighted["TEST"]["avg_sentiment"] > unweighted["TEST"]["avg_sentiment"]


def test_weighted_all_zero_relevance():
    """모든 relevance_score가 0이면 빈 결과"""
    news = [
        {"tickers": ["TEST"], "sentiment": 0.5, "relevance_score": 0.0},
        {"tickers": ["TEST"], "sentiment": 0.3, "relevance_score": 0.0},
    ]
    result = aggregate_sentiment_by_ticker_weighted(news)
    assert len(result) == 0


def test_weighted_missing_sentiment():
    """sentiment 필드가 없으면 스킵"""
    news = [
        {"tickers": ["TEST"], "relevance_score": 0.9},
    ]
    result = aggregate_sentiment_by_ticker_weighted(news)
    assert len(result) == 0


def test_weighted_empty_tickers():
    """tickers가 빈 리스트인 경우"""
    news = [
        {"tickers": [], "sentiment": 0.5, "relevance_score": 0.8},
    ]
    result = aggregate_sentiment_by_ticker_weighted(news)
    assert len(result) == 0


def test_weighted_tickers_with_empty_string():
    """tickers에 빈 문자열이 있으면 무시"""
    news = [
        {"tickers": ["", "TSLA"], "sentiment": 0.5, "relevance_score": 0.8},
    ]
    result = aggregate_sentiment_by_ticker_weighted(news)
    assert "TSLA" in result
    assert "" not in result


def test_weighted_precision():
    """결과가 소수점 4자리로 반올림되는지 확인"""
    news = [
        {"tickers": ["TEST"], "sentiment": 0.33333, "relevance_score": 0.5},
        {"tickers": ["TEST"], "sentiment": 0.66667, "relevance_score": 0.5},
    ]
    result = aggregate_sentiment_by_ticker_weighted(news)
    # 평균: 0.5, 반올림 후 4자리
    assert result["TEST"]["avg_sentiment"] == pytest.approx(0.5, abs=0.0001)

#!/usr/bin/env python3
"""
뉴스 감성 분석 모듈 — 한/영 키워드 기반 감성 점수 계산
- 제목 + 요약 기반 감성 점수 (-1.0 ~ 1.0)
- news 테이블 sentiment 컬럼 저장
- 종목별 평균 감성 점수 집계
외부 패키지 없이 순수 stdlib만 사용
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.sentiment_keywords import (  # noqa: F401, E402  # re-export
    EN_NEGATIVE,
    EN_POSITIVE,
    KO_NEGATIVE,
    KO_POSITIVE,
)

logger = logging.getLogger(__name__)


def calculate_sentiment(title: str, summary: str) -> float:
    """제목 + 요약 기반 감성 점수 계산 (-1.0 ~ 1.0)

    키워드 매칭 방식: 텍스트에 키워드가 포함되면 카운트
    점수 = (긍정 - 부정) / (긍정 + 부정), 매칭 없으면 0.0

    Args:
        title: 뉴스 제목
        summary: 뉴스 요약

    Returns:
        float: -1.0 ~ 1.0 감성 점수 (소수점 2자리)
    """
    if not title and not summary:
        return 0.0

    text = f"{title} {summary}".lower()

    pos_count = 0
    neg_count = 0

    # 한국어 키워드 매칭
    for kw in KO_POSITIVE:
        if kw in text:
            pos_count += 1
    for kw in KO_NEGATIVE:
        if kw in text:
            neg_count += 1

    # 영어 키워드 매칭
    for kw in EN_POSITIVE:
        if kw in text:
            pos_count += 1
    for kw in EN_NEGATIVE:
        if kw in text:
            neg_count += 1

    total = pos_count + neg_count
    if total == 0:
        return 0.0

    score = (pos_count - neg_count) / total
    return round(max(-1.0, min(1.0, score)), 2)


def analyze_news_sentiment(records: list[dict]) -> list[dict]:
    """뉴스 레코드 리스트에 sentiment 필드 추가

    Args:
        records: 뉴스 레코드 리스트 (title, summary 필드 필요)

    Returns:
        sentiment 필드가 추가된 레코드 리스트
    """
    if not records:
        return []

    for record in records:
        if "error" in record:
            record["sentiment"] = 0.0
            continue

        title = record.get("title", "")
        summary = record.get("summary", "")
        record["sentiment"] = calculate_sentiment(title, summary)

    return records


def save_sentiment_to_db(conn, updates: list[dict]):
    """감성 점수를 news 테이블에 업데이트

    Args:
        conn: sqlite3.Connection 객체
        updates: [{"title": str, "source": str, "sentiment": float}, ...]
    """
    if not updates:
        return

    cursor = conn.cursor()
    updated = 0
    for item in updates:
        cursor.execute(
            "UPDATE news SET sentiment = ? WHERE title = ? AND source = ?",
            (item["sentiment"], item["title"], item["source"]),
        )
        if cursor.rowcount > 0:
            updated += 1
    conn.commit()
    logger.info(f"감성 점수 DB 업데이트: {updated}/{len(updates)}건")


def aggregate_sentiment_by_ticker(records: list[dict]) -> dict:
    """종목별 평균 감성 점수 집계

    Args:
        records: sentiment 필드가 있는 뉴스 레코드 리스트

    Returns:
        {ticker: {"avg_sentiment": float, "count": int}}
    """
    if not records:
        return {}

    ticker_scores = {}
    for record in records:
        tickers = record.get("tickers", [])
        sentiment = record.get("sentiment", 0.0)
        for ticker in tickers:
            if ticker not in ticker_scores:
                ticker_scores[ticker] = []
            ticker_scores[ticker].append(sentiment)

    result = {}
    for ticker, scores in ticker_scores.items():
        avg = sum(scores) / len(scores)
        result[ticker] = {
            "avg_sentiment": round(avg, 2),
            "count": len(scores),
        }

    return result


def aggregate_sentiment_by_ticker_weighted(news_records: list[dict]) -> dict:
    """relevance_score 가중 평균으로 종목별 감성 집계.

    Args:
        news_records: {"tickers": [...], "sentiment": float, "relevance_score": float} 리스트

    Returns:
        {"ticker": {"avg_sentiment": float, "count": int}} dict
    """
    import json as _json

    weighted_sum: dict = {}
    weight_total: dict = {}
    counts: dict = {}

    for record in news_records:
        sentiment = record.get("sentiment")
        if sentiment is None:
            continue
        relevance = record.get("relevance_score", 0.5)
        if relevance <= 0:
            continue
        tickers = record.get("tickers") or []
        if isinstance(tickers, str):
            try:
                tickers = _json.loads(tickers)
            except Exception:
                tickers = [tickers]

        for ticker in tickers:
            if not ticker:
                continue
            weighted_sum[ticker] = weighted_sum.get(ticker, 0.0) + sentiment * relevance
            weight_total[ticker] = weight_total.get(ticker, 0.0) + relevance
            counts[ticker] = counts.get(ticker, 0) + 1

    result = {}
    for ticker in weighted_sum:
        total_w = weight_total[ticker]
        result[ticker] = {
            "avg_sentiment": round(weighted_sum[ticker] / total_w, 4) if total_w > 0 else 0.0,
            "count": counts[ticker],
        }
    return result

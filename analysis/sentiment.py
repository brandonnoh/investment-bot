#!/usr/bin/env python3
"""
뉴스 감성 분석 모듈 — 한/영 키워드 기반 감성 점수 계산
- 한국어/영어 금융 도메인 키워드 사전
- 제목 + 요약 기반 감성 점수 (-1.0 ~ 1.0)
- news 테이블 sentiment 컬럼 저장
- 종목별 평균 감성 점수 집계
외부 패키지 없이 순수 stdlib만 사용
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger(__name__)

# ── 한국어 긍정 키워드 (금융 도메인) ──
KO_POSITIVE = frozenset([
    "급등", "상승", "호조", "호재", "매출 증가", "영업이익", "사상 최대",
    "신고가", "돌파", "반등", "회복", "강세", "매수", "순매수",
    "성장", "확대", "투자 확대", "수출 증가", "흑자", "개선",
    "기대", "전망 밝", "수혜", "최고치", "상향", "호황",
    "안정", "완화", "유입", "상승세", "이익 증가",
])

# ── 한국어 부정 키워드 (금융 도메인) ──
KO_NEGATIVE = frozenset([
    "급락", "폭락", "하락", "악재", "매출 감소", "적자", "손실",
    "침체", "위기", "불안", "매도", "순매도", "투매",
    "하향", "축소", "감소", "둔화", "약세", "저조",
    "우려", "리스크", "불확실", "전쟁", "제재", "파산",
    "폭탄", "디폴트", "인플레이션", "긴축", "유출", "하락세",
])

# ── 영어 긍정 키워드 (금융 도메인) ──
EN_POSITIVE = frozenset([
    "surge", "rally", "gain", "bullish", "beat", "growth",
    "profit", "revenue", "upgrade", "outperform", "record high",
    "recovery", "strong", "boost", "optimistic", "upside",
    "buy", "accumulate", "breakout", "expansion", "earnings beat",
    "positive", "improve", "advance", "momentum", "all-time high",
])

# ── 영어 부정 키워드 (금융 도메인) ──
EN_NEGATIVE = frozenset([
    "crash", "plunge", "drop", "bearish", "miss", "decline",
    "loss", "deficit", "downgrade", "underperform", "sell-off",
    "recession", "weak", "risk", "pessimistic", "downside",
    "sell", "bankruptcy", "default", "inflation", "fear",
    "negative", "worsen", "slump", "crisis", "warning",
])


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

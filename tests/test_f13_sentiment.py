#!/usr/bin/env python3
"""
F13 — 뉴스 감성 점수 테스트
한/영 키워드 기반 감성 분석, DB 저장, JSON 출력, 종목별 집계
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── 키워드 사전 테스트 ──


class TestSentimentDictionaries:
    """감성 키워드 사전 구조 검증"""

    def test_korean_positive_keywords_exist(self):
        """한국어 긍정 키워드 사전이 존재하고 비어있지 않음"""
        from analysis.sentiment import KO_POSITIVE

        assert isinstance(KO_POSITIVE, (list, set, frozenset))
        assert len(KO_POSITIVE) >= 10  # 최소 10개 이상

    def test_korean_negative_keywords_exist(self):
        """한국어 부정 키워드 사전이 존재하고 비어있지 않음"""
        from analysis.sentiment import KO_NEGATIVE

        assert isinstance(KO_NEGATIVE, (list, set, frozenset))
        assert len(KO_NEGATIVE) >= 10

    def test_english_positive_keywords_exist(self):
        """영어 긍정 키워드 사전이 존재하고 비어있지 않음"""
        from analysis.sentiment import EN_POSITIVE

        assert isinstance(EN_POSITIVE, (list, set, frozenset))
        assert len(EN_POSITIVE) >= 10

    def test_english_negative_keywords_exist(self):
        """영어 부정 키워드 사전이 존재하고 비어있지 않음"""
        from analysis.sentiment import EN_NEGATIVE

        assert isinstance(EN_NEGATIVE, (list, set, frozenset))
        assert len(EN_NEGATIVE) >= 10

    def test_no_overlap_korean(self):
        """한국어 긍정/부정 키워드가 겹치지 않음"""
        from analysis.sentiment import KO_NEGATIVE, KO_POSITIVE

        overlap = set(KO_POSITIVE) & set(KO_NEGATIVE)
        assert len(overlap) == 0, f"겹치는 키워드: {overlap}"

    def test_no_overlap_english(self):
        """영어 긍정/부정 키워드가 겹치지 않음"""
        from analysis.sentiment import EN_NEGATIVE, EN_POSITIVE

        overlap = set(EN_POSITIVE) & set(EN_NEGATIVE)
        assert len(overlap) == 0, f"겹치는 키워드: {overlap}"


# ── 감성 점수 계산 테스트 ──


class TestCalculateSentiment:
    """감성 점수 계산 함수 검증"""

    def test_positive_korean_news(self):
        """한국어 긍정 뉴스 — 양수 점수"""
        from analysis.sentiment import calculate_sentiment

        score = calculate_sentiment(
            title="삼성전자 실적 호조, 매출 급증 기대",
            summary="반도체 수출 증가로 영업이익 상승 전망",
        )
        assert score > 0
        assert -1.0 <= score <= 1.0

    def test_negative_korean_news(self):
        """한국어 부정 뉴스 — 음수 점수"""
        from analysis.sentiment import calculate_sentiment

        score = calculate_sentiment(
            title="코스피 폭락, 외국인 대량 매도",
            summary="경기 침체 우려에 투매 확산",
        )
        assert score < 0
        assert -1.0 <= score <= 1.0

    def test_positive_english_news(self):
        """영어 긍정 뉴스 — 양수 점수"""
        from analysis.sentiment import calculate_sentiment

        score = calculate_sentiment(
            title="Tesla stock surges on strong earnings beat",
            summary="Revenue growth accelerates amid bullish outlook",
        )
        assert score > 0
        assert -1.0 <= score <= 1.0

    def test_negative_english_news(self):
        """영어 부정 뉴스 — 음수 점수"""
        from analysis.sentiment import calculate_sentiment

        score = calculate_sentiment(
            title="Market crash deepens as recession fears grow",
            summary="Sell-off accelerates with massive losses",
        )
        assert score < 0
        assert -1.0 <= score <= 1.0

    def test_neutral_news_near_zero(self):
        """중립적 뉴스 — 0 근처 점수"""
        from analysis.sentiment import calculate_sentiment

        score = calculate_sentiment(
            title="삼성전자 주주총회 개최 안내",
            summary="정기 주주총회가 3월 25일에 개최됩니다",
        )
        assert -0.3 <= score <= 0.3

    def test_score_range_always_valid(self):
        """모든 입력에서 점수가 -1.0 ~ 1.0 범위"""
        from analysis.sentiment import calculate_sentiment

        test_cases = [
            ("", ""),
            ("긍정 긍정 긍정 호조 호조 급등 급등 상승 상승 돌파 돌파", ""),
            ("폭락 폭락 폭락 하락 하락 급락 급락 침체 침체 손실 손실", ""),
            ("a" * 1000, "b" * 1000),
        ]
        for title, summary in test_cases:
            score = calculate_sentiment(title, summary)
            assert -1.0 <= score <= 1.0, f"범위 초과: {score}"

    def test_empty_inputs_return_zero(self):
        """빈 입력 시 0.0 반환"""
        from analysis.sentiment import calculate_sentiment

        assert calculate_sentiment("", "") == 0.0

    def test_title_only(self):
        """summary 없이 title만으로도 점수 계산 가능"""
        from analysis.sentiment import calculate_sentiment

        score = calculate_sentiment(title="주가 급등 호재 발표", summary="")
        assert score > 0

    def test_summary_only(self):
        """title 없이 summary만으로도 점수 계산 가능"""
        from analysis.sentiment import calculate_sentiment

        score = calculate_sentiment(
            title="", summary="Stock market rally continues with gains"
        )
        assert score > 0

    def test_return_type_is_float(self):
        """반환 타입이 float"""
        from analysis.sentiment import calculate_sentiment

        result = calculate_sentiment("테스트", "테스트")
        assert isinstance(result, float)

    def test_score_rounded_to_two_decimal(self):
        """점수가 소수점 2자리로 반올림"""
        from analysis.sentiment import calculate_sentiment

        score = calculate_sentiment("급등 호재", "상승 전망")
        assert score == round(score, 2)


# ── 뉴스 레코드 감성 분석 테스트 ──


class TestAnalyzeNewsSentiment:
    """뉴스 레코드 리스트에 감성 점수 추가"""

    def test_adds_sentiment_field(self):
        """각 뉴스 레코드에 sentiment 필드 추가"""
        from analysis.sentiment import analyze_news_sentiment

        records = [
            {"title": "삼성전자 실적 호조", "summary": "매출 증가"},
            {"title": "코스피 하락", "summary": "경기 침체 우려"},
        ]
        result = analyze_news_sentiment(records)
        for r in result:
            assert "sentiment" in r
            assert isinstance(r["sentiment"], float)
            assert -1.0 <= r["sentiment"] <= 1.0

    def test_positive_news_gets_positive_score(self):
        """긍정 뉴스에 양수 점수 부여"""
        from analysis.sentiment import analyze_news_sentiment

        records = [
            {
                "title": "삼성전자 실적 급증, 사상 최대 매출",
                "summary": "영업이익 상승 호조",
            }
        ]
        result = analyze_news_sentiment(records)
        assert result[0]["sentiment"] > 0

    def test_preserves_existing_fields(self):
        """기존 필드를 보존하면서 sentiment 추가"""
        from analysis.sentiment import analyze_news_sentiment

        records = [
            {
                "title": "테스트 뉴스",
                "summary": "",
                "source": "Test",
                "url": "https://example.com",
                "relevance_score": 0.8,
                "tickers": ["TSLA"],
                "category": "stock",
            }
        ]
        result = analyze_news_sentiment(records)
        assert result[0]["source"] == "Test"
        assert result[0]["url"] == "https://example.com"
        assert result[0]["tickers"] == ["TSLA"]

    def test_empty_list(self):
        """빈 리스트 입력 시 빈 리스트 반환"""
        from analysis.sentiment import analyze_news_sentiment

        assert analyze_news_sentiment([]) == []

    def test_error_record_skipped(self):
        """error 필드가 있는 레코드는 sentiment=0.0"""
        from analysis.sentiment import analyze_news_sentiment

        records = [{"title": "", "summary": "", "error": "수집 실패"}]
        result = analyze_news_sentiment(records)
        assert result[0]["sentiment"] == 0.0


# ── DB 저장 테스트 ──


class TestSentimentDB:
    """감성 점수 DB 저장 검증"""

    def test_save_sentiment_to_db(self, db_conn):
        """sentiment 값이 news 테이블에 저장됨"""
        from analysis.sentiment import save_sentiment_to_db

        # 먼저 뉴스 레코드 삽입
        db_conn.execute(
            "INSERT INTO news (title, summary, source, url, published_at, relevance_score, tickers, category) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "삼성전자 호재",
                "매출 급증",
                "RSS",
                "https://example.com/1",
                "2026-03-25",
                0.9,
                '["005930.KS"]',
                "stock",
            ),
        )
        db_conn.commit()

        # sentiment 저장
        updates = [{"title": "삼성전자 호재", "source": "RSS", "sentiment": 0.65}]
        save_sentiment_to_db(db_conn, updates)

        row = db_conn.execute(
            "SELECT sentiment FROM news WHERE title=?", ("삼성전자 호재",)
        ).fetchone()
        assert row["sentiment"] == 0.65

    def test_update_multiple_records(self, db_conn):
        """여러 레코드의 sentiment를 일괄 업데이트"""
        from analysis.sentiment import save_sentiment_to_db

        db_conn.execute(
            "INSERT INTO news (title, summary, source, url, published_at, relevance_score, tickers, category) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("뉴스1", "", "RSS", "http://a.com", "2026-03-25", 0.5, "[]", "stock"),
        )
        db_conn.execute(
            "INSERT INTO news (title, summary, source, url, published_at, relevance_score, tickers, category) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("뉴스2", "", "Brave", "http://b.com", "2026-03-25", 0.5, "[]", "macro"),
        )
        db_conn.commit()

        updates = [
            {"title": "뉴스1", "source": "RSS", "sentiment": 0.3},
            {"title": "뉴스2", "source": "Brave", "sentiment": -0.5},
        ]
        save_sentiment_to_db(db_conn, updates)

        rows = db_conn.execute(
            "SELECT title, sentiment FROM news ORDER BY title"
        ).fetchall()
        assert rows[0]["sentiment"] == 0.3
        assert rows[1]["sentiment"] == -0.5

    def test_no_records_no_error(self, db_conn):
        """빈 업데이트 리스트에도 에러 없음"""
        from analysis.sentiment import save_sentiment_to_db

        save_sentiment_to_db(db_conn, [])  # 에러 없이 통과


# ── 종목별 감성 집계 테스트 ──


class TestTickerSentimentAggregate:
    """종목별 평균 감성 점수 집계"""

    def test_aggregate_by_ticker(self):
        """종목별 평균 감성 점수 계산"""
        from analysis.sentiment import aggregate_sentiment_by_ticker

        records = [
            {"title": "뉴스1", "tickers": ["005930.KS"], "sentiment": 0.6},
            {"title": "뉴스2", "tickers": ["005930.KS"], "sentiment": 0.4},
            {"title": "뉴스3", "tickers": ["TSLA"], "sentiment": -0.3},
        ]
        result = aggregate_sentiment_by_ticker(records)
        assert "005930.KS" in result
        assert result["005930.KS"]["avg_sentiment"] == 0.5
        assert result["005930.KS"]["count"] == 2
        assert result["TSLA"]["avg_sentiment"] == -0.3
        assert result["TSLA"]["count"] == 1

    def test_empty_tickers_excluded(self):
        """tickers가 빈 레코드는 종목별 집계에서 제외"""
        from analysis.sentiment import aggregate_sentiment_by_ticker

        records = [
            {"title": "매크로 뉴스", "tickers": [], "sentiment": 0.5},
        ]
        result = aggregate_sentiment_by_ticker(records)
        assert len(result) == 0

    def test_multi_ticker_news(self):
        """여러 종목에 관련된 뉴스는 각 종목에 반영"""
        from analysis.sentiment import aggregate_sentiment_by_ticker

        records = [
            {
                "title": "반도체 호황",
                "tickers": ["005930.KS", "TSLA"],
                "sentiment": 0.8,
            },
        ]
        result = aggregate_sentiment_by_ticker(records)
        assert result["005930.KS"]["avg_sentiment"] == 0.8
        assert result["TSLA"]["avg_sentiment"] == 0.8

    def test_empty_records(self):
        """빈 레코드 리스트"""
        from analysis.sentiment import aggregate_sentiment_by_ticker

        assert aggregate_sentiment_by_ticker([]) == {}

    def test_avg_rounded_to_two_decimal(self):
        """평균 점수가 소수점 2자리로 반올림"""
        from analysis.sentiment import aggregate_sentiment_by_ticker

        records = [
            {"title": "뉴스1", "tickers": ["TSLA"], "sentiment": 0.33},
            {"title": "뉴스2", "tickers": ["TSLA"], "sentiment": 0.33},
            {"title": "뉴스3", "tickers": ["TSLA"], "sentiment": 0.34},
        ]
        result = aggregate_sentiment_by_ticker(records)
        score = result["TSLA"]["avg_sentiment"]
        assert score == round(score, 2)


# ── news.json 출력 검증 ──


class TestSentimentInNewsJson:
    """news.json에 sentiment 필드 포함 검증"""

    def test_sentiment_field_in_news_json(self, tmp_output_dir):
        """news.json의 각 뉴스 항목에 sentiment 필드 존재"""
        from analysis.sentiment import analyze_news_sentiment

        records = [
            {
                "title": "삼성전자 실적 호조",
                "summary": "매출 급증",
                "source": "RSS",
                "url": "https://example.com",
                "published_at": "2026-03-25",
                "relevance_score": 0.9,
                "tickers": ["005930.KS"],
                "category": "stock",
                "fetch_method": "rss",
                "timestamp": "2026-03-25T15:00:00+09:00",
            },
        ]
        result = analyze_news_sentiment(records)

        # JSON 파일 저장 시뮬레이션
        output = {
            "updated_at": "2026-03-25T15:00:00+09:00",
            "count": len(result),
            "news": result,
        }
        output_path = tmp_output_dir / "news.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        # 검증
        with open(output_path, encoding="utf-8") as f:
            loaded = json.load(f)

        for item in loaded["news"]:
            assert "sentiment" in item
            assert isinstance(item["sentiment"], float)

    def test_ticker_sentiment_aggregation_in_output(self):
        """종목별 감성 집계 결과 구조 검증"""
        from analysis.sentiment import aggregate_sentiment_by_ticker

        records = [
            {"title": "호재", "tickers": ["005930.KS"], "sentiment": 0.7},
            {"title": "악재", "tickers": ["005930.KS"], "sentiment": -0.2},
        ]
        agg = aggregate_sentiment_by_ticker(records)

        # 구조 검증
        assert "005930.KS" in agg
        ticker_data = agg["005930.KS"]
        assert "avg_sentiment" in ticker_data
        assert "count" in ticker_data
        assert isinstance(ticker_data["avg_sentiment"], float)
        assert isinstance(ticker_data["count"], int)

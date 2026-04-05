"""F25 — 성과 추적 + 가중치 학습 테스트

outcome_1w/outcome_1m 자동 기록, 월간 성적표 생성, 팩터별 적중률
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.init_db import init_schema

KST = timezone(timedelta(hours=9))


@pytest.fixture
def perf_db():
    """성과 추적 테스트용 인메모리 DB"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def _insert_opportunity(
    conn,
    ticker,
    name,
    discovered_at,
    price_at_discovery,
    composite_score=0.7,
    status="discovered",
    score_value=0.6,
    score_quality=0.7,
    score_growth=0.5,
    score_return=0.8,
    score_rsi=0.4,
    score_sentiment=0.6,
    score_macro=0.5,
    outcome_1w=None,
    outcome_1m=None,
):
    """테스트용 opportunity 삽입 헬퍼"""
    conn.execute(
        """
        INSERT INTO opportunities
        (ticker, name, discovered_at, discovered_via, source,
         composite_score, score_value, score_quality, score_growth,
         score_return, score_rsi, score_sentiment, score_macro,
         price_at_discovery, outcome_1w, outcome_1m, status)
        VALUES (?, ?, ?, 'test', 'test',
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?)
    """,
        (
            ticker,
            name,
            discovered_at,
            composite_score,
            score_value,
            score_quality,
            score_growth,
            score_return,
            score_rsi,
            score_sentiment,
            score_macro,
            price_at_discovery,
            outcome_1w,
            outcome_1m,
            status,
        ),
    )
    conn.commit()


def _insert_price_daily(conn, ticker, date_str, close_price):
    """테스트용 일봉 데이터 삽입"""
    conn.execute(
        """
        INSERT INTO prices_daily (ticker, date, open, high, low, close, volume, change_pct)
        VALUES (?, ?, ?, ?, ?, ?, 1000, 0.0)
    """,
        (ticker, date_str, close_price, close_price, close_price, close_price),
    )
    conn.commit()


# ── outcome 기록 테스트 ──


class TestUpdateOutcomes:
    """outcome_1w/outcome_1m 자동 기록 함수 테스트"""

    def test_update_outcome_1w(self, perf_db):
        """발굴 후 7일 경과 → outcome_1w 기록"""
        from analysis.performance import update_outcomes

        now = datetime.now(KST)
        discovered = (now - timedelta(days=8)).strftime("%Y-%m-%d")

        _insert_opportunity(perf_db, "005930.KS", "삼성전자", discovered, 70000)
        # 발굴일+7 가격 데이터
        week_later = (
            datetime.strptime(discovered, "%Y-%m-%d") + timedelta(days=7)
        ).strftime("%Y-%m-%d")
        _insert_price_daily(perf_db, "005930.KS", week_later, 73500)  # +5%

        result = update_outcomes(conn=perf_db)

        row = perf_db.execute(
            "SELECT outcome_1w FROM opportunities WHERE ticker='005930.KS'"
        ).fetchone()
        assert row["outcome_1w"] is not None
        assert abs(row["outcome_1w"] - 5.0) < 0.1
        assert result["updated_1w"] >= 1

    def test_update_outcome_1m(self, perf_db):
        """발굴 후 30일 경과 → outcome_1m 기록"""
        from analysis.performance import update_outcomes

        now = datetime.now(KST)
        discovered = (now - timedelta(days=32)).strftime("%Y-%m-%d")

        _insert_opportunity(perf_db, "TSLA", "테슬라", discovered, 200.0)
        month_later = (
            datetime.strptime(discovered, "%Y-%m-%d") + timedelta(days=30)
        ).strftime("%Y-%m-%d")
        _insert_price_daily(perf_db, "TSLA", month_later, 220.0)  # +10%

        result = update_outcomes(conn=perf_db)

        row = perf_db.execute(
            "SELECT outcome_1m FROM opportunities WHERE ticker='TSLA'"
        ).fetchone()
        assert row["outcome_1m"] is not None
        assert abs(row["outcome_1m"] - 10.0) < 0.1
        assert result["updated_1m"] >= 1

    def test_skip_already_recorded(self, perf_db):
        """이미 outcome이 기록된 종목은 스킵"""
        from analysis.performance import update_outcomes

        now = datetime.now(KST)
        discovered = (now - timedelta(days=10)).strftime("%Y-%m-%d")

        _insert_opportunity(
            perf_db, "005930.KS", "삼성전자", discovered, 70000, outcome_1w=3.5
        )

        result = update_outcomes(conn=perf_db)
        assert result["updated_1w"] == 0

    def test_skip_not_enough_days(self, perf_db):
        """발굴 후 7일 미경과 → 스킵"""
        from analysis.performance import update_outcomes

        now = datetime.now(KST)
        discovered = (now - timedelta(days=3)).strftime("%Y-%m-%d")

        _insert_opportunity(perf_db, "005930.KS", "삼성전자", discovered, 70000)

        result = update_outcomes(conn=perf_db)
        assert result["updated_1w"] == 0
        assert result["updated_1m"] == 0

    def test_no_price_data_graceful(self, perf_db):
        """가격 데이터 없으면 graceful 스킵 (에러 아님)"""
        from analysis.performance import update_outcomes

        now = datetime.now(KST)
        discovered = (now - timedelta(days=10)).strftime("%Y-%m-%d")

        _insert_opportunity(perf_db, "005930.KS", "삼성전자", discovered, 70000)
        # 가격 데이터 없음

        result = update_outcomes(conn=perf_db)
        assert result["updated_1w"] == 0

        row = perf_db.execute(
            "SELECT outcome_1w FROM opportunities WHERE ticker='005930.KS'"
        ).fetchone()
        assert row["outcome_1w"] is None

    def test_empty_opportunities(self, perf_db):
        """opportunities 테이블 비어있을 때"""
        from analysis.performance import update_outcomes

        result = update_outcomes(conn=perf_db)
        assert result["updated_1w"] == 0
        assert result["updated_1m"] == 0

    def test_negative_outcome(self, perf_db):
        """음수 수익률도 정상 기록"""
        from analysis.performance import update_outcomes

        now = datetime.now(KST)
        discovered = (now - timedelta(days=8)).strftime("%Y-%m-%d")

        _insert_opportunity(perf_db, "005930.KS", "삼성전자", discovered, 70000)
        week_later = (
            datetime.strptime(discovered, "%Y-%m-%d") + timedelta(days=7)
        ).strftime("%Y-%m-%d")
        _insert_price_daily(perf_db, "005930.KS", week_later, 63000)  # -10%

        update_outcomes(conn=perf_db)

        row = perf_db.execute(
            "SELECT outcome_1w FROM opportunities WHERE ticker='005930.KS'"
        ).fetchone()
        assert row["outcome_1w"] is not None
        assert row["outcome_1w"] < 0


# ── 월간 성적표 테스트 ──


class TestMonthlyReport:
    """월간 성적표 생성 함수 테스트"""

    def test_basic_report(self, perf_db):
        """기본 성적표 생성"""
        from analysis.performance import generate_monthly_report

        now = datetime.now(KST)
        base = (now - timedelta(days=15)).strftime("%Y-%m-%d")

        # 적중 (양수 수익)
        _insert_opportunity(
            perf_db,
            "005930.KS",
            "삼성전자",
            base,
            70000,
            outcome_1w=5.0,
            outcome_1m=10.0,
            composite_score=0.8,
            score_value=0.9,
        )
        # 실패 (음수 수익)
        _insert_opportunity(
            perf_db,
            "TSLA",
            "테슬라",
            base,
            200.0,
            outcome_1w=-3.0,
            outcome_1m=-5.0,
            composite_score=0.6,
            score_value=0.3,
        )

        report = generate_monthly_report(conn=perf_db)

        assert "period" in report
        assert "total_picks" in report
        assert report["total_picks"] == 2
        assert "hit_rate_1w" in report
        assert report["hit_rate_1w"] == 50.0
        assert "avg_return_1w" in report
        assert "avg_return_1m" in report
        assert "factor_analysis" in report

    def test_hit_rate_calculation(self, perf_db):
        """적중률 = 양수 수익 / 전체"""
        from analysis.performance import generate_monthly_report

        base = (datetime.now(KST) - timedelta(days=10)).strftime("%Y-%m-%d")

        # 3개 적중, 1개 실패
        for i, ret in enumerate([5.0, 3.0, 8.0, -2.0]):
            _insert_opportunity(
                perf_db,
                f"T{i}.KS",
                f"종목{i}",
                base,
                10000,
                outcome_1w=ret,
                composite_score=0.5 + i * 0.1,
            )

        report = generate_monthly_report(conn=perf_db)
        assert report["hit_rate_1w"] == 75.0

    def test_average_return(self, perf_db):
        """평균 수익률 계산"""
        from analysis.performance import generate_monthly_report

        base = (datetime.now(KST) - timedelta(days=10)).strftime("%Y-%m-%d")

        _insert_opportunity(
            perf_db, "A.KS", "A", base, 10000, outcome_1w=10.0, outcome_1m=20.0
        )
        _insert_opportunity(
            perf_db, "B.KS", "B", base, 10000, outcome_1w=-4.0, outcome_1m=-10.0
        )

        report = generate_monthly_report(conn=perf_db)
        assert abs(report["avg_return_1w"] - 3.0) < 0.1  # (10-4)/2
        assert abs(report["avg_return_1m"] - 5.0) < 0.1  # (20-10)/2

    def test_factor_analysis(self, perf_db):
        """팩터별 적중률/기여도 분석"""
        from analysis.performance import generate_monthly_report

        base = (datetime.now(KST) - timedelta(days=10)).strftime("%Y-%m-%d")

        # 높은 value score + 적중
        _insert_opportunity(
            perf_db,
            "A.KS",
            "A",
            base,
            10000,
            outcome_1w=10.0,
            score_value=0.9,
            score_quality=0.8,
            score_growth=0.7,
        )
        # 낮은 value score + 실패
        _insert_opportunity(
            perf_db,
            "B.KS",
            "B",
            base,
            10000,
            outcome_1w=-5.0,
            score_value=0.2,
            score_quality=0.3,
            score_growth=0.4,
        )

        report = generate_monthly_report(conn=perf_db)
        fa = report["factor_analysis"]

        assert "value" in fa
        assert "quality" in fa
        assert "growth" in fa
        assert "timing" in fa
        assert "catalyst" in fa
        assert "macro" in fa

        # 각 팩터에 avg_score_hit, avg_score_miss 포함
        assert "avg_score_hit" in fa["value"]
        assert "avg_score_miss" in fa["value"]

    def test_empty_data(self, perf_db):
        """데이터 없을 때 빈 성적표"""
        from analysis.performance import generate_monthly_report

        report = generate_monthly_report(conn=perf_db)
        assert report["total_picks"] == 0
        assert report["hit_rate_1w"] == 0.0
        assert report["hit_rate_1m"] == 0.0

    def test_partial_outcomes(self, perf_db):
        """outcome_1w만 있고 outcome_1m 없는 경우"""
        from analysis.performance import generate_monthly_report

        base = (datetime.now(KST) - timedelta(days=10)).strftime("%Y-%m-%d")

        _insert_opportunity(
            perf_db, "A.KS", "A", base, 10000, outcome_1w=5.0, outcome_1m=None
        )

        report = generate_monthly_report(conn=perf_db)
        assert report["total_picks"] == 1
        assert report["hit_rate_1w"] == 100.0
        assert report["avg_return_1m"] == 0.0  # 데이터 없음

    def test_top_bottom_picks(self, perf_db):
        """최고/최저 성과 종목"""
        from analysis.performance import generate_monthly_report

        base = (datetime.now(KST) - timedelta(days=10)).strftime("%Y-%m-%d")

        _insert_opportunity(
            perf_db, "A.KS", "A", base, 10000, outcome_1w=15.0, outcome_1m=25.0
        )
        _insert_opportunity(
            perf_db, "B.KS", "B", base, 10000, outcome_1w=3.0, outcome_1m=5.0
        )
        _insert_opportunity(
            perf_db, "C.KS", "C", base, 10000, outcome_1w=-8.0, outcome_1m=-12.0
        )

        report = generate_monthly_report(conn=perf_db)
        assert len(report["top_picks"]) > 0
        assert report["top_picks"][0]["ticker"] == "A.KS"
        assert len(report["bottom_picks"]) > 0
        assert report["bottom_picks"][0]["ticker"] == "C.KS"


# ── weight_suggestion 테스트 ──


class TestWeightSuggestion:
    """마커스용 가중치 조정 제안"""

    def test_weight_suggestion_with_data(self, perf_db):
        """팩터 분석 기반 가중치 제안"""
        from analysis.performance import generate_weight_suggestion

        base = (datetime.now(KST) - timedelta(days=10)).strftime("%Y-%m-%d")

        _insert_opportunity(
            perf_db,
            "A.KS",
            "A",
            base,
            10000,
            outcome_1w=10.0,
            score_value=0.9,
            score_quality=0.8,
            score_growth=0.7,
            score_return=0.6,
            score_rsi=0.5,
            score_sentiment=0.4,
            score_macro=0.3,
        )
        _insert_opportunity(
            perf_db,
            "B.KS",
            "B",
            base,
            10000,
            outcome_1w=-5.0,
            score_value=0.2,
            score_quality=0.3,
            score_growth=0.8,
            score_return=0.7,
            score_rsi=0.6,
            score_sentiment=0.5,
            score_macro=0.4,
        )

        suggestion = generate_weight_suggestion(conn=perf_db)

        assert "current_weights" in suggestion
        assert "suggested_weights" in suggestion
        assert "reasoning" in suggestion
        # 가중치 합 = 1.0
        total = sum(suggestion["suggested_weights"].values())
        assert abs(total - 1.0) < 0.01

    def test_weight_suggestion_empty(self, perf_db):
        """데이터 없으면 현재 가중치 유지"""
        from analysis.performance import generate_weight_suggestion

        suggestion = generate_weight_suggestion(conn=perf_db)
        assert suggestion["suggested_weights"] == suggestion["current_weights"]


# ── JSON 출력 테스트 ──


class TestPerformanceJson:
    """performance_report.json 출력 테스트"""

    def test_save_report_json(self, perf_db, tmp_path):
        """JSON 파일 저장"""
        from analysis.performance import save_performance_report

        base = (datetime.now(KST) - timedelta(days=10)).strftime("%Y-%m-%d")
        _insert_opportunity(
            perf_db, "A.KS", "A", base, 10000, outcome_1w=5.0, outcome_1m=10.0
        )

        save_performance_report(conn=perf_db, output_dir=tmp_path)

        filepath = tmp_path / "performance_report.json"
        assert filepath.exists()

        data = json.loads(filepath.read_text(encoding="utf-8"))
        assert "updated_at" in data
        assert "monthly_report" in data
        assert "weight_suggestion" in data
        assert "outcome_summary" in data

    def test_report_schema(self, perf_db, tmp_path):
        """JSON 스키마 필수 필드 검증"""
        from analysis.performance import save_performance_report

        save_performance_report(conn=perf_db, output_dir=tmp_path)

        filepath = tmp_path / "performance_report.json"
        data = json.loads(filepath.read_text(encoding="utf-8"))

        # 최상위 필수 필드
        assert isinstance(data["updated_at"], str)
        assert isinstance(data["monthly_report"], dict)
        assert isinstance(data["weight_suggestion"], dict)
        assert isinstance(data["outcome_summary"], dict)


# ── run() 함수 테스트 ──


class TestRun:
    """파이프라인 통합 run() 함수 테스트"""

    def test_run_returns_result(self, perf_db, tmp_path):
        """run() 함수가 결과 반환"""
        from analysis.performance import run

        result = run(conn=perf_db, output_dir=tmp_path)
        assert "outcomes" in result
        assert "report_saved" in result

    def test_run_creates_json(self, perf_db, tmp_path):
        """run() 실행 후 JSON 파일 생성"""
        from analysis.performance import run

        run(conn=perf_db, output_dir=tmp_path)
        assert (tmp_path / "performance_report.json").exists()

    def test_run_graceful_on_error(self, perf_db, tmp_path):
        """DB 에러 시 graceful 처리"""
        from analysis.performance import run

        # 닫힌 연결로 테스트
        perf_db.close()
        result = run(conn=perf_db, output_dir=tmp_path)
        # 에러 발생해도 크래시 안 함
        assert result is not None

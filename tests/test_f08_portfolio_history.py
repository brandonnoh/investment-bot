#!/usr/bin/env python3
"""
F08 테스트 — portfolio_history 일별 자산 스냅샷
스냅샷 저장/조회, 중복 방지(UPSERT), 30일 수익률 추이 검증
"""

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── 픽스처 ──


@pytest.fixture
def sample_holdings():
    """calculate_holdings 반환 형식의 샘플 보유 종목"""
    return [
        {
            "ticker": "005930.KS",
            "name": "삼성전자",
            "sector": "반도체",
            "currency": "KRW",
            "price": 82000,
            "avg_cost": 80000,
            "qty": 42,
            "current_value_krw": 3444000,
            "invested_krw": 3360000,
            "pnl_krw": 84000,
            "pnl_pct": 2.5,
            "pnl_label": None,
            "change_pct": 0.61,
        },
        {
            "ticker": "TSLA",
            "name": "테슬라",
            "sector": "전기차/AI",
            "currency": "USD",
            "price": 275.50,
            "avg_cost": 300.0,
            "qty": 1,
            "current_value_krw": 380190,
            "invested_krw": 414000,
            "pnl_krw": -33810,
            "pnl_pct": -8.17,
            "pnl_label": None,
            "change_pct": 2.04,
        },
    ]


@pytest.fixture
def sample_summary(sample_holdings):
    """build_summary 반환 형식의 샘플 요약"""
    return {
        "updated_at": "2026-03-25T15:30:00+09:00",
        "exchange_rate": 1380.0,
        "total": {
            "invested_krw": 3774000,
            "current_value_krw": 3824190,
            "pnl_krw": 50190,
            "pnl_pct": 1.33,
        },
        "holdings": sample_holdings,
        "sectors": [],
        "risk": {},
    }


# ── save_snapshot 테스트 ──


class TestSaveSnapshot:
    """portfolio_history 테이블에 스냅샷 저장"""

    def test_save_snapshot_inserts_row(self, db_conn, sample_summary):
        """스냅샷 저장 시 portfolio_history에 1행 삽입"""
        from analysis.portfolio import save_snapshot

        save_snapshot(db_conn, sample_summary, "2026-03-25")

        cursor = db_conn.cursor()
        cursor.execute("SELECT * FROM portfolio_history WHERE date = '2026-03-25'")
        row = cursor.fetchone()
        assert row is not None
        assert row["total_value_krw"] == 3824190
        assert row["total_invested_krw"] == 3774000
        assert row["total_pnl_krw"] == 50190
        assert abs(row["total_pnl_pct"] - 1.33) < 0.01
        assert row["fx_rate"] == 1380.0

    def test_save_snapshot_holdings_json(self, db_conn, sample_summary):
        """holdings_snapshot에 종목별 상세 JSON 저장"""
        from analysis.portfolio import save_snapshot

        save_snapshot(db_conn, sample_summary, "2026-03-25")

        cursor = db_conn.cursor()
        cursor.execute(
            "SELECT holdings_snapshot FROM portfolio_history WHERE date = '2026-03-25'"
        )
        row = cursor.fetchone()
        snapshot = json.loads(row["holdings_snapshot"])
        assert isinstance(snapshot, list)
        assert len(snapshot) == 2
        tickers = [h["ticker"] for h in snapshot]
        assert "005930.KS" in tickers
        assert "TSLA" in tickers

    def test_save_snapshot_upsert(self, db_conn, sample_summary):
        """같은 날짜 중복 저장 시 UPSERT (덮어쓰기)"""
        from analysis.portfolio import save_snapshot

        save_snapshot(db_conn, sample_summary, "2026-03-25")

        # 값 변경 후 같은 날짜로 다시 저장
        sample_summary["total"]["pnl_krw"] = 99999
        save_snapshot(db_conn, sample_summary, "2026-03-25")

        cursor = db_conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM portfolio_history WHERE date = '2026-03-25'"
        )
        assert cursor.fetchone()["cnt"] == 1

        cursor.execute(
            "SELECT total_pnl_krw FROM portfolio_history WHERE date = '2026-03-25'"
        )
        assert cursor.fetchone()["total_pnl_krw"] == 99999

    def test_save_snapshot_multiple_dates(self, db_conn, sample_summary):
        """여러 날짜 스냅샷 저장"""
        from analysis.portfolio import save_snapshot

        save_snapshot(db_conn, sample_summary, "2026-03-23")
        save_snapshot(db_conn, sample_summary, "2026-03-24")
        save_snapshot(db_conn, sample_summary, "2026-03-25")

        cursor = db_conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM portfolio_history")
        assert cursor.fetchone()["cnt"] == 3


# ── load_history 테스트 ──


class TestLoadHistory:
    """portfolio_history에서 최근 N일 이력 조회"""

    def _insert_history(self, db_conn, days=30):
        """테스트용 이력 데이터 삽입"""
        cursor = db_conn.cursor()
        base_value = 10000000  # 1000만원
        for i in range(days):
            date = f"2026-03-{(i + 1):02d}" if i < 28 else f"2026-04-{(i - 27):02d}"
            # 약간의 변동 시뮬레이션
            value = base_value + (i * 50000)
            pnl = value - base_value
            pnl_pct = round(pnl / base_value * 100, 2) if base_value > 0 else 0
            cursor.execute(
                """
                INSERT OR REPLACE INTO portfolio_history
                (date, total_value_krw, total_invested_krw, total_pnl_krw, total_pnl_pct,
                 fx_rate, fx_pnl_krw, holdings_snapshot)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (date, value, base_value, pnl, pnl_pct, 1380.0, 0, "[]"),
            )
        db_conn.commit()

    def test_load_history_returns_list(self, db_conn):
        """이력 조회 결과는 리스트"""
        from analysis.portfolio import load_history

        self._insert_history(db_conn, 10)
        history = load_history(db_conn, days=30)
        assert isinstance(history, list)
        assert len(history) == 10

    def test_load_history_sorted_by_date(self, db_conn):
        """이력은 날짜 오름차순 정렬"""
        from analysis.portfolio import load_history

        self._insert_history(db_conn, 10)
        history = load_history(db_conn, days=30)
        dates = [h["date"] for h in history]
        assert dates == sorted(dates)

    def test_load_history_fields(self, db_conn):
        """이력 각 행에 필수 필드 포함"""
        from analysis.portfolio import load_history

        self._insert_history(db_conn, 5)
        history = load_history(db_conn, days=30)
        required_fields = [
            "date",
            "total_value_krw",
            "total_invested_krw",
            "total_pnl_krw",
            "total_pnl_pct",
            "fx_rate",
        ]
        for row in history:
            for field in required_fields:
                assert field in row, f"필드 누락: {field}"

    def test_load_history_limit_days(self, db_conn):
        """days 파라미터로 조회 범위 제한"""
        from analysis.portfolio import load_history

        self._insert_history(db_conn, 30)
        history = load_history(db_conn, days=5)
        assert len(history) <= 5

    def test_load_history_empty(self, db_conn):
        """이력 없으면 빈 리스트"""
        from analysis.portfolio import load_history

        history = load_history(db_conn, days=30)
        assert history == []


# ── portfolio_summary.json에 history 포함 테스트 ──


class TestSummaryWithHistory:
    """portfolio_summary.json에 최근 30일 수익률 추이 포함"""

    def test_build_summary_includes_history(self, sample_holdings):
        """build_summary 결과에 history 필드 포함"""
        from analysis.portfolio import build_summary

        history = [
            {
                "date": "2026-03-24",
                "total_value_krw": 3800000,
                "total_invested_krw": 3774000,
                "total_pnl_krw": 26000,
                "total_pnl_pct": 0.69,
                "fx_rate": 1375.0,
            },
            {
                "date": "2026-03-25",
                "total_value_krw": 3824190,
                "total_invested_krw": 3774000,
                "total_pnl_krw": 50190,
                "total_pnl_pct": 1.33,
                "fx_rate": 1380.0,
            },
        ]

        summary = build_summary(sample_holdings, [], {}, 1380.0, history=history)
        assert "history" in summary
        assert len(summary["history"]) == 2
        assert summary["history"][0]["date"] == "2026-03-24"
        assert summary["history"][1]["date"] == "2026-03-25"

    def test_build_summary_history_default_empty(self, sample_holdings):
        """history 파라미터 없으면 빈 리스트"""
        from analysis.portfolio import build_summary

        summary = build_summary(sample_holdings, [], {}, 1380.0)
        assert summary.get("history") == []


# ── run() 통합 테스트 ──


class TestRunIntegration:
    """run() 호출 시 스냅샷 저장 + history 포함 통합 검증"""

    def test_run_saves_snapshot_to_db(self, tmp_path):
        """run() 실행 시 portfolio_history에 스냅샷 저장"""
        from analysis import portfolio
        from db.init_db import init_schema

        # 파일 기반 DB 생성
        db_path = tmp_path / "test.db"
        file_conn = sqlite3.connect(str(db_path))
        file_conn.row_factory = sqlite3.Row
        init_schema(file_conn)
        file_conn.close()

        # prices.json / macro.json 준비
        intel_dir = tmp_path / "output" / "intel"
        intel_dir.mkdir(parents=True)

        prices_data = {
            "prices": [
                {
                    "name": "삼성전자",
                    "ticker": "005930.KS",
                    "price": 82000,
                    "prev_close": 81500,
                    "change_pct": 0.61,
                    "volume": 15000000,
                    "market": "KR",
                    "currency": "KRW",
                    "avg_cost": 80000,
                    "qty": 42,
                    "timestamp": "2026-03-25T15:30:00+09:00",
                }
            ],
            "updated_at": "2026-03-25T15:30:00+09:00",
        }
        macro_data = {
            "indicators": [
                {
                    "name": "원/달러",
                    "indicator": "원/달러",
                    "value": 1380.0,
                    "change_pct": 0.1,
                },
            ],
            "updated_at": "2026-03-25T15:30:00+09:00",
        }

        with open(intel_dir / "prices.json", "w") as f:
            json.dump(prices_data, f)
        with open(intel_dir / "macro.json", "w") as f:
            json.dump(macro_data, f)

        # OUTPUT_DIR, DB_PATH 패치 (실제 파일 DB 사용)
        with (
            patch.object(portfolio, "OUTPUT_DIR", intel_dir),
            patch.object(portfolio, "DB_PATH", db_path),
        ):
            result = portfolio.run()

        assert result is not None

        # DB에 스냅샷 저장 확인
        verify_conn = sqlite3.connect(str(db_path))
        verify_conn.row_factory = sqlite3.Row
        cursor = verify_conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM portfolio_history")
        assert cursor.fetchone()["cnt"] == 1
        verify_conn.close()

    def test_run_output_includes_history(self, tmp_path, db_conn):
        """run() 출력 JSON에 history 필드 포함"""
        from analysis import portfolio

        intel_dir = tmp_path / "output" / "intel"
        intel_dir.mkdir(parents=True)

        prices_data = {
            "prices": [
                {
                    "name": "삼성전자",
                    "ticker": "005930.KS",
                    "price": 82000,
                    "prev_close": 81500,
                    "change_pct": 0.61,
                    "volume": 15000000,
                    "market": "KR",
                    "currency": "KRW",
                    "avg_cost": 80000,
                    "qty": 42,
                    "timestamp": "2026-03-25T15:30:00+09:00",
                }
            ],
            "updated_at": "2026-03-25T15:30:00+09:00",
        }
        macro_data = {
            "indicators": [
                {
                    "name": "원/달러",
                    "indicator": "원/달러",
                    "value": 1380.0,
                    "change_pct": 0.1,
                },
            ],
        }

        with open(intel_dir / "prices.json", "w") as f:
            json.dump(prices_data, f)
        with open(intel_dir / "macro.json", "w") as f:
            json.dump(macro_data, f)

        with (
            patch.object(portfolio, "OUTPUT_DIR", intel_dir),
            patch.object(portfolio, "DB_PATH", tmp_path / "test.db"),
        ):
            with patch.object(portfolio, "_get_db_conn", return_value=db_conn):
                result = portfolio.run()

        assert "history" in result

        # 저장된 JSON 파일에도 history 포함
        with open(intel_dir / "portfolio_summary.json") as f:
            saved = json.load(f)
        assert "history" in saved

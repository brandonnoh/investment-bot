#!/usr/bin/env python3
"""
F03 — 일봉 자동 집계 모듈 테스트
prices/macro 원시 데이터 → OHLCV 일봉 집계 검증
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestAggregateImport:
    """모듈 import 테스트"""

    def test_import_aggregate(self):
        """db.aggregate 모듈 import 가능"""
        from db.aggregate import aggregate_daily

        assert callable(aggregate_daily)

    def test_import_run(self):
        """db.aggregate.run() 함수 존재"""
        from db.aggregate import run

        assert callable(run)


class TestAggregatePricesDaily:
    """prices 원시 → prices_daily OHLCV 집계"""

    def _insert_prices(self, conn, rows):
        """prices 테이블에 원시 데이터 삽입"""
        conn.executemany(
            "INSERT INTO prices (ticker, name, price, prev_close, change_pct, volume, timestamp, market, data_source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()

    def test_single_ticker_single_day(self, db_conn):
        """단일 종목 하루 데이터 → 일봉 1행"""
        from db.aggregate import aggregate_daily

        rows = [
            (
                "005930.KS",
                "삼성전자",
                81000,
                80000,
                1.25,
                10000000,
                "2026-03-25T09:00:00+09:00",
                "KR",
                "naver",
            ),
            (
                "005930.KS",
                "삼성전자",
                82000,
                80000,
                2.50,
                12000000,
                "2026-03-25T12:00:00+09:00",
                "KR",
                "naver",
            ),
            (
                "005930.KS",
                "삼성전자",
                81500,
                80000,
                1.88,
                15000000,
                "2026-03-25T15:30:00+09:00",
                "KR",
                "naver",
            ),
        ]
        self._insert_prices(db_conn, rows)
        aggregate_daily(db_conn)

        cursor = db_conn.execute(
            "SELECT * FROM prices_daily WHERE ticker='005930.KS' AND date='2026-03-25'"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["open"] == 81000  # 첫 번째 가격
        assert row["high"] == 82000  # 최고가
        assert row["low"] == 81000  # 최저가
        assert row["close"] == 81500  # 마지막 가격
        assert row["volume"] == 15000000  # 마지막 거래량 (누적)

    def test_multiple_tickers(self, db_conn):
        """복수 종목 → 각각 일봉 생성"""
        from db.aggregate import aggregate_daily

        rows = [
            (
                "005930.KS",
                "삼성전자",
                81000,
                80000,
                1.25,
                10000000,
                "2026-03-25T09:00:00+09:00",
                "KR",
                "naver",
            ),
            (
                "005930.KS",
                "삼성전자",
                82000,
                80000,
                2.50,
                15000000,
                "2026-03-25T15:30:00+09:00",
                "KR",
                "naver",
            ),
            (
                "TSLA",
                "테슬라",
                270.0,
                265.0,
                1.89,
                50000000,
                "2026-03-25T04:00:00+09:00",
                "US",
                "yahoo",
            ),
            (
                "TSLA",
                "테슬라",
                275.5,
                265.0,
                3.96,
                80000000,
                "2026-03-25T06:00:00+09:00",
                "US",
                "yahoo",
            ),
        ]
        self._insert_prices(db_conn, rows)
        aggregate_daily(db_conn)

        count = db_conn.execute("SELECT COUNT(*) FROM prices_daily").fetchone()[0]
        assert count == 2

    def test_multiple_days(self, db_conn):
        """여러 날짜 → 날짜별 분리 집계"""
        from db.aggregate import aggregate_daily

        rows = [
            (
                "005930.KS",
                "삼성전자",
                81000,
                80000,
                1.25,
                10000000,
                "2026-03-24T15:30:00+09:00",
                "KR",
                "naver",
            ),
            (
                "005930.KS",
                "삼성전자",
                82000,
                81000,
                1.23,
                12000000,
                "2026-03-25T15:30:00+09:00",
                "KR",
                "naver",
            ),
        ]
        self._insert_prices(db_conn, rows)
        aggregate_daily(db_conn)

        count = db_conn.execute(
            "SELECT COUNT(*) FROM prices_daily WHERE ticker='005930.KS'"
        ).fetchone()[0]
        assert count == 2

    def test_change_pct_from_prev_close(self, db_conn):
        """change_pct는 마지막 레코드의 change_pct 사용"""
        from db.aggregate import aggregate_daily

        rows = [
            (
                "005930.KS",
                "삼성전자",
                81000,
                80000,
                1.25,
                10000000,
                "2026-03-25T09:00:00+09:00",
                "KR",
                "naver",
            ),
            (
                "005930.KS",
                "삼성전자",
                82000,
                80000,
                2.50,
                15000000,
                "2026-03-25T15:30:00+09:00",
                "KR",
                "naver",
            ),
        ]
        self._insert_prices(db_conn, rows)
        aggregate_daily(db_conn)

        row = db_conn.execute(
            "SELECT change_pct FROM prices_daily WHERE ticker='005930.KS'"
        ).fetchone()
        assert row["change_pct"] == 2.50

    def test_data_source_preserved(self, db_conn):
        """data_source 필드 보존"""
        from db.aggregate import aggregate_daily

        rows = [
            (
                "005930.KS",
                "삼성전자",
                81000,
                80000,
                1.25,
                10000000,
                "2026-03-25T09:00:00+09:00",
                "KR",
                "kiwoom",
            ),
        ]
        self._insert_prices(db_conn, rows)
        aggregate_daily(db_conn)

        row = db_conn.execute(
            "SELECT data_source FROM prices_daily WHERE ticker='005930.KS'"
        ).fetchone()
        assert row["data_source"] == "kiwoom"

    def test_upsert_no_duplicate(self, db_conn):
        """중복 집계 방지 — 같은 날짜 재실행 시 UPDATE"""
        from db.aggregate import aggregate_daily

        rows = [
            (
                "005930.KS",
                "삼성전자",
                81000,
                80000,
                1.25,
                10000000,
                "2026-03-25T09:00:00+09:00",
                "KR",
                "naver",
            ),
        ]
        self._insert_prices(db_conn, rows)
        aggregate_daily(db_conn)

        # 추가 데이터 삽입 후 재집계
        db_conn.execute(
            "INSERT INTO prices (ticker, name, price, prev_close, change_pct, volume, timestamp, market, data_source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "005930.KS",
                "삼성전자",
                83000,
                80000,
                3.75,
                20000000,
                "2026-03-25T15:30:00+09:00",
                "KR",
                "naver",
            ),
        )
        db_conn.commit()
        aggregate_daily(db_conn)

        count = db_conn.execute(
            "SELECT COUNT(*) FROM prices_daily WHERE ticker='005930.KS' AND date='2026-03-25'"
        ).fetchone()[0]
        assert count == 1  # 중복 없이 1행

        row = db_conn.execute(
            "SELECT close FROM prices_daily WHERE ticker='005930.KS' AND date='2026-03-25'"
        ).fetchone()
        assert row["close"] == 83000  # 업데이트된 값


class TestAggregateMacroDaily:
    """macro 원시 → macro_daily OHLC 집계"""

    def _insert_macro(self, conn, rows):
        """macro 테이블에 원시 데이터 삽입"""
        conn.executemany(
            "INSERT INTO macro (indicator, value, change_pct, timestamp) VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.commit()

    def test_single_indicator_single_day(self, db_conn):
        """단일 지표 하루 데이터 → 일봉 1행"""
        from db.aggregate import aggregate_daily

        rows = [
            ("KOSPI", 2640.0, -0.20, "2026-03-25T09:00:00+09:00"),
            ("KOSPI", 2660.0, 0.56, "2026-03-25T12:00:00+09:00"),
            ("KOSPI", 2650.0, 0.18, "2026-03-25T15:30:00+09:00"),
        ]
        self._insert_macro(db_conn, rows)
        aggregate_daily(db_conn)

        row = db_conn.execute(
            "SELECT * FROM macro_daily WHERE indicator='KOSPI' AND date='2026-03-25'"
        ).fetchone()
        assert row is not None
        assert row["open"] == 2640.0
        assert row["high"] == 2660.0
        assert row["low"] == 2640.0
        assert row["close"] == 2650.0

    def test_multiple_indicators(self, db_conn):
        """복수 지표 → 각각 집계"""
        from db.aggregate import aggregate_daily

        rows = [
            ("KOSPI", 2650.0, 0.18, "2026-03-25T15:30:00+09:00"),
            ("KRW=X", 1380.0, 0.12, "2026-03-25T15:30:00+09:00"),
            ("^VIX", 18.5, -2.1, "2026-03-25T04:00:00+09:00"),
        ]
        self._insert_macro(db_conn, rows)
        aggregate_daily(db_conn)

        count = db_conn.execute("SELECT COUNT(*) FROM macro_daily").fetchone()[0]
        assert count == 3

    def test_macro_upsert(self, db_conn):
        """macro_daily 중복 집계 방지"""
        from db.aggregate import aggregate_daily

        rows = [
            ("KOSPI", 2650.0, 0.18, "2026-03-25T15:30:00+09:00"),
        ]
        self._insert_macro(db_conn, rows)
        aggregate_daily(db_conn)
        aggregate_daily(db_conn)  # 재실행

        count = db_conn.execute(
            "SELECT COUNT(*) FROM macro_daily WHERE indicator='KOSPI' AND date='2026-03-25'"
        ).fetchone()[0]
        assert count == 1

    def test_macro_change_pct(self, db_conn):
        """change_pct는 마지막 레코드 값 사용"""
        from db.aggregate import aggregate_daily

        rows = [
            ("KOSPI", 2640.0, -0.20, "2026-03-25T09:00:00+09:00"),
            ("KOSPI", 2650.0, 0.18, "2026-03-25T15:30:00+09:00"),
        ]
        self._insert_macro(db_conn, rows)
        aggregate_daily(db_conn)

        row = db_conn.execute(
            "SELECT change_pct FROM macro_daily WHERE indicator='KOSPI'"
        ).fetchone()
        assert row["change_pct"] == 0.18


class TestAggregateEdgeCases:
    """엣지 케이스"""

    def test_empty_tables(self, db_conn):
        """빈 테이블에서 실행 — 에러 없이 완료"""
        from db.aggregate import aggregate_daily

        aggregate_daily(db_conn)  # 예외 발생하지 않아야 함
        assert db_conn.execute("SELECT COUNT(*) FROM prices_daily").fetchone()[0] == 0
        assert db_conn.execute("SELECT COUNT(*) FROM macro_daily").fetchone()[0] == 0

    def test_single_data_point(self, db_conn):
        """데이터 포인트 1개 → OHLC 모두 동일"""
        from db.aggregate import aggregate_daily

        db_conn.execute(
            "INSERT INTO prices (ticker, name, price, prev_close, change_pct, volume, timestamp, market, data_source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "TSLA",
                "테슬라",
                275.5,
                270.0,
                2.04,
                80000000,
                "2026-03-25T04:00:00+09:00",
                "US",
                "yahoo",
            ),
        )
        db_conn.commit()
        aggregate_daily(db_conn)

        row = db_conn.execute(
            "SELECT * FROM prices_daily WHERE ticker='TSLA'"
        ).fetchone()
        assert row["open"] == 275.5
        assert row["high"] == 275.5
        assert row["low"] == 275.5
        assert row["close"] == 275.5

    def test_null_volume(self, db_conn):
        """volume이 NULL인 경우 처리"""
        from db.aggregate import aggregate_daily

        db_conn.execute(
            "INSERT INTO prices (ticker, name, price, prev_close, change_pct, volume, timestamp, market, data_source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "GOLD_KRW_G",
                "금 현물",
                225564,
                225000,
                0.25,
                None,
                "2026-03-25T15:30:00+09:00",
                "COMMODITY",
                "calculated",
            ),
        )
        db_conn.commit()
        aggregate_daily(db_conn)

        row = db_conn.execute(
            "SELECT * FROM prices_daily WHERE ticker='GOLD_KRW_G'"
        ).fetchone()
        assert row is not None
        assert row["volume"] is None


class TestAggregateSpecificDate:
    """특정 날짜만 집계"""

    def test_aggregate_specific_date(self, db_conn):
        """특정 날짜 지정 시 해당 날짜만 집계"""
        from db.aggregate import aggregate_daily

        db_conn.executemany(
            "INSERT INTO prices (ticker, name, price, prev_close, change_pct, volume, timestamp, market, data_source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "005930.KS",
                    "삼성전자",
                    81000,
                    80000,
                    1.25,
                    10000000,
                    "2026-03-24T15:30:00+09:00",
                    "KR",
                    "naver",
                ),
                (
                    "005930.KS",
                    "삼성전자",
                    82000,
                    81000,
                    1.23,
                    12000000,
                    "2026-03-25T15:30:00+09:00",
                    "KR",
                    "naver",
                ),
            ],
        )
        db_conn.commit()

        aggregate_daily(db_conn, target_date="2026-03-25")

        count = db_conn.execute("SELECT COUNT(*) FROM prices_daily").fetchone()[0]
        assert count == 1  # 25일만 집계

        row = db_conn.execute("SELECT * FROM prices_daily").fetchone()
        assert row["date"] == "2026-03-25"


class TestRunFunction:
    """run() 함수 통합 테스트"""

    def test_run_with_conn(self, db_conn):
        """run(conn=) 파라미터로 DB 연결 전달"""
        from db.aggregate import run

        db_conn.execute(
            "INSERT INTO prices (ticker, name, price, prev_close, change_pct, volume, timestamp, market, data_source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "005930.KS",
                "삼성전자",
                82000,
                80000,
                2.50,
                15000000,
                "2026-03-25T15:30:00+09:00",
                "KR",
                "naver",
            ),
        )
        db_conn.execute(
            "INSERT INTO macro (indicator, value, change_pct, timestamp) VALUES (?, ?, ?, ?)",
            ("KOSPI", 2650.0, 0.18, "2026-03-25T15:30:00+09:00"),
        )
        db_conn.commit()

        run(conn=db_conn)

        assert db_conn.execute("SELECT COUNT(*) FROM prices_daily").fetchone()[0] == 1
        assert db_conn.execute("SELECT COUNT(*) FROM macro_daily").fetchone()[0] == 1

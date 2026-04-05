#!/usr/bin/env python3
"""
F12 — alerts.py 레거시 정리 + 통합 테스트
알림 생성/중복 방지/삭제, 공통 로직 추출 검증
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── 공통 감지 로직 테스트 ──


class TestCheckStockAlerts:
    """종목 급등/급락 감지"""

    def test_stock_drop_detected(self):
        """급락 감지 — RED 알림 생성"""
        from analysis.alerts import check_stock_alerts

        prices = [
            {
                "ticker": "005930.KS",
                "name": "삼성전자",
                "price": 50000,
                "change_pct": -6.0,
            }
        ]
        alerts = check_stock_alerts(prices)
        assert len(alerts) == 1
        assert alerts[0]["level"] == "RED"
        assert alerts[0]["event_type"] == "stock_drop"
        assert alerts[0]["ticker"] == "005930.KS"

    def test_stock_surge_detected(self):
        """급등 감지 — GREEN 알림 생성"""
        from analysis.alerts import check_stock_alerts

        prices = [{"ticker": "TSLA", "name": "테슬라", "price": 300, "change_pct": 7.0}]
        alerts = check_stock_alerts(prices)
        assert len(alerts) == 1
        assert alerts[0]["level"] == "GREEN"
        assert alerts[0]["event_type"] == "stock_surge"

    def test_no_alert_within_threshold(self):
        """임계값 이내 — 알림 없음"""
        from analysis.alerts import check_stock_alerts

        prices = [
            {
                "ticker": "005930.KS",
                "name": "삼성전자",
                "price": 55000,
                "change_pct": -2.0,
            }
        ]
        alerts = check_stock_alerts(prices)
        assert len(alerts) == 0

    def test_none_change_pct_skipped(self):
        """change_pct가 None이면 스킵"""
        from analysis.alerts import check_stock_alerts

        prices = [
            {
                "ticker": "005930.KS",
                "name": "삼성전자",
                "price": 55000,
                "change_pct": None,
            }
        ]
        alerts = check_stock_alerts(prices)
        assert len(alerts) == 0

    def test_multiple_stocks(self):
        """여러 종목 동시 감지"""
        from analysis.alerts import check_stock_alerts

        prices = [
            {
                "ticker": "005930.KS",
                "name": "삼성전자",
                "price": 50000,
                "change_pct": -6.0,
            },
            {"ticker": "TSLA", "name": "테슬라", "price": 300, "change_pct": 8.0},
            {"ticker": "GOOGL", "name": "알파벳", "price": 150, "change_pct": -1.0},
        ]
        alerts = check_stock_alerts(prices)
        assert len(alerts) == 2  # 삼성전자 급락 + 테슬라 급등


class TestCheckMacroAlerts:
    """매크로 지표 알림 감지"""

    def test_kospi_drop(self):
        """코스피 폭락 감지"""
        from analysis.alerts import check_macro_alerts

        macro = [
            {
                "indicator": "코스피",
                "ticker": "KOSPI",
                "value": 2300,
                "change_pct": -4.0,
            }
        ]
        alerts = check_macro_alerts(macro)
        assert any(a["event_type"] == "kospi_drop" for a in alerts)

    def test_usd_krw_high(self):
        """환율 급등 감지"""
        from analysis.alerts import check_macro_alerts

        macro = [
            {
                "indicator": "원/달러",
                "ticker": "KRW=X",
                "value": 1560,
                "change_pct": 1.0,
            }
        ]
        alerts = check_macro_alerts(macro)
        assert any(a["event_type"] == "usd_krw_high" for a in alerts)

    def test_oil_surge(self):
        """유가 급등 감지"""
        from analysis.alerts import check_macro_alerts

        macro = [
            {
                "indicator": "WTI 유가",
                "ticker": "CL=F",
                "value": 85.0,
                "change_pct": 6.0,
            }
        ]
        alerts = check_macro_alerts(macro)
        assert any(a["event_type"] == "oil_surge" for a in alerts)

    def test_gold_swing(self):
        """금 현물 급변 감지"""
        from analysis.alerts import check_macro_alerts

        macro = [
            {
                "indicator": "금 현물",
                "ticker": "GC=F",
                "value": 2000,
                "change_pct": -4.0,
            }
        ]
        alerts = check_macro_alerts(macro)
        assert any(a["event_type"] == "gold_swing" for a in alerts)

    def test_vix_high(self):
        """VIX 급등 감지"""
        from analysis.alerts import check_macro_alerts

        macro = [
            {"indicator": "VIX", "ticker": "^VIX", "value": 35.0, "change_pct": 10.0}
        ]
        alerts = check_macro_alerts(macro)
        assert any(a["event_type"] == "vix_high" for a in alerts)

    def test_no_alert_normal_values(self):
        """정상 범위 — 알림 없음"""
        from analysis.alerts import check_macro_alerts

        macro = [
            {
                "indicator": "코스피",
                "ticker": "KOSPI",
                "value": 2500,
                "change_pct": 0.5,
            },
            {
                "indicator": "원/달러",
                "ticker": "KRW=X",
                "value": 1350,
                "change_pct": 0.1,
            },
        ]
        alerts = check_macro_alerts(macro)
        assert len(alerts) == 0


class TestCheckPortfolioAlert:
    """포트폴리오 손실 알림"""

    def test_portfolio_loss_detected(self):
        """포트폴리오 -10% 이상 손실 감지"""
        from analysis.alerts import check_portfolio_alert

        prices = [
            {
                "ticker": "005930.KS",
                "price": 40000,
                "avg_cost": 50000,
                "currency": "KRW",
                "qty": 10,
            }
        ]
        alerts = check_portfolio_alert(prices)
        assert len(alerts) == 1
        assert alerts[0]["event_type"] == "portfolio_loss"

    def test_no_alert_small_loss(self):
        """소폭 손실 — 알림 없음"""
        from analysis.alerts import check_portfolio_alert

        prices = [
            {
                "ticker": "005930.KS",
                "price": 48000,
                "avg_cost": 50000,
                "currency": "KRW",
                "qty": 10,
            }
        ]
        alerts = check_portfolio_alert(prices)
        assert len(alerts) == 0


# ── 알림 JSON 저장/삭제 테스트 ──


class TestSaveAlertsJson:
    """alerts.json 생성/삭제"""

    def test_alerts_json_created_when_alerts_exist(self, tmp_output_dir):
        """알림이 있으면 alerts.json 생성"""
        from analysis.alerts import save_alerts_to_json

        alerts = [
            {
                "level": "RED",
                "event_type": "stock_drop",
                "ticker": "005930.KS",
                "message": "테스트 알림",
                "value": -6.0,
                "threshold": -5.0,
            }
        ]
        save_alerts_to_json(alerts, output_dir=tmp_output_dir)

        alerts_path = tmp_output_dir / "alerts.json"
        assert alerts_path.exists()
        data = json.loads(alerts_path.read_text(encoding="utf-8"))
        assert data["count"] == 1
        assert len(data["alerts"]) == 1

    def test_alerts_json_deleted_when_no_alerts(self, tmp_output_dir):
        """알림이 없으면 alerts.json 삭제"""
        from analysis.alerts import save_alerts_to_json

        # 기존 파일 생성
        alerts_path = tmp_output_dir / "alerts.json"
        alerts_path.write_text('{"old": true}', encoding="utf-8")

        save_alerts_to_json([], output_dir=tmp_output_dir)
        assert not alerts_path.exists()

    def test_no_file_when_empty_and_no_existing(self, tmp_output_dir):
        """기존 파일도 없고 알림도 없으면 아무 일 없음"""
        from analysis.alerts import save_alerts_to_json

        save_alerts_to_json([], output_dir=tmp_output_dir)
        assert not (tmp_output_dir / "alerts.json").exists()


# ── DB 저장 테스트 ──


class TestSaveAlertsDB:
    """알림 DB 저장"""

    def test_save_to_db(self, db_conn):
        """알림이 alerts 테이블에 저장됨"""
        from analysis.alerts import save_alerts_to_db

        alerts = [
            {
                "level": "RED",
                "event_type": "stock_drop",
                "ticker": "005930.KS",
                "message": "테스트 급락",
                "value": -6.0,
                "threshold": -5.0,
            }
        ]
        save_alerts_to_db(alerts, conn=db_conn)

        rows = db_conn.execute("SELECT * FROM alerts").fetchall()
        assert len(rows) == 1
        assert rows[0]["level"] == "RED"
        assert rows[0]["event_type"] == "stock_drop"

    def test_save_empty_no_error(self, db_conn):
        """빈 알림 — 에러 없음"""
        from analysis.alerts import save_alerts_to_db

        save_alerts_to_db([], conn=db_conn)
        rows = db_conn.execute("SELECT * FROM alerts").fetchall()
        assert len(rows) == 0

    def test_notified_flag(self, db_conn):
        """notified 파라미터로 플래그 설정"""
        from analysis.alerts import save_alerts_to_db

        alerts = [
            {
                "level": "RED",
                "event_type": "stock_drop",
                "ticker": "005930.KS",
                "message": "테스트",
                "value": -6.0,
                "threshold": -5.0,
            }
        ]
        save_alerts_to_db(alerts, conn=db_conn, notified=True)

        row = db_conn.execute("SELECT notified FROM alerts").fetchone()
        assert row["notified"] == 1


# ── 중복 방지 테스트 ──


class TestDuplicateAlertPrevention:
    """중복 알림 방지"""

    def test_duplicate_within_interval(self, db_conn):
        """1시간 내 같은 알림은 중복으로 판단"""
        from datetime import datetime, timedelta, timezone

        from analysis.alerts_watch import is_duplicate_alert

        KST = timezone(timedelta(hours=9))
        now = datetime.now(KST).isoformat()

        # 기존 알림 삽입
        db_conn.execute(
            "INSERT INTO alerts (level, event_type, ticker, message, value, threshold, triggered_at, notified) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("RED", "stock_drop", "005930.KS", "테스트", -6.0, -5.0, now, 1),
        )
        db_conn.commit()

        result = is_duplicate_alert("stock_drop", "005930.KS", "drop", conn=db_conn)
        assert result is True

    def test_not_duplicate_after_interval(self, db_conn):
        """1시간 경과 후에는 중복이 아님"""
        from datetime import datetime, timedelta, timezone

        from analysis.alerts_watch import is_duplicate_alert

        KST = timezone(timedelta(hours=9))
        old_time = (datetime.now(KST) - timedelta(hours=9)).isoformat()

        db_conn.execute(
            "INSERT INTO alerts (level, event_type, ticker, message, value, threshold, triggered_at, notified) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("RED", "stock_drop", "005930.KS", "테스트", -6.0, -5.0, old_time, 1),
        )
        db_conn.commit()

        result = is_duplicate_alert("stock_drop", "005930.KS", "drop", conn=db_conn)
        assert result is False

    def test_different_ticker_not_duplicate(self, db_conn):
        """다른 종목은 중복이 아님"""
        from datetime import datetime, timedelta, timezone

        from analysis.alerts_watch import is_duplicate_alert

        KST = timezone(timedelta(hours=9))
        now = datetime.now(KST).isoformat()

        db_conn.execute(
            "INSERT INTO alerts (level, event_type, ticker, message, value, threshold, triggered_at, notified) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("RED", "stock_drop", "005930.KS", "테스트", -6.0, -5.0, now, 1),
        )
        db_conn.commit()

        result = is_duplicate_alert("stock_drop", "TSLA", "drop", conn=db_conn)
        assert result is False


# ── alerts_watch가 alerts의 공통 함수를 사용하는지 테스트 ──


class TestAlertsIntegration:
    """alerts.py와 alerts_watch.py 통합 검증"""

    def test_alerts_watch_imports_from_alerts(self):
        """alerts_watch.py가 alerts.py의 공통 함수를 import"""
        from analysis import alerts

        # alerts에 공통 핵심 함수가 존재
        assert hasattr(alerts, "check_stock_alerts")
        assert hasattr(alerts, "check_macro_alerts")
        assert hasattr(alerts, "check_portfolio_alert")
        assert hasattr(alerts, "save_alerts_to_json")
        assert hasattr(alerts, "save_alerts_to_db")

    def test_alerts_run_returns_alerts(self, tmp_output_dir):
        """alerts.py run()이 알림 리스트 반환"""
        from analysis.alerts import run

        with (
            patch("analysis.alerts.load_latest_prices") as mock_prices,
            patch("analysis.alerts.load_latest_macro") as mock_macro,
            patch(
                "analysis.alerts.DB_PATH",
                MagicMock(exists=MagicMock(return_value=True)),
            ),
            patch("analysis.alerts.save_alerts_to_db"),
            patch("analysis.alerts.save_alerts_to_json"),
        ):
            mock_prices.return_value = [
                {
                    "ticker": "005930.KS",
                    "name": "삼성전자",
                    "price": 50000,
                    "change_pct": -6.0,
                    "avg_cost": 55000,
                    "currency": "KRW",
                    "qty": 10,
                }
            ]
            mock_macro.return_value = []
            result = run()
            assert isinstance(result, list)
            assert len(result) >= 1

    def test_pipeline_calls_alerts(self):
        """run_pipeline.py에서 alerts.run을 호출함"""
        import run_pipeline

        assert hasattr(run_pipeline, "check_alerts")


class TestAlertFieldStructure:
    """알림 필드 구조 검증"""

    def test_alert_has_required_fields(self):
        """생성된 알림에 필수 필드 존재"""
        from analysis.alerts import check_stock_alerts

        prices = [
            {
                "ticker": "005930.KS",
                "name": "삼성전자",
                "price": 50000,
                "change_pct": -6.0,
            }
        ]
        alerts = check_stock_alerts(prices)
        assert len(alerts) == 1
        alert = alerts[0]
        required = ["level", "event_type", "ticker", "message", "value", "threshold"]
        for field in required:
            assert field in alert, f"필수 필드 '{field}' 누락"

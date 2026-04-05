"""T3: 동적 알림 임계값 (VIX 기반) 테스트"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── config: get_dynamic_thresholds ──


def test_get_dynamic_thresholds_calm():
    """VIX 15 → calm 레짐, stock_drop -5%"""
    from config import get_dynamic_thresholds

    result = get_dynamic_thresholds(15.0)
    assert result["regime"] == "calm"
    assert result["stock_drop"] == -5.0
    assert result["stock_surge"] == 5.0
    assert result["kospi_drop"] == -3.0


def test_get_dynamic_thresholds_normal():
    """VIX 22 → normal 레짐"""
    from config import get_dynamic_thresholds

    result = get_dynamic_thresholds(22.0)
    assert result["regime"] == "normal"


def test_get_dynamic_thresholds_fear():
    """VIX 28 → fear 레짐, stock_drop -7%"""
    from config import get_dynamic_thresholds

    result = get_dynamic_thresholds(28.0)
    assert result["regime"] == "fear"
    assert result["stock_drop"] == -7.0
    assert result["kospi_drop"] == -4.0


def test_get_dynamic_thresholds_panic():
    """VIX 35 → panic 레짐, stock_drop -10%"""
    from config import get_dynamic_thresholds

    result = get_dynamic_thresholds(35.0)
    assert result["regime"] == "panic"
    assert result["stock_drop"] == -10.0
    assert result["kospi_drop"] == -5.0


def test_get_dynamic_thresholds_boundary():
    """경계값: VIX 정확히 20 → calm, VIX 20.01 → normal"""
    from config import get_dynamic_thresholds

    assert get_dynamic_thresholds(20.0)["regime"] == "calm"
    assert get_dynamic_thresholds(20.01)["regime"] == "normal"
    assert get_dynamic_thresholds(30.0)["regime"] == "fear"
    assert get_dynamic_thresholds(30.01)["regime"] == "panic"


# ── alerts: get_current_vix ──


def test_get_current_vix_found():
    """VIX 지표가 있으면 값 반환"""
    from analysis.alerts import get_current_vix

    macro = [
        {"indicator": "코스피", "value": 2500.0},
        {"indicator": "VIX", "value": 28.5},
        {"indicator": "원/달러", "value": 1503.0},
    ]
    assert get_current_vix(macro) == 28.5


def test_get_current_vix_not_found():
    """VIX 지표 없으면 None 반환"""
    from analysis.alerts import get_current_vix

    macro = [{"indicator": "코스피", "value": 2500.0}]
    assert get_current_vix(macro) is None


def test_get_current_vix_empty():
    """빈 리스트 → None"""
    from analysis.alerts import get_current_vix

    assert get_current_vix([]) is None


# ── alerts: check_stock_alerts with dynamic thresholds ──


def test_check_stock_alerts_uses_dynamic_threshold():
    """fear 레짐(-7%) 적용 시 -5% 급락은 알림 미발동"""
    from analysis.alerts import check_stock_alerts

    prices = [
        {"ticker": "005930.KS", "name": "삼성전자", "price": 60000, "change_pct": -6.0}
    ]
    # 기본값(-5%) 적용 → 알림 발동
    default_alerts = check_stock_alerts(prices)
    assert len(default_alerts) == 1

    # fear 레짐(-7%) 적용 → -6%는 알림 미발동
    fear_thresholds = {"stock_drop": -7.0, "stock_surge": 7.0}
    fear_alerts = check_stock_alerts(prices, fear_thresholds)
    assert len(fear_alerts) == 0


def test_check_stock_alerts_panic_threshold():
    """panic 레짐(-10%) 적용 시 -8% 급락은 알림 미발동"""
    from analysis.alerts import check_stock_alerts

    prices = [{"ticker": "TSLA", "name": "테슬라", "price": 200.0, "change_pct": -8.0}]
    panic_thresholds = {"stock_drop": -10.0, "stock_surge": 10.0}
    alerts = check_stock_alerts(prices, panic_thresholds)
    assert len(alerts) == 0


def test_check_stock_alerts_none_thresholds_uses_default():
    """thresholds=None 이면 기존 ALERT_THRESHOLDS 사용"""
    from analysis.alerts import check_stock_alerts

    prices = [{"ticker": "TSLA", "name": "테슬라", "price": 200.0, "change_pct": -6.0}]
    alerts = check_stock_alerts(prices, None)
    # 기본값 -5% → -6% 이므로 발동
    assert len(alerts) == 1


# ── alerts: check_macro_alerts with dynamic thresholds ──


def test_check_macro_alerts_kospi_dynamic():
    """fear 레짐 kospi_drop -4% 적용 시 -3.5%는 알림 미발동"""
    from analysis.alerts import check_macro_alerts

    macro = [{"indicator": "코스피", "value": 2400.0, "change_pct": -3.5}]

    # 기본값(-3%) → -3.5%는 알림 발동
    default_alerts = check_macro_alerts(macro)
    assert len(default_alerts) == 1

    # fear 레짐(-4%) → -3.5%는 알림 미발동
    fear_thresholds = {"kospi_drop": -4.0}
    fear_alerts = check_macro_alerts(macro, fear_thresholds)
    assert len(fear_alerts) == 0


# ── 통합: run() 로그에 레짐 정보 출력 ──


def test_run_logs_regime(tmp_path, capsys):  # noqa: F811
    """run() 실행 시 VIX 레짐 로그 출력"""
    import json
    import sqlite3

    import config
    from analysis import alerts
    from db.init_db import init_schema

    orig_out = config.OUTPUT_DIR
    orig_db = config.DB_PATH
    db_path = tmp_path / "history.db"
    config.OUTPUT_DIR = tmp_path
    config.DB_PATH = db_path
    alerts.OUTPUT_DIR = tmp_path
    alerts.DB_PATH = db_path

    # DB 초기화
    conn = sqlite3.connect(str(db_path))
    init_schema(conn)
    conn.close()

    # macro.json 생성 (VIX 31 = panic 레짐)
    macro_data = {
        "indicators": [
            {"indicator": "VIX", "value": 31.05, "change_pct": 5.0},
        ]
    }
    with open(tmp_path / "macro.json", "w") as f:
        json.dump(macro_data, f)

    # prices.json 생성 (빈 목록)
    with open(tmp_path / "prices.json", "w") as f:
        json.dump({"prices": []}, f)

    alerts.run()

    captured = capsys.readouterr()
    assert "panic" in captured.out
    assert "31.05" in captured.out

    config.OUTPUT_DIR = orig_out
    config.DB_PATH = orig_db
    alerts.OUTPUT_DIR = orig_out
    alerts.DB_PATH = orig_db

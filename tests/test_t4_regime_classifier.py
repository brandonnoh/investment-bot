"""T4: 시장 레짐 분류기 테스트"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_macro(vix=None, fx_change=None, oil_change=None, oil_value=None) -> dict:
    """테스트용 macro_data 딕셔너리 생성 헬퍼"""
    indicators = []
    if vix is not None:
        indicators.append({"indicator": "VIX", "value": vix, "change_pct": 0.0})
    if fx_change is not None:
        indicators.append({"indicator": "원/달러", "value": 1300.0, "change_pct": fx_change})
    if oil_change is not None or oil_value is not None:
        indicators.append({
            "indicator": "WTI 유가",
            "value": oil_value if oil_value is not None else 70.0,
            "change_pct": oil_change if oil_change is not None else 0.0,
        })
    return {"indicators": indicators}


# ── classify() 테스트 ──


def test_classify_risk_on():
    """VIX 15, 안정적 FX/유가 → RISK_ON"""
    # Arrange
    from analysis.regime_classifier import RegimeClassifier
    classifier = RegimeClassifier()
    macro = _make_macro(vix=15.0, fx_change=0.5, oil_change=1.0, oil_value=70.0)

    # Act
    result = classifier.classify(macro)

    # Assert
    assert result == "RISK_ON"


def test_classify_risk_off_high_vix():
    """VIX 28 → RISK_OFF"""
    # Arrange
    from analysis.regime_classifier import RegimeClassifier
    classifier = RegimeClassifier()
    macro = _make_macro(vix=28.0, fx_change=0.5, oil_change=1.0, oil_value=70.0)

    # Act
    result = classifier.classify(macro)

    # Assert
    assert result == "RISK_OFF"


def test_classify_risk_off_fx_surge():
    """원/달러 +4% 급등 → RISK_OFF"""
    # Arrange
    from analysis.regime_classifier import RegimeClassifier
    classifier = RegimeClassifier()
    macro = _make_macro(vix=18.0, fx_change=4.0, oil_change=1.0, oil_value=70.0)

    # Act
    result = classifier.classify(macro)

    # Assert
    assert result == "RISK_OFF"


def test_classify_inflationary():
    """유가 +8% 급등 → INFLATIONARY"""
    # Arrange
    from analysis.regime_classifier import RegimeClassifier
    classifier = RegimeClassifier()
    macro = _make_macro(vix=18.0, fx_change=0.5, oil_change=8.0, oil_value=75.0)

    # Act
    result = classifier.classify(macro)

    # Assert
    assert result == "INFLATIONARY"


def test_classify_stagflation():
    """VIX 28 + 유가 +6% → STAGFLATION"""
    # Arrange
    from analysis.regime_classifier import RegimeClassifier
    classifier = RegimeClassifier()
    macro = _make_macro(vix=28.0, fx_change=1.0, oil_change=6.0, oil_value=80.0)

    # Act
    result = classifier.classify(macro)

    # Assert
    assert result == "STAGFLATION"


def test_classify_default_missing_data():
    """지표 없는 빈 데이터 → 유효한 레짐 문자열 반환"""
    # Arrange
    from analysis.regime_classifier import RegimeClassifier
    classifier = RegimeClassifier()
    valid_regimes = {"RISK_ON", "RISK_OFF", "INFLATIONARY", "STAGFLATION"}

    # Act
    result_empty = classifier.classify({})
    result_no_indicators = classifier.classify({"indicators": []})

    # Assert
    assert result_empty in valid_regimes
    assert result_no_indicators in valid_regimes


# ── get_strategy() 테스트 ──


def test_get_strategy_returns_required_fields():
    """get_strategy()가 필수 필드를 모두 반환"""
    # Arrange
    from analysis.regime_classifier import RegimeClassifier
    classifier = RegimeClassifier()

    # Act
    strategy = classifier.get_strategy("RISK_OFF")

    # Assert
    assert "stance" in strategy
    assert "preferred_sectors" in strategy
    assert "avoid_sectors" in strategy
    assert "cash_ratio" in strategy
    assert isinstance(strategy["preferred_sectors"], list)
    assert isinstance(strategy["avoid_sectors"], list)
    assert isinstance(strategy["cash_ratio"], float)


def test_get_strategy_all_regimes():
    """모든 4가지 레짐에 대해 유효한 전략 반환"""
    # Arrange
    from analysis.regime_classifier import RegimeClassifier
    classifier = RegimeClassifier()
    regimes = ["RISK_ON", "RISK_OFF", "INFLATIONARY", "STAGFLATION"]

    for regime in regimes:
        # Act
        strategy = classifier.get_strategy(regime)

        # Assert
        assert "stance" in strategy, f"{regime}: stance 필드 없음"
        assert "preferred_sectors" in strategy, f"{regime}: preferred_sectors 필드 없음"
        assert "avoid_sectors" in strategy, f"{regime}: avoid_sectors 필드 없음"
        assert "cash_ratio" in strategy, f"{regime}: cash_ratio 필드 없음"
        assert 0.0 <= strategy["cash_ratio"] <= 1.0, f"{regime}: cash_ratio 범위 오류"


# ── run() 통합 테스트 ──


def test_run_saves_regime_json(tmp_path):
    """run()이 regime.json을 OUTPUT_DIR에 저장"""
    # Arrange
    import analysis.regime_classifier as rc_module
    import config

    original_output_dir = config.OUTPUT_DIR
    config.OUTPUT_DIR = tmp_path
    rc_module.OUTPUT_DIR = tmp_path

    # macro.json 생성
    macro_data = {
        "indicators": [
            {"indicator": "VIX", "value": 15.0, "change_pct": 0.0},
            {"indicator": "원/달러", "value": 1300.0, "change_pct": 0.5},
            {"indicator": "WTI 유가", "value": 70.0, "change_pct": 1.0},
        ]
    }
    with open(tmp_path / "macro.json", "w", encoding="utf-8") as f:
        json.dump(macro_data, f)

    try:
        # Act
        result = rc_module.run()

        # Assert
        regime_path = tmp_path / "regime.json"
        assert regime_path.exists(), "regime.json이 생성되지 않음"

        with open(regime_path, encoding="utf-8") as f:
            saved = json.load(f)

        assert "classified_at" in saved
        assert "regime" in saved
        assert saved["regime"] in {"RISK_ON", "RISK_OFF", "INFLATIONARY", "STAGFLATION"}
        assert "strategy" in saved
        assert result["regime"] == saved["regime"]
    finally:
        config.OUTPUT_DIR = original_output_dir
        rc_module.OUTPUT_DIR = original_output_dir


def test_run_detects_regime_change(tmp_path, capsys):
    """이전 레짐과 다르면 변경 메시지 출력"""
    # Arrange
    import analysis.regime_classifier as rc_module
    import config

    original_output_dir = config.OUTPUT_DIR
    config.OUTPUT_DIR = tmp_path
    rc_module.OUTPUT_DIR = tmp_path

    # 이전 레짐을 RISK_ON으로 설정
    previous = {
        "classified_at": "2026-04-01T09:00:00+09:00",
        "regime": "RISK_ON",
        "vix": 15.0,
        "fx_change": 0.5,
        "oil_change": 1.0,
        "strategy": {},
    }
    with open(tmp_path / "regime.json", "w", encoding="utf-8") as f:
        json.dump(previous, f)

    # 현재 데이터: VIX 30 → RISK_OFF로 변경
    macro_data = {
        "indicators": [
            {"indicator": "VIX", "value": 30.0, "change_pct": 15.0},
            {"indicator": "원/달러", "value": 1400.0, "change_pct": 1.0},
            {"indicator": "WTI 유가", "value": 70.0, "change_pct": 1.0},
        ]
    }
    with open(tmp_path / "macro.json", "w", encoding="utf-8") as f:
        json.dump(macro_data, f)

    try:
        # Act
        rc_module.run()
        captured = capsys.readouterr()

        # Assert
        assert "레짐 변경" in captured.out
        assert "RISK_ON" in captured.out
    finally:
        config.OUTPUT_DIR = original_output_dir
        rc_module.OUTPUT_DIR = original_output_dir

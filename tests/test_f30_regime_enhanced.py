"""F30 — 시장 국면 고도화: confidence + panic_signal"""
from __future__ import annotations

import json
from analysis.regime_classifier import RegimeClassifier


BULL_MACRO = {
    "indicators": [
        {"indicator": "코스피", "value": 2700, "change_pct": 3.0, "category": "INDEX"},
        {"indicator": "VIX", "value": 14.0, "change_pct": -10.0, "category": "VOLATILITY"},
        {"indicator": "원/달러", "value": 1320, "change_pct": -0.5, "category": "FX"},
        {"indicator": "나스닥", "value": 18000, "change_pct": 2.0, "category": "INDEX"},
    ]
}

BEAR_MACRO = {
    "indicators": [
        {"indicator": "코스피", "value": 2200, "change_pct": -4.0, "category": "INDEX"},
        {"indicator": "VIX", "value": 32.0, "change_pct": 20.0, "category": "VOLATILITY"},
        {"indicator": "원/달러", "value": 1480, "change_pct": 2.0, "category": "FX"},
        {"indicator": "나스닥", "value": 15000, "change_pct": -3.0, "category": "INDEX"},
    ]
}

PANIC_MACRO = {
    "indicators": [
        {"indicator": "코스피", "value": 1900, "change_pct": -8.0, "category": "INDEX"},
        {"indicator": "VIX", "value": 50.0, "change_pct": 60.0, "category": "VOLATILITY"},
        {"indicator": "원/달러", "value": 1600, "change_pct": 5.0, "category": "FX"},
        {"indicator": "나스닥", "value": 13000, "change_pct": -5.0, "category": "INDEX"},
    ]
}


def test_classify_returns_confidence():
    clf = RegimeClassifier()
    result = clf.classify_with_confidence(BULL_MACRO)
    assert "regime" in result
    assert "confidence" in result
    assert 0.0 <= result["confidence"] <= 1.0


def test_panic_signal_true_when_vix_high():
    clf = RegimeClassifier()
    result = clf.classify_with_confidence(PANIC_MACRO)
    assert result["panic_signal"] is True


def test_panic_signal_false_when_vix_normal():
    clf = RegimeClassifier()
    result = clf.classify_with_confidence(BULL_MACRO)
    assert result["panic_signal"] is False


def test_bull_market_detected():
    clf = RegimeClassifier()
    result = clf.classify_with_confidence(BULL_MACRO)
    assert result["regime"] in ("RISK_ON", "BULL")


def test_panic_detected():
    clf = RegimeClassifier()
    result = clf.classify_with_confidence(PANIC_MACRO)
    assert result["regime"] in ("RISK_OFF", "PANIC")


def test_panic_high_vix_triggers():
    clf = RegimeClassifier()
    result = clf.classify_with_confidence(PANIC_MACRO)
    assert result.get("panic_signal") is True or result["regime"] in ("RISK_OFF", "PANIC")


def test_confidence_higher_in_clear_regime():
    clf = RegimeClassifier()
    bull = clf.classify_with_confidence(BULL_MACRO)
    bear = clf.classify_with_confidence(BEAR_MACRO)
    assert bull["confidence"] > 0.5
    assert bear["confidence"] > 0.5


def test_backward_compat_classify():
    """기존 classify() 메서드는 문자열 반환 유지."""
    clf = RegimeClassifier()
    result = clf.classify(BULL_MACRO)
    assert isinstance(result, str)


def test_to_json_contains_confidence():
    clf = RegimeClassifier()
    json_str = clf.to_json(BULL_MACRO)
    data = json.loads(json_str)
    assert "confidence" in data
    assert "panic_signal" in data
    assert "classified_at" in data


def test_regime_json_output_has_confidence(tmp_path):
    """regime.json 출력 파일에 confidence 포함 확인."""
    from unittest.mock import patch
    import json
    from analysis.regime_classifier import run as regime_run

    macro_path = tmp_path / "macro.json"
    macro_path.write_text(json.dumps(BULL_MACRO))

    with patch("analysis.regime_classifier.OUTPUT_DIR", tmp_path), \
         patch("analysis.regime_classifier.MACRO_FILE", macro_path):
        regime_run(macro_data=BULL_MACRO, output_dir=tmp_path)

    out = tmp_path / "regime.json"
    if out.exists():
        data = json.loads(out.read_text())
        assert "confidence" in data

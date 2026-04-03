"""F28 — 자기 교정: 성과 분석 → correction_notes.json 생성"""
import json
import pytest
from pathlib import Path


SAMPLE_PERFORMANCE = {
    "monthly_report": {
        "period": "2026-03",
        "hit_rate_1w": 0.40,
        "avg_return_1w": -0.02,
        "factor_analysis": {
            "value":   {"hit_count": 7, "miss_count": 3, "avg_score_hit": 0.70, "avg_score_miss": -0.03},
            "quality": {"hit_count": 13, "miss_count": 7, "avg_score_hit": 0.65, "avg_score_miss": -0.02},
            "growth":  {"hit_count": 3, "miss_count": 7, "avg_score_hit": 0.30, "avg_score_miss": -0.05},
            "timing":  {"hit_count": 9, "miss_count": 11, "avg_score_hit": 0.45, "avg_score_miss": -0.02},
            "catalyst":{"hit_count": 2, "miss_count": 8, "avg_score_hit": 0.20, "avg_score_miss": -0.04},
            "macro":   {"hit_count": 11, "miss_count": 9, "avg_score_hit": 0.55, "avg_score_miss": -0.01},
        },
    },
    "weight_suggestion": {
        "suggested_weights": {
            "value": 0.25, "quality": 0.22, "growth": 0.10,
            "timing": 0.20, "catalyst": 0.08, "macro": 0.15,
        },
    }
}


def test_generate_correction_notes_basic():
    from analysis.self_correction import generate_correction_notes
    notes = generate_correction_notes(SAMPLE_PERFORMANCE)
    assert "weak_factors" in notes
    assert "strong_factors" in notes
    assert "weight_adjustment" in notes
    assert "summary" in notes


def test_weak_factors_detected():
    from analysis.self_correction import generate_correction_notes
    notes = generate_correction_notes(SAMPLE_PERFORMANCE)
    # growth(0.30)와 catalyst(0.20)는 weak (< 0.40)
    assert "growth" in notes["weak_factors"]
    assert "catalyst" in notes["weak_factors"]


def test_strong_factors_detected():
    from analysis.self_correction import generate_correction_notes
    notes = generate_correction_notes(SAMPLE_PERFORMANCE)
    # value(0.70)와 quality(0.65)는 strong (> 0.60)
    assert "value" in notes["strong_factors"]
    assert "quality" in notes["strong_factors"]


def test_weight_adjustment_uses_suggestion():
    from analysis.self_correction import generate_correction_notes
    notes = generate_correction_notes(SAMPLE_PERFORMANCE)
    assert notes["weight_adjustment"]["value"] == pytest.approx(0.25)
    assert notes["weight_adjustment"]["growth"] == pytest.approx(0.10)


def test_save_correction_notes(tmp_path):
    from analysis.self_correction import save_correction_notes
    notes = {"summary": "테스트", "weak_factors": [], "strong_factors": [], "weight_adjustment": {}}
    out = tmp_path / "correction_notes.json"
    save_correction_notes(notes, out)
    data = json.loads(out.read_text())
    assert data["summary"] == "테스트"
    assert "generated_at" in data


def test_run_no_performance_report(tmp_path):
    from analysis.self_correction import run
    result = run(performance_path=tmp_path / "missing.json", output_dir=tmp_path)
    assert result is None  # 입력 없으면 None


def test_run_generates_output(tmp_path):
    from analysis.self_correction import run
    perf_path = tmp_path / "performance_report.json"
    perf_path.write_text(json.dumps(SAMPLE_PERFORMANCE))
    result = run(performance_path=perf_path, output_dir=tmp_path)
    assert result is not None
    out = tmp_path / "correction_notes.json"
    assert out.exists()
    data = json.loads(out.read_text())
    assert "weak_factors" in data


def test_period_in_output(tmp_path):
    from analysis.self_correction import run
    perf_path = tmp_path / "performance_report.json"
    perf_path.write_text(json.dumps(SAMPLE_PERFORMANCE))
    result = run(performance_path=perf_path, output_dir=tmp_path)
    assert result["period"] == "2026-03"


def test_no_monthly_report_returns_none(tmp_path):
    from analysis.self_correction import run
    perf_path = tmp_path / "performance_report.json"
    perf_path.write_text(json.dumps({"outcomes": []}))
    result = run(performance_path=perf_path, output_dir=tmp_path)
    assert result is None

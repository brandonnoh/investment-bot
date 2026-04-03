# tests/test_f26_fallback_keywords.py
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

KST = timezone(timedelta(hours=9))


def test_is_keywords_fresh_missing(tmp_path):
    from analysis.fallback_keywords import is_keywords_fresh
    assert is_keywords_fresh(tmp_path / "missing.json") is False


def test_is_keywords_fresh_recent(tmp_path):
    from analysis.fallback_keywords import is_keywords_fresh
    p = tmp_path / "keywords.json"
    p.write_text(json.dumps({"generated_at": datetime.now(KST).isoformat(), "keywords": []}))
    assert is_keywords_fresh(p) is True


def test_is_keywords_fresh_stale(tmp_path):
    from analysis.fallback_keywords import is_keywords_fresh
    stale_time = (datetime.now(KST) - timedelta(hours=26)).isoformat()
    p = tmp_path / "keywords.json"
    p.write_text(json.dumps({"generated_at": stale_time, "keywords": []}))
    assert is_keywords_fresh(p) is False


def test_generate_fallback_risk_on(tmp_path):
    from analysis.fallback_keywords import generate_fallback_keywords
    macro = tmp_path / "macro.json"
    regime = tmp_path / "regime.json"
    macro.write_text(json.dumps({"indicators": []}))
    regime.write_text(json.dumps({"regime": "RISK_ON"}))
    keywords = generate_fallback_keywords(macro, regime)
    assert len(keywords) >= 1
    assert all("keyword" in k and "category" in k and "priority" in k for k in keywords)


def test_generate_fallback_risk_off(tmp_path):
    from analysis.fallback_keywords import generate_fallback_keywords
    macro = tmp_path / "macro.json"
    regime = tmp_path / "regime.json"
    macro.write_text(json.dumps({"indicators": []}))
    regime.write_text(json.dumps({"regime": "RISK_OFF"}))
    keywords = generate_fallback_keywords(macro, regime)
    assert len(keywords) >= 1


def test_generate_fallback_high_vix(tmp_path):
    from analysis.fallback_keywords import generate_fallback_keywords
    macro = tmp_path / "macro.json"
    regime = tmp_path / "regime.json"
    macro.write_text(json.dumps({"indicators": [{"indicator": "VIX", "value": 30, "change_pct": 0}]}))
    regime.write_text(json.dumps({"regime": "RISK_OFF"}))
    keywords = generate_fallback_keywords(macro, regime)
    kwds = [k["keyword"] for k in keywords]
    assert "저변동성 방어주 배당" in kwds


def test_generate_fallback_high_usdkrw(tmp_path):
    from analysis.fallback_keywords import generate_fallback_keywords
    macro = tmp_path / "macro.json"
    regime = tmp_path / "regime.json"
    macro.write_text(json.dumps({"indicators": [{"indicator": "원/달러", "value": 1500, "change_pct": 0}]}))
    regime.write_text(json.dumps({"regime": "RISK_ON"}))
    keywords = generate_fallback_keywords(macro, regime)
    kwds = [k["keyword"] for k in keywords]
    assert "수출 선도기업 환율 수혜" in kwds


def test_save_fallback_keywords(tmp_path):
    from analysis.fallback_keywords import save_fallback_keywords
    keywords = [{"keyword": "테스트", "category": "sector", "priority": 1}]
    out = tmp_path / "keywords.json"
    save_fallback_keywords(keywords, out)
    data = json.loads(out.read_text())
    assert data["source"] == "fallback"
    assert data["keywords"] == keywords
    assert "generated_at" in data


def test_ensure_fresh_creates_fallback(tmp_path):
    from analysis.fallback_keywords import ensure_fresh_keywords
    macro = tmp_path / "macro.json"
    regime = tmp_path / "regime.json"
    macro.write_text(json.dumps({"indicators": []}))
    regime.write_text(json.dumps({"regime": "RISK_OFF"}))
    kw_path = tmp_path / "discovery_keywords.json"
    # patch OUTPUT_DIR so macro/regime paths resolve correctly
    with patch("analysis.fallback_keywords.MACRO_PATH", macro), \
         patch("analysis.fallback_keywords.REGIME_PATH", regime):
        result = ensure_fresh_keywords(kw_path, tmp_path)
    assert result is False  # fallback used
    assert kw_path.exists()
    data = json.loads(kw_path.read_text())
    assert data["source"] == "fallback"

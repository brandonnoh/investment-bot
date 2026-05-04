#!/usr/bin/env python3
"""
헬스체크 시스템 TDD 테스트 — test_f33
각 체크 함수의 OK/WARN/FAIL 분기를 검증한다.
"""

import json
import sqlite3
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── 픽스처 ──────────────────────────────────────────────────────────


@pytest.fixture
def tmp_intel(tmp_path):
    d = tmp_path / "output" / "intel"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def mem_db(tmp_path):
    db = tmp_path / "history.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE regime_history (date TEXT UNIQUE, regime TEXT)")
    conn.execute("CREATE TABLE prices (ticker TEXT, timestamp TEXT)")
    conn.commit()
    conn.close()
    return db


# ── check_intel_file ────────────────────────────────────────────────


def test_intel_file_ok_when_exists_and_fresh(tmp_intel):
    from scripts.health_check import check_intel_file

    f = tmp_intel / "prices.json"
    f.write_text('{"prices":[]}')
    result = check_intel_file(f, max_age_hours=25)
    assert result.status == "ok"
    assert "prices.json" in result.name


def test_intel_file_fail_when_missing(tmp_intel):
    from scripts.health_check import check_intel_file

    result = check_intel_file(tmp_intel / "prices.json", max_age_hours=25)
    assert result.status == "fail"


def test_intel_file_warn_when_stale(tmp_intel):
    from scripts.health_check import check_intel_file

    f = tmp_intel / "prices.json"
    f.write_text('{"prices":[]}')
    # 파일 수정 시각을 26시간 전으로 조작
    old_mtime = time.time() - 26 * 3600
    import os

    os.utime(str(f), (old_mtime, old_mtime))
    result = check_intel_file(f, max_age_hours=25)
    assert result.status == "warn"


def test_intel_file_fail_when_too_small(tmp_intel):
    from scripts.health_check import check_intel_file

    f = tmp_intel / "prices.json"
    f.write_text("{}")
    result = check_intel_file(f, max_age_hours=25)
    assert result.status == "fail"


# ── check_md_content ────────────────────────────────────────────────


def test_md_content_ok_when_valid(tmp_intel):
    from scripts.health_check import check_md_content

    f = tmp_intel / "marcus-analysis.md"
    f.write_text("# 마커스 분석\n" + "A" * 500)
    result = check_md_content(f, min_chars=200)
    assert result.status == "ok"


def test_md_content_fail_when_contains_auth_error(tmp_intel):
    from scripts.health_check import check_md_content

    f = tmp_intel / "cio-briefing.md"
    f.write_text('Failed to authenticate. API Error: 401 {"type":"error"}')
    result = check_md_content(f, min_chars=200)
    assert result.status == "fail"
    assert "401" in result.detail or "인증" in result.detail


def test_md_content_fail_when_too_short(tmp_intel):
    from scripts.health_check import check_md_content

    f = tmp_intel / "cio-briefing.md"
    f.write_text("짧은 내용")
    result = check_md_content(f, min_chars=200)
    assert result.status == "fail"


def test_md_content_fail_when_missing(tmp_intel):
    from scripts.health_check import check_md_content

    result = check_md_content(tmp_intel / "cio-briefing.md", min_chars=200)
    assert result.status == "fail"


# ── check_db_today ──────────────────────────────────────────────────


def test_db_today_ok_when_record_exists(mem_db):
    from datetime import datetime, timedelta, timezone

    from scripts.health_check import check_db_today

    today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
    conn = sqlite3.connect(str(mem_db))
    conn.execute("INSERT INTO regime_history VALUES (?, ?)", (today, "BULL"))
    conn.commit()
    conn.close()
    result = check_db_today(mem_db, "regime_history", "date")
    assert result.status == "ok"


def test_db_today_fail_when_no_record(mem_db):
    from scripts.health_check import check_db_today

    result = check_db_today(mem_db, "regime_history", "date")
    assert result.status == "fail"


def test_db_today_warn_when_table_missing(mem_db):
    from scripts.health_check import check_db_today

    result = check_db_today(mem_db, "nonexistent_table", "date")
    assert result.status == "warn"


# ── check_log_today ─────────────────────────────────────────────────


def test_log_today_ok_when_modified_today(tmp_path):
    from scripts.health_check import check_log_today

    log = tmp_path / "pipeline.log"
    log.write_text("=== 파이프라인 완료 ===")
    result = check_log_today(log, "pipeline")
    assert result.status == "ok"


def test_log_today_warn_when_not_modified_today(tmp_path):
    import os

    from scripts.health_check import check_log_today

    log = tmp_path / "pipeline.log"
    log.write_text("old log")
    old_mtime = time.time() - 26 * 3600
    os.utime(str(log), (old_mtime, old_mtime))
    result = check_log_today(log, "pipeline")
    assert result.status == "warn"


def test_log_today_warn_when_missing(tmp_path):
    from scripts.health_check import check_log_today

    result = check_log_today(tmp_path / "missing.log", "pipeline")
    assert result.status == "warn"


# ── check_api ───────────────────────────────────────────────────────


def test_api_ok_when_responds(tmp_path):
    from scripts.health_check import check_api

    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__ = lambda s: s
        mock_open.return_value.__exit__ = lambda s, *a: False
        mock_open.return_value.status = 200
        result = check_api("http://localhost:8421/api/status")
    assert result.status == "ok"


def test_api_fail_when_connection_refused(tmp_path):
    import urllib.error

    from scripts.health_check import check_api

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
        result = check_api("http://localhost:8421/api/status")
    assert result.status == "fail"


# ── format_report ───────────────────────────────────────────────────


def test_format_report_includes_summary_counts():
    from scripts.health_check import CheckResult, format_report

    results = [
        CheckResult("prices.json", "ok", "정상"),
        CheckResult("cio-briefing.md", "fail", "인증 오류"),
        CheckResult("pipeline log", "warn", "오늘 실행 없음"),
    ]
    report = format_report(results)
    assert "✅" in report
    assert "❌" in report
    assert "⚠️" in report
    assert "1/3" in report or "1 /" in report or "OK: 1" in report


def test_format_report_lists_failures_first():
    from scripts.health_check import CheckResult, format_report

    results = [
        CheckResult("ok_check", "ok", "정상"),
        CheckResult("fail_check", "fail", "오류"),
    ]
    report = format_report(results)
    assert report.index("fail_check") < report.index("ok_check")


# ── check_pipeline_step ────────────────────────────────────────────


def test_pipeline_step_ok_when_success():
    from scripts.health_check import check_pipeline_step

    modules = {
        "fetch_prices": {
            "success": True,
            "item_count": 42,
            "error_count": 0,
            "last_run": "2026-05-04",
        }
    }
    result = check_pipeline_step(modules, "fetch_prices")
    assert result.status == "ok"
    assert "42" in result.detail


def test_pipeline_step_fail_when_failed():
    from scripts.health_check import check_pipeline_step

    modules = {
        "fetch_prices": {
            "success": False,
            "item_count": 0,
            "error_count": 1,
            "error_msg": "timeout",
            "last_run": "2026-05-04",
        }
    }
    result = check_pipeline_step(modules, "fetch_prices")
    assert result.status == "fail"
    assert "timeout" in result.detail


def test_pipeline_step_warn_when_not_in_modules():
    from scripts.health_check import check_pipeline_step

    result = check_pipeline_step({}, "classify_regime")
    assert result.status == "warn"


def test_pipeline_step_name_contains_step():
    from scripts.health_check import check_pipeline_step

    modules = {
        "fetch_prices": {
            "success": True,
            "item_count": 5,
            "error_count": 0,
            "last_run": "2026-05-04",
        }
    }
    result = check_pipeline_step(modules, "fetch_prices")
    assert "fetch_prices" in result.name


def test_pipeline_step_fail_without_error_msg():
    from scripts.health_check import check_pipeline_step

    modules = {
        "analyze_prices": {
            "success": False,
            "item_count": 0,
            "error_count": 0,
            "last_run": "2026-05-04",
        }
    }
    result = check_pipeline_step(modules, "analyze_prices")
    assert result.status == "fail"


# ── run_all_checks 통합 ─────────────────────────────────────────────


def test_run_all_checks_returns_list_of_results(tmp_intel, mem_db):
    from scripts.health_check import run_all_checks

    results = run_all_checks(intel_dir=tmp_intel, db_path=mem_db)
    assert isinstance(results, list)
    assert len(results) > 0
    for r in results:
        assert r.status in ("ok", "warn", "fail")


def test_run_all_checks_includes_pipeline_steps(tmp_intel, mem_db):
    from scripts.health_check import run_all_checks

    # engine_status.json 없을 때 → pipeline 항목이 warn으로 포함되어야 함
    results = run_all_checks(intel_dir=tmp_intel, db_path=mem_db)
    pipeline_results = [r for r in results if r.name.startswith("pipeline:")]
    assert len(pipeline_results) > 0
    # engine_status.json 없으므로 모두 warn
    for r in pipeline_results:
        assert r.status == "warn"


def test_run_all_checks_pipeline_ok_when_engine_status_present(tmp_intel, mem_db):
    from scripts.health_check import run_all_checks

    engine_status = {
        "modules": {
            "fetch_prices": {
                "success": True,
                "item_count": 10,
                "error_count": 0,
                "last_run": "2026-05-04",
            },
        }
    }
    (tmp_intel / "engine_status.json").write_text(json.dumps(engine_status))
    results = run_all_checks(intel_dir=tmp_intel, db_path=mem_db)
    prices_result = next((r for r in results if "fetch_prices" in r.name), None)
    assert prices_result is not None
    assert prices_result.status == "ok"

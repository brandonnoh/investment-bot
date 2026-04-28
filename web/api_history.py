#!/usr/bin/env python3
"""
파이프라인 이력 조회 API 로직
regime_history / sector_scores_history / correction_notes_history / performance_report_history
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.connection import get_db_conn


def load_regime_history(days: int = 90) -> list[dict]:
    """regime_history 최근 N일 조회."""
    try:
        with get_db_conn() as conn:
            rows = conn.execute(
                """SELECT date, regime, confidence, panic_signal,
                          vix, fx_change, oil_change, strategy_json
                   FROM regime_history ORDER BY date DESC LIMIT ?""",
                (days,),
            ).fetchall()
        result = []
        for r in rows:
            row = dict(r)
            raw = row.pop("strategy_json", None)
            try:
                row["strategy"] = json.loads(raw) if raw else None
            except Exception:
                row["strategy"] = None
            result.append(row)
        return result
    except Exception as e:
        print(f"[api_history] regime_history 조회 실패: {e}")
        return []


def load_sector_scores_history(days: int = 90) -> list[dict]:
    """sector_scores_history 최근 N일 조회."""
    try:
        with get_db_conn() as conn:
            rows = conn.execute(
                """SELECT date, regime, sectors_json, updated_at
                   FROM sector_scores_history ORDER BY date DESC LIMIT ?""",
                (days,),
            ).fetchall()
        result = []
        for r in rows:
            row = dict(r)
            raw = row.pop("sectors_json", None)
            try:
                row["sectors"] = json.loads(raw) if raw else []
            except Exception:
                row["sectors"] = []
            result.append(row)
        return result
    except Exception as e:
        print(f"[api_history] sector_scores_history 조회 실패: {e}")
        return []


def load_correction_notes_history(limit: int = 30) -> list[dict]:
    """correction_notes_history 최근 N개 조회."""
    try:
        with get_db_conn() as conn:
            rows = conn.execute(
                """SELECT date, period, weak_factors_json, strong_factors_json,
                          weight_adjustment_json, summary, generated_at
                   FROM correction_notes_history ORDER BY date DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        result = []
        for r in rows:
            row = dict(r)
            for key in ("weak_factors_json", "strong_factors_json", "weight_adjustment_json"):
                raw = row.pop(key, None)
                dest = key.replace("_json", "")
                try:
                    row[dest] = json.loads(raw) if raw else None
                except Exception:
                    row[dest] = None
            result.append(row)
        return result
    except Exception as e:
        print(f"[api_history] correction_notes_history 조회 실패: {e}")
        return []


def load_performance_report_history(days: int = 90) -> list[dict]:
    """performance_report_history 최근 N일 조회."""
    try:
        with get_db_conn() as conn:
            rows = conn.execute(
                """SELECT date, outcome_summary_json, monthly_report_json,
                          weight_suggestion_json, updated_at
                   FROM performance_report_history ORDER BY date DESC LIMIT ?""",
                (days,),
            ).fetchall()
        result = []
        for r in rows:
            row = dict(r)
            for key in ("outcome_summary_json", "monthly_report_json", "weight_suggestion_json"):
                raw = row.pop(key, None)
                dest = key.replace("_json", "")
                try:
                    row[dest] = json.loads(raw) if raw else None
                except Exception:
                    row[dest] = None
            result.append(row)
        return result
    except Exception as e:
        print(f"[api_history] performance_report_history 조회 실패: {e}")
        return []

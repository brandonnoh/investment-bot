#!/usr/bin/env python3
"""
미션컨트롤 API 로직
JSON 파일 로드, 프로세스 실행 관리
"""

import json
import logging
import os
import subprocess
import threading
from pathlib import Path

from db.connection import get_db_conn
from utils.schema import validate_json
from web.portfolio_refresh import refresh_portfolio_with_live_prices

logger = logging.getLogger(__name__)

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent
INTEL_DIR = PROJECT_ROOT / "output" / "intel"
PID_DIR = PROJECT_ROOT / "logs"
DB_PATH = PROJECT_ROOT / "db" / "history.db"

# 읽을 JSON 파일 목록
INTEL_FILES = [
    "prices.json",
    "macro.json",
    "portfolio_summary.json",
    "alerts.json",
    "regime.json",
    "price_analysis.json",
    "engine_status.json",
    "opportunities.json",
    "screener_results.json",
    "news.json",
    "fundamentals.json",
    "supply_data.json",
    "holdings_proposal.json",
    "performance_report.json",
    "simulation_report.json",
    "sector_scores.json",
    "proactive_alerts.json",
    "correction_notes.json",
]

# 읽을 마크다운 파일 목록
MD_FILES = [
    "marcus-analysis.md",
    "cio-briefing.md",
    "daily_report.md",
]


def load_intel_data() -> dict:
    """output/intel/의 JSON 파일들을 로드하여 반환. 실패 시 빈 딕셔너리 반환."""
    result = {}
    for filename in INTEL_FILES:
        key = filename.replace(".json", "").replace("-", "_")
        filepath = INTEL_DIR / filename
        try:
            if filepath.exists():
                with filepath.open(encoding="utf-8") as f:
                    data = json.load(f)
                warnings = validate_json(filename, data)
                for w in warnings:
                    logger.warning(w)
                result[key] = data
            else:
                result[key] = {}
        except Exception as e:
            # graceful degradation: 개별 파일 실패 시 빈 딕셔너리
            print(f"[api] {filename} 로드 실패: {e}")
            result[key] = {}

    # 마크다운 파일도 포함
    for md_filename in MD_FILES:
        key = md_filename.replace(".md", "").replace("-", "_")
        result[key] = load_md_file(md_filename)

    # portfolio_summary를 prices.json 최신 가격으로 실시간 재계산
    if result.get("portfolio_summary") and result.get("prices"):
        try:
            result["portfolio_summary"] = refresh_portfolio_with_live_prices(
                result["portfolio_summary"], result["prices"]
            )
        except Exception as e:
            print(f"[api] portfolio 가격 갱신 실패: {e}")

    return result


def load_md_file(filename: str) -> str:
    """마크다운 파일 읽기. 없으면 빈 문자열 반환."""
    filepath = INTEL_DIR / filename
    try:
        if filepath.exists():
            with filepath.open(encoding="utf-8") as f:
                return f.read()
        return ""
    except Exception as e:
        print(f"[api] {filename} 로드 실패: {e}")
        return ""


def _pid_file(name: str) -> Path:
    """PID 파일 경로 반환."""
    return PID_DIR / f"{name}.pid"


def get_running_pid(name: str) -> int | None:
    """PID 파일을 확인해 실행 중인 프로세스 PID 반환. 없거나 죽었으면 None."""
    pid_path = _pid_file(name)
    try:
        if not pid_path.exists():
            return None
        pid = int(pid_path.read_text().strip())
        # 프로세스 생존 확인
        os.kill(pid, 0)
        return pid
    except (ValueError, ProcessLookupError, PermissionError, OSError):
        # 죽은 프로세스 → PID 파일 정리
        pid_path.unlink(missing_ok=True)
        return None


def _cleanup_pid_when_done(proc: subprocess.Popen, name: str) -> None:
    """데몬 스레드: 프로세스 종료 후 PID 파일 삭제 (좀비 방지)."""
    proc.wait()
    _pid_file(name).unlink(missing_ok=True)


def run_background(name: str, cmd: list) -> dict:
    """subprocess.Popen으로 백그라운드 실행, PID 파일 생성."""
    # 이미 실행 중이면 중복 실행 방지
    existing_pid = get_running_pid(name)
    if existing_pid:
        return {
            "ok": False,
            "error": f"이미 실행 중 (PID {existing_pid})",
            "pid": existing_pid,
        }

    try:
        # 로그 파일 경로 (소유자만 읽기/쓰기)
        log_path = PID_DIR / f"{name}.log"
        with log_path.open("a", encoding="utf-8") as log_f:
            os.chmod(log_path, 0o600)
            proc = subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                stdout=log_f,
                stderr=log_f,
                start_new_session=True,
            )
        # PID 파일 저장
        _pid_file(name).write_text(str(proc.pid))
        # 종료 시 PID 파일 자동 정리 (좀비 프로세스로 인한 뻥뻥이 방지)
        t = threading.Thread(target=_cleanup_pid_when_done, args=(proc, name), daemon=True)
        t.start()
        return {"ok": True, "pid": proc.pid, "name": name}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def load_log_tail(log_path: Path, lines: int = 80) -> dict:
    """로그 파일 마지막 N줄 반환."""
    if not log_path.exists():
        return {"lines": [], "exists": False}
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
        all_lines = text.splitlines()
        return {"lines": all_lines[-lines:], "exists": True, "total": len(all_lines)}
    except Exception as e:
        return {"lines": [f"로그 읽기 실패: {e}"], "exists": True}


def get_process_status() -> dict:
    """실행 중인 프로세스 상태 딕셔너리 반환."""
    processes = ["pipeline", "marcus"]
    status = {}
    for name in processes:
        pid = get_running_pid(name)
        status[name] = {"running": pid is not None, "pid": pid}
    return status


def load_analysis_history(limit: int = 30) -> list[dict]:
    """analysis_history 테이블에서 최신 N개 조회 (내용 제외 목록용)."""
    if not DB_PATH.exists():
        return []
    try:
        with get_db_conn() as conn:
            rows = conn.execute(
                """
                SELECT date, confidence_level, regime, regime as stance, today_call, created_at
                FROM analysis_history
                ORDER BY date DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[api] analysis_history 조회 실패: {e}")
        return []


def load_wealth_data(days: int = 60) -> dict:
    """전재산(투자 + 비금융 자산) 요약 데이터 반환."""
    import sys as _sys

    _sys.path.insert(0, str(PROJECT_ROOT))
    try:
        from db.ssot_wealth import get_extra_assets, get_total_wealth_history

        extra_assets = get_extra_assets()
        wealth_history = get_total_wealth_history(days=days)

        # 투자 포트폴리오 데이터 로드
        portfolio_path = INTEL_DIR / "portfolio_summary.json"
        portfolio_data = {}
        if portfolio_path.exists():
            with portfolio_path.open(encoding="utf-8") as f:
                portfolio_data = json.load(f)

        total_info = portfolio_data.get("total", {})
        investment_total = total_info.get("current_value_krw", 0)
        investment_pnl = total_info.get("pnl_krw", 0)
        investment_pnl_pct = total_info.get("pnl_pct", 0)

        extra_total = sum(a["current_value_krw"] for a in extra_assets)
        total_wealth = investment_total + extra_total
        monthly_recurring = sum(a.get("monthly_deposit_krw", 0) for a in extra_assets)

        last_updated = portfolio_data.get("updated_at")
        return {
            "total_wealth_krw": total_wealth,
            "investment_krw": investment_total,
            "investment_pnl_krw": investment_pnl,
            "investment_pnl_pct": investment_pnl_pct,
            "extra_assets_krw": extra_total,
            "monthly_recurring_krw": monthly_recurring,
            "extra_assets": extra_assets,
            "wealth_history": wealth_history,
            "last_updated": last_updated,
        }
    except Exception as e:
        print(f"[api] wealth 데이터 로드 실패: {e}")
        return {"error": str(e)}


def load_solar_listings(limit: int = 100) -> list[dict]:
    """solar_listings 테이블에서 최신 매물 조회"""
    if not DB_PATH.exists():
        return []
    try:
        with get_db_conn() as conn:
            rows = conn.execute(
                """
                SELECT source, listing_id, title, capacity_kw, location,
                       price_krw, deal_type, url, status, first_seen_at, last_seen_at
                FROM solar_listings
                ORDER BY first_seen_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[api] solar_listings 조회 실패: {e}")
        return []


def load_investment_assets() -> list[dict]:
    """investment_assets 테이블 전체 조회 (DB SSoT)."""
    try:
        with get_db_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM investment_assets ORDER BY category, risk_level"
            ).fetchall()
        return [
            {
                **dict(r),
                "leverage_available": bool(r["leverage_available"]),
                "beginner_friendly": bool(r["beginner_friendly"]),
            }
            for r in rows
        ]
    except Exception as e:
        print(f"[api] investment_assets 조회 실패: {e}")
        return []


def load_analysis_detail(date: str) -> dict | None:
    """특정 날짜의 전체 분석 내용 조회."""
    if not DB_PATH.exists():
        return None
    try:
        with get_db_conn() as conn:
            row = conn.execute("SELECT * FROM analysis_history WHERE date = ?", (date,)).fetchone()
        return dict(row) if row else None
    except Exception as e:
        print(f"[api] analysis_history 상세 조회 실패: {e}")
        return None


def load_health_status() -> dict:
    """health_check.json 로드 — 없으면 빈 결과 반환."""
    path = INTEL_DIR / "health_check.json"
    try:
        if path.exists():
            with path.open(encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[api] health_check.json 로드 실패: {e}")
    return {
        "checked_at": None,
        "summary": {"ok": 0, "warn": 0, "fail": 0, "total": 0},
        "results": [],
    }


def run_health_check_sync() -> dict:
    """health_check.py 동기 실행 후 최신 결과 반환 (새로고침 버튼용)."""
    try:
        subprocess.run(
            ["python3", str(PROJECT_ROOT / "scripts" / "health_check.py")],
            cwd=str(PROJECT_ROOT),
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        logger.warning("health_check.py 30초 초과 — 중간 결과 반환")
    except Exception as e:
        logger.error(f"health_check.py 실행 실패: {e}")
    return load_health_status()


def load_price_history(ticker: str, days: int = 30) -> list[dict]:
    """prices_daily 테이블에서 최근 N일 종가 이력 반환 (차트용)."""
    if not ticker:
        return []
    try:
        with get_db_conn() as conn:
            rows = conn.execute(
                """SELECT date, close FROM prices_daily
                   WHERE ticker = ?
                   ORDER BY date DESC LIMIT ?""",
                (ticker, days),
            ).fetchall()
        return [{"date": r["date"], "close": float(r["close"])} for r in reversed(rows)]
    except Exception as e:
        logger.error(f"[api] price_history 조회 실패 {ticker}: {e}")
        return []

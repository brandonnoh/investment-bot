#!/usr/bin/env python3
"""
미션컨트롤 API 로직
JSON 파일 로드, 프로세스 실행 관리
"""

import json
import os
import subprocess
from pathlib import Path

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent
INTEL_DIR = PROJECT_ROOT / "output" / "intel"
PID_DIR = PROJECT_ROOT / "logs"

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
                    result[key] = json.load(f)
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
        # 로그 파일 경로
        log_path = PID_DIR / f"{name}.log"
        with log_path.open("a", encoding="utf-8") as log_f:
            proc = subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                stdout=log_f,
                stderr=log_f,
                start_new_session=True,
            )
        # PID 파일 저장
        _pid_file(name).write_text(str(proc.pid))
        return {"ok": True, "pid": proc.pid, "name": name}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_process_status() -> dict:
    """실행 중인 프로세스 상태 딕셔너리 반환."""
    processes = ["pipeline", "marcus"]
    status = {}
    for name in processes:
        pid = get_running_pid(name)
        status[name] = {"running": pid is not None, "pid": pid}
    return status

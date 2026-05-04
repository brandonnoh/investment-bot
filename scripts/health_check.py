#!/usr/bin/env python3
"""
투자봇 자가진단 헬스체크 — 매일 09:00 KST 실행
모든 크론 잡 결과물·DB·API 상태를 점검하고 Discord로 보고한다.
"""

import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

KST = timezone(timedelta(hours=9))
PROJECT_ROOT = Path(__file__).resolve().parent.parent
INTEL_DIR = PROJECT_ROOT / "output" / "intel"
DB_PATH = PROJECT_ROOT / "db" / "history.db"
LOG_DIR = PROJECT_ROOT / "logs"

# 인증 에러 키워드 — 이 문자열이 포함된 MD는 유효하지 않음
_AUTH_ERROR_KEYWORDS = (
    "authentication_error",
    "Failed to authenticate",
    "API Error:",
    "Not logged in",
    "Please run /login",
)

# 최소 유효 파일 크기 (bytes)
_MIN_JSON_BYTES = 10
_MIN_MD_CHARS = 200

# Intel 파일별 최대 허용 경과 시간 (시간)
_INTEL_MAX_AGE: dict[str, int] = {
    "prices.json": 25,
    "macro.json": 25,
    "news.json": 25,
    "portfolio_summary.json": 25,
    "regime.json": 25,
    "price_analysis.json": 25,
    "engine_status.json": 25,
    "opportunities.json": 25,
    "screener_results.json": 25,
    "fundamentals.json": 25,
    "supply_data.json": 25,
    "holdings_proposal.json": 25,
    "performance_report.json": 25,
    "simulation_report.json": 25,
    "sector_scores.json": 25,
    "proactive_alerts.json": 25,
    "correction_notes.json": 25,
}

_MD_MIN_CHARS: dict[str, int] = {
    "marcus-analysis.md": _MIN_MD_CHARS,
    "cio-briefing.md": _MIN_MD_CHARS,
    "daily_report.md": _MIN_MD_CHARS,
}

# 크론 잡별 로그 파일 (평일 기준)
_DAILY_LOGS: list[tuple[str, str]] = [
    ("marcus", "marcus.log"),
    ("jarvis", "jarvis.log"),
    ("pipeline", "pipeline.log"),
    ("news", "news.log"),
    ("company_profiles", "company_profiles.log"),
    ("sync_r2", "sync_r2.log"),
]

# 매일 갱신되어야 하는 DB 테이블
_DAILY_DB_TABLES: list[tuple[str, str]] = [
    ("regime_history", "date"),
    ("sector_scores_history", "date"),
    ("correction_notes_history", "date"),
    ("performance_report_history", "date"),
]


# 파이프라인 단계 목록 (engine_status.json modules 키와 일치)
_PIPELINE_STEPS: list[str] = [
    "fetch_prices",
    "fetch_macro",
    "fetch_news",
    "classify_regime",
    "fetch_fundamentals",
    "fetch_supply",
    "sector_intel",
    "fetch_opportunities",
    "analyze_prices",
    "run_screener",
    "analyze_portfolio",
]

_PIPELINE_STEP_DESCS: dict[str, str] = {
    "fetch_prices": "주가 수집 — 보유 종목 + 주요 지수 (Yahoo/Kiwoom)",
    "fetch_macro": "매크로 지표 수집 — VIX, 환율, 원자재, 국채",
    "fetch_news": "뉴스 수집 — Brave Search + RSS 피드",
    "classify_regime": "시장 레짐 분류 — BULL/BEAR/RISK_OFF 판별",
    "fetch_fundamentals": "펀더멘탈 수집 — PER/PBR/ROE/부채비율 (DART + Naver)",
    "fetch_supply": "수급 데이터 수집 — 외국인·기관 순매수 + F&G 지수",
    "sector_intel": "섹터 인텔리전스 — 레짐별 섹터 점수 산출",
    "fetch_opportunities": "종목 발굴 — 퀀트·가치·기술 복합 스크리닝",
    "analyze_prices": "가격 분석 — RSI, 이동평균, 변동성 기술분석",
    "run_screener": "스크리너 실행 — B+ 이상 종목 필터링",
    "analyze_portfolio": "포트폴리오 분석 — 보유 종목 손익·섹터 비중 계산",
}


# 각 항목 한국어 설명
_DESCRIPTIONS: dict[str, str] = {
    # Intel JSON
    "prices.json": "실시간 주가 데이터 (보유 종목 + 주요 지수)",
    "macro.json": "매크로 지표 (VIX, 환율, 원자재, 국채 등)",
    "news.json": "최신 뉴스 수집 결과 (Brave/RSS)",
    "portfolio_summary.json": "포트폴리오 현황 + 손익 요약",
    "regime.json": "시장 레짐 분류 (BULL/BEAR/RISK_OFF 등)",
    "price_analysis.json": "기술 분석 결과 (RSI, 이평, 변동성)",
    "engine_status.json": "파이프라인 마지막 실행 상태",
    "opportunities.json": "퀀트 발굴 종목 목록 (전략별 점수)",
    "screener_results.json": "스크리너 통과 종목 (B+ 이상)",
    "fundamentals.json": "기업 펀더멘탈 (PER/PBR/ROE 등)",
    "supply_data.json": "수급 데이터 (외국인·기관 순매수)",
    "holdings_proposal.json": "AI 추천 비중 조정 안",
    "performance_report.json": "발굴 종목 성과 추적 리포트",
    "simulation_report.json": "포트폴리오 시뮬레이션 결과",
    "sector_scores.json": "섹터별 점수 및 레짐별 전략",
    "proactive_alerts.json": "선제적 이상 신호 알림 목록",
    "correction_notes.json": "자기교정 메모 (가중치 조정 기록)",
    # MD
    "marcus-analysis.md": "Marcus AI 시황 분석 (05:30 KST 생성)",
    "cio-briefing.md": "Jarvis CIO 브리핑 (07:30 KST 생성)",
    "daily_report.md": "일일 리포트 마크다운 (07:40 파이프라인 생성)",
    # DB
    "DB:regime_history": "레짐 분류 이력 테이블 — 오늘 날짜 레코드 존재 여부",
    "DB:sector_scores_history": "섹터 점수 이력 테이블 — 오늘 날짜 레코드",
    "DB:correction_notes_history": "자기교정 이력 테이블 — 오늘 날짜 레코드",
    "DB:performance_report_history": "성과 리포트 이력 테이블 — 오늘 날짜 레코드",
    # 크론 로그
    "cron:marcus": "Marcus AI 분석 크론 (평일 05:30 KST)",
    "cron:jarvis": "Jarvis CIO 브리핑 크론 (평일 07:30 KST)",
    "cron:pipeline": "전체 데이터 파이프라인 크론 (평일 07:40 KST)",
    "cron:news": "뉴스 수집 크론 (평일 08:00 KST)",
    "cron:company_profiles": "기업 프로필 수집 크론 (평일 08:10 KST)",
    "cron:sync_r2": "R2 스토리지 동기화 크론 (평일 07:50 KST)",
    # API
    "Flask API": "Flask 백엔드 서버 응답 상태 (포트 8421)",
    # 파이프라인 단계
    **{f"pipeline:{k}": v for k, v in _PIPELINE_STEP_DESCS.items()},
}

# 카테고리 매핑
_CATEGORIES: dict[str, str] = {
    **{k: "intel" for k in _INTEL_MAX_AGE},  # type: ignore[arg-type] — dict comprehension
    "marcus-analysis.md": "report",
    "cio-briefing.md": "report",
    "daily_report.md": "report",
    "DB:regime_history": "database",
    "DB:sector_scores_history": "database",
    "DB:correction_notes_history": "database",
    "DB:performance_report_history": "database",
    "cron:marcus": "cron",
    "cron:jarvis": "cron",
    "cron:pipeline": "cron",
    "cron:news": "cron",
    "cron:company_profiles": "cron",
    "cron:sync_r2": "cron",
    "Flask API": "service",
    **{f"pipeline:{k}": "pipeline" for k in _PIPELINE_STEPS},
}


@dataclass
class CheckResult:
    name: str
    status: str  # "ok" | "warn" | "fail"
    detail: str


# ── 개별 체크 함수 ────────────────────────────────────────────────────


def check_intel_file(path: Path, max_age_hours: int) -> CheckResult:
    """Intel 파일 존재 + 신선도 + 최소 크기 점검."""
    name = path.name
    if not path.exists():
        return CheckResult(name, "fail", "파일 없음")
    size = path.stat().st_size
    if size < _MIN_JSON_BYTES:
        return CheckResult(name, "fail", f"파일 크기 미달 ({size}B)")
    age_hours = (time.time() - path.stat().st_mtime) / 3600
    if age_hours > max_age_hours:
        return CheckResult(name, "warn", f"갱신 경과 {age_hours:.1f}시간 (기준 {max_age_hours}h)")
    return CheckResult(name, "ok", f"{age_hours:.1f}시간 전 갱신")


def check_md_content(path: Path, min_chars: int) -> CheckResult:
    """마크다운 파일 존재 + 인증 에러 미포함 + 최소 길이 점검."""
    name = path.name
    if not path.exists():
        return CheckResult(name, "fail", "파일 없음")
    content = path.read_text(encoding="utf-8", errors="replace")
    for kw in _AUTH_ERROR_KEYWORDS:
        if kw in content:
            return CheckResult(name, "fail", f"인증 에러 포함 ({kw})")
    if len(content) < min_chars:
        return CheckResult(name, "fail", f"내용 미달 ({len(content)}자 < {min_chars}자)")
    return CheckResult(name, "ok", f"{len(content)}자")


def check_db_today(db_path: Path, table: str, date_col: str) -> CheckResult:
    """DB 테이블에 오늘 날짜 레코드 존재 여부 점검."""
    today = datetime.now(KST).strftime("%Y-%m-%d")
    name = f"DB:{table}"
    try:
        with sqlite3.connect(str(db_path)) as conn:
            row = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {date_col} = ?", (today,)
            ).fetchone()
        count = row[0] if row else 0
        if count == 0:
            return CheckResult(name, "fail", f"오늘({today}) 레코드 없음")
        return CheckResult(name, "ok", f"오늘 {count}건")
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            return CheckResult(name, "warn", f"테이블 없음: {e}")
        return CheckResult(name, "fail", str(e))
    except Exception as e:
        return CheckResult(name, "fail", str(e))


def check_log_today(log_path: Path, job_name: str) -> CheckResult:
    """로그 파일이 오늘 수정됐는지 확인 (크론 잡 실행 여부 간접 확인)."""
    name = f"cron:{job_name}"
    if not log_path.exists():
        return CheckResult(name, "warn", "로그 파일 없음")
    age_hours = (time.time() - log_path.stat().st_mtime) / 3600
    if age_hours > 25:
        return CheckResult(name, "warn", f"마지막 실행 {age_hours:.1f}시간 전")
    return CheckResult(name, "ok", f"{age_hours:.1f}시간 전 실행")


def check_pipeline_step(modules: dict, step_name: str) -> CheckResult:
    """engine_status.json의 modules 딕셔너리에서 단계 성공/실패 확인."""
    name = f"pipeline:{step_name}"
    entry = modules.get(step_name)
    if entry is None:
        return CheckResult(name, "warn", "추적 데이터 없음 (미실행 또는 미등록)")
    if entry.get("success"):
        count = entry.get("item_count", 0)
        return CheckResult(name, "ok", f"{count}건 처리")
    error_msg = entry.get("error_msg", "")
    detail = f"실패: {error_msg}" if error_msg else "실패"
    return CheckResult(name, "fail", detail)


def check_api(url: str) -> CheckResult:
    """Flask API 엔드포인트 응답 여부 점검."""
    name = "Flask API"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "health-check/1.0"}, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return CheckResult(name, "ok", f"HTTP {resp.status}")
            return CheckResult(name, "warn", f"HTTP {resp.status}")
    except urllib.error.URLError as e:
        return CheckResult(name, "fail", f"연결 실패: {e.reason}")
    except Exception as e:
        return CheckResult(name, "fail", str(e))


# ── 전체 점검 ─────────────────────────────────────────────────────────


def run_all_checks(
    intel_dir: Path = INTEL_DIR,
    db_path: Path = DB_PATH,
    log_dir: Path = LOG_DIR,
    api_url: str = "http://localhost:8421/api/status",
) -> list[CheckResult]:
    """모든 점검 항목 실행 후 결과 목록 반환."""
    results: list[CheckResult] = []

    # Intel JSON 파일
    for fname, max_age in _INTEL_MAX_AGE.items():
        results.append(check_intel_file(intel_dir / fname, max_age))

    # 마크다운 파일
    for fname, min_chars in _MD_MIN_CHARS.items():
        results.append(check_md_content(intel_dir / fname, min_chars))

    # DB 일별 테이블
    for table, date_col in _DAILY_DB_TABLES:
        results.append(check_db_today(db_path, table, date_col))

    # 크론 잡 로그
    for job_name, log_fname in _DAILY_LOGS:
        results.append(check_log_today(log_dir / log_fname, job_name))

    # Flask API
    results.append(check_api(api_url))

    # 파이프라인 단계 (engine_status.json modules 딕셔너리)
    engine_status_path = intel_dir / "engine_status.json"
    modules: dict = {}
    if engine_status_path.exists():
        try:
            engine_data = json.loads(engine_status_path.read_text(encoding="utf-8"))
            modules = engine_data.get("modules", {})
        except (json.JSONDecodeError, OSError):
            pass
    for step_name in _PIPELINE_STEPS:
        results.append(check_pipeline_step(modules, step_name))

    return results


# ── 보고서 포맷 ───────────────────────────────────────────────────────


def format_report(results: list[CheckResult]) -> str:
    """Discord 전송용 헬스체크 요약 보고서 생성."""
    ok = [r for r in results if r.status == "ok"]
    warn = [r for r in results if r.status == "warn"]
    fail = [r for r in results if r.status == "fail"]

    now = datetime.now(KST).strftime("%m/%d %H:%M")
    lines = [
        f"🏥 헬스체크 {now} KST",
        f"OK: {len(ok)} / {len(results)}  ⚠️ {len(warn)}  ❌ {len(fail)}",
        "",
    ]

    # 실패 → 경고 → OK 순
    if fail:
        lines.append("❌ 실패")
        for r in fail:
            lines.append(f"  {r.name}: {r.detail}")
    if warn:
        lines.append("⚠️ 경고")
        for r in warn:
            lines.append(f"  {r.name}: {r.detail}")
    if ok and not fail and not warn:
        lines.append("✅ 모든 항목 정상")
    elif ok:
        ok_names = ", ".join(r.name for r in ok[:5])
        if len(ok) > 5:
            ok_names += f" 외 {len(ok) - 5}개"
        lines.append(f"✅ 정상: {ok_names}")

    return "\n".join(lines)


# ── Discord 전송 ──────────────────────────────────────────────────────


def _send_discord(message: str) -> None:
    """Discord Webhook으로 헬스체크 결과 전송."""
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not webhook:
        print("  ⚠️  DISCORD_WEBHOOK_URL 미설정 — Discord 전송 건너뜀")
        return
    try:
        payload = json.dumps({"content": message[:2000]}).encode("utf-8")
        req = urllib.request.Request(
            webhook,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "investment-bot/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status in (200, 204):
                print("  📡 Discord 전송 완료")
    except Exception as e:
        print(f"  ⚠️  Discord 전송 실패: {e}")


# ── .env 로드 ─────────────────────────────────────────────────────────


def _load_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


# ── 진입점 ────────────────────────────────────────────────────────────


def save_results_json(results: list[CheckResult]) -> None:
    """결과를 output/intel/health_check.json에 저장 — 웹 UI용."""
    ok = sum(1 for r in results if r.status == "ok")
    warn = sum(1 for r in results if r.status == "warn")
    fail = sum(1 for r in results if r.status == "fail")
    payload = {
        "checked_at": datetime.now(KST).isoformat(),
        "summary": {"ok": ok, "warn": warn, "fail": fail, "total": len(results)},
        "results": [
            {
                "name": r.name,
                "status": r.status,
                "detail": r.detail,
                "description": _DESCRIPTIONS.get(r.name, ""),
                "category": _CATEGORIES.get(r.name, "other"),
            }
            for r in results
        ],
    }
    out = INTEL_DIR / "health_check.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run() -> None:
    """헬스체크 실행 메인 함수."""
    _load_env()
    print("=== 투자봇 헬스체크 시작 ===")
    results = run_all_checks()

    fail_cnt = sum(1 for r in results if r.status == "fail")
    warn_cnt = sum(1 for r in results if r.status == "warn")
    ok_cnt = sum(1 for r in results if r.status == "ok")
    print(f"  결과: OK {ok_cnt} / WARN {warn_cnt} / FAIL {fail_cnt}")

    for r in results:
        icon = {"ok": "✅", "warn": "⚠️ ", "fail": "❌"}.get(r.status, "?")
        print(f"  {icon} {r.name}: {r.detail}")

    save_results_json(results)
    print("  💾 health_check.json 저장 완료")

    report = format_report(results)
    _send_discord(report)
    print("=== 헬스체크 종료 ===")


if __name__ == "__main__":
    run()

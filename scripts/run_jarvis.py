#!/usr/bin/env python3
"""
Jarvis 07:30 KST CIO 브리핑 실행기
launchd → 매일 07:30 KST 실행 (평일)
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── 경로 정의 ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent
INTEL_DIR = PROJECT_ROOT / "output" / "intel"
OUTPUT_FILE = INTEL_DIR / "cio-briefing.md"
CRON_PROMPT_PATH = PROJECT_ROOT / "docs" / "cron-prompt-phase4.md"

# Claude CLI 경로 자동 탐지
CLAUDE_BIN = shutil.which("claude") or "/Users/jarvis/.local/bin/claude"

# 도커 재시동 후 갱신된 Claude 인증 토큰 동기화용 경로
_CREDENTIALS_SRC = Path("/root/.claude-host/.credentials.json")
_CREDENTIALS_DST = Path("/root/.claude/.credentials.json")


def _sync_claude_credentials() -> None:
    """도커 재시동 후 갱신된 Claude 인증 토큰을 컨테이너 내부로 동기화."""
    if not _CREDENTIALS_SRC.exists():
        return
    try:
        import shutil as _shutil

        _shutil.copy2(str(_CREDENTIALS_SRC), str(_CREDENTIALS_DST))
        print("  ✅ Claude 인증 동기화 완료")
    except Exception as e:
        print(f"  ⚠️  Claude 인증 동기화 실패: {e}")


def _load_file(path: Path, label: str) -> str:
    """파일을 텍스트로 로드 (실패 시 빈 문자열)"""
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  ⚠️  {label} 로드 실패: {e}")
        return ""


def _load_news_json(path: Path, max_items: int = 20) -> str:
    """뉴스 JSON 최신 N개만 추출"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            items = data[:max_items]
        elif isinstance(data, dict):
            items = data.get("items", data.get("news", []))[:max_items]
        else:
            items = []
        return json.dumps(items, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠️  뉴스 JSON 로드 실패: {e}")
        return "[]"


def _run_realtime() -> str:
    """data/realtime.py 실행 후 stdout 반환"""
    try:
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "data" / "realtime.py")],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(PROJECT_ROOT),
        )
        output = result.stdout.strip()
        return output if output else "실시간 데이터 없음"
    except subprocess.TimeoutExpired:
        print("  ⚠️  realtime.py 타임아웃 (60초)")
        return "실시간 데이터 없음 (타임아웃)"
    except Exception as e:
        print(f"  ⚠️  realtime.py 실행 실패: {e}")
        return "실시간 데이터 없음"


def _build_prompt_with_data(cron_prompt: str) -> str:
    """
    cron-prompt-phase4.md의 파일 참조를 실제 데이터로 대체하여 프롬프트 조립.
    cat /path/to/file → 실제 파일 내용 인라인
    python3 /path/to/script → 실행 결과 인라인
    """
    # daily_report.md 대체
    daily_report_path = INTEL_DIR / "daily_report.md"
    daily_report = _load_file(daily_report_path, "daily_report.md")

    # macro.json 대체
    macro_json = _load_file(INTEL_DIR / "macro.json", "macro.json")

    # news.json 최신 20개 대체
    news_json = _load_news_json(INTEL_DIR / "news.json", max_items=20)

    # price_analysis.json 대체
    price_analysis_json = _load_file(INTEL_DIR / "price_analysis.json", "price_analysis.json")

    # realtime.py 실행 결과 대체
    realtime_output = _run_realtime()

    # 출력 지시 (실제 저장은 stdout 캡처로 수행)
    output_instruction = f"""
## 출력 지시
# 참고: Claude가 직접 파일을 저장할 필요 없음 — 이 스크립트가 stdout을 파일에 저장함
# 저장 경로: {OUTPUT_FILE}
분석 결과를 마크다운 형식으로 출력하세요. 아래 형식에 맞게 작성하세요:

# CIO 브리핑 — 오늘 날짜
**수집 시각:** HH:MM KST

## EXECUTIVE SUMMARY
> 리스크 온/오프 + 한줄 요약

이하 cron-prompt-phase4.md의 지시에 따라 STEP 2~7 형식으로 작성.
임원 보고서 스타일, 한국어.
"""

    # 실제 데이터를 인라인으로 삽입한 프롬프트 조립
    prompt = f"""{cron_prompt}

---

## 인라인 데이터 (자동 수집 — 파일 참조 대신 직접 삽입)

### 실시간 시세 (`python3 data/realtime.py`)
{realtime_output}

### 일일 리포트 (`daily_report.md`)
{daily_report}

### 매크로 지표 (`macro.json`)
{macro_json}

### 최신 뉴스 최근 20건 (`news.json`)
{news_json}

### 기술 분석 (`price_analysis.json`)
{price_analysis_json}

{output_instruction}
"""
    return prompt


def run():
    """자비스 CIO 브리핑 실행 메인 함수"""
    print("=== 자비스 CIO 브리핑 실행기 시작 ===")

    # ── STEP 1: cron-prompt-phase4.md 로드 ──
    print("[1/6] cron-prompt-phase4.md 로드...")
    cron_prompt = _load_file(CRON_PROMPT_PATH, "cron-prompt-phase4.md")
    if not cron_prompt:
        print("  ❌ cron-prompt-phase4.md 없음 — 중단")
        return

    # ── STEP 2: 데이터 인라인화 ──
    print("[2/6] 데이터 인라인 대체...")
    prompt = _build_prompt_with_data(cron_prompt)

    # ── STEP 3: Claude CLI 실행 ──
    _sync_claude_credentials()  # 도커 재시동 후 갱신 토큰 자동 반영
    print(f"[3/6] Claude CLI 실행 ({CLAUDE_BIN})...")
    claude_output = ""
    try:
        result = subprocess.run(
            [CLAUDE_BIN, "--print", "-p", "-"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(PROJECT_ROOT),
        )
        claude_output = result.stdout.strip()
        if result.returncode != 0 and not claude_output:
            error_msg = result.stderr[:300] if result.stderr else f"종료코드 {result.returncode}"
            print(f"  ❌ Claude 실행 오류: {error_msg}")
            return
        if result.stderr:
            print(f"  ℹ️  Claude stderr: {result.stderr[:200]}")
        print(f"  ✅ Claude 응답 수신 ({len(claude_output)}자)")
    except subprocess.TimeoutExpired:
        print("  ❌ Claude 실행 타임아웃 (300초)")
        return
    except Exception as e:
        print(f"  ❌ Claude 실행 실패: {e}")
        return

    # ── STEP 3.5: 응답 유효성 검증 ──
    MIN_VALID_RESPONSE = 200
    is_error_response = any(kw in claude_output for kw in ("authentication_error", "Not logged in", "Failed to authenticate", "API Error:"))
    if len(claude_output) < MIN_VALID_RESPONSE or is_error_response:
        print(f"  ❌ Claude 응답 불량 ({len(claude_output)}자) — 저장 차단: {claude_output[:100]}")
        return

    # ── STEP 4: 결과 저장 (stdout을 직접 파일에 저장) ──
    print("[4/6] CIO 브리핑 저장...")
    try:
        INTEL_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(claude_output, encoding="utf-8")
        print(f"  ✅ 저장 완료: {OUTPUT_FILE}")
    except Exception as e:
        print(f"  ❌ 파일 저장 실패: {e}")
        return

    # ── STEP 5: Discord 완료 알림 ──
    print("[5/6] Discord 완료 알림...")
    try:
        from scripts.discord_notify import notify_jarvis_complete

        notify_jarvis_complete(OUTPUT_FILE)
    except Exception as e:
        print(f"  ⚠️  Discord 알림 실패: {e}")

    print("[6/6] 완료")
    print("=== 자비스 CIO 브리핑 실행기 종료 ===")


if __name__ == "__main__":
    run()

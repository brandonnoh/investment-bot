#!/usr/bin/env python3
"""
Marcus 05:30 KST 분석 실행기
launchd → 매일 05:30 KST 실행 (평일)
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
OUTPUT_FILE = INTEL_DIR / "marcus-analysis.md"

# Claude CLI 경로 자동 탐지
CLAUDE_BIN = shutil.which("claude") or "/Users/jarvis/.local/bin/claude"

KST = timezone(timedelta(hours=9))


def _parse_analysis(content: str) -> dict:
    """마크다운에서 confidence_level, regime, today_call 추출"""
    # 확신 레벨: "(4/5)" 패턴
    confidence = None
    m = re.search(r"\((\d)/5\)", content)
    if m:
        confidence = int(m.group(1))
    elif (stars := content.count("★")) > 0:
        confidence = stars

    # 레짐: "## MARKET REGIME" 섹션 첫 줄
    regime = None
    m = re.search(r"## MARKET REGIME[^\n]*\n+([^\n]+)", content)
    if m:
        regime = m.group(1).strip()[:50]

    # TODAY'S CALL 섹션 전체
    today_call = None
    m = re.search(r"## TODAY'S CALL[^\n]*\n+([\s\S]+?)(?=\n## |\Z)", content)
    if m:
        today_call = m.group(1).strip()[:500]

    return {"confidence_level": confidence, "regime": regime, "today_call": today_call}


def _save_to_db(content: str) -> None:
    """분석 결과를 DB analysis_history 테이블에 저장 (일별 1행 UPSERT)"""
    try:
        db_path = PROJECT_ROOT / "db" / "history.db"
        parsed = _parse_analysis(content)
        today = datetime.now(KST).strftime("%Y-%m-%d")
        created_at = datetime.now(KST).isoformat()
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                """
                INSERT INTO analysis_history (date, content, confidence_level, regime, today_call, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    content=excluded.content,
                    confidence_level=excluded.confidence_level,
                    regime=excluded.regime,
                    today_call=excluded.today_call,
                    created_at=excluded.created_at
                """,
                (
                    today,
                    content,
                    parsed["confidence_level"],
                    parsed["regime"],
                    parsed["today_call"],
                    created_at,
                ),
            )
        print(f"  ✅ DB 저장 완료 ({today})")
    except Exception as e:
        print(f"  ⚠️  DB 저장 실패: {e}")


def _load_json(path: Path, label: str) -> str:
    """JSON 파일을 문자열로 로드 (실패 시 빈 객체 반환)"""
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  ⚠️  {label} 로드 실패: {e}")
        return "{}"


def _load_news_json(path: Path, max_items: int = 20) -> str:
    """뉴스 JSON에서 최신 N개만 추출"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # news.json이 리스트이거나 {"items": [...]} 구조 처리
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
    """data/realtime.py 실행 후 stdout 반환 (실패 시 대체 문자열)"""
    try:
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "data" / "realtime.py")],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(PROJECT_ROOT),
        )
        output = result.stdout.strip()
        if output:
            return output
        if result.returncode != 0:
            print(f"  ⚠️  realtime.py 오류: {result.stderr[:200]}")
        return "실시간 데이터 없음"
    except subprocess.TimeoutExpired:
        print("  ⚠️  realtime.py 타임아웃 (60초)")
        return "실시간 데이터 없음 (타임아웃)"
    except Exception as e:
        print(f"  ⚠️  realtime.py 실행 실패: {e}")
        return "실시간 데이터 없음"


def _assemble_prompt(
    soul_md: str,
    prompt_md: str,
    realtime_output: str,
    engine_status: str,
    price_analysis: str,
    fundamentals: str,
    supply_data: str,
    portfolio_summary: str,
    macro: str,
    news: str,
    opportunities: str,
) -> str:
    """마커스 분석용 프롬프트 조립"""
    return f"""{soul_md}

---

{prompt_md}

---

## 현재 데이터 (자동 수집)

### 실시간 시세
{realtime_output}

### 엔진 상태
{engine_status}

### 기술 분석
{price_analysis}

### 펀더멘털
{fundamentals}

### 수급 데이터
{supply_data}

### 포트폴리오 요약
{portfolio_summary}

### 매크로 지표
{macro}

### 최신 뉴스 (최근 20건)
{news}

### 발굴 기회
{opportunities}

출력 파일: {OUTPUT_FILE}
위 형식에 맞게 분석 결과를 작성하세요.
"""


def _send_failure_alert(error_msg: str) -> None:
    """Claude 실행 실패 시 Discord 알림"""
    try:
        import json as _json
        import os
        import urllib.request as _urllib

        webhook = os.environ.get(
            "DISCORD_WEBHOOK_URL",
            "https://discord.com/api/webhooks/1490306786870165624/0JjO5i_BNWCmIDnFJXQZ0OcDGeWdYsryKnUFGXvoKlqALza6mFPqcjbFz40fWltCIkRR",
        )
        payload = _json.dumps({"content": f"❌ 마커스 분석 실패: {error_msg}"}).encode("utf-8")
        req = _urllib.Request(
            webhook,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "investment-bot/1.0"},
            method="POST",
        )
        _urllib.urlopen(req, timeout=15)
    except Exception:
        pass


def run():
    """마커스 분석 실행 메인 함수"""
    print("=== 마커스 분석 실행기 시작 ===")

    # ── STEP 1: JSON 데이터 로드 ──
    print("[1/9] JSON 데이터 로드...")
    engine_status = _load_json(INTEL_DIR / "engine_status.json", "engine_status")
    price_analysis = _load_json(INTEL_DIR / "price_analysis.json", "price_analysis")
    fundamentals = _load_json(INTEL_DIR / "fundamentals.json", "fundamentals")
    supply_data = _load_json(INTEL_DIR / "supply_data.json", "supply_data")
    portfolio_summary = _load_json(INTEL_DIR / "portfolio_summary.json", "portfolio_summary")
    macro = _load_json(INTEL_DIR / "macro.json", "macro")
    news = _load_news_json(INTEL_DIR / "news.json", max_items=20)
    opportunities = _load_json(INTEL_DIR / "opportunities.json", "opportunities")

    # ── STEP 2: 실시간 데이터 수집 ──
    print("[2/9] 실시간 시세 수집...")
    realtime_output = _run_realtime()

    # ── STEP 3: SOUL.md + prompt.md 읽기 ──
    print("[3/9] 마커스 페르소나 로드...")
    soul_path = PROJECT_ROOT / "docs" / "marcus" / "SOUL.md"
    prompt_path = PROJECT_ROOT / "docs" / "marcus" / "prompt.md"

    soul_md = ""
    try:
        soul_md = soul_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  ⚠️  SOUL.md 로드 실패: {e}")

    prompt_md = ""
    try:
        prompt_md = prompt_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  ⚠️  prompt.md 로드 실패: {e}")

    # ── STEP 4: 프롬프트 조립 ──
    print("[4/9] 프롬프트 조립...")
    prompt = _assemble_prompt(
        soul_md=soul_md,
        prompt_md=prompt_md,
        realtime_output=realtime_output,
        engine_status=engine_status,
        price_analysis=price_analysis,
        fundamentals=fundamentals,
        supply_data=supply_data,
        portfolio_summary=portfolio_summary,
        macro=macro,
        news=news,
        opportunities=opportunities,
    )

    # ── STEP 5: Claude CLI 실행 ──
    print(f"[5/9] Claude CLI 실행 ({CLAUDE_BIN})...")
    claude_output = ""
    try:
        result = subprocess.run(
            [CLAUDE_BIN, "--dangerously-skip-permissions", "--print", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(PROJECT_ROOT),
        )
        claude_output = result.stdout.strip()
        if result.returncode != 0 and not claude_output:
            error_msg = result.stderr[:300] if result.stderr else f"종료코드 {result.returncode}"
            print(f"  ❌ Claude 실행 오류: {error_msg}")
            _send_failure_alert(error_msg)
            return
        if result.stderr:
            print(f"  ℹ️  Claude stderr: {result.stderr[:200]}")
        print(f"  ✅ Claude 응답 수신 ({len(claude_output)}자)")
    except subprocess.TimeoutExpired:
        msg = "Claude 실행 타임아웃 (300초)"
        print(f"  ❌ {msg}")
        _send_failure_alert(msg)
        return
    except Exception as e:
        msg = str(e)
        print(f"  ❌ Claude 실행 실패: {msg}")
        _send_failure_alert(msg)
        return

    # ── STEP 6: 결과 저장 ──
    print("[6/9] 분석 결과 저장...")
    try:
        INTEL_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(claude_output, encoding="utf-8")
        print(f"  ✅ 저장 완료: {OUTPUT_FILE}")
    except Exception as e:
        print(f"  ❌ 파일 저장 실패: {e}")
        _send_failure_alert(f"파일 저장 실패: {e}")
        return

    # ── STEP 6.5: DB 저장 ──
    _save_to_db(claude_output)

    # ── STEP 7: marcus_analysis.py 검증 ──
    print("[7/9] 출력 형식 검증...")
    try:
        subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "marcus_analysis.py")],
            cwd=str(PROJECT_ROOT),
            timeout=30,
        )
    except Exception as e:
        print(f"  ⚠️  검증 스크립트 오류: {e}")

    # ── STEP 8: Discord 완료 알림 ──
    print("[8/9] Discord 완료 알림...")
    try:
        from scripts.discord_notify import notify_marcus_complete

        notify_marcus_complete(OUTPUT_FILE)
    except Exception as e:
        print(f"  ⚠️  Discord 알림 실패: {e}")

    print("[9/9] 완료")
    print("=== 마커스 분석 실행기 종료 ===")


if __name__ == "__main__":
    run()

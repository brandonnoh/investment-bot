#!/usr/bin/env python3
"""
Marcus 05:30 KST 분석 실행기
launchd → 매일 05:30 KST 실행 (평일)
"""

import json
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
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
    yesterday_analysis: str = "",
) -> str:
    """마커스 분석용 프롬프트 조립"""
    yesterday_section = (
        f"\n### 어제 분석 (변화 감지용)\n{yesterday_analysis}\n" if yesterday_analysis else ""
    )
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
{yesterday_section}
텍스트만 stdout에 출력하세요. 파일 저장·도구 사용 금지.
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


def _build_keyword_prompt(analysis_snippet: str) -> str:
    """뉴스 추적용 검색 키워드 프롬프트"""
    today = datetime.now(KST).strftime("%Y-%m-%d")
    return (
        "다음 분석 결과를 바탕으로, 오늘 추가로 수집해야 할 뉴스 검색 키워드 8개를 "
        "JSON으로만 출력해.\n"
        f'형식: {{"date": "{today}", "keywords": ["키워드1", ...], '
        '"reason": "왜 이 키워드들이 중요한지 한줄"}\n\n'
        f"분석:\n{analysis_snippet}"
    )


def _build_discovery_prompt(analysis_snippet: str) -> str:
    """종목 발굴용 Brave 검색 키워드 프롬프트"""
    ts = datetime.now(KST).isoformat()
    return (
        "다음 시장 분석을 보고, 현재 보유하지 않은 새로운 투자 기회를 찾기 위한 "
        "Brave 검색 키워드 4~5개를 JSON으로만 출력해.\n"
        "기존 보유 종목(삼성전자, 현대차, 테슬라 등) 관련 키워드는 제외하고, "
        "오늘 시장 상황에서 새롭게 주목할 만한 섹터·테마·종목군에 집중해.\n\n"
        "형식:\n"
        '{"generated_at": "' + ts + '", "source": "marcus", '
        '"keywords": ['
        '{"keyword": "검색어", "category": "sector|macro|theme|geopolitics|fx", "priority": 1}'
        "]}\n\n"
        f"분석:\n{analysis_snippet}"
    )


def _extract_claude_result(raw: str) -> str:
    """--output-format json 출력에서 result 필드 추출. 훅 노이즈 제거."""
    # stdout에서 마지막 JSON 객체 탐색 (훅 출력이 앞에 섞일 수 있음)
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if line.startswith("{") and '"result"' in line:
            try:
                return json.loads(line).get("result", "")
            except json.JSONDecodeError:
                pass
    # fallback: result 키 없으면 원문 그대로
    return raw


def _parse_keyword_json(raw: str) -> dict | None:
    """Claude 응답에서 JSON 블록 추출 및 파싱"""
    # ```json ... ``` 블록 또는 { ... } 직접 파싱
    m = re.search(r"\{[\s\S]*\"keywords\"[\s\S]*\}", raw)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _call_claude_json(prompt: str, timeout: int = 60) -> dict | None:
    """Claude CLI 호출 후 JSON 파싱. 실패 시 None."""
    try:
        result = subprocess.run(
            [CLAUDE_BIN, "--dangerously-skip-permissions", "--output-format", "json", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        raw = _extract_claude_result(result.stdout.strip())
        return _parse_keyword_json(raw)
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None


def _generate_search_keywords(analysis: str, macro: str, portfolio: str) -> None:
    """뉴스 추적용 동적 검색 키워드 생성 → search_keywords.json"""
    print("  🔑 동적 검색 키워드 생성 중...")
    parsed = _call_claude_json(_build_keyword_prompt(analysis[:500]))
    if not parsed or "keywords" not in parsed:
        print("  ⚠️  검색 키워드 생성 실패")
        return
    parsed["date"] = datetime.now(KST).strftime("%Y-%m-%d")
    out_path = INTEL_DIR / "search_keywords.json"
    out_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✅ 검색 키워드 {len(parsed['keywords'])}개 저장")


def _generate_discovery_keywords(analysis: str) -> None:
    """종목 발굴용 AI 키워드 생성 → discovery_keywords.json"""
    print("  🔍 종목 발굴 키워드 생성 중...")
    parsed = _call_claude_json(_build_discovery_prompt(analysis[:500]))
    if not parsed or "keywords" not in parsed:
        print("  ⚠️  발굴 키워드 생성 실패 (fallback 유지)")
        return
    parsed["generated_at"] = datetime.now(KST).isoformat()
    parsed["source"] = "marcus"
    out_path = INTEL_DIR / "discovery_keywords.json"
    out_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    kws = [k["keyword"] for k in parsed["keywords"][:3]]
    print(f"  ✅ 발굴 키워드 {len(parsed['keywords'])}개 저장: {kws}")


def _load_yesterday_analysis() -> str:
    """어제 분석 내용 로드 — Marcus가 변화를 감지할 수 있도록"""
    try:
        db_path = PROJECT_ROOT / "db" / "history.db"
        if not db_path.exists():
            return ""
        with sqlite3.connect(str(db_path)) as conn:
            row = conn.execute(
                "SELECT date, content FROM analysis_history ORDER BY date DESC LIMIT 2"
            ).fetchall()
        # 가장 최근 = 오늘(방금 저장 전이므로 사실상 어제), 두 번째 = 그 전날
        if len(row) >= 1:
            return f"[{row[0][0]} 분석]\n{row[0][1][:800]}"
        return ""
    except Exception:
        return ""


def run():
    """마커스 분석 실행 메인 함수"""
    print("=== 마커스 분석 실행기 시작 ===")

    # ── STEP 1: JSON 데이터 로드 ──
    print("[1/9] JSON 데이터 로드...")
    yesterday_analysis = _load_yesterday_analysis()
    if yesterday_analysis:
        print(f"  ✅ 어제 분석 로드 ({len(yesterday_analysis)}자)")
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
        yesterday_analysis=yesterday_analysis,
    )

    # ── STEP 5: Claude CLI 실행 ──
    print(f"[5/9] Claude CLI 실행 ({CLAUDE_BIN})...")
    claude_output = ""
    try:
        result = subprocess.run(
            [CLAUDE_BIN, "--dangerously-skip-permissions", "--output-format", "json", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(PROJECT_ROOT),
        )
        # --output-format json → stdout에 훅 노이즈가 섞여도 마지막 JSON 객체에서 result 추출
        raw = result.stdout.strip()
        claude_output = _extract_claude_result(raw)
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

    # ── STEP 6.3: 뉴스 추적용 동적 검색 키워드 생성 ──
    _generate_search_keywords(claude_output, macro, portfolio_summary)

    # ── STEP 6.4: 종목 발굴용 동적 키워드 생성 ──
    _generate_discovery_keywords(claude_output)

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

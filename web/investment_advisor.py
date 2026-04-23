#!/usr/bin/env python3
"""
투자 어드바이저 API 로직
Claude API/CLI를 사용한 맞춤형 투자 포트폴리오 추천
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
INTEL_DIR = PROJECT_ROOT / "output" / "intel"

# 리스크 레벨 라벨 매핑
_RISK_LABELS = {
    1: "매우 보수적",
    2: "보수적",
    3: "중립",
    4: "공격적",
    5: "매우 공격적",
}

# Claude CLI 경로
CLAUDE_BIN = shutil.which("claude") or "/Users/jarvis/.local/bin/claude"


def _load_market_context() -> str:
    """시장 컨텍스트 로드 (macro.json + daily_report.md 앞 500자)."""
    parts = []

    # macro.json 로드
    macro_path = INTEL_DIR / "macro.json"
    if macro_path.exists():
        try:
            data = json.loads(macro_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                lines = [f"- {m.get('name', '')}: {m.get('value', '')} ({m.get('change_pct', '')}%)" for m in data[:10]]
                parts.append("### 주요 매크로 지표\n" + "\n".join(lines))
            elif isinstance(data, dict):
                parts.append(f"### 매크로 데이터\n{json.dumps(data, ensure_ascii=False)[:400]}")
        except Exception:
            pass

    # daily_report.md 로드 (앞 500자)
    report_path = INTEL_DIR / "daily_report.md"
    if report_path.exists():
        try:
            content = report_path.read_text(encoding="utf-8")[:500]
            parts.append(f"### 최신 일일 리포트 (요약)\n{content}")
        except Exception:
            pass

    return "\n\n".join(parts) if parts else "(시장 데이터 로드 불가)"


def _build_prompt(capital: int, leverage: bool, risk_level: int, available_assets: list[str]) -> str:
    """Claude에 전달할 프롬프트 구성."""
    capital_억 = capital / 100_000_000
    risk_label = _RISK_LABELS.get(risk_level, "중립")
    macro_context = _load_market_context()
    leverage_text = "예" if leverage else "아니오"
    assets_text = ", ".join(available_assets) if available_assets else "미확인"

    return f"""당신은 한국 개인 투자자를 위한 전문 투자 어드바이저입니다.

## 투자자 조건
- 가용 자본금: {capital:,}원 ({capital_억:.1f}억원)
- 레버리지 활용: {leverage_text}
- 리스크 성향: {risk_level}/5 ({risk_label})
- 현재 조건에서 접근 가능한 자산: {assets_text}

## 현재 시장 환경 (2026년 4월)
{macro_context}

## 요청
위 조건에 맞는 투자 포트폴리오 배분과 핵심 전략을 한국어로 300자 이내로 작성해줘.
형식: 자산1 X% + 자산2 Y% + ... 배분 제안 + 2~3줄 근거"""


def _call_claude_api(prompt: str) -> str:
    """anthropic 패키지로 Claude API 호출."""
    import anthropic

    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def _call_claude_cli(prompt: str) -> str:
    """Claude CLI subprocess로 호출."""
    result = subprocess.run(
        [CLAUDE_BIN, "--print", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI 실패: {result.stderr[:200]}")
    return result.stdout.strip()


def _call_claude(prompt: str) -> str:
    """Claude 호출 (API 우선, CLI 폴백)."""
    # anthropic 패키지 시도
    try:
        return _call_claude_api(prompt)
    except ImportError:
        pass
    except Exception as e:
        print(f"[advisor] anthropic API 실패, CLI 폴백: {e}")

    # CLI 폴백
    return _call_claude_cli(prompt)


def _parse_request(body: dict) -> tuple[int, bool, int, list[str]]:
    """요청 파라미터 파싱 및 검증."""
    capital = int(body.get("capital", 0))
    if capital < 0:
        capital = 0

    leverage = bool(body.get("leverage", False))

    risk_level = int(body.get("risk_level", 3))
    risk_level = max(1, min(5, risk_level))

    available_assets = body.get("available_assets", [])
    if not isinstance(available_assets, list):
        available_assets = []

    return capital, leverage, risk_level, available_assets


def get_investment_advice(body: dict) -> dict:
    """투자 어드바이스 생성 — 메인 핸들러."""
    try:
        capital, leverage, risk_level, assets = _parse_request(body)
    except (TypeError, ValueError):
        capital, leverage, risk_level, assets = 0, False, 3, []

    prompt = _build_prompt(capital, leverage, risk_level, assets)

    try:
        recommendation = _call_claude(prompt)
        return {"recommendation": recommendation}
    except Exception as e:
        print(f"[advisor] Claude 호출 실패: {e}")
        return {
            "recommendation": "AI 분석 일시 불가. 잠시 후 다시 시도해주세요.",
            "error": True,
        }

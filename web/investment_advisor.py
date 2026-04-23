#!/usr/bin/env python3
"""
투자 어드바이저 API 로직
Claude에게 접근 가능한 자산 전체 데이터를 넘겨 구체적 투자 전략을 생성.
"""

import json
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
INTEL_DIR = PROJECT_ROOT / "output" / "intel"

_RISK_LABELS = {
    1: "매우 보수적 (원금 보존 최우선)",
    2: "보수적 (안정 수익 추구)",
    3: "중립 (수익·리스크 균형)",
    4: "공격적 (고수익 추구, 변동성 감내)",
    5: "매우 공격적 (최대 수익 추구, 손실 감내)",
}

CLAUDE_BIN = shutil.which("claude") or "/Users/jarvis/.local/bin/claude"


def _load_market_context() -> str:
    """시장 컨텍스트 로드 (macro.json + daily_report.md 앞 800자)."""
    parts = []
    macro_path = INTEL_DIR / "macro.json"
    if macro_path.exists():
        try:
            data = json.loads(macro_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                lines = [
                    f"- {m.get('name', '')}: {m.get('value', '')} (변동 {m.get('change_pct', '')}%)"
                    for m in data[:12]
                ]
                parts.append("### 주요 매크로 지표\n" + "\n".join(lines))
            elif isinstance(data, dict):
                parts.append(f"### 매크로 데이터\n{json.dumps(data, ensure_ascii=False)[:600]}")
        except Exception:
            pass

    report_path = INTEL_DIR / "daily_report.md"
    if report_path.exists():
        try:
            content = report_path.read_text(encoding="utf-8")[:800]
            parts.append(f"### 최신 일일 리포트 (요약)\n{content}")
        except Exception:
            pass

    return "\n\n".join(parts) if parts else "(시장 데이터 없음)"


def _format_asset_table(assets: list[dict]) -> str:
    """자산 목록을 Claude가 읽기 쉬운 텍스트 표로 변환."""
    if not assets:
        return "(접근 가능한 자산 없음)"

    lines = ["| 자산명 | 최소자본 | 기대수익(연) | 리스크 | 레버리지 | 세제혜택 | 주의 |"]
    lines.append("|--------|---------|------------|------|---------|---------|------|")

    for a in assets:
        min_cap = a.get("min_capital", 0)
        min_cap_str = f"{min_cap // 10000}만" if min_cap < 100_000_000 else f"{min_cap / 100_000_000:.1f}억"
        ret_min = a.get("expected_return_min", 0)
        ret_max = a.get("expected_return_max", 0)
        risk = a.get("risk_level", 0)
        lev = a.get("leverage_type") or ("가능" if a.get("leverage_available") else "불가")
        tax = a.get("tax_benefit") or "-"
        caution = a.get("caution") or a.get("regulation_note") or "-"

        lines.append(
            f"| {a.get('name', '')} | {min_cap_str} | {ret_min}~{ret_max}% | {risk}/5 | {lev} | {tax} | {caution[:20] if caution != '-' else '-'} |"
        )

    return "\n".join(lines)


def _build_prompt(capital: int, leverage: bool, risk_level: int, assets: list[dict]) -> str:
    """구체적 투자 전략 요청 프롬프트 구성."""
    capital_억 = capital / 100_000_000
    capital_str = f"{capital_억:.1f}억원" if capital >= 100_000_000 else f"{capital // 10000:,}만원"
    risk_label = _RISK_LABELS.get(risk_level, "중립")
    macro_context = _load_market_context()
    leverage_text = "활용 가능 (대출·신용·담보 고려 가능)" if leverage else "활용 안 함 (자기자본만 사용)"
    asset_table = _format_asset_table(assets)

    return f"""당신은 한국 개인 투자자를 위한 전문 투자 어드바이저입니다.

## 투자자 조건
- 가용 자본금: {capital:,}원 ({capital_str})
- 레버리지: {leverage_text}
- 리스크 성향: {risk_level}/5 ({risk_label})

## 현재 접근 가능한 투자처 (자동 스크리닝 결과)

{asset_table}

## 현재 시장 환경 (2026년 4월)
{macro_context}

## 요청 (중요)
위 투자자 조건과 접근 가능한 투자처 데이터를 바탕으로, **구체적인 투자 전략**을 작성해주세요.

반드시 포함할 내용:
1. **자산별 투자 금액** — "X자산에 YY만원 (총 자본의 Z%)" 형식으로 구체적 금액 명시
2. **레버리지 활용 시** — 어떤 자산에 얼마를 대출하고, 예상 이자는 얼마인지
3. **예상 연 수익률** — 보수적/기대/낙관 시나리오별로
4. **월 현금흐름** — 배당·임대·이자수익 등 월 수령 예상액
5. **실행 순서** — 어떤 것부터 시작하면 좋은지 우선순위

현실적이고 구체적인 수치로 작성하세요. 한국어로 답변."""


def _call_claude_cli(prompt: str) -> str:
    """Claude CLI stdin으로 호출 (ARG_MAX 방지)."""
    result = subprocess.run(
        [CLAUDE_BIN, "--dangerously-skip-permissions", "--print", "-p", "-"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0 and not result.stdout.strip():
        raise RuntimeError(f"Claude CLI 실패: {result.stderr[:200]}")
    return result.stdout.strip()


def _call_claude(prompt: str) -> str:
    """Claude 호출 (API 우선, CLI 폴백)."""
    try:
        import anthropic
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except ImportError:
        pass
    except Exception as e:
        print(f"[advisor] anthropic API 실패, CLI 폴백: {e}")

    return _call_claude_cli(prompt)


def _parse_request(body: dict) -> tuple[int, bool, int, list[dict]]:
    """요청 파싱 및 검증."""
    capital = max(0, int(body.get("capital", 0)))
    leverage = bool(body.get("leverage", False))
    risk_level = max(1, min(5, int(body.get("risk_level", 3))))
    assets = body.get("available_assets", [])
    if not isinstance(assets, list):
        assets = []
    return capital, leverage, risk_level, assets


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

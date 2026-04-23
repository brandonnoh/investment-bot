#!/usr/bin/env python3
"""
투자 어드바이저 API 로직
Claude에게 접근 가능한 자산 전체 데이터를 넘겨 구체적 투자 전략을 생성.
"""

import json
import os
import shutil
import subprocess
import urllib.request
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

CLAUDE_BIN = shutil.which("claude") or "/usr/local/bin/claude"


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
        min_cap_str = (
            f"{min_cap // 10000}만" if min_cap < 100_000_000 else f"{min_cap / 100_000_000:.1f}억"
        )
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


def _build_prompt(capital: int, leverage_amt: int, risk_level: int, assets: list[dict]) -> str:
    """구체적 투자 전략 요청 프롬프트 구성."""
    capital_str = (
        f"{capital / 100_000_000:.1f}억원"
        if capital >= 100_000_000
        else f"{capital // 10000:,}만원"
    )
    risk_label = _RISK_LABELS.get(risk_level, "중립")
    macro_context = _load_market_context()
    if leverage_amt > 0:
        lev_str = (
            f"{leverage_amt / 100_000_000:.1f}억원"
            if leverage_amt >= 100_000_000
            else f"{leverage_amt // 10000:,}만원"
        )
        total_str = f"{(capital + leverage_amt) / 100_000_000:.1f}억원"
        leverage_text = f"활용 ({lev_str} 대출, 총 투자금 {total_str})"
    else:
        leverage_text = "활용 안 함 (자기자본만 사용)"
    asset_table = _format_asset_table(assets)

    return f"""당신은 "민준"이라는 이름의 한국인 투자 고수입니다.
30대 후반, 10년 넘게 직접 투자해온 경험자. 부동산·주식·대체투자를 두루 거쳤고,
레버리지로 자산을 불려본 경험이 있습니다. 말투는 직설적이고 솔직하며,
"나라면 이렇게 한다"는 식으로 자신의 의견을 강하게 밝힙니다.
투자 원칙: 현금흐름 먼저, 시세차익은 보너스. 레버리지는 도구일 뿐 목적이 아님.

---

## 이 투자자의 현재 조건
- 시드머니: {capital:,}원 ({capital_str})
- 레버리지: {leverage_text}
- 리스크 성향: {risk_level}/5 ({risk_label})

## 지금 이 돈으로 접근 가능한 투자처

{asset_table}

## 현재 시장 환경 (2026년 4월)
{macro_context}

---

## 민준이 해야 할 일

민준 본인이 이 시드머니를 갖고 있다고 가정하고, **단계별 자산 증식 로드맵**을 직접 짜주세요.

형식:
- "나라면 이렇게 한다"는 1인칭 직설 어투
- **1단계 / 2단계 / 3단계**로 시간축 구분 (각 단계별 기간 명시)
- 각 단계마다:
  - 어떤 자산에 얼마를 투자하는지 (구체적 금액)
  - 레버리지를 썼다면 **거치기간(이자만 납부)과 원리금 상환기간을 반드시 구분**:
    - 거치기간(예: 1~2년): 월 이자 부담 얼마, 그 기간에 남은 현금으로 뭘 더 하는지
    - 원리금 상환기간: 월 원리금 얼마, 현금흐름이 줄어드니 포트폴리오를 어떻게 조정하는지
  - 그 기간이 끝나면 총자산이 얼마가 되는지
  - 다음 단계로 어떻게 전환하는지 (매도·재투자·추가 레버리지·상환 등)
- 마지막에 최종 목표 자산 규모와 월 현금흐름 제시

레버리지가 없을 때도 "만약 여기서 신용대출 X원을 거치 1년으로 끊는다면" 같은 선택지를 한 줄 언급해줘.
현실적인 수치로, 솔직하게. 한국어로."""


def _call_claude_api(prompt: str) -> str:
    """Anthropic API를 urllib으로 직접 호출 (API 키 있을 때)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY 없음")

    payload = json.dumps(
        {
            "model": "claude-sonnet-4-6",
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=240) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["content"][0]["text"].strip()


def _call_claude_cli(prompt: str) -> str:
    """Claude CLI stdin으로 호출 (OAuth 인증 사용, 퍼미션 플래그 불필요)."""
    result = subprocess.run(
        [CLAUDE_BIN, "--print", "-p", "-"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=240,
    )
    if result.returncode != 0 and not result.stdout.strip():
        raise RuntimeError(f"Claude CLI 실패: {result.stderr[:300]}")
    return result.stdout.strip()


def _call_claude(prompt: str) -> str:
    """Claude 호출 (API 키 우선, CLI 폴백)."""
    try:
        return _call_claude_api(prompt)
    except RuntimeError:
        pass
    except Exception as e:
        print(f"[advisor] API 호출 실패, CLI 폴백: {e}")

    return _call_claude_cli(prompt)


def _parse_request(body: dict) -> tuple[int, int, int, list[dict]]:
    """요청 파싱 및 검증."""
    capital = max(0, int(body.get("capital", 0)))
    leverage_amt = max(0, int(body.get("leverage_amt", 0)))
    risk_level = max(1, min(5, int(body.get("risk_level", 3))))
    assets = body.get("available_assets", [])
    if not isinstance(assets, list):
        assets = []
    return capital, leverage_amt, risk_level, assets


def get_investment_advice(body: dict) -> dict:
    """투자 어드바이스 생성 — 메인 핸들러."""
    try:
        capital, leverage_amt, risk_level, assets = _parse_request(body)
    except (TypeError, ValueError):
        capital, leverage_amt, risk_level, assets = 0, 0, 3, []

    prompt = _build_prompt(capital, leverage_amt, risk_level, assets)

    try:
        recommendation = _call_claude(prompt)
        return {"recommendation": recommendation}
    except Exception as e:
        print(f"[advisor] Claude 호출 실패: {e}")
        return {
            "recommendation": "AI 분석 일시 불가. 잠시 후 다시 시도해주세요.",
            "error": True,
        }

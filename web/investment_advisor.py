#!/usr/bin/env python3
"""투자 어드바이저 API 로직 — system/user 분리, XML 구조, prompt caching."""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from web.advisor_data import (
    _format_asset_table,
    _load_assets_from_db,
    _load_market_context,
    _load_portfolio,
)
from web.claude_caller import call_claude, stream_via_api, stream_via_cli, sync_credentials
from web.loan_math import format_loans

_RISK_LABELS = {
    1: "매우 보수적 (원금 보존 최우선)",
    2: "보수적 (안정 수익 추구)",
    3: "중립 (수익·리스크 균형)",
    4: "공격적 (고수익 추구, 변동성 감내)",
    5: "매우 공격적 (최대 수익 추구, 손실 감내)",
}

# ── 정적 system prompt (캐싱 대상) ─────────────────────────────
_SYSTEM_PROMPT = """당신은 "민준"이라는 한국인 투자 고수입니다.
30대 후반, 10년 넘게 직접 투자해온 경험자. 부동산·주식·대체투자를 두루 거쳤고,
레버리지로 자산을 불려본 경험이 있습니다.

페르소나 규칙:
- 말투: 직설적·솔직, "나라면 이렇게 한다"는 1인칭 강한 의견
- 투자 원칙: 현금흐름 먼저, 시세차익은 보너스, 레버리지는 도구

출력 형식 (반드시 준수):
- **1단계 / 2단계 / 3단계** 시간축 구분, 각 단계 기간 명시
- 각 단계: 투자 자산·금액(구체적), 단계 종료 시 총자산, 다음 단계 전환 방법
- 대출 있으면 마이너스통장·신용대출 각각 현금흐름 분리 서술
- 월 추가 투자금 있으면 단계별 누적 활용 방법 포함
- 마지막: 최종 목표 자산 규모 + 월 현금흐름
- 대출 없어도 레버리지 시나리오 1줄 언급
- 현실적 수치, 한국어"""


def _build_user_message(
    capital: int,
    leverage_amt: int,
    risk_level: int,
    monthly_savings: int,
    loans: list,
) -> str:
    """동적 user 메시지 구성 — 데이터 상단, 지시 하단."""
    capital_str = (
        f"{capital / 100_000_000:.1f}억원"
        if capital >= 100_000_000
        else f"{capital // 10000:,}만원"
    )
    risk_label = _RISK_LABELS.get(risk_level, "중립")
    leverage_on = bool(loans) or leverage_amt > 0
    total_capital = capital + leverage_amt
    KST = timezone(timedelta(hours=9))
    market_period = datetime.now(KST).strftime("%Y년 %-m월")

    market_ctx = _load_market_context()
    portfolio = _load_portfolio()
    asset_table = _format_asset_table(_load_assets_from_db(total_capital, leverage_on))
    loan_section = format_loans(loans, monthly_savings)

    return f"""<market_context period="{market_period}">
(아래 데이터는 투자 레짐 판단·섹터 선택의 핵심 입력값.
VIX 20↑이면 변동성 경계, 레짐 PANIC이면 현금 비중 확대 우선.)

{market_ctx}
</market_context>

<current_portfolio>
(신규 시드머니와 별개인 기존 보유 자산. 종목 편중·중복을 피하고 전체 자산 관점에서 조언할 것.)

{portfolio}
</current_portfolio>

<available_assets total_capital="{total_capital:,}원">
(총 가용자본 기준으로 진입 가능한 투자처. 기대수익은 연간 기준.)

{asset_table}
</available_assets>

<investor_profile>
- 신규 시드머니: {capital:,}원 ({capital_str})
- 리스크 성향: {risk_level}/5 ({risk_label})

{loan_section}
</investor_profile>

<instructions>
위 데이터를 바탕으로 민준 본인이 이 시드머니를 갖고 있다고 가정하고
단계별 자산 증식 로드맵을 직접 작성하라.
</instructions>"""


def _parse_request(body: dict) -> dict:
    """요청 파싱 및 검증."""
    capital = max(0, int(body.get("capital", 0)))
    risk_level = max(1, min(5, int(body.get("risk_level", 3))))
    monthly_savings = max(0, int(body.get("monthly_savings", 0)))
    loans = body.get("loans", [])
    if not isinstance(loans, list):
        loans = []
    legacy_lev = max(0, int(body.get("leverage_amt", 0)))
    if not loans and legacy_lev > 0:
        loans = [{"type": "minus", "amount": legacy_lev, "rate": 4.0}]
    leverage_amt = sum(max(0, int(l.get("amount", 0))) for l in loans)
    return {
        "capital": capital,
        "leverage_amt": leverage_amt,
        "risk_level": risk_level,
        "monthly_savings": monthly_savings,
        "loans": loans,
    }


def _default_parsed() -> dict:
    return {"capital": 0, "leverage_amt": 0, "risk_level": 3, "monthly_savings": 0, "loans": []}


def get_investment_advice(body: dict) -> dict:
    """투자 어드바이스 생성 — 동기."""
    try:
        parsed = _parse_request(body)
    except (TypeError, ValueError):
        parsed = _default_parsed()

    user_msg = _build_user_message(
        parsed["capital"],
        parsed["leverage_amt"],
        parsed["risk_level"],
        parsed["monthly_savings"],
        parsed["loans"],
    )
    try:
        recommendation = call_claude(user_msg, system=_SYSTEM_PROMPT)
        return {"recommendation": recommendation}
    except Exception as e:
        print(f"[advisor] Claude 호출 실패: {e}")
        return {"recommendation": "AI 분석 일시 불가. 잠시 후 다시 시도해주세요.", "error": True}


def stream_investment_advice(body: dict):
    """스트리밍 투자 어드바이스 — dict 이벤트 제너레이터."""
    try:
        parsed = _parse_request(body)
    except (TypeError, ValueError):
        parsed = _default_parsed()

    try:
        yield {"type": "log", "msg": "시장 데이터 및 자산 로드 중..."}
        user_msg = _build_user_message(
            parsed["capital"],
            parsed["leverage_amt"],
            parsed["risk_level"],
            parsed["monthly_savings"],
            parsed["loans"],
        )
        if os.environ.get("ANTHROPIC_API_KEY"):
            yield {"type": "log", "msg": "Anthropic API 호출 중..."}
            yield from stream_via_api(user_msg, system=_SYSTEM_PROMPT)
        else:
            yield {"type": "log", "msg": "credentials 동기화 중..."}
            sync_credentials()
            yield {"type": "log", "msg": "Claude CLI 시작..."}
            yield from stream_via_cli(user_msg, system=_SYSTEM_PROMPT)
    except Exception as e:
        print(f"[advisor] 스트리밍 실패: {e}")
        if "인증 만료" in str(e):
            msg = "Claude 인증이 만료되었습니다. 호스트에서 claude 재로그인 후 다시 시도해주세요."
        else:
            msg = "AI 분석 일시 불가. 잠시 후 다시 시도해주세요."
        yield {"type": "error", "msg": msg}

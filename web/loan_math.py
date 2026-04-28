#!/usr/bin/env python3
"""대출 월납입액 계산 및 AI 프롬프트용 포맷."""


def _monthly_annuity(principal: int, annual_rate_pct: float, n_months: int) -> float:
    """원리금균등상환 월납입액. n_months=0 이면 0 반환."""
    if n_months <= 0 or principal <= 0:
        return 0.0
    r = annual_rate_pct / 100 / 12
    if r == 0:
        return float(principal) / n_months
    return principal * r / (1 - (1 + r) ** (-n_months))


def _fmt_krw(amount: int) -> str:
    if amount >= 100_000_000:
        return f"{amount / 100_000_000:.1f}억원"
    return f"{amount // 10_000:,}만원"


def format_loans(loans: list[dict], monthly_savings: int) -> str:
    """대출 목록을 AI 프롬프트용 상세 블록으로 변환."""
    if not loans:
        base = "## 대출\n대출 없음 (자기자본만 사용)"
        if monthly_savings > 0:
            return base + f"\n\n## 월 추가 투자금\n- 월 {_fmt_krw(monthly_savings)} 추가 투자 가능"
        return base

    sections = []
    grace_total = 0.0
    repay_total = 0.0

    for loan in loans:
        amt = max(0, int(loan.get("amount", 0)))
        rate = float(loan.get("rate", 4.0))
        loan_type = loan.get("type", "minus")

        if loan_type == "minus":
            mi = amt * rate / 100 / 12
            sections.append(
                f"### 마이너스통장 (이자만 납입, 수시 상환 가능)\n"
                f"- 사용금액: {_fmt_krw(amt)} ({amt:,}원)\n"
                f"- 연이율: {rate}% → 월 이자 약 {mi:,.0f}원\n"
                f"- 성격: 언제든 상환·재인출 가능, 미사용 한도 이자 없음"
            )
            grace_total += mi
            repay_total += mi

        elif loan_type == "credit":
            grace = int(loan.get("grace_period", 0))
            repay = max(1, int(loan.get("repay_period", 36)))
            mi = amt * rate / 100 / 12
            mp = _monthly_annuity(amt, rate, repay)
            gt = f"{grace}개월 거치 후 " if grace > 0 else ""
            grace_line = f"\n- 거치기간({grace}개월) 월 이자: 약 {mi:,.0f}원" if grace > 0 else ""
            sections.append(
                f"### 신용대출 (고정금리, 원리금균등상환)\n"
                f"- 금액: {_fmt_krw(amt)} ({amt:,}원)\n"
                f"- 연이율: {rate}%, {gt}상환 {repay}개월 (총 {grace + repay}개월)"
                f"{grace_line}\n"
                f"- 상환기간 월 원리금: 약 {mp:,.0f}원"
            )
            grace_total += mi
            repay_total += mp

    lines = ["## 현재 대출 현황"]
    lines.extend(sections)

    if len(loans) > 1:
        lines.append(
            f"### 합산 월 부담\n"
            f"- 거치기간 중: 약 {grace_total:,.0f}원/월\n"
            f"- 상환기간 중: 약 {repay_total:,.0f}원/월"
        )

    if monthly_savings > 0:
        net_grace = monthly_savings - grace_total
        net_repay = monthly_savings - repay_total
        lines.append(
            f"## 월 추가 투자금\n"
            f"- 월 {_fmt_krw(monthly_savings)} 꾸준히 추가 투자 가능\n"
            f"- 대출 부담 차감 후 실질 여유자금: "
            f"거치 중 약 {net_grace:,.0f}원, 상환 중 약 {net_repay:,.0f}원/월"
        )
    else:
        lines.append("## 월 추가 투자금\n- 없음 (현재 자본금으로만 운용)")

    return "\n\n".join(lines)

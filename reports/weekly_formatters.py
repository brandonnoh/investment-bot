#!/usr/bin/env python3
"""
주간 리포트 포매팅 레이어 — 각 섹션을 마크다운 문자열로 변환
weekly.py에서 분리된 순수 포매팅 함수 모음
"""

import sys
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import OUTPUT_DIR


def format_weekly_performance(performances: list[dict]) -> str:
    """주간 포트폴리오 성과 섹션"""
    if not performances:
        return "## 📊 주간 포트폴리오 성과\n\n> DB 히스토리 부족 — 데이터 축적 후 사용 가능\n"

    lines = ["## 📊 주간 포트폴리오 성과\n"]
    lines.append("| 종목 | 주초 | 주말 | 주간 수익률 | 주간 고/저 |")
    lines.append("|------|------|------|-----------|----------|")

    for p in performances:
        flag = "🟢" if p["weekly_return"] >= 0 else "🔴"
        # 가격 형식 (한국 종목은 원, 해외는 $)
        is_kr = p["ticker"].endswith(".KS") or p["ticker"].endswith(".KQ")
        if is_kr:
            start_str = f"{p['start_price']:,.0f}원"
            end_str = f"{p['end_price']:,.0f}원"
            hl_str = f"{p['high']:,.0f} / {p['low']:,.0f}"
        else:
            start_str = f"${p['start_price']:,.2f}"
            end_str = f"${p['end_price']:,.2f}"
            hl_str = f"${p['high']:,.2f} / ${p['low']:,.2f}"

        lines.append(
            f"| {flag} {p['name']} | {start_str} | {end_str} | {p['weekly_return']:+.2f}% | {hl_str} |"
        )

    lines.append("")
    return "\n".join(lines)


def format_macro_weekly(macro_changes: list[dict]) -> str:
    """매크로 지표 주간 변동 섹션"""
    if not macro_changes:
        return "## 🌍 매크로 주간 변동\n\n> DB 히스토리 부족\n"

    lines = ["## 🌍 매크로 주간 변동\n"]
    lines.append("| 지표 | 주초 | 주말 | 주간 변동 |")
    lines.append("|------|------|------|---------|")

    for m in macro_changes:
        flag = "🟢" if m["weekly_change"] >= 0 else "🔴"
        if m["indicator"] == "원/달러":
            start_str = f"{m['start_value']:,.2f}원"
            end_str = f"{m['end_value']:,.2f}원"
        elif m["indicator"] in ("코스피", "코스닥", "VIX", "달러 인덱스"):
            start_str = f"{m['start_value']:,.2f}"
            end_str = f"{m['end_value']:,.2f}"
        else:
            start_str = f"${m['start_value']:,.2f}"
            end_str = f"${m['end_value']:,.2f}"

        lines.append(
            f"| {flag} {m['indicator']} | {start_str} | {end_str} | {m['weekly_change']:+.2f}% |"
        )

    lines.append("")
    return "\n".join(lines)


def format_portfolio_analysis(portfolio_data: dict | None) -> str:
    """포트폴리오 분석 결과 섹션"""
    if not portfolio_data:
        return "## 💼 포트폴리오 분석\n\n> portfolio_summary.json 없음 — portfolio.py 실행 필요\n"

    lines = ["## 💼 포트폴리오 분석\n"]

    # 총 수익률
    total = portfolio_data.get("total", {})
    if total.get("pnl_pct") is not None:
        flag = "🟢" if total["pnl_pct"] >= 0 else "🔴"
        lines.append(
            f"- {flag} **총 수익률**: {total['pnl_pct']:+.2f}% ({total['pnl_krw']:+,.0f}원)"
        )
        lines.append(
            f"- 투자금: {total['invested_krw']:,.0f}원 → 평가액: {total['current_value_krw']:,.0f}원"
        )
    lines.append(f"- 적용 환율: {portfolio_data.get('exchange_rate', 0):,.2f}원/USD")
    lines.append("")

    # 섹터 비중
    sectors = portfolio_data.get("sectors", [])
    if sectors:
        lines.append("### 섹터별 비중")
        lines.append("| 섹터 | 비중 | 수익률 | 종목 |")
        lines.append("|------|------|--------|------|")
        for s in sectors:
            pnl_str = f"{s['pnl_pct']:+.2f}%" if s.get("pnl_pct") is not None else "N/A"
            stocks_str = ", ".join(s.get("stocks", []))
            lines.append(
                f"| {s['sector']} | {s['weight_pct']}% | {pnl_str} | {stocks_str} |"
            )
        lines.append("")

    # 리스크 지표
    risk = portfolio_data.get("risk", {})
    if any(v is not None for v in risk.values()):
        lines.append("### 리스크 지표")
        if risk.get("volatility_daily") is not None:
            lines.append(f"- 일간 변동성: {risk['volatility_daily']}%")
        if risk.get("max_drawdown_pct") is not None:
            lines.append(f"- 최대 낙폭(MDD): -{risk['max_drawdown_pct']}%")
        if risk.get("worst_performer"):
            wp = risk["worst_performer"]
            lines.append(f"- 최악 종목: {wp['name']} ({wp['pnl_pct']:+.2f}%)")
        if risk.get("best_performer"):
            bp = risk["best_performer"]
            lines.append(f"- 최고 종목: {bp['name']} ({bp['pnl_pct']:+.2f}%)")
        lines.append("")

    return "\n".join(lines)


def format_screener_summary() -> str:
    """스크리너 결과 요약 (screener.md에서 주목 종목 추출)"""
    screener_path = OUTPUT_DIR / "screener.md"
    if not screener_path.exists():
        return "## 🔍 신규 주목 종목\n\n> screener.md 없음 — screener.py 실행 필요\n"

    with screener_path.open(encoding="utf-8") as f:
        content = f.read()

    # 스크리너 리포트에서 주목 종목 테이블 추출
    lines = ["## 🔍 신규 주목 종목\n"]

    # 주목 종목 섹션 찾기
    in_highlight = False
    for line in content.split("\n"):
        if "오늘의 주목 종목" in line:
            in_highlight = True
            continue
        if in_highlight:
            if line.startswith("---"):
                break
            if line.strip():
                lines.append(line)

    lines.append("")
    return "\n".join(lines)

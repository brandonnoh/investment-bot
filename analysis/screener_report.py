#!/usr/bin/env python3
"""
스크리너 리포트 생성 레이어 — 마크다운 리포트 생성 함수 모음
screener.py에서 분리된 리포트 전용 모듈
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

KST = timezone(timedelta(hours=9))


def pick_highlights(sector_results: dict) -> list[dict]:
    """주목 종목 3~5개 선별"""
    candidates = []
    for sector_name, data in sector_results.items():
        for stock in data["stocks"]:
            if stock.get("month_return") is not None:
                candidates.append(
                    {
                        **stock,
                        "sector": sector_name,
                    }
                )

    # 1개월 수익률 상위 + 일간 양전환 우선
    candidates.sort(
        key=lambda x: (
            x.get("month_return", -999),
            x.get("day_change", 0),
        ),
        reverse=True,
    )

    return candidates[:5]


def generate_screener_report(sector_results: dict, highlights: list[dict]) -> str:
    """스크리너 마크다운 리포트 생성"""
    now = datetime.now(KST)
    lines = [
        f"# 🔍 종목 스크리너 — {now.strftime('%Y-%m-%d')}",
        f"> 생성 시각: {now.strftime('%H:%M KST')}",
        "",
        "---",
        "",
    ]

    # 주목 종목 TOP 5
    lines.append("## ⭐ 오늘의 주목 종목")
    lines.append("")
    if highlights:
        lines.append("| 순위 | 종목 | 섹터 | 현재가 | 1개월 수익률 | 일간 등락 |")
        lines.append("|------|------|------|--------|-------------|----------|")
        for i, h in enumerate(highlights, 1):
            price_str = (
                f"${h['price']:,.2f}" if h["market"] == "US" else f"{h['price']:,.0f}원"
            )
            month_str = (
                f"{h['month_return']:+.2f}%" if h["month_return"] is not None else "N/A"
            )
            day_str = f"{h['day_change']:+.2f}%"
            flag = "🔺" if (h.get("month_return") or 0) > 0 else "🔻"
            lines.append(
                f"| {i} | {flag} {h['name']} ({h['ticker']}) | {h['sector']} | {price_str} | {month_str} | {day_str} |"
            )
            # 복합 점수가 있으면 서브 점수도 표시
            if h.get("composite_score") is not None:
                score_pct = (
                    f"{h['composite_score']:.0%}"
                    if h["composite_score"] <= 1
                    else str(h["composite_score"])
                )
                sub = h.get("sub_scores", {})
                if sub:
                    lines.append(
                        f"|   | ↳ 종합 점수 {score_pct} — 수익률 {sub.get('return', 0):.0%} | RSI {sub.get('rsi', 0):.0%} | 감성 {sub.get('sentiment', 0):.0%} | 매크로 {sub.get('macro', 0):.0%} | |"
                    )
                else:
                    lines.append(f"|   | ↳ 종합 점수 {score_pct} | | | | |")
        lines.append("")
    else:
        lines.append("> 분석 데이터 부족")
        lines.append("")

    # 섹터별 상세
    lines.append("---")
    lines.append("")
    lines.append("## 📊 섹터별 분석")
    lines.append("")

    for sector_name, data in sector_results.items():
        lines.append(f"### {sector_name} — {data['description']}")
        lines.append("")
        stocks = data["stocks"]
        if stocks:
            lines.append("| 종목 | 현재가 | 전일比 | 1개월 수익률 | 거래량 |")
            lines.append("|------|--------|--------|-------------|--------|")
            for s in stocks:
                if s is None or "price" not in s:
                    continue
                price_str = (
                    f"${s['price']:,.2f}"
                    if s["market"] == "US"
                    else f"{s['price']:,.0f}원"
                )
                day_str = f"{s['day_change']:+.2f}%"
                month_str = (
                    f"{s['month_return']:+.2f}%"
                    if s["month_return"] is not None
                    else "N/A"
                )
                vol_str = f"{s['volume']:,.0f}" if s["volume"] else "N/A"
                flag = "🟢" if s["day_change"] >= 0 else "🔴"
                lines.append(
                    f"| {flag} {s['name']} | {price_str} | {day_str} | {month_str} | {vol_str} |"
                )
            lines.append("")
        else:
            lines.append("> 데이터 수집 실패")
            lines.append("")

    lines.append("---")
    lines.append(f"*자동 생성 by investment-bot screener | {now.isoformat()}*")
    lines.append("")

    return "\n".join(lines)


def generate_universe_section(
    kospi_top: list[dict],
    sp_top: list[dict],
    kospi_scanned: int,
    sp_scanned: int,
) -> str:
    """유니버스 스크리닝 결과 마크다운 섹션 생성"""
    lines = [
        "---",
        "",
        "## 🌏 유니버스 스크리닝 (1개월 수익률 기준)",
        "",
        f"> 코스피 200 상위 {kospi_scanned}개 + S&P 100 상위 {sp_scanned}개 스캔",
        "",
    ]

    def _table(stocks: list[dict], market_label: str) -> list[str]:
        section = [f"### {market_label} TOP 10", ""]
        if not stocks:
            section.append("> 데이터 수집 실패")
            section.append("")
            return section
        section.append("| 순위 | 종목 | 현재가 | 1개월 수익률 | 전일比 |")
        section.append("|------|------|--------|-------------|--------|")
        for i, s in enumerate(stocks, 1):
            is_us = s["market"] == "US"
            price_str = f"${s['price']:,.2f}" if is_us else f"{s['price']:,.0f}원"
            month_str = (
                f"{s['month_return']:+.2f}%"
                if s.get("month_return") is not None
                else "N/A"
            )
            day_str = f"{s['day_change']:+.2f}%"
            flag = "🔺" if (s.get("month_return") or 0) > 0 else "🔻"
            section.append(
                f"| {i} | {flag} {s['name']} ({s['ticker']}) | {price_str} | {month_str} | {day_str} |"
            )
        section.append("")
        return section

    lines.extend(_table(kospi_top, "코스피 200"))
    lines.extend(_table(sp_top, "S&P 100"))
    return "\n".join(lines)

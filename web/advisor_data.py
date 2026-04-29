#!/usr/bin/env python3
"""어드바이저 데이터 로드: 시장 컨텍스트, DB 자산 목록, 포트폴리오 현황."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.connection import get_db_conn

PROJECT_ROOT = Path(__file__).parent.parent
INTEL_DIR = PROJECT_ROOT / "output" / "intel"


def _load_json(filename: str) -> dict | list | None:
    path = INTEL_DIR / filename
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[advisor] {filename} 로드 실패: {e}")
        return None


def _fmt_krw(amount: float) -> str:
    if amount >= 100_000_000:
        return f"{amount / 100_000_000:.1f}억원"
    return f"{int(amount) // 10_000:,}만원"


def _load_market_context() -> str:
    parts = []

    # 매크로 지표
    macro = _load_json("macro.json")
    if isinstance(macro, list):
        lines = [
            f"- {m.get('name', '')}: {m.get('value', '')} (변동 {m.get('change_pct', '')}%)"
            for m in macro[:12]
        ]
        parts.append("### 주요 매크로 지표\n" + "\n".join(lines))

    # 레짐 분석
    regime = _load_json("regime.json")
    if isinstance(regime, dict):
        s = regime.get("strategy", {})
        parts.append(
            f"### 현재 시장 레짐\n"
            f"- 레짐: {regime.get('regime', '?')} (신뢰도 {regime.get('confidence', 0):.0%})\n"
            f"- 패닉 신호: {'있음' if regime.get('panic_signal') else '없음'} "
            f"(VIX {regime.get('vix', '?')})\n"
            f"- 투자 스탠스: {s.get('stance', '?')}\n"
            f"- 선호 섹터: {', '.join(s.get('preferred_sectors', []))}\n"
            f"- 회피 섹터: {', '.join(s.get('avoid_sectors', []))}\n"
            f"- 권장 현금 비율: {s.get('cash_ratio', 0):.0%}"
        )

    # 발굴 종목 (키워드 + 상위 기회)
    opp = _load_json("opportunities.json")
    if isinstance(opp, dict):
        keywords = [k.get("keyword", "") for k in opp.get("keywords", [])[:5]]
        top = opp.get("top_opportunities", [])[:5]
        lines = [f"- 주목 키워드: {', '.join(keywords)}"] if keywords else []
        for t in top:
            lines.append(
                f"- {t.get('ticker', '')} {t.get('name', '')} "
                f"(종합점수 {t.get('composite_score', 0):.1f})"
            )
        if lines:
            parts.append("### 발굴 종목 시그널\n" + "\n".join(lines))

    # 스크리너 — 전략별 추천 종목
    screener = _load_json("screener_results.json")
    if isinstance(screener, dict):
        lines = []
        for key, label in [("kospi200_top10", "국장 모멘텀"), ("nasdaq100_top10", "미장 모멘텀")]:
            picks = screener.get(key, [])[:5]
            if picks:
                names = ", ".join(p.get("name", p.get("ticker", "")) for p in picks)
                lines.append(f"- {label}: {names}")
        if lines:
            parts.append("### 스크리너 추천 종목\n" + "\n".join(lines))

    return "\n\n".join(parts) if parts else "(시장 데이터 없음)"


def _load_portfolio_from_prices() -> list[dict] | None:
    """prices.json에서 현재가 포함 포트폴리오 데이터 로드."""
    data = _load_json("prices.json")
    if not isinstance(data, dict):
        return None
    prices = data.get("prices", [])
    # qty가 있는 항목만 (보유 종목)
    holdings = [p for p in prices if p.get("qty")]
    return holdings if holdings else None


def _load_portfolio_from_db() -> list[dict] | None:
    """DB holdings 테이블에서 폴백 로드."""
    try:
        with get_db_conn() as conn:
            rows = conn.execute(
                "SELECT ticker, name, qty, avg_cost, currency FROM holdings ORDER BY ticker"
            ).fetchall()
        if not rows:
            return None
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[advisor] DB 포트폴리오 로드 실패: {e}")
        return None


def _load_portfolio() -> str:
    """현재 보유 포트폴리오 로드 → AI용 마크다운 텍스트."""
    holdings = _load_portfolio_from_prices() or _load_portfolio_from_db()
    if not holdings:
        return "(보유 종목 없음)"

    # 총 평가금액 계산 (현재가 기반, 없으면 평균단가 기반)
    total_value = sum(h.get("qty", 0) * (h.get("price") or h.get("avg_cost", 0)) for h in holdings)
    lines = [
        f"### 현재 보유 포트폴리오\n총 평가금액: 약 {_fmt_krw(total_value)}\n",
        "| 종목 | 수량 | 평균단가 | 현재가 | 평가손익 | 비중 |",
        "|------|------|---------|-------|---------|-----|",
    ]
    for h in holdings:
        qty = h.get("qty", 0)
        avg_cost = h.get("avg_cost", 0)
        price = h.get("price") or avg_cost
        pnl_pct = h.get("pnl_pct", 0)
        cur_val = qty * price
        weight = (cur_val / total_value * 100) if total_value else 0
        usd = " (USD)" if h.get("currency") == "USD" else ""
        sign = "+" if pnl_pct >= 0 else ""
        lines.append(
            f"| {h.get('name', '')}({h.get('ticker', '')}){usd} "
            f"| {qty:.1f} | {avg_cost:,.0f} | {price:,.0f} "
            f"| {sign}{pnl_pct:.1f}% | {weight:.1f}% |"
        )
    lines.append("\n(투자 조언 시 기존 포트폴리오 편중/중복 고려할 것)")
    return "\n".join(lines)


def _load_assets_from_db(total_capital: int, leverage_on: bool) -> list[dict]:
    """DB에서 총 자본금(현금+대출) 조건에 맞는 투자 자산 로드."""
    try:
        with get_db_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM investment_assets WHERE status != 'upcoming' ORDER BY category, risk_level"
            ).fetchall()
        assets = []
        for r in rows:
            row = dict(r)
            min_cap = row.get("min_capital") or 0
            min_lev = row.get("min_capital_leveraged")
            min_req = min_lev if (leverage_on and min_lev) else min_cap
            if min_req <= total_capital:
                row["leverage_available"] = bool(row["leverage_available"])
                row["beginner_friendly"] = bool(row["beginner_friendly"])
                assets.append(row)
        return assets
    except Exception as e:
        print(f"[advisor] DB 자산 로드 실패: {e}")
        return []


def _format_asset_table(assets: list[dict]) -> str:
    if not assets:
        return "(접근 가능한 자산 없음)"
    lines = [
        "| 자산명 | 최소자본 | 기대수익(연) | 리스크 | 레버리지 | 세제혜택 | 실제 비용 (진입/보유/출구/숨은비용) |"
    ]
    lines.append(
        "|--------|---------|------------|------|---------|---------|----------------------------------|"
    )
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
        real_costs = a.get("real_costs") or "-"
        lines.append(
            f"| {a.get('name', '')} | {min_cap_str} | {ret_min}~{ret_max}% | {risk}/5 | {lev} | {tax} | {real_costs} |"
        )
    return "\n".join(lines)

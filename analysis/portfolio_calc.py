#!/usr/bin/env python3
"""
포트폴리오 계산 레이어 — 종목별 평가손익, 섹터 비중, 리스크 지표 계산
portfolio.py에서 분리된 순수 계산 함수 모음
"""

import math
import sqlite3
import sys
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH

# 섹터 분류
SECTOR_MAP = {
    "005930.KS": "반도체",
    "005380.KS": "자동차",
    "0117V0.KS": "AI/전력",
    "458730.KS": "방산",
    "TSLA": "전기차/AI",
    "GOOGL": "빅테크",
    "XOP": "에너지",
    "GOLD_KRW_G": "원자재(금)",
}


def calculate_holdings(prices: list[dict], exchange_rate: float) -> list[dict]:
    """종목별 평가금액 계산 (원화 통일) + 환율/주식 손익 분리"""
    holdings = []

    for p in prices:
        if p.get("price") is None:
            continue

        ticker = p["ticker"]
        price = p["price"]
        avg_cost = p.get("avg_cost", 0)
        qty = p.get("qty", 0)
        currency = p.get("currency", "USD")
        buy_fx_rate = p.get("buy_fx_rate")

        # 평가금액 (원화 환산)
        if currency == "KRW":
            current_value_krw = price * qty
            invested_krw = avg_cost * qty if avg_cost > 0 else 0
        else:
            current_value_krw = price * qty * exchange_rate
            # 매입 환율이 있으면 실제 투자금(매입 시점) 사용
            if avg_cost > 0 and buy_fx_rate:
                invested_krw = avg_cost * qty * buy_fx_rate
            elif avg_cost > 0:
                invested_krw = avg_cost * qty * exchange_rate
            else:
                invested_krw = 0

        # 평가손익 (avg_cost=0인 종목은 수익률 계산 제외)
        cost_set = avg_cost > 0
        pnl_krw = current_value_krw - invested_krw if cost_set else None
        pnl_pct = (
            (pnl_krw / invested_krw * 100) if cost_set and invested_krw > 0 else None
        )

        # 환율 손익 분리: stock_pnl + fx_pnl = pnl_krw
        if cost_set and currency != "KRW" and buy_fx_rate:
            # 주식 손익 = (현재가 - 평균단가) × 수량 × 매입환율
            stock_pnl_krw = round((price - avg_cost) * qty * buy_fx_rate)
            # 환율 손익 = 현재가 × 수량 × (현재환율 - 매입환율)
            fx_pnl_krw = round(price * qty * (exchange_rate - buy_fx_rate))
        elif cost_set and currency == "KRW":
            stock_pnl_krw = round(pnl_krw) if pnl_krw is not None else 0
            fx_pnl_krw = 0
        else:
            # 매입 환율 미설정 USD 종목 또는 평단 미설정
            stock_pnl_krw = round(pnl_krw) if pnl_krw is not None else None
            fx_pnl_krw = 0

        sector = SECTOR_MAP.get(ticker, "기타")

        holdings.append(
            {
                "ticker": ticker,
                "name": p["name"],
                "sector": sector,
                "currency": currency,
                "price": price,
                "avg_cost": avg_cost,
                "qty": qty,
                "current_value_krw": round(current_value_krw),
                "invested_krw": round(invested_krw) if cost_set else 0,
                "pnl_krw": round(pnl_krw) if pnl_krw is not None else None,
                "pnl_pct": round(pnl_pct, 2) if pnl_pct is not None else None,
                "stock_pnl_krw": stock_pnl_krw,
                "fx_pnl_krw": fx_pnl_krw,
                "pnl_label": None if cost_set else "평단 미설정",
                "change_pct": p.get("change_pct"),
            }
        )

    return holdings


def calculate_sector_weights(holdings: list[dict]) -> list[dict]:
    """섹터별 비중 계산"""
    total_value = sum(h["current_value_krw"] for h in holdings)
    if total_value == 0:
        return []

    sector_totals = {}
    for h in holdings:
        sector = h["sector"]
        if sector not in sector_totals:
            sector_totals[sector] = {"value": 0, "invested": 0, "stocks": []}
        sector_totals[sector]["value"] += h["current_value_krw"]
        if h.get("pnl_label") is None:
            sector_totals[sector]["invested"] += h["invested_krw"]
        sector_totals[sector]["stocks"].append(h["name"])

    sectors = []
    for name, data in sector_totals.items():
        weight = round(data["value"] / total_value * 100, 1)
        pnl_pct = None
        if data["invested"] > 0:
            pnl_pct = round(
                (data["value"] - data["invested"]) / data["invested"] * 100, 2
            )
        sectors.append(
            {
                "sector": name,
                "weight_pct": weight,
                "value_krw": data["value"],
                "pnl_pct": pnl_pct,
                "stocks": data["stocks"],
            }
        )

    sectors.sort(key=lambda x: x["weight_pct"], reverse=True)
    return sectors


def calculate_risk_metrics(holdings: list[dict]) -> dict:
    """리스크 지표 계산 — DB 이력 활용"""
    metrics = {
        "max_drawdown_pct": None,
        "volatility_daily": None,
        "worst_performer": None,
        "best_performer": None,
    }

    # 현재 보유 종목 중 최악/최고 수익률
    valid = [h for h in holdings if h.get("pnl_pct") is not None]
    if valid:
        worst = min(valid, key=lambda x: x["pnl_pct"])
        best = max(valid, key=lambda x: x["pnl_pct"])
        metrics["worst_performer"] = {
            "name": worst["name"],
            "pnl_pct": worst["pnl_pct"],
        }
        metrics["best_performer"] = {
            "name": best["name"],
            "pnl_pct": best["pnl_pct"],
        }

    # DB에서 최근 30일 가격 히스토리로 변동성 계산
    if not DB_PATH.exists():
        return metrics

    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        # 포트폴리오 전체 일간 수익률 히스토리
        tickers = [h["ticker"] for h in holdings]
        if not tickers:
            conn.close()
            return metrics

        placeholders = ",".join("?" * len(tickers))
        cursor.execute(
            f"""
            SELECT timestamp, ticker, change_pct
            FROM prices
            WHERE ticker IN ({placeholders})
              AND timestamp >= datetime('now', '-30 days')
            ORDER BY timestamp
        """,
            tickers,
        )

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return metrics

        # 일별 포트폴리오 평균 변동률
        daily_changes = {}
        for ts, ticker, change_pct in rows:
            if change_pct is None:
                continue
            date_key = ts[:10]  # YYYY-MM-DD
            if date_key not in daily_changes:
                daily_changes[date_key] = []
            daily_changes[date_key].append(change_pct)

        if len(daily_changes) < 2:
            return metrics

        # 일별 평균 수익률
        daily_returns = []
        for date_key in sorted(daily_changes.keys()):
            changes = daily_changes[date_key]
            avg_return = sum(changes) / len(changes)
            daily_returns.append(avg_return)

        # 변동성 (일간 수익률 표준편차)
        if len(daily_returns) >= 2:
            mean = sum(daily_returns) / len(daily_returns)
            variance = sum((r - mean) ** 2 for r in daily_returns) / (
                len(daily_returns) - 1
            )
            volatility = round(math.sqrt(variance), 2)
            metrics["volatility_daily"] = volatility

        # 최대 낙폭 (MDD)
        cumulative = [1.0]
        for r in daily_returns:
            cumulative.append(cumulative[-1] * (1 + r / 100))
        peak = cumulative[0]
        max_dd = 0.0
        for val in cumulative:
            if val > peak:
                peak = val
            dd = (peak - val) / peak * 100
            if dd > max_dd:
                max_dd = dd
        metrics["max_drawdown_pct"] = round(max_dd, 2) if max_dd > 0 else 0.0

    except Exception as e:
        print(f"  ⚠️  리스크 지표 계산 오류: {e}")

    return metrics

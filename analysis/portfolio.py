#!/usr/bin/env python3
"""
포트폴리오 분석 모듈 — 평가손익, 섹터 비중, 리스크 지표
원화 환산 통일 계산
출력: output/intel/portfolio_summary.json
"""

import json
import math
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, OUTPUT_DIR

KST = timezone(timedelta(hours=9))

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


def load_prices() -> list[dict]:
    """최신 주가 데이터 로드"""
    prices_path = OUTPUT_DIR / "prices.json"
    if not prices_path.exists():
        print("  ⚠️  prices.json 없음")
        return []
    with open(prices_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("prices", [])


def load_macro() -> list[dict]:
    """최신 매크로 데이터 로드 (환율용)"""
    macro_path = OUTPUT_DIR / "macro.json"
    if not macro_path.exists():
        return []
    with open(macro_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("indicators", [])


def get_exchange_rate(macro: list[dict]) -> float:
    """원/달러 환율 조회 (실패 시 기본값 1450)"""
    for m in macro:
        if m.get("indicator") == "원/달러" and m.get("value") is not None:
            return m["value"]
    return 1450.0


def _get_db_conn():
    """DB 연결 반환 (테스트에서 패치 가능)"""
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def save_snapshot(conn, summary: dict, date_str: str):
    """일별 포트폴리오 스냅샷을 portfolio_history에 저장 (UPSERT)"""
    total = summary["total"]
    holdings_json = json.dumps(summary.get("holdings", []), ensure_ascii=False)

    conn.execute(
        """
        INSERT INTO portfolio_history
            (date, total_value_krw, total_invested_krw, total_pnl_krw,
             total_pnl_pct, fx_rate, fx_pnl_krw, holdings_snapshot)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            total_value_krw = excluded.total_value_krw,
            total_invested_krw = excluded.total_invested_krw,
            total_pnl_krw = excluded.total_pnl_krw,
            total_pnl_pct = excluded.total_pnl_pct,
            fx_rate = excluded.fx_rate,
            fx_pnl_krw = excluded.fx_pnl_krw,
            holdings_snapshot = excluded.holdings_snapshot
    """,
        (
            date_str,
            total.get("current_value_krw"),
            total.get("invested_krw"),
            total.get("pnl_krw"),
            total.get("pnl_pct"),
            summary.get("exchange_rate"),
            None,  # fx_pnl_krw — F09에서 구현
            holdings_json,
        ),
    )
    conn.commit()


def load_history(conn, days: int = 30) -> list[dict]:
    """최근 N일 포트폴리오 이력 조회 (날짜 오름차순)"""
    cursor = conn.execute(
        """
        SELECT date, total_value_krw, total_invested_krw,
               total_pnl_krw, total_pnl_pct, fx_rate
        FROM portfolio_history
        ORDER BY date DESC
        LIMIT ?
    """,
        (days,),
    )
    rows = cursor.fetchall()

    result = []
    for row in rows:
        result.append(
            {
                "date": row["date"],
                "total_value_krw": row["total_value_krw"],
                "total_invested_krw": row["total_invested_krw"],
                "total_pnl_krw": row["total_pnl_krw"],
                "total_pnl_pct": row["total_pnl_pct"],
                "fx_rate": row["fx_rate"],
            }
        )

    # 날짜 오름차순 정렬
    result.sort(key=lambda x: x["date"])
    return result


def calculate_holdings(prices: list[dict], exchange_rate: float) -> list[dict]:
    """종목별 평가금액 계산 (원화 통일)"""
    holdings = []

    for p in prices:
        if p.get("price") is None:
            continue

        ticker = p["ticker"]
        price = p["price"]
        avg_cost = p.get("avg_cost", 0)
        qty = p.get("qty", 0)
        currency = p.get("currency", "USD")

        # 평가금액 (원화 환산)
        if currency == "KRW":
            current_value_krw = price * qty
            invested_krw = avg_cost * qty if avg_cost > 0 else 0
        else:
            current_value_krw = price * qty * exchange_rate
            invested_krw = avg_cost * qty * exchange_rate if avg_cost > 0 else 0

        # 평가손익 (avg_cost=0인 종목은 수익률 계산 제외)
        cost_set = avg_cost > 0
        pnl_krw = current_value_krw - invested_krw if cost_set else None
        pnl_pct = (
            (pnl_krw / invested_krw * 100) if cost_set and invested_krw > 0 else None
        )

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


def build_summary(
    holdings: list[dict],
    sectors: list[dict],
    risk: dict,
    exchange_rate: float,
    history: list[dict] = None,
) -> dict:
    """포트폴리오 전체 요약 생성 (history: 최근 30일 수익률 추이)"""
    total_invested = sum(
        h["invested_krw"]
        for h in holdings
        if h.get("pnl_label") is None and h["invested_krw"] > 0
    )
    total_current = sum(h["current_value_krw"] for h in holdings)
    total_pnl = total_current - total_invested if total_invested > 0 else 0
    total_pnl_pct = (
        round(total_pnl / total_invested * 100, 2) if total_invested > 0 else None
    )

    return {
        "updated_at": datetime.now(KST).isoformat(),
        "exchange_rate": exchange_rate,
        "total": {
            "invested_krw": total_invested,
            "current_value_krw": total_current,
            "pnl_krw": total_pnl,
            "pnl_pct": total_pnl_pct,
        },
        "holdings": holdings,
        "sectors": sectors,
        "risk": risk,
        "history": history if history is not None else [],
    }


def run():
    """포트폴리오 분석 파이프라인 실행"""
    print(
        f"\n💼 포트폴리오 분석 시작 — {datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}"
    )

    # 데이터 로드
    prices = load_prices()
    macro = load_macro()

    if not prices:
        print("  ⚠️  가격 데이터 없음 — 분석 건너뜀")
        return None

    # 환율 조회
    exchange_rate = get_exchange_rate(macro)
    print(f"  💱 적용 환율: {exchange_rate:,.2f}원/USD")

    # 종목별 평가금액 (원화 통일)
    holdings = calculate_holdings(prices, exchange_rate)
    print(f"  📊 분석 종목: {len(holdings)}개")

    # 평단 미설정 종목 안내
    no_cost = [h["name"] for h in holdings if h.get("pnl_label") == "평단 미설정"]
    if no_cost:
        print(f"  ⚠️  평단 미설정 (수익률 제외): {', '.join(no_cost)}")

    # 섹터별 비중
    sectors = calculate_sector_weights(holdings)
    for s in sectors:
        print(f"    {s['sector']}: {s['weight_pct']}%")

    # 리스크 지표
    risk = calculate_risk_metrics(holdings)
    if risk.get("volatility_daily") is not None:
        print(f"  📉 일간 변동성: {risk['volatility_daily']}%")
    if risk.get("max_drawdown_pct") is not None:
        print(f"  📉 MDD: -{risk['max_drawdown_pct']}%")

    # DB 연결 → 이력 조회 + 스냅샷 저장
    history = []
    conn = _get_db_conn()
    if conn is not None:
        try:
            history = load_history(conn, days=30)
        except Exception as e:
            print(f"  ⚠️  이력 조회 오류: {e}")

    # 요약 생성 (이력 포함)
    summary = build_summary(holdings, sectors, risk, exchange_rate, history=history)

    # 스냅샷 저장
    if conn is not None:
        try:
            today = datetime.now(KST).strftime("%Y-%m-%d")
            save_snapshot(conn, summary, today)
            print(f"  💾 일별 스냅샷 저장: {today}")
        except Exception as e:
            print(f"  ⚠️  스냅샷 저장 오류: {e}")
        finally:
            conn.close()

    # 총 수익률 출력
    total = summary["total"]
    if total["pnl_pct"] is not None:
        flag = "🟢" if total["pnl_pct"] >= 0 else "🔴"
        print(
            f"\n  {flag} 총 포트폴리오: {total['pnl_krw']:+,.0f}원 ({total['pnl_pct']:+.2f}%)"
        )

    if history:
        print(f"  📈 수익률 추이: 최근 {len(history)}일")

    # JSON 저장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "portfolio_summary.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"  📄 포트폴리오 요약 저장: {output_path}")
    print()

    return summary


if __name__ == "__main__":
    run()

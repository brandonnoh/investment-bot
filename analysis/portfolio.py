#!/usr/bin/env python3
"""
포트폴리오 분석 모듈 — 평가손익, 섹터 비중, 리스크 지표
원화 환산 통일 계산
출력: output/intel/portfolio_summary.json
"""

import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis.portfolio_calc import (  # noqa: E402  # re-export
    calculate_holdings,
    calculate_risk_metrics,
    calculate_sector_weights,
)
from config import DB_PATH, OUTPUT_DIR

KST = timezone(timedelta(hours=9))


def load_prices() -> list[dict]:
    """최신 주가 데이터 로드"""
    prices_path = OUTPUT_DIR / "prices.json"
    if not prices_path.exists():
        print("  ⚠️  prices.json 없음")
        return []
    with prices_path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data.get("prices", [])


def load_macro() -> list[dict]:
    """최신 매크로 데이터 로드 (환율용)"""
    macro_path = OUTPUT_DIR / "macro.json"
    if not macro_path.exists():
        return []
    with macro_path.open(encoding="utf-8") as f:
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
            total.get("fx_pnl_krw"),
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

    # 환율/주식 손익 합계
    valid_holdings = [h for h in holdings if h.get("pnl_label") is None]
    total_fx_pnl = sum(h.get("fx_pnl_krw", 0) for h in valid_holdings)
    total_stock_pnl = sum(
        h.get("stock_pnl_krw", 0)
        for h in valid_holdings
        if h.get("stock_pnl_krw") is not None
    )

    return {
        "updated_at": datetime.now(KST).isoformat(),
        "exchange_rate": exchange_rate,
        "total": {
            "invested_krw": total_invested,
            "current_value_krw": total_current,
            "pnl_krw": total_pnl,
            "pnl_pct": total_pnl_pct,
            "stock_pnl_krw": total_stock_pnl,
            "fx_pnl_krw": total_fx_pnl,
        },
        "holdings": holdings,
        "sectors": sectors,
        "risk": risk,
        "history": history if history is not None else [],
    }


def _load_history_from_db(conn) -> list[dict]:
    """DB에서 최근 30일 이력 조회 (오류 시 빈 리스트)"""
    try:
        return load_history(conn, days=30)
    except Exception as e:
        print(f"  ⚠️  이력 조회 오류: {e}")
        return []


def _save_snapshots(conn, summary: dict, today: str, exchange_rate: float):
    """portfolio_history + total_wealth_history 스냅샷 저장"""
    try:
        save_snapshot(conn, summary, today)
        print(f"  💾 일별 스냅샷 저장: {today}")
        _save_total_wealth(conn, summary, exchange_rate, today)
    except Exception as e:
        print(f"  ⚠️  스냅샷 저장 오류: {e}")


def _save_total_wealth(conn, summary: dict, exchange_rate: float, today: str):
    """SSoT: total_wealth_history에 저장"""
    try:
        from db.ssot import get_extra_assets_total, save_total_wealth_snapshot

        extra_total = get_extra_assets_total(conn)
        total_data = summary["total"]
        save_total_wealth_snapshot(
            investment_value=total_data["current_value_krw"],
            extra_assets=extra_total,
            pnl_krw=total_data["pnl_krw"],
            pnl_pct=total_data["pnl_pct"],
            fx_rate=exchange_rate,
            date=today,
            conn=conn,
        )
    except Exception as e:
        print(f"  ⚠️  total_wealth 저장 오류: {e}")


def _print_total_summary(summary: dict):
    """포트폴리오 총 손익 및 분해 출력"""
    total = summary["total"]
    history = summary.get("history", [])
    if total["pnl_pct"] is not None:
        flag = "🟢" if total["pnl_pct"] >= 0 else "🔴"
        print(
            f"\n  {flag} 총 포트폴리오: {total['pnl_krw']:+,.0f}원 ({total['pnl_pct']:+.2f}%)"
        )
        if total.get("fx_pnl_krw") is not None:
            print(f"    📈 주식 손익: {total['stock_pnl_krw']:+,.0f}원")
            print(f"    💱 환율 손익: {total['fx_pnl_krw']:+,.0f}원")
    if history:
        print(f"  📈 수익률 추이: 최근 {len(history)}일")


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

    # DB 연결 → 이력 조회
    history = []
    conn = _get_db_conn()
    if conn is not None:
        history = _load_history_from_db(conn)

    # 요약 생성 (이력 포함)
    summary = build_summary(holdings, sectors, risk, exchange_rate, history=history)

    # 스냅샷 저장
    if conn is not None:
        today = datetime.now(KST).strftime("%Y-%m-%d")
        _save_snapshots(conn, summary, today, exchange_rate)
        conn.close()

    # 총 수익률 출력
    _print_total_summary(summary)

    # JSON 저장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "portfolio_summary.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"  📄 포트폴리오 요약 저장: {output_path}")
    print()

    return summary


if __name__ == "__main__":
    run()

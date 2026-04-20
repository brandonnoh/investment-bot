#!/usr/bin/env python3
"""
포트폴리오 가격 실시간 갱신 — portfolio_summary holdings를 prices.json 최신 가격으로 재계산.
pipeline 주기 사이 가격 stale 문제를 API 서빙 시점에 보정.
"""


def _recalc_holding(h: dict, new_price: float, new_change_pct: float | None, fx: float) -> dict:
    """holding 하나를 새 가격으로 재계산하여 반환."""
    h = dict(h)
    h["price"] = new_price
    if new_change_pct is not None:
        h["change_pct"] = new_change_pct

    qty = h.get("qty", 0)
    avg_cost = h.get("avg_cost", 0)
    currency = h.get("currency", "USD")
    buy_fx = h.get("buy_fx_rate")
    cost_set = avg_cost > 0

    if currency == "KRW":
        cur_val = new_price * qty
        inv_val = avg_cost * qty if cost_set else 0
    else:
        cur_val = new_price * qty * fx
        if cost_set and buy_fx:
            inv_val = avg_cost * qty * buy_fx
        elif cost_set:
            inv_val = avg_cost * qty * fx
        else:
            inv_val = 0

    pnl = cur_val - inv_val if cost_set else None
    pnl_pct = (pnl / inv_val * 100) if cost_set and inv_val > 0 else None

    if cost_set and currency != "KRW" and buy_fx:
        stock_pnl = round((new_price - avg_cost) * qty * buy_fx)
        fx_pnl = round(new_price * qty * (fx - buy_fx))
    elif cost_set and currency == "KRW":
        stock_pnl = round(pnl) if pnl is not None else 0
        fx_pnl = 0
    else:
        stock_pnl = round(pnl) if pnl is not None else None
        fx_pnl = 0

    h["current_value_krw"] = round(cur_val)
    h["invested_krw"] = round(inv_val) if cost_set else 0
    h["pnl_krw"] = round(pnl) if pnl is not None else None
    h["pnl_pct"] = round(pnl_pct, 2) if pnl_pct is not None else None
    h["stock_pnl_krw"] = stock_pnl
    h["fx_pnl_krw"] = fx_pnl
    return h


def refresh_portfolio_with_live_prices(portfolio: dict, prices: dict) -> dict:
    """portfolio_summary holdings를 prices.json 최신 가격으로 재계산."""
    holdings = portfolio.get("holdings", [])
    if not holdings:
        return portfolio

    price_map = {p["ticker"]: p for p in prices.get("prices", [])}
    fx = portfolio.get("exchange_rate", 1450.0)

    updated = []
    for h in holdings:
        live = price_map.get(h.get("ticker", ""))
        if live and live.get("price") is not None:
            h = _recalc_holding(h, live["price"], live.get("change_pct"), fx)
        updated.append(h)

    total_val = sum(h["current_value_krw"] for h in updated)
    total_inv = sum(h.get("invested_krw", 0) for h in updated)
    total_pnl = total_val - total_inv
    total_pnl_pct = round(total_pnl / total_inv * 100, 2) if total_inv > 0 else 0
    stock_pnl = sum(h.get("stock_pnl_krw") or 0 for h in updated)
    fx_pnl = sum(h.get("fx_pnl_krw") or 0 for h in updated)

    result = dict(portfolio)
    result["holdings"] = updated
    result["total"] = {
        **portfolio.get("total", {}),
        "current_value_krw": round(total_val),
        "invested_krw": round(total_inv),
        "pnl_krw": round(total_pnl),
        "pnl_pct": total_pnl_pct,
        "stock_pnl_krw": round(stock_pnl),
        "fx_pnl_krw": round(fx_pnl),
    }
    return result

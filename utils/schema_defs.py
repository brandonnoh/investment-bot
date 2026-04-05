"""
JSON 출력 스키마 상수 정의 모듈
output/intel/ 파일별 필수 필드 + 타입 규칙 딕셔너리
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── "number" 타입: int 또는 float 모두 허용 ──
# 스키마에서 "number"로 지정하면 int/float 둘 다 통과

SCHEMAS = {
    "prices.json": {
        "top_level": {
            "updated_at": str,
            "count": int,
            "prices": list,
        },
        "items_key": "prices",
        "item_fields": {
            "ticker": str,
            "name": str,
            "price": "number",
            "prev_close": "number",
            "change_pct": "number",
            "volume": "number",
            "currency": str,
            "market": str,
            "timestamp": str,
            "data_source": str,
        },
    },
    "macro.json": {
        "top_level": {
            "updated_at": str,
            "count": int,
            "indicators": list,
        },
        "items_key": "indicators",
        "item_fields": {
            "indicator": str,
            "ticker": str,
            "value": "number",
            "prev_close": "number",
            "change_pct": "number",
            "category": str,
            "timestamp": str,
        },
    },
    "news.json": {
        "top_level": {
            "updated_at": str,
            "count": int,
            "news": list,
        },
        "items_key": "news",
        "item_fields": {
            "title": str,
            "source": str,
            "url": str,
            "published_at": str,
            "relevance_score": "number",
            "sentiment": "number",
            "category": str,
            "tickers": list,
            "timestamp": str,
        },
    },
    "portfolio_summary.json": {
        "top_level": {
            "updated_at": str,
            "exchange_rate": "number",
            "total": dict,
            "holdings": list,
            "sectors": list,
            "risk": dict,
        },
        "items_key": "holdings",
        "item_fields": {
            "ticker": str,
            "name": str,
            "currency": str,
            "price": "number",
            "avg_cost": "number",
            "qty": "number",
            "current_value_krw": "number",
            "invested_krw": "number",
            "pnl_krw": "number",
            "pnl_pct": "number",
        },
        "nested": {
            "total": {
                "invested_krw": "number",
                "current_value_krw": "number",
                "pnl_krw": "number",
                "pnl_pct": "number",
            },
        },
    },
    "alerts.json": {
        "top_level": {
            "triggered_at": str,
            "count": int,
            "alerts": list,
        },
        "items_key": "alerts",
        "item_fields": {
            "level": str,
            "event_type": str,
            "message": str,
            "value": "number",
            "threshold": "number",
        },
    },
    "price_analysis.json": {
        "top_level": {
            "updated_at": str,
            "analysis": dict,
        },
        "items_key": "analysis",
        "items_type": "dict",  # 배열이 아닌 딕셔너리 구조
        "item_fields": {
            "name": str,
            "current": "number",
            "rsi_14": "number",
            "trend": str,
        },
    },
    "opportunities.json": {
        "top_level": {
            "updated_at": str,
            "keywords": list,
            "opportunities": list,
            "summary": dict,
        },
        "items_key": "opportunities",
        "item_fields": {
            "ticker": str,
            "name": str,
            "discovered_via": str,
        },
    },
    "fundamentals.json": {
        "top_level": {
            "updated_at": str,
            "count": int,
            "fundamentals": list,
        },
        "items_key": "fundamentals",
        "item_fields": {
            "ticker": str,
            "name": str,
            "market": str,
            "data_source": str,
        },
    },
    "engine_status.json": {
        "top_level": {
            "updated_at": str,
            "pipeline_ok": bool,
            "total_errors": int,
            "db_size_mb": "number",
            "uptime_days": int,
            "first_run": str,
            "modules": dict,
        },
    },
    "performance_report.json": {
        "top_level": {
            "updated_at": str,
            "outcome_summary": dict,
            "monthly_report": dict,
            "weight_suggestion": dict,
        },
    },
}

#!/usr/bin/env python3
"""
투자 인텔리전스 봇 — 설정 파일
포트폴리오 정의, 매크로 지표, 알림 임계값, 경로 설정
"""

from pathlib import Path

# ── 프로젝트 경로 ──
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "db" / "history.db"
OUTPUT_DIR = BASE_DIR / "output" / "intel"

# ── 포트폴리오 정의 ──
# (이름, 야후티커, 평균단가, 통화, 수량, 계좌)
PORTFOLIO = [
    {
        "name": "삼성전자",
        "ticker": "005930.KS",
        "avg_cost": 203102,
        "currency": "KRW",
        "qty": 42,
        "account": "ISA",
    },
    {
        "name": "현대차",
        "ticker": "005380.KS",
        "avg_cost": 519000,
        "currency": "KRW",
        "qty": 9,
        "account": "혼합",
    },
    {
        "name": "TIGER 코리아AI전력기",
        "ticker": "0117V0.KS",
        "avg_cost": 16795,
        "currency": "KRW",
        "qty": 60,
        "account": "ISA",
    },
    {
        "name": "TIGER 미국방산TOP10",
        "ticker": "458730.KS",
        "avg_cost": 15485,
        "currency": "KRW",
        "qty": 64,
        "account": "ISA",
    },
    {
        "name": "테슬라",
        "ticker": "TSLA",
        "avg_cost": 394.32,
        "currency": "USD",
        "qty": 1,
        "account": "미국",
    },
    {
        "name": "알파벳",
        "ticker": "GOOGL",
        "avg_cost": 308.27,
        "currency": "USD",
        "qty": 2,
        "account": "미국",
    },
    {
        "name": "SPDR S&P Oil",
        "ticker": "XOP",
        "avg_cost": 178.26,
        "currency": "USD",
        "qty": 1,
        "account": "미국",
    },
    {
        "name": "금 현물",
        "ticker": "GOLD_KRW_G",
        "avg_cost": 225564,
        "currency": "KRW",
        "qty": 128,
        "account": "실물",
    },  # 128g, 원/g
]

# ── 매크로 지표 정의 ──
# (지표명, 야후티커, 카테고리)
MACRO_INDICATORS = [
    {"name": "코스피", "ticker": "KOSPI", "category": "INDEX"},
    {"name": "코스닥", "ticker": "KOSDAQ", "category": "INDEX"},
    {"name": "원/달러", "ticker": "KRW=X", "category": "FX"},
    {"name": "WTI 유가", "ticker": "CL=F", "category": "COMMODITY"},
    {"name": "브렌트유", "ticker": "BZ=F", "category": "COMMODITY"},
    {"name": "금 현물", "ticker": "GC=F", "category": "COMMODITY"},
    {"name": "달러 인덱스", "ticker": "DX-Y.NYB", "category": "FX"},
    {"name": "VIX", "ticker": "^VIX", "category": "VOLATILITY"},
]

# ── 알림 임계값 ──
ALERT_THRESHOLDS = {
    # 종목 개별 변동
    "stock_drop": {"threshold": -5.0, "level": "RED", "label": "종목 급락"},
    "stock_surge": {"threshold": 5.0, "level": "GREEN", "label": "종목 급등"},
    # 매크로 지표
    "kospi_drop": {"threshold": -3.0, "level": "RED", "label": "코스피 폭락"},
    "usd_krw_high": {"threshold": 1550, "level": "RED", "label": "환율 급등"},
    "oil_surge": {"threshold": 5.0, "level": "YELLOW", "label": "유가 급등"},
    "gold_swing": {"threshold": 3.0, "level": "YELLOW", "label": "금 현물 급변"},
    "vix_high": {"threshold": 30.0, "level": "YELLOW", "label": "VIX 급등"},
    # 포트폴리오 전체
    "portfolio_loss": {
        "threshold": -10.0,
        "level": "RED",
        "label": "포트폴리오 전체 손실",
    },
}

# ── 보존 정책 ──
RETENTION_POLICY = {
    "raw_months": 3,  # 원시 데이터 (prices, macro) 보존 개월 수
    "news_months": 12,  # 뉴스 보존 개월 수
}

# ── 분석 파라미터 ──
ANALYSIS_PARAMS = {
    "ma_periods": [5, 20, 60],  # 이동평균 기간
    "rsi_period": 14,  # RSI 기간
    "volatility_period": 30,  # 변동성 계산 기간 (일)
    "trend_period": 20,  # 추세 판단 기간 (일)
    "support_resistance_period": 20,  # 지지/저항 계산 기간 (일)
    "week_52_days": 252,  # 52주 거래일 수
}

# ── Yahoo Finance 요청 설정 ──
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0"}
YAHOO_TIMEOUT = 10  # 초


# ── 마켓 분류 ──
def get_market(ticker: str) -> str:
    """티커 기반 마켓 분류"""
    if ticker.startswith("GOLD_KRW"):
        return "COMMODITY"
    elif ticker.endswith(".KS") or ticker.endswith(".KQ"):
        return "KR"
    elif "=F" in ticker or "=X" in ticker:
        return "COMMODITY"
    else:
        return "US"

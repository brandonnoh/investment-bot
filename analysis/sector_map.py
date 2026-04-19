#!/usr/bin/env python3
"""
섹터 → 종목 매핑 + 매크로 신호 룰셋

- SECTOR_MAP: 10개 섹터별 KR/US 종목, ETF, 키워드
- MACRO_SECTOR_RULES: 매크로 신호별 유리/불리 섹터 룰셋
- 헬퍼: get_sector_tickers, get_ticker_sector, get_all_tickers
"""

from __future__ import annotations

# ── 섹터 → 종목 매핑 (10개 섹터) ──

SECTOR_MAP: dict[str, dict] = {
    "반도체": {
        "kr": ["005930.KS", "000660.KS", "009150.KS"],
        "us": ["NVDA", "AMD", "AVGO", "TXN", "QCOM", "ADI", "INTC"],
        "etf": ["SMH", "SOXX"],
        "keywords": ["반도체", "HBM", "AI 칩", "파운드리", "semiconductor"],
    },
    "방산": {
        "kr": ["012450.KS", "047810.KS", "042660.KS", "009540.KS"],
        "us": ["LMT", "RTX", "GE", "BA", "NOC"],
        "etf": ["ITA", "XAR"],
        "keywords": ["방산", "방위", "무기", "조선", "군비", "defense"],
    },
    "바이오/헬스케어": {
        "kr": [
            "207940.KS", "068270.KS", "000100.KS",
            "128940.KS", "326030.KS",
        ],
        "us": [
            "LLY", "UNH", "MRK", "ABBV", "TMO",
            "ABT", "AMGN", "GILD", "ZTS", "REGN",
            "SYK", "ISRG", "DHR",
        ],
        "etf": ["XLV", "IBB"],
        "keywords": [
            "바이오", "제약", "헬스케어", "신약",
            "임상", "biotech", "pharma",
        ],
    },
    "2차전지": {
        "kr": ["051910.KS", "006400.KS", "003670.KS"],
        "us": ["ALB", "LTHM"],
        "etf": ["LIT", "BATT"],
        "keywords": [
            "2차전지", "배터리", "전기차 배터리",
            "리튬", "양극재", "battery",
        ],
    },
    "금융": {
        "kr": [
            "055550.KS", "105560.KS", "086790.KS",
            "316140.KS", "024110.KS",
        ],
        "us": [
            "JPM", "BAC", "GS", "MS", "V",
            "MA", "AXP", "BLK", "SCHW", "SPGI",
        ],
        "etf": ["XLF", "KBE"],
        "keywords": [
            "금융", "은행", "증권", "보험",
            "금리", "bank", "finance",
        ],
    },
    "에너지": {
        "kr": ["096770.KS", "009830.KS"],
        "us": ["XOM", "CVX"],
        "etf": ["XLE", "XOP", "USO"],
        "keywords": [
            "에너지", "유가", "원유", "정유",
            "WTI", "oil", "energy",
        ],
    },
    "AI/소프트웨어": {
        "kr": ["035420.KS", "035720.KS"],
        "us": [
            "MSFT", "GOOGL", "META", "AMZN",
            "CRM", "ORCL", "NOW", "INTU", "BKNG",
        ],
        "etf": ["QQQ", "IGV"],
        "keywords": [
            "AI", "인공지능", "클라우드",
            "소프트웨어", "플랫폼", "software",
        ],
    },
    "자동차": {
        "kr": ["005380.KS", "000270.KS", "012330.KS"],
        "us": ["TSLA", "GM", "F"],
        "etf": [],
        "keywords": ["자동차", "전기차", "EV", "automotive", "차량"],
    },
    "원자재/화학": {
        "kr": [
            "005490.KS", "051910.KS", "011170.KS",
            "010130.KS", "004020.KS",
        ],
        "us": ["LIN", "DE"],
        "etf": ["GLD", "PDBC"],
        "keywords": [
            "원자재", "철강", "화학", "금",
            "구리", "commodities",
        ],
    },
    "소비재/리테일": {
        "kr": ["139480.KS", "003490.KS"],
        "us": [
            "AMZN", "WMT", "COST", "TJX", "MCD",
            "PG", "KO", "PEP", "HD", "LOW",
        ],
        "etf": ["XLP", "XLY"],
        "keywords": [
            "소비재", "유통", "소매",
            "consumer", "retail",
        ],
    },
}

# ── 매크로 신호별 섹터 유불리 룰셋 (7개 규칙) ──

MACRO_SECTOR_RULES: dict[str, dict] = {
    "vix_high": {
        "favorable": ["방산", "원자재/화학", "소비재/리테일"],
        "unfavorable": ["AI/소프트웨어", "2차전지", "자동차"],
        "threshold": 25,
        "direction": "above",
    },
    "vix_low": {
        "favorable": ["AI/소프트웨어", "반도체", "2차전지"],
        "unfavorable": ["방산", "소비재/리테일"],
        "threshold": 15,
        "direction": "below",
    },
    "oil_surge": {
        "favorable": ["에너지", "원자재/화학"],
        "unfavorable": ["자동차", "소비재/리테일"],
        "threshold": 5.0,
        "direction": "above_change",
    },
    "oil_crash": {
        "favorable": ["자동차", "소비재/리테일", "AI/소프트웨어"],
        "unfavorable": ["에너지"],
        "threshold": -5.0,
        "direction": "below_change",
    },
    "krw_weak": {
        "favorable": ["반도체", "자동차", "방산"],
        "unfavorable": ["소비재/리테일", "금융"],
        "threshold": 1400,
        "direction": "above",
    },
    "krw_strong": {
        "favorable": ["소비재/리테일", "바이오/헬스케어"],
        "unfavorable": ["반도체", "자동차"],
        "threshold": 1300,
        "direction": "below",
    },
    "gold_surge": {
        "favorable": ["원자재/화학", "방산"],
        "unfavorable": ["AI/소프트웨어", "2차전지"],
        "threshold": 2.0,
        "direction": "above_change",
    },
}

# ── 종목명 매핑 (헬퍼용) ──

_TICKER_NAMES: dict[str, str] = {
    "005930.KS": "삼성전자", "000660.KS": "SK하이닉스",
    "009150.KS": "삼성전기", "012450.KS": "한화에어로스페이스",
    "047810.KS": "한국항공우주", "042660.KS": "한화오션",
    "009540.KS": "HD현대중공업", "207940.KS": "삼성바이오로직스",
    "068270.KS": "셀트리온", "000100.KS": "유한양행",
    "128940.KS": "한미약품", "326030.KS": "SK바이오팜",
    "051910.KS": "LG화학", "006400.KS": "삼성SDI",
    "003670.KS": "포스코퓨처엠", "055550.KS": "신한지주",
    "105560.KS": "KB금융", "086790.KS": "하나금융지주",
    "316140.KS": "우리금융지주", "024110.KS": "IBK기업은행",
    "096770.KS": "SK이노베이션", "009830.KS": "한화솔루션",
    "035420.KS": "NAVER", "035720.KS": "카카오",
    "005380.KS": "현대차", "000270.KS": "기아",
    "012330.KS": "현대모비스", "005490.KS": "POSCO홀딩스",
    "011170.KS": "롯데케미칼", "010130.KS": "고려아연",
    "004020.KS": "현대제철", "139480.KS": "이마트",
    "003490.KS": "대한항공",
    "NVDA": "NVIDIA", "AMD": "AMD", "AVGO": "Broadcom",
    "TXN": "Texas Instruments", "QCOM": "Qualcomm",
    "ADI": "Analog Devices", "INTC": "Intel",
    "LMT": "Lockheed Martin", "RTX": "RTX Corp",
    "GE": "GE Aerospace", "BA": "Boeing",
    "NOC": "Northrop Grumman",
    "LLY": "Eli Lilly", "UNH": "UnitedHealth",
    "MRK": "Merck", "ABBV": "AbbVie",
    "TMO": "Thermo Fisher", "ABT": "Abbott",
    "AMGN": "Amgen", "GILD": "Gilead",
    "ZTS": "Zoetis", "REGN": "Regeneron",
    "SYK": "Stryker", "ISRG": "Intuitive Surgical",
    "DHR": "Danaher", "ALB": "Albemarle", "LTHM": "Livent",
    "JPM": "JPMorgan", "BAC": "Bank of America",
    "GS": "Goldman Sachs", "MS": "Morgan Stanley",
    "V": "Visa", "MA": "Mastercard",
    "AXP": "American Express", "BLK": "BlackRock",
    "SCHW": "Charles Schwab", "SPGI": "S&P Global",
    "XOM": "Exxon Mobil", "CVX": "Chevron",
    "MSFT": "Microsoft", "GOOGL": "Alphabet",
    "META": "Meta", "AMZN": "Amazon",
    "CRM": "Salesforce", "ORCL": "Oracle",
    "NOW": "ServiceNow", "INTU": "Intuit",
    "BKNG": "Booking Holdings",
    "TSLA": "Tesla", "GM": "General Motors", "F": "Ford",
    "LIN": "Linde", "DE": "Deere & Company",
    "WMT": "Walmart", "COST": "Costco",
    "TJX": "TJX Companies", "MCD": "McDonald's",
    "PG": "Procter & Gamble", "KO": "Coca-Cola",
    "PEP": "PepsiCo", "HD": "Home Depot", "LOW": "Lowe's",
}


def get_sector_tickers(
    sector_name: str, market: str = "all",
) -> list[str]:
    """섹터명으로 종목 리스트 반환. market: 'kr'|'us'|'etf'|'all'"""
    sector = SECTOR_MAP.get(sector_name)
    if sector is None:
        return []
    if market == "all":
        return sector["kr"] + sector["us"] + sector["etf"]
    return list(sector.get(market, []))


def get_ticker_sector(ticker: str) -> str | None:
    """종목 코드로 소속 섹터 반환"""
    for sector_name, sector_data in SECTOR_MAP.items():
        for mkt in ("kr", "us", "etf"):
            if ticker in sector_data[mkt]:
                return sector_name
    return None


def get_all_tickers(market: str = "all") -> list[dict]:
    """전체 유니버스 종목 리스트 반환 [{ticker, name, sector, market}]"""
    results: list[dict] = []
    seen: set[str] = set()
    for sector_name, sector_data in SECTOR_MAP.items():
        markets = (
            [("kr", "KR"), ("us", "US"), ("etf", "ETF")]
            if market == "all"
            else [(_market_key(market), market.upper())]
        )
        for mkt_key, mkt_label in markets:
            for ticker in sector_data.get(mkt_key, []):
                if ticker not in seen:
                    seen.add(ticker)
                    results.append({
                        "ticker": ticker,
                        "name": _TICKER_NAMES.get(ticker, ticker),
                        "sector": sector_name,
                        "market": mkt_label,
                    })
    return results


def _market_key(market: str) -> str:
    """마켓 파라미터를 SECTOR_MAP 키로 변환"""
    return market.lower()

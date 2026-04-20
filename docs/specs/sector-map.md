# sector-map: 섹터 → 종목 매핑 + 매크로 신호 룰셋

## 배경
종목 발굴이 뉴스 텍스트 매칭에 의존하여 이미 유명한 종목(삼성전자, SK하이닉스)만 걸린다.
섹터 기반 접근을 위해 "어떤 섹터에 어떤 종목이 속하는지", "어떤 매크로 신호가 어떤 섹터에 유리한지"를 
명시적으로 정의한 레퍼런스 모듈이 필요하다.

## 현재 코드 구조
- `analysis/screener_universe.py`: UNIVERSE_KOSPI200 (50종목), UNIVERSE_SP100 (약 70종목) 이미 정의됨
  - 줄 22-75: UNIVERSE_KOSPI200 — 섹터 분류 없이 리스트만
  - 줄 78-150: UNIVERSE_SP100 — 섹터 분류 없이 리스트만
- `analysis/regime_classifier.py`: STRATEGIES 딕셔너리에 레짐별 preferred/avoid 섹터 한글명 정의됨
  - RISK_OFF → preferred: ["방산", "유틸리티", "금"]
  - RISK_ON → preferred: ["성장주", "기술주", "소비재"]
  - INFLATIONARY → preferred: ["에너지", "원자재", "금융"]

## 변경 범위
| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `analysis/sector_map.py` | 신규 생성 | SECTOR_MAP + MACRO_SECTOR_RULES |

## 구현 방향

### SECTOR_MAP 구조
```python
SECTOR_MAP: dict[str, dict] = {
    "반도체": {
        "kr": ["005930.KS", "000660.KS", "009150.KS"],  # 삼성전자, SK하이닉스, 삼성전기
        "us": ["NVDA", "AMD", "AVGO", "TXN", "QCOM", "ADI", "INTC"],
        "etf": ["SMH", "SOXX"],
        "keywords": ["반도체", "HBM", "AI 칩", "파운드리", "semiconductor"],
    },
    "방산": {
        "kr": ["012450.KS", "047810.KS", "042660.KS", "009540.KS"],  # 한화에어로, 한국항공우주, 한화오션, HD현대중공업
        "us": ["LMT", "RTX", "GE", "BA", "NOC"],
        "etf": ["ITA", "XAR"],
        "keywords": ["방산", "방위", "무기", "조선", "군비", "defense"],
    },
    "바이오/헬스케어": {
        "kr": ["207940.KS", "068270.KS", "000100.KS", "128940.KS", "326030.KS"],  # 삼성바이오, 셀트리온, 유한양행, 한미약품, SK바이오팜
        "us": ["LLY", "UNH", "MRK", "ABBV", "TMO", "ABT", "AMGN", "GILD", "ZTS", "REGN", "SYK", "ISRG", "DHR"],
        "etf": ["XLV", "IBB"],
        "keywords": ["바이오", "제약", "헬스케어", "신약", "임상", "biotech", "pharma"],
    },
    "2차전지": {
        "kr": ["051910.KS", "006400.KS", "003670.KS"],  # LG화학, 삼성SDI, 포스코퓨처엠
        "us": ["ALB", "LTHM"],
        "etf": ["LIT", "BATT"],
        "keywords": ["2차전지", "배터리", "전기차 배터리", "리튬", "양극재", "battery"],
    },
    "금융": {
        "kr": ["055550.KS", "105560.KS", "086790.KS", "316140.KS", "024110.KS"],  # 신한, KB, 하나, 우리, IBK
        "us": ["JPM", "BAC", "GS", "MS", "V", "MA", "AXP", "BLK", "SCHW", "SPGI"],
        "etf": ["XLF", "KBE"],
        "keywords": ["금융", "은행", "증권", "보험", "금리", "bank", "finance"],
    },
    "에너지": {
        "kr": ["096770.KS", "009830.KS"],  # SK이노베이션, 한화솔루션
        "us": ["XOM", "CVX"],
        "etf": ["XLE", "XOP", "USO"],
        "keywords": ["에너지", "유가", "원유", "정유", "WTI", "oil", "energy"],
    },
    "AI/소프트웨어": {
        "kr": ["035420.KS", "035720.KS"],  # NAVER, 카카오
        "us": ["MSFT", "GOOGL", "META", "AMZN", "CRM", "ORCL", "NOW", "INTU", "BKNG"],
        "etf": ["QQQ", "IGV"],
        "keywords": ["AI", "인공지능", "클라우드", "소프트웨어", "플랫폼", "software"],
    },
    "자동차": {
        "kr": ["005380.KS", "000270.KS", "012330.KS"],  # 현대차, 기아, 현대모비스
        "us": ["TSLA", "GM", "F"],
        "etf": [],
        "keywords": ["자동차", "전기차", "EV", "automotive", "차량"],
    },
    "원자재/화학": {
        "kr": ["005490.KS", "051910.KS", "011170.KS", "010130.KS", "004020.KS"],  # POSCO, LG화학, 롯데케미칼, 고려아연, 현대제철
        "us": ["LIN", "DE"],
        "etf": ["GLD", "PDBC"],
        "keywords": ["원자재", "철강", "화학", "금", "구리", "commodities"],
    },
    "소비재/리테일": {
        "kr": ["139480.KS", "003490.KS"],  # 이마트, 대한항공
        "us": ["AMZN", "WMT", "COST", "TJX", "MCD", "PG", "KO", "PEP", "HD", "LOW"],
        "etf": ["XLP", "XLY"],
        "keywords": ["소비재", "유통", "소매", "consumer", "retail"],
    },
}
```

### MACRO_SECTOR_RULES 구조
```python
# 매크로 신호별 섹터 유불리 룰셋
# signal_value: 임계값 초과/미만 시 적용
MACRO_SECTOR_RULES: dict[str, dict] = {
    "vix_high": {  # VIX > 25 (공포 국면)
        "favorable": ["방산", "원자재/화학", "소비재/리테일"],
        "unfavorable": ["AI/소프트웨어", "2차전지", "자동차"],
        "threshold": 25,
        "direction": "above",
    },
    "vix_low": {  # VIX < 15 (탐욕 국면)
        "favorable": ["AI/소프트웨어", "반도체", "2차전지"],
        "unfavorable": ["방산", "소비재/리테일"],
        "threshold": 15,
        "direction": "below",
    },
    "oil_surge": {  # WTI 변화 > +5%
        "favorable": ["에너지", "원자재/화학"],
        "unfavorable": ["자동차", "항공/운송", "소비재/리테일"],
        "threshold": 5.0,
        "direction": "above_change",
    },
    "oil_crash": {  # WTI 변화 < -5%
        "favorable": ["자동차", "소비재/리테일", "AI/소프트웨어"],
        "unfavorable": ["에너지"],
        "threshold": -5.0,
        "direction": "below_change",
    },
    "krw_weak": {  # 원달러 > 1400 (원화 약세)
        "favorable": ["반도체", "자동차", "방산"],  # 수출주 유리
        "unfavorable": ["소비재/리테일", "금융"],
        "threshold": 1400,
        "direction": "above",
    },
    "krw_strong": {  # 원달러 < 1300 (원화 강세)
        "favorable": ["소비재/리테일", "바이오/헬스케어"],
        "unfavorable": ["반도체", "자동차"],
        "threshold": 1300,
        "direction": "below",
    },
    "gold_surge": {  # 금 변화 > +2%
        "favorable": ["원자재/화학", "방산"],  # 안전자산 선호
        "unfavorable": ["AI/소프트웨어", "2차전지"],
        "threshold": 2.0,
        "direction": "above_change",
    },
}
```

### 헬퍼 함수
```python
def get_sector_tickers(sector_name: str, market: str = "all") -> list[str]:
    """섹터명으로 종목 리스트 반환. market: 'kr'|'us'|'etf'|'all'"""

def get_ticker_sector(ticker: str) -> str | None:
    """종목 코드로 소속 섹터 반환"""

def get_all_tickers(market: str = "all") -> list[dict]:
    """전체 유니버스 종목 리스트 반환 [{ticker, name, sector, market}]"""
```

## 의존 관계
- 이 파일을 읽는 곳: `analysis/sector_intel.py`, `analysis/value_screener.py`
- 이 파일이 읽는 곳: 없음 (독립 데이터 모듈)

## 수락 조건
tasks.json의 acceptance_criteria와 동일.

## 검증 명령
```bash
cd /Users/jarvis/Projects/investment-bot
python3 -c "from analysis.sector_map import SECTOR_MAP, MACRO_SECTOR_RULES; print(len(SECTOR_MAP)); print(list(SECTOR_MAP.keys()))"
ruff check analysis/sector_map.py
```

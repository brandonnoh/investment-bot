# 🏦 Investment Intelligence Engine — 시스템 아키텍처

> 최종 업데이트: 2026-03-25
> 비전: 세계 최고 수준의 개인 금융 데이터 엔진
> 원칙: 수집/계산/저장은 엔진, 해석/판단/전략은 에이전트

---

## 비전

이 엔진은 단순한 "주가 수집 스크립트"가 아니다.
**개인 투자자를 위한 기관급 금융 인텔리전스 인프라**다.

```
금융 시장 전체 → 수집 → 정제 → 저장 → 분석 → 에이전트 → 투자 판단 → (미래) 자동매매
```

엔진이 고도화될수록 에이전트의 판단 품질이 올라간다.
에이전트가 "삼성전자를 팔아야 할까?"에 답하려면, 엔진이 이미 이동평균 이탈, 외국인 수급 변화, 섹터 로테이션 신호, 뉴스 감성 악화를 계산해놓아야 한다.

---

## 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Investment Intelligence Engine                   │
│                                                                      │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐                 │
│  │  수집 계층   │ →  │  저장 계층   │ →  │  분석 계층   │                │
│  │ Collection  │    │  Storage   │    │  Analysis  │                │
│  │             │    │            │    │            │                │
│  │ • 시세      │    │ • 원시 데이터│    │ • 기술 분석 │                │
│  │ • 매크로    │    │ • 일봉 집계 │    │ • 포트폴리오│                │
│  │ • 뉴스      │    │ • 주봉/월봉 │    │ • 리스크    │                │
│  │ • 발굴      │    │ • 스냅샷    │    │ • 감성      │                │
│  └──────┬─────┘    └──────┬─────┘    └──────┬─────┘                │
│         │                 │                  │                      │
│         ▼                 ▼                  ▼                      │
│  ┌──────────────────────────────────────────────────────┐          │
│  │                  출력 인터페이스                        │          │
│  │           output/intel/ + db/history.db               │          │
│  └──────────────────────────┬───────────────────────────┘          │
└─────────────────────────────┼───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      OpenClaw (자비스 에이전트)                       │
│                                                                      │
│  • 엔진 출력 읽기 → 해석 → 판단 → 전략 수립                          │
│  • 텔레그램으로 사용자에게 인사이트 전달                               │
│  • (미래) 자동매매 명령 실행                                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 1. 수집 계층 (Collection Layer)

**목표:** 다양한 소스에서 금융 데이터를 빠짐없이, 정확하게, 안정적으로 수집

### 설계 원칙
- **어댑터 패턴**: 각 데이터 소스는 독립적인 어댑터. 새 소스 추가 = 어댑터 하나 추가
- **지능형 폴백**: 주 소스 실패 시 자동으로 대체 소스 전환
- **서킷 브레이커**: 연속 실패 시 일정 시간 해당 소스 건너뛰기 (rate limit 보호)
- **수집 시점 검증**: 수집 즉시 이상값 감지 (가격 0, 전일 대비 ±50% 등)

### 현재 소스 매트릭스

| 데이터 | 주 소스 | 폴백 | 비용 |
|--------|---------|------|------|
| 한국 주식 | Kiwoom REST | Naver Finance | 무료 |
| 미국 주식 | Yahoo Finance | — | 무료 |
| 금 현물 | Kiwoom KRX | Yahoo GC=F × 환율 | 무료 |
| 코스피/코스닥 | Naver Finance | — | 무료 |
| 환율/유가/VIX | Yahoo Finance | — | 무료 |
| 뉴스 (종목/매크로) | Google News RSS | — | 무료 |
| 뉴스 (기회 발굴) | Brave Search API | — | ~$2/월 |

### 확장 가능한 소스 (미래)
- KRX 공시 시스템 (DART API) — 기업 공시, 대주주 변동
- 한국은행 경제통계 (ECOS API) — 금리, 통화량, GDP
- FRED (미국 연준 데이터) — 미국 경제 지표
- 증권사 API — 호가, 체결, 수급 데이터
- 소셜 미디어 — 시장 심리 지표

### 모듈 구조
```
data/
├── fetch_prices.py      # 주가 수집 (멀티소스 폴백)
├── fetch_macro.py       # 매크로 지표 수집
├── fetch_news.py        # 뉴스 수집 (RSS + Brave)
├── fetch_gold_krx.py    # 키움 REST API 래퍼
├── realtime.py          # 실시간 시세 출력 (stdout)
└── (미래)
    ├── fetch_disclosure.py  # 공시 수집
    ├── fetch_supply.py      # 수급 데이터 (외국인/기관)
    └── adapters/            # 데이터 소스 어댑터 패턴
        ├── base.py
        ├── yahoo.py
        ├── naver.py
        ├── kiwoom.py
        └── brave.py
```

---

## 2. 저장 계층 (Storage Layer)

**목표:** 시계열 금융 데이터를 효율적으로 저장하고, 빠르게 조회하고, 무한히 성장해도 느려지지 않게

### 설계 원칙
- **다중 해상도 저장**: 원시(10분) → 일봉 → 주봉 → 월봉 자동 집계
- **보존 정책**: 원시 데이터는 N개월 보존, 집계 데이터는 영구 보존
- **인덱스 최적화**: 시간 범위 + 종목 조회가 주 패턴
- **스키마 확장성**: 새 종목/지표 추가 시 스키마 변경 불필요

### 테이블 설계 (ERD)

```
┌─────────────────────┐     ┌─────────────────────┐
│     prices (원시)     │     │    prices_daily      │
│─────────────────────│     │─────────────────────│
│ id (PK)             │     │ id (PK)             │
│ ticker              │ ──→ │ ticker              │
│ name                │     │ date (UNIQUE w/tick) │
│ price               │     │ open                │
│ prev_close          │     │ high                │
│ change_pct          │     │ low                 │
│ volume              │     │ close               │
│ timestamp           │     │ volume              │
│ market              │     │ change_pct          │
│ data_source         │     │ data_source         │
└─────────────────────┘     └─────────────────────┘
                                     │
                                     ▼
┌─────────────────────┐     ┌─────────────────────┐
│   macro (원시)       │     │   macro_daily        │
│─────────────────────│     │─────────────────────│
│ id (PK)             │     │ id (PK)             │
│ indicator           │     │ indicator           │
│ value               │     │ date (UNIQUE w/ind) │
│ change_pct          │     │ open, high, low     │
│ timestamp           │     │ close, change_pct   │
└─────────────────────┘     └─────────────────────┘

┌─────────────────────┐     ┌─────────────────────┐
│      news            │     │  portfolio_history   │
│─────────────────────│     │─────────────────────│
│ id (PK)             │     │ id (PK)             │
│ title               │     │ date (UNIQUE)       │
│ summary             │     │ total_value_krw     │
│ source              │     │ total_invested_krw  │
│ url                 │     │ total_pnl_krw       │
│ published_at        │     │ total_pnl_pct       │
│ relevance_score     │     │ fx_rate             │
│ sentiment           │     │ fx_pnl_krw          │
│ tickers             │     │ holdings_snapshot   │
│ category            │     │   (JSON)            │
└─────────────────────┘     └─────────────────────┘

┌─────────────────────┐     ┌─────────────────────┐
│     alerts           │     │  price_analysis      │
│─────────────────────│     │  (뷰 or 계산 결과)    │
│ id (PK)             │     │─────────────────────│
│ level               │     │ ticker              │
│ event_type          │     │ date                │
│ ticker              │     │ ma5, ma20, ma60     │
│ message             │     │ rsi_14              │
│ value               │     │ high_52w, low_52w   │
│ threshold           │     │ volatility_30d      │
│ triggered_at        │     │ trend               │
│ notified            │     │ support, resistance │
└─────────────────────┘     └─────────────────────┘
```

### 보존 정책
| 데이터 | 해상도 | 보존 기간 |
|--------|--------|----------|
| prices (원시) | 10분 | 3개월 |
| prices_daily | 일봉 | 영구 |
| macro (원시) | 10분 | 3개월 |
| macro_daily | 일봉 | 영구 |
| news | 건별 | 1년 |
| alerts | 건별 | 영구 |
| portfolio_history | 일별 | 영구 |
| price_analysis | 일별 | 최근 1년 (재계산 가능) |

### 자동 집계 & 정리
```
매일 00:00 (장 마감 후):
  1. 오늘 prices 원시 → prices_daily OHLCV 집계
  2. 오늘 macro 원시 → macro_daily OHLC 집계
  3. price_analysis 재계산 (MA, RSI, 변동성, 추세)
  4. portfolio_history 일별 스냅샷 저장

매월 1일:
  5. 3개월 이전 prices/macro 원시 데이터 삭제
  6. 1년 이전 news 삭제
  7. VACUUM (DB 최적화)
```

---

## 3. 분석 계층 (Analysis Layer)

**목표:** 에이전트가 "왜?"에 답할 수 있는 충분한 분석 데이터 제공

### 분석 모듈

| 모듈 | 출력 | 내용 |
|------|------|------|
| `price_analysis.py` | price_analysis.json | MA5/20/60, RSI, 52주 고/저, 변동성, 추세, 지지/저항 |
| `portfolio.py` | portfolio_summary.json | 종목별 손익, 섹터 비중, 환율 손익, 리스크 지표 |
| `portfolio.py` | portfolio_history 테이블 | 일별 총 자산, 수익률 추이 |
| `alerts_watch.py` | alerts.json | 임계값 초과 실시간 감지 |
| `screener.py` | screener.md | 섹터별 종목 스크리닝 |
| `news_sentiment.py` (신규) | news.json sentiment 필드 | 종목별 뉴스 감성 점수 |

### 기술 분석 지표 (price_analysis.json)
```json
{
  "updated_at": "2026-03-25T16:00:00+09:00",
  "analysis": {
    "005930.KS": {
      "name": "삼성전자",
      "current": 188300,
      "ma5": 191200, "ma20": 195400, "ma60": 198700,
      "ma_signal": "하락 (5일선 < 20일선 < 60일선)",
      "rsi_14": 38.5,
      "rsi_signal": "과매도 접근",
      "high_52w": 223000, "low_52w": 152900,
      "position_52w": "하단 25%",
      "volatility_30d": 8.3,
      "trend": "downtrend",
      "trend_duration_days": 12,
      "support": 185000, "resistance": 195000,
      "data_points": 180
    }
  }
}
```

### 포트폴리오 분석 (portfolio_summary.json)
```json
{
  "updated_at": "2026-03-25T16:00:00+09:00",
  "total_value_krw": 45230000,
  "total_invested_krw": 42000000,
  "total_pnl_krw": 3230000,
  "total_pnl_pct": 7.69,
  "fx_pnl_krw": -180000,
  "stock_pnl_krw": 3410000,
  "sector_weights": {
    "반도체": 35.2, "자동차": 18.1, "에너지": 12.4,
    "방산": 15.8, "AI인프라": 10.3, "실물자산": 8.2
  },
  "risk": {
    "max_drawdown_30d": -4.2,
    "daily_volatility": 1.8,
    "concentration_top3": 68.5
  },
  "pnl_history_30d": [
    {"date": "2026-02-24", "pnl_pct": 5.2},
    {"date": "2026-02-25", "pnl_pct": 5.8}
  ]
}
```

---

## 4. 출력 인터페이스 (Output Interface)

### output/intel/ — 에이전트가 읽는 모든 것

| 파일 | 역할 | 갱신 주기 |
|------|------|---------|
| `prices.json` | 현재가 + data_source | 장 중 10분 |
| `macro.json` | 매크로 지표 | 장 중 10분 |
| `news.json` | 뉴스 + 감성 점수 | 매시간 |
| `price_analysis.json` | 기술 분석 (MA, RSI, 추세) | 장마감 후 |
| `portfolio_summary.json` | 포트폴리오 + 환율 손익 + 리스크 | 05:00 + 장마감 |
| `alerts.json` | 긴급 알림 (있을 때만) | 실시간 |
| `daily_report.md` | 일간 리포트 | 05:00 |
| `weekly_report.md` | 주간 리포트 | 월 04:00 |
| `closing_report.md` | 장마감 리포트 | 15:40 |
| `screener.md` | 종목 스크리닝 | 05:00 |
| `engine_status.json` | 엔진 상태 (정상/에러/마지막 수집 시각) | 매 수집 시 |

### db/history.db — 시계열 데이터 직접 접근
에이전트가 필요 시 `sqlite3` 명령으로 직접 쿼리 가능.
가이드: [AGENT_GUIDE.md](AGENT_GUIDE.md)

---

## 5. 확장성 설계

### 종목 추가/삭제
```python
# config.py만 수정하면 전체 파이프라인 자동 적용
PORTFOLIO = [
    {"ticker": "000660.KS", "name": "SK하이닉스", ...},  # 추가
    # {"ticker": "005930.KS", ...},  # 삭제 (주석 처리)
]
```
- DB 스키마 변경 불필요 (ticker 기반 동적 구조)
- 새 종목 추가 즉시 수집/분석/리포트 자동 포함
- 에이전트(자비스)가 config.py를 직접 수정 가능

### 새 데이터 소스 추가
```python
# data/adapters/ 패턴 (미래)
class DartAdapter(BaseAdapter):
    def fetch(self, ticker): ...
    def validate(self, data): ...
    def fallback(self): return None
```

### 미래 확장 로드맵
| Phase | 내용 |
|-------|------|
| 3 (현재) | 기술 분석, DB 최적화, 테스트, 에이전트 가이드 |
| 4 | 수급 데이터 (외국인/기관), 공시 수집, 상관관계 분석 |
| 5 | 백테스트 엔진, 시뮬레이션, 전략 검증 |
| 6 | 자동매매 API 연동 (증권사 주문 실행) |

---

## 6. config.py 중앙 관리

```python
# 모든 설정은 config.py 한 곳에서 관리
PORTFOLIO = [...]           # 종목 목록 + 보유 수량 + 평단가
MACRO_INDICATORS = [...]    # 매크로 지표 목록
ALERT_THRESHOLDS = {...}    # 알림 임계값
NEWS_KEYWORDS = {...}       # 뉴스 수집 키워드
RETENTION_POLICY = {...}    # 데이터 보존 기간
ANALYSIS_PARAMS = {...}     # 분석 파라미터 (MA 기간, RSI 기간 등)
```

---

## 7. 스케줄 (crontab)

| 주기 | 모듈 | 시간 |
|------|------|------|
| 10분마다 | fetch_prices, fetch_macro, alerts_watch | 평일 09:00-15:30 |
| 매시간 | fetch_news | 24시간 |
| 일 1회 | run_pipeline.py | 05:00 |
| 일 1회 | 일봉 집계 + price_analysis | 16:00 (장마감 후) |
| 주 1회 | run_pipeline.py --weekly | 월요일 04:00 |
| 월 1회 | DB 정리 (원시 데이터 삭제 + VACUUM) | 매월 1일 01:00 |

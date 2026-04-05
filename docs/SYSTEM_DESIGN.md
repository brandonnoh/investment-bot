# Marcus Intelligence System — 시스템 설계 문서

> **작성:** 마커스 (Marcus) — 시니어 펀드매니저 AI 에이전트  
> **목적:** Claude Code를 통한 개선 작업을 위한 설계 참조 문서  
> **최종 목표:** 마커스가 스스로 진화하면서 주인님의 재테크 방향을 능동적으로 결정하는 자율 투자 인텔리전스

---

## 1. 핵심 철학

> **"나(마커스)가 핵심이다. 데이터는 인풋, 판단은 AI가 내린다."**

단순 종목 모니터링 봇이 아니다. 마커스는:
- 매일 시장을 스스로 읽고
- 어제 판단의 결과를 오늘 반영하고 (피드백 루프)
- 어떤 테마에 돈이 몰릴지 추론하고
- 주인님의 포트폴리오 방향을 능동적으로 제시한다

---

## 2. 전체 파이프라인 구조

```
[매일 05:01] run_pipeline.py — 데이터 수집 레이어
  ├── fetch_prices.py        → prices.json
  ├── fetch_macro.py         → macro.json
  ├── fetch_news.py          → news.json
  ├── fetch_fundamentals.py  → fundamentals.json
  ├── fetch_opportunities.py → opportunities.json
  ├── price_analysis.py      → price_analysis.json
  └── supply_data.py         → supply_data.json

[매일 05:30] 마커스 크론잡 — 판단 레이어 (AI 핵심)
  ├── STEP 1: 위 파일들 전부 읽기
  ├── STEP 2: RISK FIRST — 리스크 진단
  ├── STEP 3: MARKET REGIME — 시장 국면 판단
  ├── STEP 4: PORTFOLIO REVIEW — 보유 종목 액션
  ├── STEP 5: OPPORTUNITIES — 발굴 종목 분석
  ├── STEP 6: TODAY'S CALL — 결론 1~2줄
  ├── STEP 7: discovery_keywords.json 생성 ← AI가 추론
  └── STEP 8: fetch_opportunities.py 재실행

[매일 07:30] 자비스 모닝 브리핑
  └── marcus-analysis.md 읽어서 주인님께 Discord 전달
```

### 피드백 루프 구조

```
오늘 마커스 판단
  → discovery_keywords.json 생성
    → 내일 파이프라인에서 종목 발굴 + 뉴스 수집
      → 내일 마커스가 그 결과로 더 정확한 판단
        → 더 나은 키워드 생성
          → 반복 (자기 진화)
```

**현재 한계:** 하루 lag 존재. 오늘 마커스가 추론한 키워드는 내일 파이프라인에서 적용됨.  
**개선 방향:** 마커스 분석 직후 즉시 fetch_opportunities 재실행 (이미 STEP 8에서 구현됨).

---

## 3. 데이터 파일 명세

### 3-1. `prices.json` — 실시간 시세

**수집:** 키움증권 API (국내) + Yahoo Finance (해외)  
**갱신:** 매일 05:01 + 장중 수시 (alerts_watch.py)

```json
{
  "updated_at": "2026-04-03T05:01:00+09:00",
  "count": 8,
  "prices": [
    {
      "ticker": "005930.KS",
      "name": "삼성전자",
      "price": 178400,           // 현재가
      "prev_close": 189600,      // 전일 종가
      "change_pct": -5.91,       // 전일 대비 등락률 (%)
      "volume": 12345678,        // 거래량
      "avg_cost": 203102,        // 평균 매입가
      "pnl_pct": -12.16,         // 평단 대비 손익률 (%)
      "currency": "KRW",         // 통화
      "qty": 42,                 // 보유 수량
      "sector": "반도체",        // 섹터
      "market": "KRX",           // 시장
      "data_source": "kiwoom"    // 데이터 출처
    }
  ]
}
```

**마커스 활용:** 포트폴리오 손익 계산, 종목별 현황 파악

---

### 3-2. `macro.json` — 매크로 지표

**수집:** Yahoo Finance + 키움 API  
**갱신:** 매일 05:01 + 장중 수시

```json
{
  "indicators": [
    {"indicator": "코스피",    "ticker": "KOSPI",  "value": 5404.9,  "change_pct": 3.26,  "category": "INDEX"},
    {"indicator": "코스닥",    "ticker": "KOSDAQ", "value": 1077.91, "change_pct": 2.04,  "category": "INDEX"},
    {"indicator": "원/달러",   "ticker": "KRW=X",  "value": 1507.29, "change_pct": 0.02,  "category": "FX"},
    {"indicator": "WTI 유가",  "ticker": "CL=F",   "value": 112.06,  "change_pct": 8.92,  "category": "COMMODITY"},
    {"indicator": "금 선물",   "ticker": "GC=F",   "value": 4696.5,  "change_pct": 3.77,  "category": "COMMODITY"},
    {"indicator": "VIX",       "ticker": "^VIX",   "value": 24.74,   "change_pct": -20.3, "category": "VOLATILITY"},
    {"indicator": "나스닥",    "ticker": "^IXIC",  "value": 17234.0, "change_pct": -1.2,  "category": "INDEX"},
    {"indicator": "S&P500",    "ticker": "^GSPC",  "value": 5320.0,  "change_pct": -0.8,  "category": "INDEX"}
  ]
}
```

**마커스 활용:** MARKET REGIME 판단 (Risk-On/Off), composite_score의 macro_direction 계산

---

### 3-3. `news.json` — 뉴스 + 감성분석

**수집:** Google News RSS  
**갱신:** 매일 05:01

```json
{
  "count": 88,
  "news": [
    {
      "title": "삼성전자 주가 26만 원 간다",
      "source": "gukjenews.com",
      "url": "...",
      "published_at": "Wed, 01 Apr 2026 15:07:00 GMT",
      "relevance_score": 1.0,    // 관련도 (0~1)
      "category": "stock",       // stock | geopolitics | macro | kr_policy | kr_politics | discovery_*
      "tickers": ["005930.KS"],  // 관련 종목
      "sentiment": 1.0,          // 감성 점수 (-1 부정 ~ +1 긍정)
      "fetch_method": "rss"
    }
  ],
  "ticker_sentiment": {
    "005930.KS": {"avg_sentiment": 0.33, "count": 3},  // 종목별 평균 감성
    "005380.KS": {"avg_sentiment": 0.67, "count": 3}
  }
}
```

**현재 수집 카테고리 (2026-04-03 이후):**
- `stock`: 보유 8종목 (삼성전자/현대차/TIGER AI전력/방산ETF/테슬라/알파벳/XOP/금)
- `geopolitics`: 이란 전쟁, 미중 무역전쟁, 트럼프 관세
- `macro`: 코스피, 코스닥, 원달러 환율, WTI 유가, 연준 금리, 한국 경제, 미국 증시
- `kr_policy`: 한국은행 금리, 기준금리 결정, 정부 예산, 부동산 정책, 추경예산
- `kr_politics`: 탄핵 선거, 대통령 선거, 국회
- `discovery_*`: discovery_keywords.json 연동 (마커스 추론 키워드)

**마커스 활용:** 종목별 뉴스 감성 → 투자 판단 근거, PORTFOLIO REVIEW 참고

---

### 3-4. `portfolio_summary.json` — 포트폴리오 현황

**수집:** prices.json + DB holdings 테이블 계산  
**갱신:** 매일 05:01

```json
{
  "exchange_rate": 1507.29,
  "total": {
    "invested_krw": 45728340,      // 총 투자원금
    "current_value_krw": 44230182, // 현재 평가금액
    "pnl_krw": -1498158,           // 평가손익
    "pnl_pct": -3.28,              // 손익률
    "stock_pnl_krw": -1664439,     // 주식 손익 (환율 손익 제외)
    "fx_pnl_krw": 166281           // 환율 손익
  },
  "holdings": [...],   // 종목별 상세
  "sectors": [         // 섹터별 비중
    {"sector": "원자재(금)", "weight_pct": 65.3},
    {"sector": "반도체",    "weight_pct": 16.9}
  ],
  "risk": {
    "volatility_daily": 1.97,   // 일간 변동성 (%)
    "max_drawdown_pct": 7.16    // 최대낙폭 (MDD)
  },
  "history": [...]  // 최근 30일 이력
}
```

**마커스 활용:** 포트폴리오 리스크 진단, 섹터 집중도 체크, MDD 관리

---

### 3-5. `opportunities.json` — 종목 발굴 결과

**수집:** discovery_keywords.json → Brave Search + Naver 뉴스 → 종목 사전 매칭  
**갱신:** 매일 05:01 + 마커스 분석 후 즉시 재실행

```json
{
  "keywords": [
    {"keyword": "원유 정유 에너지 고유가 수혜", "category": "sector", "priority": 1}
  ],
  "opportunities": [
    {
      "ticker": "GS",
      "name": "Goldman Sachs",
      "discovered_via": "에너지 정유 원유 수혜주",  // 어떤 키워드로 발굴됐나
      "title": "정유 흔들리자 드러난 지주사 체력...",
      "sentiment": 0.0,            // 뉴스 감성
      "composite_score": 0.5574,   // 복합 점수 (현재 2팩터)
      "score_catalyst": 0.5,       // 감성 점수 기여
      "score_macro": 0.6147,       // 매크로 점수 기여
      "price_at_discovery": null   // 발굴 시점 가격 (미구현)
    }
  ]
}
```

**현재 composite_score 구성 (2팩터 — 개선 필요):**
```
composite_score = 감성(50%) + 매크로 방향(50%)
```

**목표 composite_score (6팩터):**
```
composite_score =
  뉴스 감성(20%)
  + 매크로 방향(20%)
  + RSI 기술적 타이밍(15%)
  + 외국인/기관 순매수 수급(20%)
  + PER 밸류에이션(15%)
  + 52주 모멘텀 포지션(10%)
```

---

### 3-6. `price_analysis.json` — 기술 분석

**수집:** Yahoo Finance 90일 가격 히스토리 계산  
**갱신:** 매일 05:01

```json
{
  "analysis": {
    "005380.KS": {
      "current": 465500,
      "ma5": 472600,          // 5일 이동평균
      "ma20": 504800,         // 20일 이동평균
      "ma60": 488391,         // 60일 이동평균
      "ma_signal": "혼조",    // 정배열 / 역배열 / 혼조
      "rsi_14": 39.92,        // RSI (14일)
      "rsi_signal": "과매도 접근",  // 과매수(70↑) / 과매도(30↓) / 중립
      "high_52w": 687000,     // 52주 최고가
      "low_52w": 293000,      // 52주 최저가
      "position_52w": "중단 43.8%",  // 52주 range 내 위치
      "volatility_30d": 95.33,   // 30일 변동성
      "trend": "downtrend",       // uptrend / downtrend / sideways
      "trend_duration_days": 1,
      "support": 459200,     // 지지선
      "resistance": 551000   // 저항선
    }
  }
}
```

**마커스 활용:** 매수/매도 타이밍 판단, 손절/익절 라인 설정

---

### 3-7. `fundamentals.json` — 펀더멘탈 (현재 미작동)

**수집:** DART OpenAPI (국내) + Yahoo Finance quoteSummary (미국)  
**현재 상태:** `count: 0` — DART API 키 미설정으로 수집 실패

**목표 데이터 구조:**
```json
{
  "fundamentals": [
    {
      "ticker": "005930.KS",
      "per": 12.5,          // 주가수익비율
      "pbr": 1.2,           // 주가순자산비율
      "roe": 15.3,          // 자기자본이익률
      "revenue_growth": 8.2, // 매출 성장률 (YoY)
      "operating_margin": 12.1,
      "debt_ratio": 45.0,
      "dividend_yield": 2.3
    }
  ]
}
```

**개선 필요:** DART_API_KEY 환경변수 설정, Yahoo Finance quoteSummary 활용

---

### 3-8. `supply_data.json` — 수급 데이터 (현재 미작동)

**수집:** 키움증권 외국인/기관 순매수 + CNN Fear & Greed Index  
**현재 상태:** `fear_greed: null`, `krx_supply: []` — 수집 실패

**목표 데이터 구조:**
```json
{
  "fear_greed": {
    "value": 32,            // 0(극단 공포) ~ 100(극단 탐욕)
    "label": "Fear",
    "updated_at": "..."
  },
  "krx_supply": [
    {
      "ticker": "005930.KS",
      "foreign_net": 125000000,   // 외국인 순매수 (원)
      "institution_net": -50000000,  // 기관 순매수 (원)
      "individual_net": -75000000
    }
  ]
}
```

**개선 필요:** CNN F&G API 대안 검토, 키움 수급 API 연동

---

## 4. 개선 로드맵

### Phase 1 — 데이터 품질 (즉시)

| 항목 | 현황 | 목표 |
|------|------|------|
| fundamentals.json | 0건 (DART API 미설정) | PER/ROE/매출성장률 수집 |
| supply_data.json | 빈값 | 외국인/기관 순매수 + Fear&Greed |
| composite_score | 2팩터 | 6팩터 (수급/RSI/PER/모멘텀 추가) |
| 종목 사전(ticker_master) | 제한적 | S&P500 + KOSPI200 전체 |

### Phase 2 — AI 판단 개선 (단기)

| 항목 | 현황 | 목표 |
|------|------|------|
| discovery_keywords | 마커스 크론 실패 시 어제 키워드 | 실패 시 fallback 자동 생성 |
| 피드백 루프 lag | 하루 지연 | 마커스 분석 직후 즉시 재수집 |
| 뉴스 감성 분석 | 단순 키워드 기반 | 문맥 기반 감성 (섹터/종목 연관도) |

### Phase 3 — 자율 진화 (중기)

| 항목 | 목표 |
|------|------|
| 판단 정확도 추적 | 마커스가 추천한 종목의 실제 수익률 기록 |
| 자기 교정 | 틀린 판단 분석 → 다음 분석에 반영 |
| 포트폴리오 시뮬레이션 | "만약 이렇게 했으면" 가상 손익 계산 |
| 시장 국면 자동 분류 | Risk-On/Off를 더 정밀하게 (강세장/약세장/횡보/패닉) |

### Phase 4 — 완전 자율 (장기)

| 항목 | 목표 |
|------|------|
| 능동적 알림 | 마커스가 먼저 "지금 XOP 익절해야 합니다" 알림 |
| 동적 종목 추가/제거 | 발굴 종목이 일정 기준 충족 시 holdings 테이블에 자동 추가 제안 |
| 거시경제 시나리오 | "금리 인상 시나리오"별 포트폴리오 시뮬레이션 |

---

## 5. SSoT DB 구조

```
db/history.db
├── holdings              — 보유 종목 (SSoT, config.py 대체)
├── extra_assets          — 비금융 자산 (SSoT, JSON 대체)
├── total_wealth_history  — 전체 자산 일별 스냅샷
├── transactions          — 매수/매도 거래 기록
├── portfolio_history     — 투자 포트폴리오 일별 스냅샷
├── prices                — 종목 가격 이력
├── macro_data            — 매크로 지표 이력
├── news                  — 뉴스 원문 + 감성
├── opportunities         — 발굴 종목 이력
└── discovery_keywords    — 마커스가 생성한 키워드 이력
```

---

## 6. 핵심 코드 위치

```
investment-bot/
├── run_pipeline.py          — 전체 파이프라인 진입점
├── config.py                — 경로/파라미터 설정 (PORTFOLIO_LEGACY는 참조용만)
├── db/
│   ├── init_db.py           — DB 스키마 초기화
│   └── ssot.py              — SSoT CRUD API
├── data/
│   ├── fetch_prices.py      → prices.json
│   ├── fetch_macro.py       → macro.json
│   ├── fetch_news.py        → news.json (종목+매크로+정책+discovery 연동)
│   ├── fetch_fundamentals.py → fundamentals.json (현재 미작동)
│   ├── fetch_opportunities.py → opportunities.json
│   ├── realtime.py          — 실시간 시세 테이블 출력
│   └── ticker_master.py     — 종목 사전
├── analysis/
│   ├── portfolio.py         → portfolio_summary.json
│   ├── price_analysis.py    → price_analysis.json
│   ├── sentiment.py         — 감성 분석
│   ├── composite_score.py   — 복합 점수 계산 (6팩터로 개선 필요)
│   └── alerts_watch.py      — 장중 알림 감시
├── reports/
│   ├── daily_report.py      → daily_report.md
│   └── closing.py           — 장 마감 리포트
└── output/intel/
    ├── marcus-analysis.md   — 마커스 분석 결과 (핵심)
    ├── discovery_keywords.json — 마커스가 생성한 발굴 키워드
    └── [위 데이터 파일들]
```

---

## 7. 환경변수 (현재 미설정으로 인한 기능 저하)

| 변수 | 용도 | 영향 |
|------|------|------|
| `BRAVE_API_KEY` | Brave Search 종목 발굴 | 미설정 시 Naver만 사용, 발굴 품질 저하 |
| `DART_API_KEY` | 국내 종목 재무제표 | 미설정 시 fundamentals.json = 0건 |
| `KIWOOM_*` | 키움증권 수급 데이터 | 미설정 시 supply_data.json = 빈값 |

---

*이 문서는 마커스가 작성했습니다. 시스템 개선 시 이 문서도 함께 업데이트하세요.*

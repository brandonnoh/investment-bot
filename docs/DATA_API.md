# Investment Bot — 데이터 통합 가이드

외부 서비스(AI 에이전트, 분석 도구, 대시보드 등)가 이 엔진의 데이터를 소비하는 방법.

---

## 접근 방법 2가지

### 1. HTTP API (권장)

Flask API 서버가 항상 가동 중. 인증 없음 (내부 네트워크 전용).

```
Base URL: http://100.90.201.87:8421
```

### 2. JSON 파일 직접 읽기

파이프라인이 매일 아침 `output/intel/` 에 JSON 파일을 생성한다.
볼륨 마운트된 환경이라면 파일을 직접 읽어도 된다.

```
/app/output/intel/   # Docker 컨테이너 내부 경로
```

---

## 실시간 업데이트 (SSE)

파일이 바뀌면 즉시 이벤트를 푸시한다. 폴링 불필요.

```
GET /api/events
Content-Type: text/event-stream
```

이벤트 수신 시 `/api/data`를 다시 호출해 최신 데이터를 가져오면 된다.

---

## 주요 엔드포인트

### 전체 통합 데이터

```
GET /api/data
```

아래 JSON 파일을 하나로 병합해 반환한다. 대부분의 use case는 이것 하나로 충분하다.

```json
{
  "prices": { ... },
  "macro": { ... },
  "opportunities": { ... },
  "portfolio_summary": { ... },
  "regime": { ... },
  "sector_scores": { ... },
  "news": { ... },
  "screener_results": { ... },
  "engine_status": { ... },
  "fundamentals": { ... },
  "supply_data": { ... },
  "performance_report": { ... },
  "correction_notes": { ... },
  "holdings_proposal": { ... },
  "simulation_report": { ... },
  "proactive_alerts": { ... },
  ...
}
```

---

## JSON 파일별 스키마

### `prices.json` — 보유 종목 현재가

```json
{
  "updated_at": "2026-05-02T15:12:47.670466+09:00",  // ISO 8601 KST
  "count": 8,                                          // int
  "prices": [
    {
      "ticker": "005380.KS",
      "name": "현대차",
      "price": 531000,           // number (KRW 정수 or USD float)
      "prev_close": 556000,      // number
      "change_pct": -4.5,        // float, 전일 대비 %
      "volume": 1150241,         // int
      "avg_cost": 519000.0,      // float, 평균 매입가
      "pnl_pct": 2.31,           // float, 보유 수익률 %
      "currency": "KRW",         // "KRW" | "USD"
      "qty": 9.0,                // float, 보유 수량
      "sector": "",              // string (빈 문자열일 수 있음)
      "market": "KR",            // "KR" | "US" | "COMMODITY"
      "timestamp": "2026-05-02T15:12:46.499294+09:00",  // ISO 8601 KST
      "data_source": "kiwoom"    // "kiwoom" | "yahoo"
    },
    {
      "ticker": "GOOGL",
      "name": "알파벳",
      "price": 385.69,
      "prev_close": 384.8,
      "change_pct": 0.23,
      "volume": 29974345,
      "avg_cost": 308.27,
      "pnl_pct": 25.11,
      "currency": "USD",
      "qty": 2.0,
      "sector": "",
      "market": "US",
      "timestamp": "2026-05-02T15:12:46.499294+09:00",
      "data_source": "yahoo",
      "buy_fx_rate": 1380.0      // float, 매수 시 환율 (USD 종목만 존재)
    },
    ...
  ]
}
```

- 갱신: 매 1분 (`scripts/refresh_prices.py`)
- 대상: `config.py`의 `PORTFOLIO` 종목 (현재 8개)
- `buy_fx_rate`는 USD 종목에만 존재하는 선택적 필드

---

### `macro.json` — 매크로 지표

```json
{
  "updated_at": "2026-05-02T15:12:49.334291+09:00",  // ISO 8601 KST
  "count": 8,                                          // int
  "indicators": [
    {
      "indicator": "코스피",
      "ticker": "KOSPI",
      "value": 6598.87,          // float
      "prev_close": 6691.21,     // float
      "change_pct": -1.38,       // float
      "category": "INDEX",       // "INDEX" | "FX" | "COMMODITY" | "VOLATILITY"
      "timestamp": "2026-05-02T15:12:47.671386+09:00"  // ISO 8601 KST
    },
    {
      "indicator": "원/달러",
      "ticker": "KRW=X",
      "value": 1471.22,
      "prev_close": 1474.69,
      "change_pct": -0.24,
      "category": "FX",
      "timestamp": "2026-05-02T15:12:47.671386+09:00"
    },
    ...
  ]
}
```

- 지표: 코스피(INDEX), 코스닥(INDEX), 원/달러(FX), WTI 유가(COMMODITY), 브렌트유(COMMODITY), 금 현물(COMMODITY), 달러 인덱스(FX), VIX(VOLATILITY)
- 갱신: 매일 07:40 파이프라인

---

### `opportunities.json` — 발굴 종목

```json
{
  "updated_at": "2026-05-02T15:21:32.734039+09:00",  // ISO 8601 KST
  "keywords": [
    {
      "keyword": "AI/소프트웨어",    // string
      "category": "marcus_sector",  // "marcus_sector" | "sector"
      "priority": 1                  // int, 낮을수록 우선
    },
    ...
  ],
  "opportunities": [
    {
      "ticker": "CNX",
      "name": "CNX Resources",
      "sector": "에너지",
      "screen_reason": "PER 5 저평가 + ROE 28% + 매출 29% 성장",  // string
      "grade": "B+",               // "A" | "A-" | "B+" | "B" | ...
      "composite_score": 0.776,    // float 0~1
      "factors": {
        "quality": 0.909,          // float 0~1
        "value": 0.858,            // float 0~1
        "flow": 0.5,               // float 0~1
        "momentum": 0.6,           // float 0~1
        "growth": 0.99             // float 0~1
      },
      "rsi": 41.48,                // float
      "per": 5.05,                 // float | null
      "pbr": 1.25,                 // float | null
      "roe": 28.08,                // float | null
      "pos_52w": 28.3,             // float, 52주 최고가 대비 현재 위치 %
      "discovered_via": "퀀트발굴:에너지",  // string
      "source": "value_screener_v2"        // string
    },
    ...
  ],
  "summary": {
    "total_count": 49,             // int
    "by_sector": {
      "에너지": 14,
      "AI/소프트웨어": 26,
      "방산": 4,
      "원자재/화학": 5
    },
    "top_reason": "52주 저점 근접"  // string
  }
}
```

- 전략별 조회: `GET /api/opportunities?strategy=graham` (composite/graham/buffett/lynch/greenblatt)
- 갱신: 매일 07:40 파이프라인
- `total_count` 최상위 키가 없음 — 총 건수는 `summary.total_count`에 있음

---

### `portfolio_summary.json` — 포트폴리오 분석

```json
{
  "updated_at": "2026-05-02T15:25:35.329114+09:00",  // ISO 8601 KST
  "exchange_rate": 1471.22,          // float, 원/달러
  "total": {
    "invested_krw": 45704937,        // int, 총 투자금 (원)
    "current_value_krw": 46397112,   // int, 현재 평가금액 (원)
    "pnl_krw": 692175,               // int, 총 손익 (원)
    "pnl_pct": 1.51,                 // float, 총 수익률 %
    "stock_pnl_krw": 561852,         // int, 주가 손익 (원)
    "fx_pnl_krw": 130322             // int, 환율 손익 (원)
  },
  "holdings": [
    {
      "ticker": "005380.KS",
      "name": "현대차",
      "sector": "자동차",
      "currency": "KRW",             // "KRW" | "USD"
      "price": 531000,               // number, 현재가
      "avg_cost": 519000.0,          // float, 평균 매입가
      "qty": 9.0,                    // float, 보유 수량
      "current_value_krw": 4779000,  // int, 현재 평가금액 (원)
      "invested_krw": 4671000,       // int, 투자금 (원)
      "pnl_krw": 108000,             // int, 손익 (원)
      "pnl_pct": 2.31,               // float, 수익률 %
      "stock_pnl_krw": 108000,       // int, 주가 손익 (원)
      "fx_pnl_krw": 0,               // int, 환율 손익 (원, KRW 종목은 항상 0)
      "pnl_label": null,             // string | null
      "change_pct": -4.5             // float, 당일 등락률 %
    },
    ...
  ],
  "sectors": [
    {
      "sector": "원자재(금)",
      "weight_pct": 59.9,            // float, 포트폴리오 비중 %
      "value_krw": 27806720,         // int, 평가금액 (원)
      "pnl_pct": -3.69,              // float, 섹터 수익률 %
      "stocks": ["금 현물"]           // string[], 해당 섹터 보유 종목명
    },
    ...
  ],
  "risk": {
    "max_drawdown_pct": 1.26,        // float, 최대 낙폭 % (양수 = 현재 고점에서 낙폭)
    "volatility_daily": 0.83,        // float, 일간 변동성 %
    "worst_performer": {
      "name": "TIGER 미국방산TOP10",
      "pnl_pct": -4.55               // float
    },
    "best_performer": {
      "name": "TIGER 코리아AI전력기",
      "pnl_pct": 62.22               // float
    }
  },
  "history": [
    {
      "date": "2026-04-03",           // "YYYY-MM-DD"
      "total_value_krw": 44833343.0,  // float
      "total_invested_krw": 45704937.0,
      "total_pnl_krw": -871594.0,
      "total_pnl_pct": -1.91,         // float
      "fx_rate": 1504.68              // float
    },
    ...
  ]
}
```

---

### `regime.json` — 시장 레짐

```json
{
  "classified_at": "2026-05-02T15:13:20.564591+09:00",  // ISO 8601 KST
  "regime": "INFLATIONARY",   // 레짐 종류 (아래 참조)
  "confidence": 0.25,         // float 0~1
  "panic_signal": false,      // bool
  "vix": 16.99,               // float, VIX 지수
  "fx_change": -0.24,         // float, 원/달러 전일 대비 %
  "oil_change": 5.78,         // float, WTI 전일 대비 %
  "strategy": {
    "stance": "중립",                           // string (한국어)
    "preferred_sectors": ["에너지", "소재", "원자재"],
    "avoid_sectors": ["성장주", "채권"],
    "cash_ratio": 0.2          // float 0~1, 권장 현금 비율
  }
}
```

레짐 종류: `BULL` / `BEAR` / `SIDEWAYS` / `CRISIS` / `INFLATIONARY` / `DEFLATIONARY`

---

### `sector_scores.json` — 섹터별 점수

```json
{
  "updated_at": "2026-05-02T15:13:30.862744+09:00",  // ISO 8601 KST
  "regime": "INFLATIONARY",
  "sectors": [
    {
      "name": "에너지",
      "score": 10.5,             // float, 점수 (높을수록 유망)
      "signal": "favorable",     // "favorable" | "neutral" | "unfavorable"
      "reasoning": "레짐 INFLATIONARY; 매크로 룰: oil_surge; 뉴스 언급 9건",
      "top_tickers": [
        "096770.KS",
        "009830.KS",
        "XOM",
        "CVX"
      ]
    },
    {
      "name": "소비재/리테일",
      "score": 2.0,
      "signal": "unfavorable",
      "reasoning": "레짐 INFLATIONARY; 매크로 룰: oil_surge, krw_weak",
      "top_tickers": ["139480.KS", "003490.KS", "AMZN", "WMT"]
    },
    ...
  ]
}
```

---

### `news.json` — 뉴스 + 감성

```json
{
  "updated_at": "2026-05-02T17:30:36.220559+09:00",  // ISO 8601 KST
  "count": 118,  // int
  "news": [
    {
      "title": "\"미국인들 '이란전쟁 당장 끝내야'\" - v.daum.net",
      "summary": "",                  // string (빈 문자열일 수 있음)
      "source": "v.daum.net",
      "url": "https://...",
      "published_at": "Fri, 01 May 2026 13:56:16 GMT",  // RFC 2822 형식
      "relevance_score": 0.9,         // float 0~1
      "category": "geopolitics",      // string (예: "geopolitics", "earnings", ...)
      "tickers": [],                  // string[], 관련 ticker 목록 (빈 배열일 수 있음)
      "ticker_name": "이란 전쟁",      // string, 관련 키워드/종목명
      "fetch_method": "rss",          // "rss" | "brave"
      "timestamp": "2026-05-02T17:30:01.181749+09:00",  // ISO 8601 KST, 수집 시각
      "sentiment": -1.0               // float -1~1 (-1=매우 부정, 0=중립, 1=매우 긍정)
    },
    ...
  ],
  "ticker_sentiment": {
    "TSLA": {
      "avg_sentiment": 0.5,  // float
      "count": 2             // int
    },
    "005380.KS": {
      "avg_sentiment": 0.0,
      "count": 2
    }
  }
}
```

---

### `screener_results.json` — 스크리너 TOP 10

```json
{
  "generated_at": "2026-05-02T15:25:35.215854+09:00",  // ISO 8601 KST
  "kospi200_top10": [
    {
      "ticker": "237880.KS",
      "name": "클리오",
      "market": "KR",
      "price": 35800.0,       // float
      "day_change": 205.46,   // float, 당일 등락률 %
      "month_return": 205.46, // float, 1개월 수익률 %
      "volume": 0,            // int (0이면 거래량 미수집)
      "currency": "KRW"       // "KRW" | "USD"
    },
    ...
  ],
  "sp100_top10": [
    {
      "ticker": "INTC",
      "name": "Intel",
      "market": "US",
      "price": 99.62,
      "day_change": 107.41,
      "month_return": 97.74,
      "volume": 156874061,
      "currency": "USD"
    },
    ...
  ],
  "total_kospi_scanned": 200,  // int, 스캔한 KOSPI 종목 수
  "total_sp_scanned": 500      // int, 스캔한 S&P 종목 수
}
```

---

### `engine_status.json` — 파이프라인 상태

```json
{
  "updated_at": "2026-05-02T15:25:35.359926+09:00",  // ISO 8601 KST
  "pipeline_ok": true,        // bool
  "total_errors": 0,          // int
  "db_size_mb": 35.09,        // float, SQLite DB 파일 크기
  "uptime_days": 37,          // int, 첫 실행일 기준 경과 일수
  "first_run": "2026-03-25T17:01:50.692348+09:00",  // ISO 8601 KST
  "modules": {
    "fetch_prices": {
      "success": true,         // bool
      "item_count": 8,         // int, 처리된 아이템 수
      "error_count": 0,        // int
      "last_run": "2026-05-02T15:12:47.671326+09:00"  // ISO 8601 KST
    },
    "fetch_macro": {
      "success": true,
      "item_count": 8,
      "error_count": 0,
      "last_run": "2026-05-02T15:12:49.334924+09:00"
    },
    "fetch_news": { "success": true, "item_count": 119, "error_count": 0, "last_run": "..." },
    "fetch_fundamentals": { "success": true, "item_count": 680, "error_count": 0, "last_run": "..." },
    "fetch_opportunities": { "success": true, "item_count": 49, "error_count": 0, "last_run": "..." }
  }
}
```

---

### `alerts.json` — 투자 알림 *(알림 있을 때만 존재)*

파일이 없으면 = 현재 알림 없음. 알림이 해소되면 파일이 삭제된다.

```json
{
  "triggered_at": "2026-05-02T15:21:35.386801+09:00",  // ISO 8601 KST
  "count": 1,  // int
  "alerts": [
    {
      "level": "YELLOW",          // "YELLOW" | "ORANGE" | "RED"
      "event_type": "oil_surge",  // string (예: "oil_surge", "price_surge", "price_crash", ...)
      "ticker": "CL=F",
      "message": "🟡 주의: WTI 유가 +5.78% 급등 (현재: $101.94)",
      "value": 5.78,              // float, 트리거된 값
      "threshold": 5.0            // float, 임계값
    }
  ]
}
```

level 색상 의미: `YELLOW`=주의, `ORANGE`=경고, `RED`=위험

---

### `fundamentals.json` — 종목별 펀더멘탈

```json
{
  "updated_at": "2026-05-02T15:13:29.032287+09:00",  // ISO 8601 KST
  "count": 680,  // int, 전체 종목 수
  "fundamentals": [
    {
      "ticker": "000070.KS",
      "name": "삼양홀딩스",
      "market": "KR",              // "KR" | "US"
      "per": null,                 // float | null
      "pbr": 0.26,                 // float | null
      "roe": -10.98,               // float | null
      "debt_ratio": 53.67,         // float | null, 부채비율 %
      "revenue_growth": null,      // float | null, 매출 성장률 %
      "operating_margin": 3.25,    // float | null, 영업이익률 %
      "fcf": 445565698048.0,       // float | null, 잉여현금흐름 (원 단위)
      "eps": -23161.0,             // float | null, 주당순이익
      "dividend_yield": 501.0,     // float | null, 배당수익률 (단위: 원/주 — KR 종목)
      "market_cap": 488315912192.0, // float | null, 시가총액 (원)
      "data_source": "yahoo_universe",  // string
      "updated_at": "2026-05-01T07:01:19.369019+09:00"  // ISO 8601 KST
    },
    ...
  ]
}
```

- 유니버스 전체(약 680개 종목) 기준. 보유 종목뿐 아니라 스크리닝 대상 전체 포함
- `null` 값은 해당 지표를 수집하지 못했음을 의미
- `dividend_yield`는 KR 종목의 경우 원/주 금액, US 종목은 % (데이터 소스에 따라 단위 상이)

---

### `supply_data.json` — 수급 지표

```json
{
  "updated_at": "2026-05-02T15:13:30.851578+09:00",  // ISO 8601 KST
  "fear_greed": {
    "score": 39.0,           // float 0~100 (0=극도의 공포, 100=극도의 탐욕)
    "rating": "Fear",        // "Extreme Fear" | "Fear" | "Neutral" | "Greed" | "Extreme Greed"
    "previous_close": null   // float | null, 전일 종가 기준 점수
  },
  "krx_supply": {}           // object, KRX 수급 데이터 (현재 비어 있을 수 있음)
}
```

---

### `performance_report.json` — 발굴 종목 성과 추적

```json
{
  "updated_at": "2026-05-02 15:25:35",  // "YYYY-MM-DD HH:MM:SS" (timezone 없음)
  "outcome_summary": {
    "updated_1w": 7,   // int, 이번 실행에서 1주 수익률 업데이트된 건수
    "updated_1m": 0    // int, 이번 실행에서 1개월 수익률 업데이트된 건수
  },
  "monthly_report": {
    "period": "2026-04-02 ~ 2026-05-02",  // string, 분석 기간
    "total_picks": 20,                     // int, 분석 대상 발굴 종목 수
    "hit_rate_1w": 95.0,                   // float, 1주 적중률 % (양의 수익률 비율)
    "hit_rate_1m": 0.0,                    // float, 1개월 적중률 %
    "avg_return_1w": 6.75,                 // float, 1주 평균 수익률 %
    "avg_return_1m": 0.0,                  // float, 1개월 평균 수익률 %
    "factor_analysis": {
      "value": {
        "avg_score_hit": 0.0,    // float, 적중 종목의 해당 팩터 평균 점수
        "avg_score_miss": 0.0,   // float, 미적중 종목의 해당 팩터 평균 점수
        "hit_count": 0,          // int
        "miss_count": 0          // int
      },
      "quality": { "avg_score_hit": 0.0, "avg_score_miss": 0.0, "hit_count": 0, "miss_count": 0 },
      "growth":  { "avg_score_hit": 0.0, "avg_score_miss": 0.0, "hit_count": 0, "miss_count": 0 },
      "timing":  { "avg_score_hit": 0.0, "avg_score_miss": 0.0, "hit_count": 0, "miss_count": 0 },
      "catalyst": {
        "avg_score_hit": 0.8947,
        "avg_score_miss": 1.0,
        "hit_count": 19,
        "miss_count": 1
      },
      "macro": {
        "avg_score_hit": 0.6748,
        "avg_score_miss": 0.4812,
        "hit_count": 19,
        "miss_count": 1
      }
    },
    "top_picks": [
      {
        "ticker": "000660.KS",
        "name": "SK하이닉스",
        "outcome_1w": 14.01,       // float | null, 1주 실현 수익률 %
        "outcome_1m": null,        // float | null, 1개월 실현 수익률 %
        "composite_score": 0.7395  // float, 발굴 당시 종합 점수
      },
      ...
    ],
    "bottom_picks": [
      {
        "ticker": "012450.KS",
        "name": "한화에어로스페이스",
        "outcome_1w": -0.42,
        "outcome_1m": null,
        "composite_score": 0.7406
      },
      ...
    ]
  },
  "weight_suggestion": {
    "current_weights": {
      "value": 0.2,
      "quality": 0.2,
      "growth": 0.15,
      "timing": 0.2,
      "catalyst": 0.1,
      "macro": 0.15
    },
    "suggested_weights": {
      "value": 0.1983,
      "quality": 0.1982,
      "growth": 0.1487,
      "timing": 0.1982,
      "catalyst": 0.0887,
      "macro": 0.1679
    },
    "reasoning": [
      "catalyst: 미적중 그룹 점수가 오히려 높음 (-0.105) → 가중치 감소 권장",
      "macro: 적중 그룹 점수가 높음 (+0.194) → 가중치 증가 권장"
    ]
  }
}
```

---

### `correction_notes.json` — AI 자기교정

```json
{
  "period": "2026-04-02 ~ 2026-05-02",  // string, 분석 기간
  "weak_factors": [                      // string[], 성과가 약했던 팩터
    "value",
    "quality",
    "growth",
    "timing"
  ],
  "strong_factors": [                    // string[], 성과가 강했던 팩터
    "catalyst",
    "macro"
  ],
  "weight_adjustment": {                 // 각 팩터의 조정된 가중치 (합계 ≈ 1)
    "value": 0.1983,
    "quality": 0.1982,
    "growth": 0.1487,
    "timing": 0.1982,
    "catalyst": 0.0887,
    "macro": 0.1679
  },
  "summary": "지난 달 적중률 95.0% (양호), 평균 수익률 6.75%. 약한 팩터: value, quality, growth, timing — 해당 종목 추천 시 신중히. 강한 팩터: catalyst, macro — 해당 신호 신뢰도 높음. 가중치 조정 적용됨.",
  "generated_at": "2026-05-02T15:25:35.343509+09:00"  // ISO 8601 KST
}
```

---

### `holdings_proposal.json` — 동적 종목 추가/제거 후보

```json
{
  "generated_at": "2026-05-02T15:25:35.348978+09:00",  // ISO 8601 KST
  "add_candidates": [           // array, 추가 후보 종목 (비어 있을 수 있음)
    {
      "ticker": "...",
      "name": "...",
      "reason": "..."           // 추가 이유 (예: 고득점 발굴 종목)
    }
  ],
  "remove_candidates": [        // array, 제거 후보 종목 (비어 있을 수 있음)
    {
      "ticker": "...",
      "name": "...",
      "reason": "..."           // 제거 이유 (예: 손절 기준 초과)
    }
  ],
  "summary": {
    "add_count": 0,             // int
    "remove_count": 0           // int
  }
}
```

- 후보가 없으면 `add_candidates`와 `remove_candidates`는 빈 배열(`[]`)

---

### `simulation_report.json` — 발굴 종목 시뮬레이션

과거 발굴 종목을 실제 가격으로 매수/매도했다면의 가상 성과.

```json
{
  "generated_at": "2026-05-02T15:25:35.351535+09:00",  // ISO 8601 KST
  "simulations": [
    {
      "ticker": "005930.KS",
      "buy_date": "2026-04-19",    // "YYYY-MM-DD"
      "sell_date": "2026-05-02",   // "YYYY-MM-DD"
      "buy_price": 216000.0,       // float | null (null이면 해당 날짜 가격 없음)
      "sell_price": 220500.0,      // float | null
      "qty": 1,                    // int
      "pnl": 4500.0,               // float | null, 손익 (통화 단위)
      "pnl_pct": 2.08,             // float | null, 수익률 %
      "error": null,               // string | null (가격 없으면 오류 메시지)
      "name": "삼성전자",
      "composite_score": 0.7395    // float, 발굴 당시 종합 점수
    },
    {
      "ticker": "000660.KS",
      "buy_date": "2026-04-19",
      "sell_date": "2026-05-02",
      "buy_price": null,
      "sell_price": null,
      "qty": 1,
      "pnl": null,
      "pnl_pct": null,
      "error": "매수가 없음 (2026-04-19)",  // 가격 데이터 없을 때
      "name": "SK하이닉스",
      "composite_score": 0.7395
    },
    ...
  ]
}
```

- `buy_price`가 `null`이면 해당 날짜의 DB 가격 데이터가 없어 시뮬레이션 불가
- `pnl`과 `pnl_pct`는 `buy_price`가 없으면 항상 `null`

---

### `proactive_alerts.json` — 선제적 위험/기회 감지

```json
{
  "generated_at": "2026-05-02T15:25:35.346887+09:00",  // ISO 8601 KST
  "count": 2,  // int
  "alerts": [
    {
      "ticker": "0117V0.KS",
      "name": "TIGER 코리아AI전력기",
      "action": "TAKE_PROFIT",      // "TAKE_PROFIT" | "STOP_LOSS" | "REBALANCE" | ...
      "pnl_pct": 62.22,             // float, 현재 수익률 %
      "reason": "수익률 62.2%로 익절 기준 초과.",
      "urgency": "MEDIUM"           // "LOW" | "MEDIUM" | "HIGH"
    },
    {
      "ticker": "GOOGL",
      "name": "알파벳",
      "action": "TAKE_PROFIT",
      "pnl_pct": 33.38,
      "reason": "수익률 33.4%로 익절 기준 초과.",
      "urgency": "MEDIUM"
    }
  ]
}
```

---

## 기업 상세 조회

```
GET /api/company?ticker=005930.KS
GET /api/company?ticker=AAPL
```

```json
{
  "ticker": "005930.KS",
  "name": "삼성전자",
  "name_kr": "삼성전자",
  "sector": "Technology",
  "description": "...",
  "market_cap": 131000000000000,
  "current_price": 220500,
  "price_52w_high": 88800,
  "price_52w_low": 49900,
  "per": 33.59,
  "pbr": 3.45,
  "roe": 10.2,
  "news": [ ... ],
  "screen_strategies": ["graham", "buffett"]
}
```

---

## 이력 조회 (DB)

단기 JSON이 덮어씌워지는 데이터를 장기 이력으로 조회할 때.

```
GET /api/regime-history?days=90
GET /api/sector-scores-history?days=90
GET /api/performance-report-history?days=90
GET /api/correction-notes-history?limit=30
GET /api/analysis-history              # Marcus 분석 이력
GET /api/wealth?days=60                # 전재산 이력
```

---

## 데이터 갱신 주기

| 데이터 | 갱신 주기 |
|--------|---------|
| 보유 종목 현재가 (`prices.json`) | 매 1분 |
| 투자 알림 감시 (`alerts.json`) | 매 5분 |
| 뉴스 수집 (`news.json`) | 평일 08:00 |
| Marcus AI 분석 | 평일 05:30 |
| 전체 파이프라인 (대부분의 JSON) | 평일 07:40 |
| 기업 프로필 DB | 평일 08:10 |
| 태양광 매물 | 매일 08:30, 19:00 |
| 유니버스 캐시 | 매주 일요일 04:00 |

---

## 통합 예시 (Python)

```python
import urllib.request, json

BASE = "http://100.90.201.87:8421"

# 전체 데이터 한 번에
data = json.loads(urllib.request.urlopen(f"{BASE}/api/data").read())

regime = data["regime"]["regime"]                            # "INFLATIONARY"
top_opp = data["opportunities"]["opportunities"][0]          # 최상위 발굴 종목
portfolio_pnl = data["portfolio_summary"]["total"]["pnl_pct"]  # 수익률 %
fear_greed = data["supply_data"]["fear_greed"]["score"]      # 39.0

# alerts.json은 없을 수 있음 — KeyError 방지
alerts = data.get("alerts", {}).get("alerts", [])

# 실시간 SSE 구독
with urllib.request.urlopen(f"{BASE}/api/events") as r:
    for line in r:
        if line.startswith(b"data:"):
            event = json.loads(line[5:])
            print("업데이트:", event)  # 새 데이터 있으면 /api/data 재호출
```

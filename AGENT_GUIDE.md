# 🤖 에이전트 사용 가이드 — Investment Intelligence Engine

> 이 문서는 AI 에이전트(자비스/OpenClaw 또는 다른 에이전트)가
> investment-bot 엔진의 데이터를 활용하기 위한 매뉴얼입니다.

---

## 1. 너는 해석자, 엔진은 계산기

```
엔진 (investment-bot)         에이전트 (너)
─────────────────────        ─────────────────
• 숫자 수집                   • 숫자 해석
• 지표 계산                   • 전략 판단
• 이상 감지                   • 이유 설명
• 데이터 저장                 • 사용자 소통
• 토큰 소모 0                 • Discord 전송
```

**너는 데이터를 직접 수집하지 않는다.**
엔진이 이미 수집해놓은 데이터를 읽고 해석하면 된다.

---

## 2. 데이터 읽는 법

### 📁 output/intel/ — 메인 인터페이스

이 폴더의 파일들이 너의 주요 입력이다.

| 파일 | 뭐가 들어있나 | 언제 갱신되나 | 어떻게 활용하나 |
|------|-------------|-------------|---------------|
| `prices.json` | 포트폴리오 종목 현재가, 전일비, 평단비 손익 | 장 중 10분마다 | 현재 시세 확인, 손익 파악 |
| `macro.json` | 코스피, 환율, 유가, VIX 등 매크로 지표 | 장 중 10분마다 | 시장 환경 판단 |
| `news.json` | 종목/매크로 관련 뉴스 + 감성 점수 | 매시간 | 뉴스 컨텍스트, 심리 파악 |
| `price_analysis.json` | 이동평균, RSI, 변동성, 추세, 지지/저항 | 장마감 후 | 기술적 분석 근거 |
| `portfolio_summary.json` | 총 손익, 섹터 비중, 환율 손익, 리스크 | 05:00 + 장마감 | 포트폴리오 전체 상황 |
| `alerts.json` | 긴급 알림 (임계값 초과) | 실시간 | **이 파일이 존재하면 즉시 대응** |
| `daily_report.md` | 일간 종합 리포트 | 매일 05:00 | 모닝 브리핑 소스 |
| `weekly_report.md` | 주간 성과 분석 | 월요일 04:00 | 주간 리뷰 소스 |
| `closing_report.md` | 장마감 OHLC + 오늘 결산 | 15:40 | 마감 브리핑 소스 |
| `screener.md` | 섹터별 종목 스크리닝 | 05:00 | 종목 발굴 참고 |
| `engine_status.json` | 엔진 상태 (정상/에러) | 매 수집 시 | 데이터 신뢰성 판단 |

### 🗄️ db/history.db — 시계열 데이터 직접 조회

JSON 파일은 "지금" 스냅샷이다. 과거 데이터가 필요하면 DB를 직접 쿼리한다.

```bash
# 삼성전자 최근 30일 종가
sqlite3 db/history.db "
  SELECT date, close FROM prices_daily
  WHERE ticker='005930.KS'
  ORDER BY date DESC LIMIT 30
"

# 코스피 최근 7일 추이
sqlite3 db/history.db "
  SELECT date, close, change_pct FROM macro_daily
  WHERE indicator='코스피'
  ORDER BY date DESC LIMIT 7
"

# 포트폴리오 수익률 추이
sqlite3 db/history.db "
  SELECT date, total_pnl_pct FROM portfolio_history
  ORDER BY date DESC LIMIT 30
"

# 특정 종목 관련 최근 뉴스
sqlite3 db/history.db "
  SELECT title, source, sentiment, published_at FROM news
  WHERE tickers LIKE '%005930%'
  ORDER BY published_at DESC LIMIT 10
"
```

### 📊 실시간 시세 (그 순간)

```bash
# stdout으로 현재 시세 마크다운 테이블 출력
python3 data/realtime.py
```

- 파일 저장 없음, stdout만
- 크론잡 프롬프트에서 직접 호출해서 사용

### 📰 뉴스 카테고리별 조회

```bash
# DB에서 카테고리별 뉴스 마크다운 출력
python3 scripts/read_news.py
```

---

## 3. 핵심 데이터 구조 이해

### prices.json 구조
```json
{
  "updated_at": "ISO8601+09:00",
  "count": 8,
  "prices": [
    {
      "ticker": "005930.KS",     // 종목 코드
      "name": "삼성전자",          // 종목명
      "price": 188700,           // 현재가
      "prev_close": 189200,      // 전일 종가
      "change_pct": -0.26,       // 전일비 등락률 (%)
      "volume": 12345000,        // 거래량
      "avg_cost": 203102,        // 내 평균 매입가
      "pnl_pct": -7.09,          // 평단 대비 손익률 (%)
      "currency": "KRW",         // 통화
      "qty": 42,                 // 보유 수량
      "account": "ISA",          // 계좌 구분
      "market": "KR",            // 시장 (KR/US)
      "data_source": "kiwoom",   // 데이터 출처
      "timestamp": "ISO8601"
    }
  ]
}
```

### price_analysis.json 구조
```json
{
  "updated_at": "ISO8601",
  "analysis": {
    "005930.KS": {
      "name": "삼성전자",
      "current": 188300,
      "ma5": 191200,             // 5일 이동평균
      "ma20": 195400,            // 20일 이동평균
      "ma60": 198700,            // 60일 이동평균
      "ma_signal": "하락 (정배열 깨짐)",
      "rsi_14": 38.5,            // RSI 14일
      "rsi_signal": "과매도 접근",
      "high_52w": 223000,        // 52주 최고
      "low_52w": 152900,         // 52주 최저
      "position_52w": "하단 25%",
      "volatility_30d": 8.3,     // 30일 변동성 (%)
      "trend": "downtrend",      // 추세 (uptrend/downtrend/sideways)
      "trend_duration_days": 12,
      "support": 185000,         // 지지선
      "resistance": 195000,      // 저항선
      "data_points": 180         // 분석에 사용된 데이터 포인트 수
    }
  }
}
```

### alerts.json 구조
```json
{
  "triggered_at": "ISO8601+09:00",
  "count": 1,
  "alerts": [
    {
      "level": "RED",
      "event_type": "stock_drop",
      "ticker": "005930.KS",
      "message": "🔴 긴급: 삼성전자 -5.72% 급락 (현재가: 178,000.00)",
      "value": -5.72,
      "threshold": -5.0
    }
  ]
}
```
> 알림이 없으면 alerts.json 파일 자체가 삭제됨. 파일 존재 = 알림 있음.

### macro.json 구조
```json
{
  "updated_at": "ISO8601+09:00",
  "count": 8,
  "indicators": [
    {
      "indicator": "코스피",
      "ticker": "KOSPI",
      "value": 2650.12,
      "prev_close": 2638.45,
      "change_pct": 0.44,
      "category": "INDEX",
      "timestamp": "ISO8601"
    }
  ]
}
```

### news.json 구조
```json
{
  "updated_at": "ISO8601+09:00",
  "count": 25,
  "news": [
    {
      "title": "삼성전자 반도체 수출 호조",
      "summary": "",
      "source": "한국경제",
      "url": "https://news.example.com/article/123",
      "published_at": "RFC2822",
      "relevance_score": 0.8,
      "sentiment": 0.45,
      "category": "stock",
      "tickers": ["005930.KS"],
      "ticker_name": "삼성전자",
      "fetch_method": "rss",
      "timestamp": "ISO8601"
    }
  ],
  "ticker_sentiment": {
    "005930.KS": {"name": "삼성전자", "avg_sentiment": 0.3, "count": 3}
  }
}
```

### portfolio_summary.json 구조
```json
{
  "updated_at": "ISO8601+09:00",
  "exchange_rate": 1450.0,
  "total": {
    "invested_krw": 42000000,
    "current_value_krw": 45230000,
    "pnl_krw": 3230000,
    "pnl_pct": 7.69,
    "stock_pnl_krw": 3410000,
    "fx_pnl_krw": -180000
  },
  "holdings": [
    {
      "ticker": "005930.KS",
      "name": "삼성전자",
      "sector": "반도체",
      "currency": "KRW",
      "price": 188700,
      "avg_cost": 203102,
      "qty": 42,
      "current_value_krw": 7925400,
      "invested_krw": 8530284,
      "pnl_krw": -604884,
      "pnl_pct": -7.09,
      "stock_pnl_krw": -604884,
      "fx_pnl_krw": 0
    }
  ],
  "sectors": [
    {"sector": "반도체", "weight_pct": 35.2, "value_krw": 7925400, "pnl_pct": -7.09, "stocks": ["삼성전자"]}
  ],
  "risk": {
    "max_drawdown_pct": 4.2,
    "volatility_daily": 1.8,
    "worst_performer": {"name": "삼성전자", "pnl_pct": -7.09},
    "best_performer": {"name": "테슬라", "pnl_pct": 12.3}
  },
  "history": [
    {"date": "2026-02-24", "total_value_krw": 44500000, "total_invested_krw": 42000000, "total_pnl_krw": 2500000, "total_pnl_pct": 5.95, "fx_rate": 1445.0}
  ]
}
```

---

## 4. 판단 가이드

### alerts.json이 존재할 때
1. 파일 내용 읽기
2. `realtime.py` 실행해서 현재 수치 재확인
3. 관련 뉴스 검색 (news.json 또는 Brave Search)
4. 상황 판단 후 **즉시** Discord 비서실 전송
5. Discord 전송 시 반드시: `--announce --channel discord --to channel:1486905937225846956`

### 모닝 브리핑 (07:30)
1. `output/intel/daily_report.md` 읽기
2. `realtime.py` 실행 (그 순간 시세)
3. `price_analysis.json` 참고 (기술적 분석)
4. `news.json` 참고 (오늘 뉴스)
5. 종합 브리핑 작성 → Discord 비서실

### 장마감 브리핑 (16:00)
1. `output/intel/closing_report.md` 읽기
2. `portfolio_summary.json` 읽기 (오늘 최종 손익)
3. `price_analysis.json` 참고 (기술적 위치)
4. 오늘 결산 + 내일 전략 → Discord 비서실

---

## 5. 설정 변경

### 종목 추가/삭제
```bash
# config.py의 PORTFOLIO 리스트 수정
# 예: SK하이닉스 추가
{"ticker": "000660.KS", "name": "SK하이닉스", "qty": 10, "avg_cost": 180000, "currency": "KRW", "account": "ISA"}
```
수정 후 다음 수집 사이클부터 자동 반영. DB 스키마 변경 불필요.

### 알림 임계값 변경
```bash
# config.py의 ALERT_THRESHOLDS 수정
"stock_drop": -5.0   →  -3.0  (더 민감하게)
```

### ⚠️ 변경 시 주의
- `config.py` 수정 후 `output/intel/` 파일 구조가 바뀌면 이 가이드도 업데이트
- `realtime.py` stdout 형식 변경 시 크론잡 프롬프트 수정 필요

---

## 6. 엔진 상태 확인

### engine_status.json
```json
{
  "updated_at": "2026-03-25T15:30:00+09:00",
  "pipeline_ok": true,
  "total_errors": 0,
  "db_size_mb": 12.4,
  "uptime_days": 45,
  "first_run": "2026-02-08T05:00:00+09:00",
  "modules": {
    "fetch_prices": {
      "success": true,
      "item_count": 8,
      "error_count": 0,
      "last_run": "2026-03-25T15:30:00+09:00"
    },
    "fetch_macro": {
      "success": true,
      "item_count": 8,
      "error_count": 0,
      "last_run": "2026-03-25T15:30:00+09:00"
    },
    "fetch_news": {
      "success": true,
      "item_count": 25,
      "error_count": 2,
      "last_run": "2026-03-25T15:00:00+09:00"
    }
  }
}
```

- `pipeline_ok`: 핵심 모듈(fetch_prices, fetch_macro)이 모두 성공이면 `true`
- `total_errors`: 전체 모듈의 에러 합계
- 모듈별 `success`, `item_count`, `error_count`로 상세 진단 가능
- 데이터가 오래되었거나 에러가 많으면 사용자에게 알릴 것

---

## 7. 미래: 자동매매 연동

엔진이 충분히 고도화되면, 에이전트는 분석 결과를 바탕으로 매매 명령을 내릴 수 있다.

```
에이전트 판단: "삼성전자 RSI 30 이하, 지지선 근접, 뉴스 감성 반등 — 매수 적기"
     ↓
에이전트 → 엔진 매매 API 호출 (미래)
     ↓
엔진 → 증권사 API → 주문 실행
     ↓
에이전트 → Discord: "삼성전자 10주 188,000원 매수 완료"
```

이것이 가능하려면 지금의 수집/분석 품질이 높아야 한다.
**지금 쌓는 데이터의 품질이 미래 자동매매의 정확도를 결정한다.**

---

## 8. opportunities.json (Phase 4 신규)

발굴 종목 후보 + 복합 점수. 자비스 05:30 파이프라인에서 생성.

```json
{
  "updated_at": "ISO 8601",
  "keywords": [{"keyword": "str", "category": "str", "priority": 0}],
  "opportunities": [
    {
      "ticker": "012450.KS",
      "name": "한화에어로스페이스",
      "discovered_via": "방산 수주",
      "source": "brave|naver|code_extract",
      "composite_score": 0.82,
      "score_return": 0.8,
      "score_rsi": 0.7,
      "score_sentiment": 0.9,
      "score_macro": 0.85
    }
  ],
  "summary": {"total_keywords": 5, "total_candidates": 12}
}
```

### DB 쿼리 예시

```sql
-- 오늘 발굴 종목 조회
SELECT ticker, name, composite_score, discovered_via
FROM opportunities
WHERE date(discovered_at) = date('now')
ORDER BY composite_score DESC;

-- 키워드별 발굴 성과
SELECT k.keyword, COUNT(o.id) as cnt, AVG(o.outcome_1w) as avg_return_1w
FROM agent_keywords k
LEFT JOIN opportunities o ON o.discovered_via = k.keyword
GROUP BY k.keyword;
```

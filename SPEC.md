# 🏦 Investment Intelligence Bot — 기획 명세서

> 작성: 자비스 | 2026-03-23
> 목적: AI 에이전트(자비스)가 활용할 투자 데이터 수집/분석 파이프라인 구축

---

## 1. 프로젝트 개요

### 배경
현재 자비스(OpenClaw AI 에이전트)가 투자 분석을 직접 수행하고 있으나:
- LLM이 숫자 계산 + 데이터 수집까지 담당 → 토큰 낭비 + 오류 가능성
- 가격 히스토리 없음 → 어제 대비 비교 불가
- 알람 임계값 설정 불가 → 급락/급등 실시간 감지 불가
- 종목 스크리닝 로직 부재 → 새 종목 발굴 한계

### 목표
**프로그램이 정확한 데이터를 수집·저장·계산하고, AI(자비스)는 해석·판단·대화에 집중**

---

## 2. 시스템 아키텍처

```
┌─────────────────────────────────────────────────────┐
│                  investment-bot                      │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │  Data    │  │ Analysis │  │    Reports       │  │
│  │ Fetchers │→ │ Engine   │→ │   Generator      │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
│       ↓              ↓                ↓             │
│  ┌──────────────────────────────────────────────┐   │
│  │           SQLite Database (history.db)        │   │
│  └──────────────────────────────────────────────┘   │
│                        ↓                            │
│  ┌──────────────────────────────────────────────┐   │
│  │         output/intel/ (마크다운 리포트)        │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
                         ↓
              자비스(OpenClaw)가 읽고 해석
                         ↓
                   Discord 보고
```

---

## 3. 포트폴리오 정의

```python
PORTFOLIO = [
    # (이름, 야후티커, 평균단가, 통화, 수량, 계좌)
    ("삼성전자",            "005930.KS", 203102, "KRW", 42, "ISA"),
    ("현대차",              "005380.KS", 519000, "KRW",  9, "혼합"),  # ISA 3 + 일반 6
    ("TIGER 코리아AI전력기", "0117V0.KS",  16795, "KRW", 60, "ISA"),
    ("TIGER 미국방산TOP10", "458730.KS",  15485, "KRW", 64, "ISA"),
    ("테슬라",              "TSLA",      394.32, "USD",  1, "미국"),
    ("알파벳",              "GOOGL",     308.27, "USD",  2, "미국"),
    ("SPDR S&P Oil",       "XOP",       178.26, "USD",  1, "미국"),
    ("금 현물",             "GC=F",           0, "USD",  128, "실물"),  # 128g
]
```

---

## 4. 모듈 명세

### 4-1. `data/fetch_prices.py` — 실시간 주가 수집
- **소스:** Yahoo Finance API (무료, 키 불필요)
- **수집 주기:** 장 중 10분마다, 장외 1회
- **저장:** SQLite `prices` 테이블 (timestamp, ticker, price, change_pct)
- **출력:** `output/intel/prices.json`

```python
# 수집 데이터
{
  "ticker": "005930.KS",
  "name": "삼성전자",
  "price": 188700,
  "prev_close": 199400,
  "change_pct": -5.37,
  "avg_cost": 203102,
  "pnl_pct": -7.09,
  "timestamp": "2026-03-23T10:34:00+09:00"
}
```

### 4-2. `data/fetch_macro.py` — 매크로 지표 수집
- **수집 항목:**
  - 코스피/코스닥 지수 (Yahoo: ^KS11, ^KQ11)
  - 원/달러 환율 (Yahoo: KRW=X)
  - WTI/Brent 유가 (Yahoo: CL=F, BZ=F)
  - 금 현물 (Yahoo: GC=F)
  - 달러 인덱스 DXY (Yahoo: DX-Y.NYB)
  - VIX 공포지수 (Yahoo: ^VIX)
- **저장:** SQLite `macro` 테이블
- **출력:** `output/intel/macro.json`

### 4-3. `data/fetch_news.py` — 뉴스 수집
- **소스:** Brave Search API, RSS 피드 (연합뉴스, Bloomberg, Reuters)
- **키워드:** 포트폴리오 종목명 + 중동/이란/유가/금리/환율
- **저장:** SQLite `news` 테이블 (title, summary, source, published_at, relevance_score)
- **출력:** `output/intel/news.json`

### 4-4. `analysis/alerts.py` — 실시간 알림 감지
- **알림 조건:**

| 이벤트 | 임계값 | 알림 레벨 |
|--------|--------|---------|
| 종목 단일 급락 | -5% 이상 | 🔴 긴급 |
| 종목 단일 급등 | +5% 이상 | 🟢 알림 |
| 코스피 폭락 | -3% 이상 | 🔴 긴급 |
| 금 현물 급변 | ±3% 이상 | 🟡 주의 |
| 유가 급등 | +5% 이상 | 🟡 주의 |
| 환율 급등 | 1,550원 돌파 | 🔴 긴급 |
| 포트폴리오 전체 손실 | -10% 초과 | 🔴 긴급 |

- **출력:** `output/intel/alerts.json` (알림 있을 때만 생성)
- **자비스 연동:** 알림 파일 존재 시 자비스가 Discord 비서실 즉시 전송

### 4-5. `analysis/screener.py` — 신규 종목 발굴
- **스크리닝 기준:**
  - 52주 신고가 돌파 종목
  - 섹터별 상위 모멘텀 (에너지, 방산, AI 인프라)
  - PER 15 이하 + 최근 1개월 수익률 양전환
  - 한국 ETF: 거래량 상위 + 최근 수익률 상위
- **출력:** `output/intel/screener.md`

### 4-6. `analysis/portfolio.py` — 포트폴리오 계산
- **계산 항목:**
  - 종목별 평가손익 (원화 환산 통일)
  - 섹터별 비중
  - 총 포트폴리오 수익률
  - 리스크 지표 (최대 낙폭, 변동성)
- **출력:** `output/intel/portfolio_summary.json`

### 4-7. `reports/daily.py` — 일일 리포트 생성
- **실행 시점:** 매일 05:00 KST (자비스 파이프라인 실행 전)
- **내용:**
  - 전일 대비 포트폴리오 변화
  - 매크로 요약
  - 알림 요약
  - 자비스용 컨텍스트 마크다운 생성
- **출력:** `output/intel/daily_report.md`

### 4-8. `reports/weekly.py` — 주간 리포트 생성
- **실행 시점:** 매주 월요일 04:00 KST
- **내용:**
  - 주간 포트폴리오 성과
  - 섹터 로테이션 분석
  - 신규 주목 종목 3~5개
  - 리밸런싱 시뮬레이션
- **출력:** `output/intel/weekly_report.md`

---

## 5. 데이터베이스 스키마

```sql
-- 가격 히스토리
CREATE TABLE prices (
  id INTEGER PRIMARY KEY,
  ticker TEXT,
  name TEXT,
  price REAL,
  prev_close REAL,
  change_pct REAL,
  volume INTEGER,
  timestamp TEXT,
  market TEXT  -- KR/US/COMMODITY
);

-- 매크로 지표
CREATE TABLE macro (
  id INTEGER PRIMARY KEY,
  indicator TEXT,  -- KOSPI, USD_KRW, WTI, GOLD, VIX 등
  value REAL,
  change_pct REAL,
  timestamp TEXT
);

-- 뉴스
CREATE TABLE news (
  id INTEGER PRIMARY KEY,
  title TEXT,
  summary TEXT,
  source TEXT,
  url TEXT,
  published_at TEXT,
  relevance_score REAL,
  tickers TEXT  -- JSON array of related tickers
);

-- 알림 이력
CREATE TABLE alerts (
  id INTEGER PRIMARY KEY,
  level TEXT,  -- RED/YELLOW/GREEN
  event_type TEXT,
  ticker TEXT,
  message TEXT,
  value REAL,
  threshold REAL,
  triggered_at TEXT,
  notified INTEGER DEFAULT 0
);
```

---

## 6. 실행 스케줄

| 시간 (KST) | 실행 모듈 | 설명 |
|-----------|---------|------|
| 04:00 (월) | `reports/weekly.py` | 주간 리포트 |
| 05:00 | `reports/daily.py` | 일일 리포트 생성 |
| 05:30 | 자비스 크론 | 매크로+전략 파이프라인 |
| 07:30 | 자비스 크론 | 모닝 브리핑 발송 |
| 09:00~15:30 | `data/fetch_prices.py` | 장 중 10분 주기 |
| 09:00~15:30 | `analysis/alerts.py` | 알림 감지 10분 주기 |
| 16:00 | `data/fetch_prices.py` | 장 마감 가격 저장 |
| 16:00 | `reports/daily.py` | 장 마감 리포트 업데이트 |

---

## 7. 자비스 연동 방식

```
investment-bot 출력 파일들
  output/intel/daily_report.md   ← 자비스 크론이 읽음
  output/intel/prices.json       ← 자비스 주가 참조
  output/intel/alerts.json       ← 알림 발생 시 자비스 즉시 전송
  output/intel/screener.md       ← 주간 종목 발굴 결과
```

자비스(OpenClaw)는:
- 숫자 계산 X → 프로그램이 한 결과 읽기
- 맥락 해석 O → "왜 이 종목이 좋은가"
- 전략 판단 O → 매크로 + 포트폴리오 + 뉴스 종합
- 대화 응답 O → 주인님 질문에 실시간 답변

---

## 8. 기술 스택

- **언어:** Python 3.11+
- **데이터:** Yahoo Finance (yfinance 라이브러리), Brave Search API
- **DB:** SQLite (로컬, 별도 서버 불필요)
- **스케줄링:** OpenClaw 크론 or crontab
- **알림:** OpenClaw → Discord
- **실행 환경:** 맥미니 (상시 가동)

---

## 9. 개발 우선순위

### Phase 1 (핵심, 먼저 개발)
- [ ] `fetch_prices.py` — 실시간 주가 수집 + SQLite 저장
- [ ] `fetch_macro.py` — 매크로 지표 수집
- [ ] `alerts.py` — 급등/급락 알림
- [ ] `daily.py` — 일일 리포트 생성

### Phase 2 (고도화)
- [ ] `fetch_news.py` — 뉴스 수집 + 관련도 스코어링
- [ ] `screener.py` — 신규 종목 발굴
- [ ] `portfolio.py` — 리스크 계산, 리밸런싱 시뮬레이션
- [ ] `weekly.py` — 주간 리포트

### Phase 3 (심화)
- [ ] 백테스트 모듈
- [ ] 수익률 차트 이미지 생성 → Discord 전송
- [ ] 자동 매매 연동 (증권사 API)

---

## 10. 디렉토리 구조

```
investment-bot/
├── README.md
├── SPEC.md                  ← 이 문서
├── requirements.txt
├── config.py                ← 포트폴리오 정의, API 키
├── data/
│   ├── __init__.py
│   ├── fetch_prices.py
│   ├── fetch_macro.py
│   └── fetch_news.py
├── analysis/
│   ├── __init__.py
│   ├── alerts.py
│   ├── screener.py
│   └── portfolio.py
├── reports/
│   ├── __init__.py
│   ├── daily.py
│   └── weekly.py
├── output/
│   └── intel/               ← 자비스가 읽는 폴더
│       ├── daily_report.md
│       ├── prices.json
│       ├── macro.json
│       ├── alerts.json
│       └── screener.md
└── db/
    └── history.db           ← SQLite
```

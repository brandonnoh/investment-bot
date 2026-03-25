# 🏦 Investment Intelligence System — 시스템 아키텍처

> 작성: 자비스 | 최종 업데이트: 2026-03-25
> 원칙: 수집/감시는 프로그램, 해석/판단/대화는 AI

---

## 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                    맥미니 (상시 가동)                          │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              crontab (Python 수집 프로그램)             │   │
│  │                                                      │   │
│  │  09~15시 매 10분                                      │   │
│  │  ├── fetch_prices.py   → DB prices 테이블             │   │
│  │  ├── fetch_macro.py    → DB macro 테이블              │   │
│  │  └── alerts_watch.py  → 임계값 초과 시 즉시 신호 ──┐  │   │
│  │                                                   │  │   │
│  │  매 1시간                                          │  │   │
│  │  └── fetch_news.py    → DB news 테이블            │  │   │
│  │                                                   │  │   │
│  │  매일 05:00                                        │  │   │
│  │  └── run_pipeline.py  → 일일 리포트 생성           │  │   │
│  │                                                   │  │   │
│  │  월요일 04:00                                       │  │   │
│  │  └── run_pipeline.py --weekly → 주간 리포트         │  │   │
│  └──────────────────────────────────────┬────────────┘   │
│                                         │                  │
│  ┌──────────────────────────────────────▼────────────┐    │
│  │              OpenClaw (자비스 AI)                   │    │
│  │                                                    │    │
│  │  🚨 긴급 알림 (즉시) — system event → 텔레그램     │    │
│  │  📊 05:30 투자팀 분석 — CIO 보고서 생성            │    │
│  │  🌅 07:30 모닝 브리핑 — 종합 브리핑 텔레그램        │    │
│  │  📈 16:00 장 마감 — 오늘 결산 + 내일 전략           │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 모듈 관계도

```
config.py ─────────────────────────────────────────────┐
  │ (PORTFOLIO, MACRO_INDICATORS, ALERT_THRESHOLDS)    │
  │                                                     │
  ├─→ data/fetch_prices.py ─┬─→ DB: prices 테이블      │
  │     ├ Kiwoom REST API   │                           │
  │     ├ Naver Finance     ├─→ output/intel/prices.json│
  │     └ Yahoo Finance     │                           │
  │                         │                           │
  ├─→ data/fetch_macro.py ─┬─→ DB: macro 테이블        │
  │     ├ Naver Finance    ├─→ output/intel/macro.json  │
  │     └ Yahoo Finance    │                            │
  │                        │                            │
  ├─→ data/fetch_news.py ─┬─→ DB: news 테이블          │
  │     ├ Google News RSS  ├─→ output/intel/news.json   │
  │     └ Brave Search API │                            │
  │                        │                            │
  ├─→ data/fetch_gold_krx.py (fetch_prices에서 import) │
  │                                                     │
  ├─→ analysis/alerts.py ────→ output/intel/alerts.json │
  │     └ prices.json + macro.json 읽기                 │
  │                                                     │
  ├─→ analysis/alerts_watch.py ─→ DB: alerts 테이블     │
  │     └ DB 직접 조회 → openclaw system event 트리거   │
  │                                                     │
  ├─→ analysis/screener.py ──→ output/intel/screener.md │
  │     └ Yahoo Finance (섹터 데이터)                    │
  │                                                     │
  ├─→ analysis/portfolio.py ─→ output/intel/portfolio_summary.json
  │     └ prices.json + config.py                       │
  │                                                     │
  ├─→ reports/daily.py ──→ output/intel/daily_report.md │
  ├─→ reports/weekly.py ─→ output/intel/weekly_report.md│
  ├─→ reports/closing.py → output/intel/closing_report.md
  │                                                     │
  └─→ data/realtime.py ──→ stdout (자비스 직접 호출)    │
```

---

## 핵심 파일 목록

| 파일 | 역할 | 줄 수 | 의존성 |
|------|------|-------|--------|
| `config.py` | 포트폴리오/지표/임계값 중앙 관리 | ~70 | 없음 |
| `run_pipeline.py` | 파이프라인 오케스트레이터 | ~62 | 모든 모듈 |
| `db/init_db.py` | SQLite 스키마 초기화 | ~92 | sqlite3 |
| `data/fetch_prices.py` | 주가 수집 (3소스 폴백) | ~264 | config, fetch_gold_krx |
| `data/fetch_macro.py` | 매크로 지표 수집 | ~174 | config |
| `data/fetch_news.py` | 뉴스 수집 (RSS+Brave) | ~355 | config |
| `data/fetch_gold_krx.py` | 키움 REST API 래퍼 | ~180 | 없음 |
| `data/realtime.py` | 실시간 시세 출력 (stdout) | ~320 | config |
| `analysis/alerts.py` | 알림 감지 (레거시) | ~200 | config |
| `analysis/alerts_watch.py` | 실시간 알림 모니터 | ~300 | config, DB |
| `analysis/screener.py` | 섹터 분석 | ~200 | Yahoo Finance |
| `analysis/portfolio.py` | 포트폴리오 계산 | ~250 | config |
| `reports/daily.py` | 일간 리포트 | ~250 | JSON 파일들 |
| `reports/weekly.py` | 주간 리포트 | ~250 | JSON 파일들 |
| `reports/closing.py` | 장마감 리포트 | ~200 | DB |

---

## API 폴백 전략

```
한국 주식 (.KS/.KQ):
  Kiwoom REST API (KIWOOM_APPKEY 설정 시)
    └→ 실패/미설정 시 → Naver Finance API (무료)

금 현물 (GOLD_KRW_G):
  Kiwoom KRX Gold (M04020000, 장 중)
    └→ 실패/장외 시 → Yahoo GC=F × USD/KRW ÷ 31.1035

미국 주식 (TSLA, GOOGL, XOP):
  Yahoo Finance API (단일, 무료)

매크로 지표:
  코스피/코스닥 → Naver Finance
  환율/유가/VIX/DXY/금 → Yahoo Finance
```

---

## DB 스키마

```sql
-- 주가 이력
CREATE TABLE prices (
  id INTEGER PRIMARY KEY,
  ticker TEXT, name TEXT, price REAL,
  prev_close REAL, change_pct REAL,
  volume INTEGER, timestamp TEXT, market TEXT
);
CREATE INDEX idx_prices ON prices(ticker, timestamp);

-- 매크로 지표 이력
CREATE TABLE macro (
  id INTEGER PRIMARY KEY,
  indicator TEXT, value REAL,
  change_pct REAL, timestamp TEXT
);
CREATE INDEX idx_macro ON macro(indicator, timestamp);

-- 뉴스
CREATE TABLE news (
  id INTEGER PRIMARY KEY,
  title TEXT, summary TEXT, source TEXT, url TEXT,
  published_at TEXT, relevance_score REAL,
  tickers TEXT, category TEXT
);
CREATE UNIQUE INDEX idx_news ON news(title, source);

-- 알림
CREATE TABLE alerts (
  id INTEGER PRIMARY KEY,
  level TEXT, event_type TEXT, ticker TEXT,
  message TEXT, value REAL, threshold REAL,
  triggered_at TEXT, notified INTEGER DEFAULT 0
);
CREATE INDEX idx_alerts ON alerts(triggered_at);
```

---

## output/intel/ 인터페이스 파일

| 파일 | 생성 모듈 | 갱신 주기 | 자비스 활용 |
|------|---------|---------|-----------|
| `prices.json` | fetch_prices | 장 중 10분 | 현재가 참조 |
| `macro.json` | fetch_macro | 장 중 10분 | 매크로 지표 |
| `news.json` | fetch_news | 매시간 | 뉴스 컨텍스트 |
| `alerts.json` | alerts_watch | 임계값 초과 시 | 긴급 알림 |
| `portfolio_summary.json` | portfolio | 05:00 | 손익 요약 |
| `daily_report.md` | daily | 05:00 | 일간 브리핑 |
| `weekly_report.md` | weekly | 월 04:00 | 주간 브리핑 |
| `closing_report.md` | closing | 15:40 | 장마감 브리핑 |
| `screener.md` | screener | 05:00 | 종목 발굴 |

---

## 개발 단계

| Phase | 상태 | 내용 |
|-------|------|------|
| 1 | ✅ 완료 | 기본 수집 + 알림 + 일간 리포트 |
| 2 | ✅ 완료 | 뉴스(RSS+Brave), 스크리너, 포트폴리오, 주간 리포트 |
| 2.5 | ✅ 완료 | 실시간 알림(alerts_watch), 장마감 리포트, system event |
| 3 | 🔧 진행 중 | 기술 분석, 포트폴리오 이력, 뉴스 감성, 환율 손익 |
| 4 | 📋 계획 | 백테스트, 차트 이미지, 자동매매 API |

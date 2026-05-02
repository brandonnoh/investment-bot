# PRD — 개인 투자자를 위한 기관급 금융 인텔리전스 엔진

**최종 업데이트:** 2026-05-01  
**상태:** 운영 중 (Production)

---

## 1. 제품 개요

### 목적
개인 투자자(운영자 본인)가 기관 수준의 정보 비대칭을 해소하고 체계적인 투자 판단을 내릴 수 있도록 지원하는 자동화 인텔리전스 엔진.

수집·계산·저장은 이 엔진이 담당하고, 해석·판단·전략·대화는 AI 에이전트(Marcus/Jarvis)가 담당한다.

### 핵심 가치
- **완전 자동화**: 매일 새벽 5:30부터 장마감 16:00까지 무인 운영
- **이중 저장**: SQLite(이력) + JSON(실시간 공유) 동시 저장으로 데이터 유실 방지
- **Graceful Degradation**: 개별 모듈 실패 시 파이프라인 전체가 중단되지 않음
- **기관급 분석**: 레짐 분류·섹터 스코어링·가치 스크리닝·수급 분석·성과 추적

---

## 2. 시스템 아키텍처

### 3계층 구조

```
수집 계층 (data/)
  Yahoo Finance · 키움증권 REST API · DART Open API
  Brave Search · RSS · 네이버금융 · KRX
        ↓
분석 계층 (analysis/)
  기술분석 · 포트폴리오 · 레짐 · 섹터 · 스크리닝 · 성과추적 · 시뮬레이션
        ↓
서비스 계층 (web/)
  Flask HTTP API (포트 8421) + SSE 실시간 스트림
        ↓
프론트엔드 (web-next/)
  Next.js 11탭 대시보드 (포트 3000)
```

### 인프라
- **플랫폼**: Docker Compose (Mac mini 자체 호스팅)
- **접속**: Tailscale VPN (`100.90.201.87`)
- **컨테이너**:
  - `investment-bot` (포트 8421): Flask API + 내부 cron 스케줄러
  - `mc-web` (포트 3000): Next.js standalone 프론트엔드
- **스케줄러**: Docker 내부 cron (HOST launchd 전부 비활성화)

---

## 3. 데이터 수집 계층

### 수집 소스 (data/ 29개 모듈)

| 소스 | 모듈 | 수집 내용 |
|------|------|---------|
| Yahoo Finance | `fetch_prices.py`, `fetch_universe_daily.py` | 포트폴리오 실시간 시세, 유니버스 150개 일봉 |
| 키움증권 REST API | `fetch_prices_kr.py` | 국내 주식 실시간 시세 |
| DART Open API | `fetch_fundamentals.py`, `fetch_dart_corp_codes.py` | 재무제표, 법인코드 |
| 네이버금융 / KRX | `fetch_supply.py`, `fetch_fundamentals_sources.py` | 수급(외국인/기관), PER/PBR/ROE |
| Brave Search | `fetch_news.py`, `fetch_opportunities.py` | 투자 뉴스, 종목 발굴 검색 |
| RSS | `fetch_news_sources.py` | 국내외 금융 미디어 |
| KRX | `fetch_gold_krx.py` | 금 현물 가격 |
| 태양광 거래소 9곳 | `fetch_solar_*.py` | 매물 리스팅 (AllThatSolar, SolarMarket, Exchange, SolarTrade, SolarDirect, Haetbit, SsunLab, KoreaRI, OnBid) |

### 수집 결과물
- `output/intel/*.json` — 모듈 간 인터페이스 (18개 JSON + 3개 MD)
- `db/history.db` — SQLite 이중 저장
- `prices_daily` 테이블 — 유니버스 150개 일봉 (value_screener DB 스크리닝 소스)

---

## 4. 분석 계층

### 분석 모듈 (analysis/ 40개 모듈)

#### 기술 분석
- `price_analysis.py` / `price_analysis_calc.py` / `price_analysis_fetch.py` / `price_analysis_indicators.py` / `price_analysis_momentum.py`
  - RSI, MACD, 볼린저밴드, 모멘텀 점수 계산
  - 결과: `price_analysis.json`

#### 레짐 분류
- `regime_classifier.py`
  - VIX, 환율 변화율, 유가 변화율 → BULL/BEAR/RISK_OFF/NEUTRAL 분류
  - 결과: `regime.json` + `regime_history` 테이블 (DB 이력)

#### 섹터 인텔리전스
- `sector_intel.py` / `sector_map.py`
  - `macro.json` + `news.json` + `regime.json` → 섹터별 점수화
  - 결과: `sector_scores.json` + `sector_scores_history` 테이블

#### 가치 스크리닝
- `value_screener.py` / `value_screener_data.py` / `value_screener_factors.py` / `value_screener_marcus.py` / `value_screener_strategies.py`
  - 유니버스 150개 종목 대상: RSI 과매도 + PER/PBR 저평가 필터
  - 복합 전략 (composite, value, momentum, mixed 등) 지원
  - Marcus 전용 B+ 이상 스크리닝 풀 제공
  - 결과: `screener_results.json`

#### 포트폴리오 분석
- `portfolio.py` / `portfolio_calc.py`
  - 보유 종목 P&L, 환율 손익, 섹터 비중 계산
  - 실시간 가격 반영 재계산 (포트폴리오 갱신 API 경유)
  - 결과: `portfolio_summary.json`

#### 종목 발굴 & 성과 추적
- `dynamic_holdings.py` — 추가/제거 후보 제안 → `holdings_proposal.json`
- `performance.py` / `performance_report.py` — 발굴 종목 1주/1개월 수익률 추적, 월간 성적표 → `performance_report.json` + `performance_report_history` 테이블
- `self_correction.py` — 약한 팩터/강한 팩터 분석 → `correction_notes.json` + `correction_notes_history` 테이블
- `simulation.py` — 발굴 종목 가상 손익 시뮬레이션 → `simulation_report.json`
- `proactive_alerts.py` — 포트폴리오 P&L + 레짐 + 교정 → `proactive_alerts.json`
- `composite_score.py` / `composite_score_factors.py` — 복합 점수 계산
- `sentiment.py` / `sentiment_keywords.py` — 뉴스 감성 분석

#### 알림
- `alerts.py` / `alerts_io.py` — 가격/레짐/포트폴리오 이상 감지 → `alerts.json` (알림 없으면 파일 삭제)
- `alerts_watch.py` / `alerts_watch_notify.py` — 5분 주기 실시간 감시 + Discord 알림
- `solar_alerts.py` — 태양광 신규 매물 알림

#### 유니버스 관리
- `universe_cache.py` — 매주 일요일 PER/PBR/ROE 캐시 갱신
- `universe_kr.py` / `universe_us.py` — 한국/미국 유니버스 정의
- `marcus_screener.py` — Marcus 전용 스크리닝 풀 제공

---

## 5. AI 에이전트

### Marcus (시황 분석가)
- **실행 시각**: 평일 05:30 KST
- **방식**: Claude CLI (`claude --output-format json -p -`) 직접 호출
- **입력 데이터**: SOUL.md(페르소나) + prompt.md(지시) + 실시간시세 + 기술분석 + B+ 스크리닝풀 + 수급 + 포트폴리오 + 매크로 + 뉴스(최신 20건) + 발굴기회 + 어제분석
- **출력**: `marcus-analysis.md` + `analysis_history` DB 저장
- **부가 작업**:
  - 뉴스 추적용 동적 검색 키워드 8개 생성 → `search_keywords.json`
  - 종목 발굴용 Brave 검색 키워드 4~5개 생성 → `discovery_keywords.json`
  - 완료 시 Discord 알림

### Jarvis (CIO 브리퍼)
- **실행 시각**: 평일 07:30 KST
- **방식**: Claude CLI (`claude --print -p -`) 직접 호출
- **입력 데이터**: cron-prompt-phase4.md + 실시간시세 + daily_report.md + 매크로 + 뉴스 + 기술분석
- **출력**: `cio-briefing.md`
- **완료 시 Discord 알림**

---

## 6. 파이프라인 실행 순서

```
평일 07:40 KST — run_pipeline.py

1. init_db()
2. _collect_data()
   ├─ fetch_prices()         → prices.json
   ├─ fetch_macro()          → macro.json
   ├─ fetch_news()           → news.json
   ├─ classify_regime()      → regime.json + regime_history
   ├─ fetch_fundamentals()   → fundamentals.json
   ├─ fetch_supply()         → supply_data.json
   ├─ sector_intel()         → sector_scores.json + sector_scores_history
   ├─ fetch_universe_daily() → DB prices_daily (150개)
   └─ fetch_opportunities()  → opportunities.json
3. aggregate_daily() + maintain_db()
4. analyze_prices()          → price_analysis.json
   check_alerts()            → alerts.json
   run_screener()            → screener_results.json
   analyze_portfolio()       → portfolio_summary.json
5. _run_post_analysis()
   ├─ track_performance()        → performance_report.json
   ├─ run_self_correction()      → correction_notes.json
   ├─ run_proactive_alerts()     → proactive_alerts.json
   ├─ run_dynamic_holdings()     → holdings_proposal.json
   └─ run_simulation()           → simulation_report.json
6. validate_all_outputs() + save_engine_status() → engine_status.json
7. generate_daily()          → daily_report.md
8. [--weekly] generate_weekly() → cio-briefing.md
```

---

## 7. 전체 스케줄 (KST, 평일 기준)

| 시각 | 잡 | 스크립트 |
|------|----|---------| 
| 매 1분 | 가격 갱신 | `scripts/refresh_prices.py` |
| 매 1분 | Claude 인증 동기화 | crontab 내부 `cp` |
| 매 5분 | 알림 감시 | `analysis/alerts_watch.py` |
| 05:30 평일 | Marcus 시황 분석 | `scripts/run_marcus.py` |
| 07:30 평일 | Jarvis CIO 브리핑 | `scripts/run_jarvis.py` |
| 07:40 평일 | 전체 파이프라인 | `run_pipeline.py` |
| 07:50 평일 | R2 동기화 | `scripts/sync_to_r2.py` |
| 07:55 평일 | 블로그 자동 발행 | `scripts/publish_blog.py` |
| 08:00 평일 | 뉴스 수집 | `scripts/refresh_news.py` |
| 08:10 평일 | 기업 프로필 수집 | `data/fetch_company_profiles.py` |
| 08:30 매일 | 태양광 매물 수집 | `scripts/refresh_solar.py` |
| 16:00 평일 | 장마감 리포트 | `reports/closing.py` |
| 19:00 매일 | 태양광 매물 수집 | `scripts/refresh_solar.py` |
| 매주 일요일 03:00 | DB 유지보수 | `db/maintenance.py` |
| 매주 일요일 04:00 | 유니버스 캐시 갱신 | `analysis/universe_cache.py` |
| 매월 1일 00:00 | 월별 입금 기록 | `scripts/monthly_deposit_cron.py` |
| 매월 1일 05:00 | DART 법인코드 갱신 | `data/fetch_dart_corp_codes.py` |
| 매일 00:05 | 로그 로테이션 | crontab `find + gzip` |

총 17개 크론잡

---

## 8. Flask API 엔드포인트 (포트 8421)

### GET

| 엔드포인트 | 역할 |
|-----------|------|
| `/api/data` | INTEL_FILES 전체 통합 조회 (18개 JSON + 3개 MD) |
| `/api/status` | 파이프라인/Marcus 실행 상태 |
| `/api/events` | SSE 스트림 (`output/intel/` 변경 감지 → 클라이언트 push) |
| `/api/analysis-history` | Marcus 분석 이력 목록 |
| `/api/analysis-history?date=YYYY-MM-DD` | 특정 날짜 상세 |
| `/api/wealth?days=60` | 전재산 요약 (금융+비금융, N일 이력) |
| `/api/logs?name=marcus&lines=80` | 로그 마지막 N줄 (marcus/pipeline/jarvis/alerts_watch/refresh_prices) |
| `/api/opportunities?strategy=composite` | 발굴 종목 (전략별) |
| `/api/solar?limit=100` | 태양광 매물 |
| `/api/strategies` | 스크리너 전략 메타 |
| `/api/file?name=X.md` | 마크다운/JSON 파일 조회 |
| `/api/investment-assets` | 투자 자산 정의 목록 |
| `/api/advisor-strategies` | 저장된 AI 어드바이저 전략 |
| `/api/company?ticker=XXX` | 기업 프로필 |
| `/api/regime-history?days=90` | 레짐 분류 이력 |
| `/api/sector-scores-history?days=90` | 섹터 점수 이력 |
| `/api/correction-notes-history?limit=30` | 자기 교정 이력 |
| `/api/performance-report-history?days=90` | 성과 보고서 이력 |

### POST

| 엔드포인트 | 역할 |
|-----------|------|
| `/api/run-pipeline` | 파이프라인 백그라운드 실행 |
| `/api/run-marcus` | Marcus 백그라운드 실행 |
| `/api/refresh-prices` | 가격 새로고침 |
| `/api/wealth/assets` | 비금융 자산 추가 |
| `/api/investment-advice` | AI 투자 어드바이스 (동기) |
| `/api/investment-advice-stream` | AI 투자 어드바이스 (SSE 스트리밍) |
| `/api/advisor-strategies` | 어드바이저 전략 저장 |

### PUT / DELETE

| 엔드포인트 | 역할 |
|-----------|------|
| `/api/wealth/assets/{id}` | 비금융 자산 수정 |
| `DELETE /api/wealth/assets/{id}` | 비금융 자산 삭제 |
| `DELETE /api/advisor-strategies/{id}` | 어드바이저 전략 삭제 |

총 28개 엔드포인트

---

## 9. Next.js 프론트엔드 (web-next/, 포트 3000)

### 기술 스택
Next.js 16.2.4 · React 19 · TypeScript 5 · Tailwind CSS 4 · Zustand · SWR · Recharts · shadcn/ui · react-markdown

### 탭 구성 (11개)

| 탭 | 컴포넌트 | 주요 내용 |
|----|---------|---------|
| overview | `OverviewTab.tsx` | 시황 요약, 레짐, 주요 지표 |
| portfolio | `PortfolioTab.tsx` | 보유 종목 P&L, 섹터 비중 |
| marcus | `MarcusTab.tsx` | Marcus 분석 원문, 이력 |
| discovery | `DiscoveryTab.tsx` | 발굴 종목, 기업 상세 드로어 |
| wealth | `WealthTab.tsx` | 전재산 추적 (금융+비금융) |
| solar | `SolarTab.tsx` | 태양광 매물 모니터링 |
| advisor | `AdvisorTab.tsx` | AI 투자 어드바이저 (SSE 스트리밍) |
| saved-strategies | `SavedStrategiesTab.tsx` | 저장된 AI 어드바이스 |
| alerts | `AlertsTab.tsx` | 투자 알림 목록 |
| system | `SystemTab.tsx` | 엔진 상태, 로그 뷰어 |
| service-map | `ServiceMapTab.tsx` | 시스템 아키텍처 시각화 |

### SSE 실시간 갱신
- `output/intel/` 파일 변경 → Flask watcher → SSE push → SWR `intel-data` 자동 재조회
- 30초마다 heartbeat ping

---

## 10. 부가 기능

### 태양광 매물 모니터링
- 9개 국내 태양광 거래 플랫폼 크롤링 (하루 2회)
- `solar_listings` 테이블 저장
- 신규 매물 Discord 알림
- 웹 대시보드에서 필터/정렬 조회

### AI 투자 어드바이저
- 자본금 · 레버리지 · 리스크 레벨 입력
- Claude API SSE 스트리밍 응답 (실시간 타이핑 표시)
- 전략 저장 → `advisor_strategies` DB
- 투자 자산 정의 DB (`investment_assets` 테이블): 20개+ 자산 카테고리, 최소 자본금/레버리지/기대수익률/리스크 레벨

### 전재산 추적
- 금융 자산: 포트폴리오 실시간 평가액
- 비금융 자산: 예금, 퇴직연금, 부동산 등 수동 입력
- 60일 이력 차트 + 월별 입금 자동 기록
- `total_wealth_history` 테이블

### Cloudflare R2 아카이브
- 파이프라인 완료 후 07:50 실행
- `regime.json`, `sector_scores.json`, `opportunities.json`, `price_analysis.json` → R2 버킷
- 날짜별 스냅샷 아카이브 (예: `archive/2026-05-01/regime.json`)

### Sanity 블로그 자동 발행
- 파이프라인 완료 후 07:55 실행
- `cio-briefing.md`, `marcus-analysis.md` → Gemini API 영어 번역 → Sanity CMS 발행
- 개인정보(매수가격/보유 종목 상세) 제거 후 공개 게시
- 카테고리: `market-analysis` (CIO 브리핑), `stock-picks` (Marcus 분석)

### Discord 알림
- 투자 긴급 알림 → Discord 비서실 채널 (`1486905937225846956`)
- 뉴스/일반 알림 → Discord 재테크 알림 채널 (`1486921732874047629`)
- Marcus 분석 완료 알림
- Jarvis CIO 브리핑 완료 알림
- 파이프라인 분석 단계 실패 알림
- 태양광 신규 매물 알림

---

## 11. DB 스키마 (db/history.db)

### 원시 테이블 (10분 해상도, 3개월 보존)
| 테이블 | 주요 컬럼 |
|--------|---------|
| `prices` | ticker, name, price, prev_close, change_pct, volume, timestamp, market, data_source |
| `macro` | indicator, value, change_pct, timestamp |
| `news` | title, summary, source, url, published_at, relevance_score, sentiment, tickers, category |
| `alerts` | level, event_type, ticker, message, value, threshold, triggered_at, notified |

### 집계 테이블 (일봉, 영구 보존)
| 테이블 | 주요 컬럼 |
|--------|---------|
| `prices_daily` | ticker, date, open, high, low, close, volume, change_pct, data_source |
| `macro_daily` | indicator, date, open, high, low, close, change_pct |

### SSoT 포트폴리오 (영구 보존)
| 테이블 | 주요 컬럼 |
|--------|---------|
| `holdings` | ticker, name, sector, currency, qty, avg_cost, buy_fx_rate, acquired_at, account, note |
| `transactions` | ticker, tx_type(BUY/SELL), qty, price, fx_rate, fee, note, executed_at |
| `extra_assets` | name, asset_type, current_value_krw, monthly_deposit_krw, is_fixed, maturity_date |
| `total_wealth_history` | date, investment_value_krw, extra_assets_krw, total_wealth_krw, investment_pnl_krw, fx_rate |
| `portfolio_history` | date, total_value_krw, total_invested_krw, total_pnl_krw, total_pnl_pct, fx_rate, fx_pnl_krw, holdings_snapshot |

### 분석·발굴 테이블
| 테이블 | 주요 컬럼 |
|--------|---------|
| `ticker_master` | ticker(PK), name, name_en, market, sector |
| `opportunities` | ticker, composite_score, discovered_at, discovered_via, score_*, price_at_discovery, outcome_1w, outcome_1m, status |
| `fundamentals` | ticker, per, pbr, roe, debt_ratio, revenue_growth, fcf, eps, dividend_yield, market_cap, sector, foreign_net, inst_net |
| `analysis_history` | date(UNIQUE), content, confidence_level, regime, today_call, created_at |
| `agent_keywords` | keyword, category, priority, reasoning, generated_at |
| `solar_listings` | source, listing_id, title, capacity_kw, location, price_krw, deal_type, url, status, first_seen_at |
| `investment_assets` | id(PK), name, category, min_capital, min_capital_leveraged, expected_return_min/max, risk_level, leverage_*, tax_benefit, status |
| `advisor_strategies` | id(PK), capital, leverage_amt, risk_level, recommendation, loans_json, monthly_savings, created_at |

### 파이프라인 이력 테이블 (JSON 덮어쓰기 보완)
| 테이블 | 주요 컬럼 | Writer 모듈 |
|--------|---------|------------|
| `regime_history` | date(UNIQUE), regime, confidence, panic_signal, vix, fx_change, oil_change, strategy_json | `analysis/regime_classifier.py` |
| `sector_scores_history` | date(UNIQUE), regime, sectors_json, updated_at | `analysis/sector_intel.py` |
| `correction_notes_history` | date(UNIQUE), period, weak_factors_json, strong_factors_json, weight_adjustment_json, summary | `analysis/self_correction.py` |
| `performance_report_history` | date(UNIQUE), outcome_summary_json, monthly_report_json, weight_suggestion_json, updated_at | `analysis/performance_report.py` |

---

## 12. 환경 변수 (.env)

| 변수 | 용도 |
|------|------|
| `BRAVE_API_KEY` | 뉴스·기회 발굴 (Brave Search) |
| `KIWOOM_APPKEY` / `KIWOOM_SECRETKEY` | 키움증권 REST API (선택) |
| `DISCORD_WEBHOOK_URL` | Discord 알림 웹훅 |
| `DART_API_KEY` | DART Open API 인증키 |
| `R2_BUCKET_NAME` / `CLOUDFLARE_ACCOUNT_ID` | Cloudflare R2 버킷 |
| `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` | R2 인증 |
| `SANITY_PROJECT_ID` / `SANITY_API_WRITE_TOKEN` | Sanity CMS 발행 |
| `GOOGLE_GEMINI_API_KEY` | 한→영 번역 (Gemini API) |

---

## 13. 출력 파일 목록 (INTEL_FILES)

`output/intel/`에 저장되어 `/api/data`로 노출:

```
prices.json             macro.json              portfolio_summary.json
alerts.json             regime.json             price_analysis.json
engine_status.json      opportunities.json      screener_results.json
news.json               fundamentals.json       supply_data.json
holdings_proposal.json  performance_report.json simulation_report.json
sector_scores.json      proactive_alerts.json   correction_notes.json
```

Markdown (직접 조회):
```
marcus-analysis.md      cio-briefing.md         daily_report.md
```

---

## 14. 코드 규칙 요약

- 모든 주석/docstring: **한국어**
- 진입점: 모든 모듈이 `run()` 함수 노출
- 설정 단일 진실 소스: `config.py`만 수정 (하드코딩 금지)
- HTTP 요청: `urllib.request` 직접 사용 (외부 라이브러리 금지)
- 외부 패키지: stdlib + pytest + ruff + yfinance + boto3 (R2용) + requests (publish_blog용)만 허용
- 시간대: KST (`timezone(timedelta(hours=9))`)
- 파일 300줄 초과 시 모듈 분리
- `server.py` 내부 모듈 임포트: 모듈 전체 임포트 방식 (`import web.api as api`)

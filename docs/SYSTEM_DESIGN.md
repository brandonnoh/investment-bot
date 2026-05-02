# 투자 인텔리전스 엔진 — 시스템 설계 문서

> **목적:** 현재 아키텍처에 대한 정확한 설계 참조. Claude Code 작업 시 기준 문서.
> **최종 갱신:** 2026-05-01

---

## 1. 핵심 철학

> **"수집·계산·저장은 엔진이, 해석·판단·전략·대화는 AI 에이전트(자비스/Marcus)가."**

3계층 분리:
- **수집 계층** `data/` — 다중 소스, 폴백, 이상값 감지
- **분석 계층** `analysis/` — 기술분석·포트폴리오·레짐·스크리닝·성과추적
- **서비스 계층** `web/` — Flask HTTP API + SSE 실시간 스트림

설계 원칙:
- 모든 모듈은 `run()` 함수를 진입점으로 노출
- **이중 저장**: SQLite (`db/history.db`) + JSON (`output/intel/`) 동시 기록
- JSON이 모듈 간 인터페이스 (분석/리포트는 DB가 아닌 JSON을 읽음)
- `output/intel/` 이 웹UI·AI 에이전트와의 유일한 인터페이스
- **Graceful degradation**: 개별 모듈 실패 시 로깅 후 파이프라인 계속 진행
- `alerts.json` 은 알림 있을 때만 생성, 없으면 삭제

---

## 2. 인프라 구조

```
외부 클라이언트 (Tailscale VPN: 100.90.201.87)
        │ :3000
        ▼
┌─────────────────────────┐
│  mc-web (Next.js)       │  web-next/Dockerfile
│  standalone 서버        │
│  /api/[...path] 프록시  ├──────────────────────┐
│  /api/events SSE 프록시 │                       │
└─────────────────────────┘                       ▼
                               ┌──────────────────────────┐
                               │  investment-bot :8421    │  Dockerfile (루트)
                               │  Flask + Docker cron     │
                               └──────────────────────────┘
```

### 컨테이너

| 컨테이너 | 포트 | 역할 |
|---------|------|------|
| `investment-bot` | 8421 | Flask HTTP API + Docker 내부 cron 스케줄러 |
| `mc-web` | 3000 | Next.js standalone 프론트엔드 |

**HOST launchd는 전부 비활성화. 모든 스케줄은 Docker 내부 cron (`crontab.docker`) 만 사용.**

### 볼륨 마운트 (docker restart만으로 코드 반영)
`web/`, `analysis/`, `data/`, `reports/`, `scripts/`, `db/`, `utils/`,
`config.py`, `run_pipeline.py`, `crontab.docker`

---

## 3. 파이프라인 실행 순서

**진입점:** `run_pipeline.py`

```
1. init_db()
2. _collect_data()
   ├─ fetch_prices()            → prices.json + DB prices
   ├─ fetch_macro()             → macro.json + DB macro
   ├─ fetch_news()              → news.json + DB news
   ├─ classify_regime()         → regime.json + DB regime_history
   ├─ fetch_fundamentals()      → fundamentals.json + DB fundamentals
   ├─ fetch_supply()            → supply_data.json
   ├─ sector_intel()            → sector_scores.json + DB sector_scores_history
   ├─ fetch_universe_daily()    → DB prices_daily (150개 유니버스 일봉)
   ├─ fetch_opportunities()     → opportunities.json + DB opportunities
   └─ update_ticker_master()    → DB ticker_master (신규 종목 UPSERT)
3. aggregate_daily() + maintain_db()
4. 분석 단계 (각 단계 독립 실행 — 실패 격리)
   ├─ analyze_prices()          → price_analysis.json
   ├─ check_alerts()            → alerts.json (알림 있을 때만)
   ├─ run_screener()            → screener_results.json
   └─ analyze_portfolio()       → portfolio_summary.json + DB portfolio_history
5. _run_post_analysis()
   ├─ track_performance()       → performance_report.json + DB performance_report_history
   ├─ run_self_correction()     → correction_notes.json + DB correction_notes_history
   ├─ run_proactive_alerts()    → proactive_alerts.json
   ├─ run_dynamic_holdings()    → holdings_proposal.json
   └─ run_simulation()          → simulation_report.json
6. validate_all_outputs()       — JSON 스키마 검증
7. save_engine_status()         → engine_status.json
8. generate_daily()             → daily_report.md
9. [--weekly] generate_weekly() → cio-briefing.md
```

### 데이터 흐름

```
config.py (설정 SSoT)
    ↓
data/ → db/history.db + output/intel/*.json (이중 저장)
    ↓
analysis/ ← JSON 읽기 → 분석 결과 JSON 생성
    ↓
reports/ → daily_report.md, cio-briefing.md, closing_report.md
    ↓
output/intel/ ← web/server.py가 읽어 /api/* 로 노출
    ↓
web-next (Next.js) ← /api/[...path] 프록시 → 클라이언트
```

---

## 4. 크론 스케줄 (Docker 내부 KST)

| 잡 | 스케줄 | 스크립트 |
|----|--------|---------|
| refresh_prices | 매 1분 | `scripts/refresh_prices.py` |
| credentials_sync | 매 1분 | `cp` 호스트 Claude 크레덴셜 동기화 |
| alerts_watch | 매 5분 | `analysis/alerts_watch.py` |
| marcus | 평일 05:30 | `scripts/run_marcus.py` |
| jarvis | 평일 07:30 | `scripts/run_jarvis.py` |
| pipeline | 평일 07:40 | `run_pipeline.py` |
| sync_to_r2 | 평일 07:50 | `scripts/sync_to_r2.py` |
| publish_blog | 평일 07:55 | `scripts/publish_blog.py` |
| news | 평일 08:00 | `scripts/refresh_news.py` |
| company_profiles | 평일 08:10 | `data/fetch_company_profiles.py` |
| refresh_solar | 매일 08:30, 19:00 | `scripts/refresh_solar.py` |
| monthly_deposit | 매월 1일 00:00 | `scripts/monthly_deposit_cron.py` |
| dart_corp_codes | 매월 1일 05:00 | `data/fetch_dart_corp_codes.py` |
| closing | 평일 16:00 | `reports/closing.py` |
| universe_cache | 매주 일요일 04:00 | `analysis/universe_cache.py` |
| db_maintenance | 매주 일요일 03:00 | `db/maintenance.py` |
| log_rotation | 매일 00:05 | find + gzip (10MB 초과 압축, 7일 이상 삭제) |

---

## 5. Flask API 엔드포인트 (web/server.py)

### GET

| 엔드포인트 | 역할 |
|-----------|------|
| `/api/data` | INTEL_FILES 전체 통합 조회 (메인 데이터) |
| `/api/status` | 파이프라인/Marcus 실행 상태 (PID 파일 기반) |
| `/api/events` | SSE 스트림 (intel/ 변경 감지 5초 폴링 → 클라이언트 push) |
| `/api/analysis-history` | Marcus 분석 이력 목록 (최신 30개) |
| `/api/analysis-history?date=YYYY-MM-DD` | 특정 날짜 전체 분석 내용 |
| `/api/wealth?days=60` | 전재산 (투자+비금융 자산, N일 이력) |
| `/api/logs?name=marcus&lines=80` | 로그 마지막 N줄 (허용 이름 화이트리스트) |
| `/api/opportunities?strategy=composite` | 발굴 종목 (전략별 스크리너) |
| `/api/solar?limit=100` | 태양광 발전소 매물 목록 |
| `/api/strategies` | 스크리너 전략 메타 목록 |
| `/api/file?name=X.md` | 마크다운/JSON 파일 직접 조회 |
| `/api/investment-assets` | 투자 자산 정의 목록 (DB SSoT) |
| `/api/advisor-strategies?limit=20` | 저장된 어드바이저 전략 이력 |
| `/api/company?ticker=XXX` | 기업 프로필 + 펀더멘탈 + 최근 뉴스 |
| `/api/regime-history?days=90` | 레짐 분류 이력 |
| `/api/sector-scores-history?days=90` | 섹터 점수 이력 |
| `/api/correction-notes-history?limit=30` | 자기 교정 노트 이력 |
| `/api/performance-report-history?days=90` | 성과 보고서 이력 |

### POST

| 엔드포인트 | 역할 |
|-----------|------|
| `/api/run-pipeline` | 파이프라인 백그라운드 실행 (PID 파일로 중복 방지) |
| `/api/run-marcus` | Marcus 백그라운드 실행 |
| `/api/refresh-prices` | 가격 새로고침 백그라운드 실행 |
| `/api/wealth/assets` | 비금융 자산 추가 (DB INSERT) |
| `/api/investment-advice` | AI 투자 어드바이스 (동기 응답) |
| `/api/investment-advice-stream` | AI 투자 어드바이스 (SSE 스트리밍) |
| `/api/advisor-strategies` | 어드바이저 전략 저장 |

### PUT / DELETE

| 엔드포인트 | 역할 |
|-----------|------|
| `/api/wealth/assets/{id}` | 비금융 자산 수정 |
| `/api/wealth/assets/{id}` | 비금융 자산 삭제 |
| `/api/advisor-strategies/{id}` | 저장된 전략 삭제 |

---

## 6. INTEL_FILES (web/api.py)

`output/intel/` 에서 읽어 `/api/data` 로 노출하는 파일 목록.
**새 분석 모듈 추가 시 반드시 이 목록에도 파일명 추가.**

```python
INTEL_FILES = [
    "prices.json",
    "macro.json",
    "portfolio_summary.json",
    "alerts.json",
    "regime.json",
    "price_analysis.json",
    "engine_status.json",
    "opportunities.json",
    "screener_results.json",
    "news.json",
    "fundamentals.json",
    "supply_data.json",
    "holdings_proposal.json",
    "performance_report.json",
    "simulation_report.json",
    "sector_scores.json",
    "proactive_alerts.json",
    "correction_notes.json",
]

MD_FILES = ["marcus-analysis.md", "cio-briefing.md", "daily_report.md"]
```

---

## 7. DB 스키마 (db/history.db)

총 **25개 테이블** (원시 4 + 집계 2 + SSoT 5 + 분석·발굴 10 + 이력 4).
WAL 모드, PRAGMA synchronous=NORMAL.

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
| `analysis_history` | date(UNIQUE), content, confidence_level, regime, today_call |
| `agent_keywords` | keyword, category, priority, reasoning, generated_at |
| `solar_listings` | source, listing_id, title, capacity_kw, location, price_krw, deal_type, url, status, first_seen_at |
| `investment_assets` | id(PK), name, category, min_capital, expected_return_min/max, risk_level, leverage_*, tax_benefit, status |
| `advisor_strategies` | id(PK), capital, leverage_amt, risk_level, recommendation, saved_at, loans_json, monthly_savings |
| `dart_corp_codes` | corp_code, corp_name, stock_code, modify_date |
| `company_profiles` | ticker(PK), name, name_en, sector, description, screen_strategies, analyst_reports, ... |

### 파이프라인 이력 테이블 (JSON 덮어쓰기 보완)

매 실행마다 DB에 UPSERT (date UNIQUE). JSON은 최신 1건만 보존하므로 이력은 DB에서 조회.

| 테이블 | 주요 컬럼 | Writer 모듈 |
|--------|---------|------------|
| `regime_history` | date(UNIQUE), regime, confidence, panic_signal, vix, fx_change, oil_change, strategy_json | `analysis/regime_classifier.py` |
| `sector_scores_history` | date(UNIQUE), regime, sectors_json, updated_at | `analysis/sector_intel.py` |
| `correction_notes_history` | date(UNIQUE), period, weak_factors_json, strong_factors_json, weight_adjustment_json, summary | `analysis/self_correction.py` |
| `performance_report_history` | date(UNIQUE), outcome_summary_json, monthly_report_json, weight_suggestion_json, updated_at | `analysis/performance.py` |

이력 조회 API: `GET /api/regime-history` · `/api/sector-scores-history` · `/api/correction-notes-history` · `/api/performance-report-history`
조회 함수: `web/api_history.py`

---

## 8. 웹 서브모듈 구조 (web/)

| 파일 | 역할 |
|------|------|
| `server.py` | ThreadingHTTPServer + 라우팅. 모든 내부 모듈을 전체 임포트 (`import web.api as api`) |
| `api.py` | INTEL_FILES 로드, 프로세스 실행 관리 (run_background, get_process_status), 분석 이력·자산 조회 |
| `api_history.py` | regime/sector/correction/performance 이력 DB 조회 (api.py 300줄 초과 방지용 분리) |
| `api_company.py` | 기업 프로필 + 펀더멘탈 + 최근 뉴스 병합 조회 |
| `api_advisor.py` | 어드바이저 저장 전략 CRUD |
| `investment_advisor.py` | AI 투자 어드바이스 생성 (동기/스트리밍) |
| `claude_caller.py` | Anthropic Claude API 호출 래퍼 |
| `portfolio_refresh.py` | portfolio_summary를 prices.json 최신 가격으로 실시간 재계산 |
| `advisor_data.py` | 어드바이저 입력 데이터 처리 보조 |
| `loan_math.py` | 대출 상환 계산 로직 |

**server.py 임포트 규칙:** 내부 모듈은 반드시 전체 임포트. 선택 임포트 금지.
```python
# 올바름
import web.api as api

# 금지
from web.api import load_intel_data, run_background
```

---

## 9. 분석 모듈 구조 (analysis/)

| 파일 | 출력 |
|------|------|
| `alerts.py` / `alerts_watch.py` | `alerts.json` + Discord 알림 |
| `composite_score.py` | 종목 복합 점수 계산 (수급/RSI/PER/모멘텀/감성/매크로) |
| `dynamic_holdings.py` | `holdings_proposal.json` |
| `performance.py` | `performance_report.json` + DB |
| `portfolio.py` | `portfolio_summary.json` + DB |
| `price_analysis.py` | `price_analysis.json` |
| `proactive_alerts.py` | `proactive_alerts.json` |
| `regime_classifier.py` | `regime.json` + DB |
| `screener.py` / `value_screener.py` | `screener_results.json` |
| `sector_intel.py` | `sector_scores.json` + DB |
| `self_correction.py` | `correction_notes.json` + DB |
| `simulation.py` | `simulation_report.json` |
| `universe_cache.py` | DB prices_daily 사전 캐시 (매주 일요일) |

---

## 10. 데이터 수집 모듈 구조 (data/)

| 파일 | 소스 | 출력 |
|------|------|------|
| `fetch_prices.py` | Yahoo Finance + 키움 API | `prices.json` + DB |
| `fetch_macro.py` | Yahoo Finance + 키움 API | `macro.json` + DB |
| `fetch_news.py` | Google News RSS + Brave Search | `news.json` + DB |
| `fetch_fundamentals.py` | DART API + Yahoo Finance | `fundamentals.json` + DB |
| `fetch_supply.py` | 키움 수급 + CNN Fear&Greed | `supply_data.json` |
| `fetch_opportunities.py` | Brave Search + Naver 뉴스 | `opportunities.json` + DB |
| `fetch_universe_daily.py` | Yahoo Finance (150개 유니버스) | DB prices_daily |
| `fetch_company_profiles.py` | Yahoo Finance + DART | DB company_profiles |
| `fetch_dart_corp_codes.py` | DART OpenAPI | DB dart_corp_codes |
| `ticker_master.py` | 내부 종합 | DB ticker_master |
| `fetch_solar_*.py` (9개) | 태양광 매물 사이트 각각 | DB solar_listings |

---

## 11. Next.js 프론트엔드 (web-next/)

**기술 스택:** Next.js 16.2.4 · React 19 · TypeScript 5 · Tailwind CSS 4 · Zustand · SWR · Recharts · shadcn/ui · react-markdown

### 탭 구성 (11개)
`overview` · `portfolio` · `marcus` · `discovery` · `wealth` · `solar` · `advisor` · `saved-strategies` · `alerts` · `system` · `service-map`

### 핵심 파일

| 경로 | 역할 |
|------|------|
| `src/app/page.tsx` | 메인 SPA (탭 렌더링) |
| `src/app/api/[...path]/route.ts` | Flask 프록시 (SSE·스트리밍 특별처리) |
| `src/store/useMCStore.ts` | Zustand 전역 상태 (activeTab, pipelineRunning 등) |
| `src/hooks/useIntelData.ts` | SWR `/api/data` (SSE 트리거로 갱신) |
| `src/hooks/useSSE.ts` | EventSource 관리 → intel-data mutate |
| `src/lib/api.ts` | fetcher 함수 모음 |
| `src/lib/format.ts` | `fmtKrw()`, `fmtPct()`, `pctColor()` |
| `src/types/api.ts` | Flask 응답 타입 (IntelData, PriceItem 등) |
| `src/types/advisor.ts` | InvestmentAsset, RiskLevel 등 |

### SWR 갱신 전략

| 키 | 갱신 방식 |
|----|---------|
| `intel-data` | 수동 + SSE 트리거 |
| `process-status` | 5초 폴링 |
| `marcus-log` | 3초 폴링 (실행 중만) |
| `opportunities-*` | 5분 캐시 |
| `/api/wealth` | 1분 폴링 |

---

## 12. 배포 규칙

| 뭘 바꿨나 | 명령 |
|-----------|------|
| 볼륨 마운트 목록 안의 파일 (Python, crontab 등) | `docker restart investment-bot` |
| `docker-compose.yml` | `docker compose up -d --no-build --no-deps investment-bot` |
| `web-next/` (Next.js) | `npm run build` → `docker cp` → `docker restart mc-web` |
| `Dockerfile` / `requirements.txt` | `docker compose build` → `docker compose up -d` |

**Next.js 배포 순서 (절대 변경 금지):**
```bash
cd web-next && npm run build && cd ..
docker exec mc-web rm -rf /app/.next/static/
docker cp web-next/.next/standalone/. mc-web:/app/
docker cp web-next/.next/static/. mc-web:/app/.next/static/
docker restart mc-web
```

`rm -rf /app/.next/static/` 생략 금지 — docker cp는 파일을 추가만 하므로 구버전 JS chunk가 남으면 브라우저가 구버전 코드를 로드한다.

**헬스 체크:**
```bash
docker exec investment-bot python3 -c \
  "import urllib.request; print(urllib.request.urlopen('http://localhost:8421/api/status').read().decode()[:80])"
docker inspect investment-bot --format='{{.State.Health.Status}}'
```

---

## 13. 환경 변수 (.env)

| 변수 | 용도 | 없을 때 영향 |
|------|------|------------|
| `BRAVE_API_KEY` | Brave Search 종목 발굴·뉴스 수집 | Naver만 사용, 발굴 품질 저하 |
| `DART_API_KEY` | DART OpenAPI 재무제표·법인코드 | fundamentals.json 국내 종목 누락 |
| `KIWOOM_APPKEY` / `KIWOOM_SECRETKEY` | 키움증권 REST API 수급 | supply_data.json krx_supply 누락 |
| `DISCORD_WEBHOOK_URL` | 파이프라인 실패 알림 Discord 전송 | 알림 미전송 |
| `ANTHROPIC_API_KEY` | Claude API (Marcus 분석, 어드바이저) | AI 분석 전체 불가 |

---

## 14. Discord 알림 규칙

| 채널 | 용도 | `--to` 값 |
|------|------|-----------|
| Discord 비서실 | 긴급 투자 알림 | `channel:1486905937225846956` |
| Discord 재테크 알림 | 뉴스/일반 알림 | `channel:1486921732874047629` |

`--to` 파라미터 누락 시 전송 실패. 반드시 지정.

---

## 15. 반복 실수 방지

### import 누락
새 함수를 다른 파일에서 호출할 때 import 추가를 빠뜨리는 패턴이 반복 발생.

```bash
# 변경 후 반드시 검증
python3 -c "import web.api; import web.server; import analysis.solar_alerts"

# 또는 전체 검사
bash .claude/skills/deploy/scripts/pre-deploy-check.sh
```

### INTEL_FILES 동기화
새 분석 모듈 추가 → JSON 출력 파일 생성 → `web/api.py`의 `INTEL_FILES` 목록에도 추가 필수.
누락 시 `/api/data` 로 해당 데이터 조회 불가.

### 모듈 참조 관계

```
db/connection.py (get_db_conn)
  └─ import: web/api.py, db/ssot.py, db/ssot_wealth.py, db/aggregate.py, db/maintenance.py

data/fetch_solar_base.py (SolarListing, parse_* 함수들)
  └─ import: data/fetch_solar_allthatsolar.py, solarmarket.py, exchange.py, solartrade.py,
             solardirect.py, haetbit.py, ssunlab.py, koreari.py, onbid.py

web/api.py (load_intel_data, load_solar_listings, load_wealth, ...)
  └─ import: web/server.py (전체 모듈 임포트: import web.api as api)

config.py (DB_PATH, PORTFOLIO, ...)
  └─ import: 거의 모든 모듈
```

---

*배포 전 `pre-deploy-check.sh` 실행 필수. GitHub push는 코드 백업용이며 자동 배포 없음.*

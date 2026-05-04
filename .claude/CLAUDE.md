# CLAUDE.md

## 프로젝트 개요

개인 투자자를 위한 **기관급 금융 인텔리전스 엔진**.
수집/계산/저장은 이 엔진이, 해석/판단/전략/대화는 AI 에이전트(자비스/Marcus)가 담당.

### 3계층 아키텍처
- **수집 계층** `data/` — 다중 소스(Yahoo/Kiwoom/DART/Brave/RSS), 폴백, 이상값 감지
- **분석 계층** `analysis/` — 기술분석·포트폴리오·레짐·스크리닝·성과추적 (39개 모듈)
- **서비스 계층** `web/` — Flask HTTP API + SSE 실시간 스트림 (포트 8421)

---

## 빌드 & 테스트

```bash
python3 run_pipeline.py           # 전체 파이프라인
python3 run_pipeline.py --weekly  # 주간 리포트 포함

# 개별 모듈
python3 data/fetch_prices.py
python3 data/fetch_macro.py
python3 data/fetch_news.py
python3 analysis/alerts.py
python3 analysis/alerts_watch.py
python3 analysis/screener.py
python3 analysis/portfolio.py
python3 reports/daily.py
python3 reports/weekly.py
python3 reports/closing.py

# 테스트
python3 -m pytest tests/ -v

# 린트
ruff check .
ruff format --check .
```

---

## 아키텍처

### 파이프라인 실행 순서 (run_pipeline.py)

```
1. init_db()
2. _collect_data()
   ├─ fetch_prices()         → prices.json
   ├─ fetch_macro()          → macro.json
   ├─ fetch_news()           → news.json
   ├─ classify_regime()      → regime.json + DB regime_history
   ├─ fetch_fundamentals()   → fundamentals.json
   ├─ fetch_supply()         → supply_data.json
   ├─ sector_intel()         → sector_scores.json + DB sector_scores_history
   ├─ fetch_universe_daily() → DB prices_daily (JSON 없음)
   └─ fetch_opportunities()  → opportunities.json
        └─ update_ticker_master() → DB ticker_master (JSON 없음)
3. aggregate_daily() + maintain_db()
4. analyze_prices()      → price_analysis.json
   check_alerts()        → alerts.json (알림 있을 때만)
   run_screener()        → screener_results.json + screener.md
   analyze_portfolio()   → portfolio_summary.json
5. _run_post_analysis()
   ├─ track_performance()     → performance_report.json + DB performance_report_history
   ├─ run_self_correction()   → correction_notes.json + DB correction_notes_history
   ├─ run_proactive_alerts()  → proactive_alerts.json
   ├─ run_dynamic_holdings()  → holdings_proposal.json
   └─ run_simulation()        → simulation_report.json
6. validate_all_outputs()
7. save_engine_status()  → engine_status.json
8. generate_daily()      → daily_report.md
9. [--weekly] generate_weekly() → weekly_report.md
   + 실패 단계 있으면 Discord 알림
```

### 데이터 흐름

```
config.py (설정 SSoT)
    ↓
data/ → SQLite(history.db) + output/intel/*.json (이중 저장)
    ↓
analysis/ ← JSON 읽기 → 분석 결과 JSON 생성
    ↓
reports/ → daily_report.md, weekly_report.md, closing_report.md
    ↓
output/intel/ ← web/server.py가 읽어 /api/* 로 노출
    ↓
web-next (Next.js) ← /api/[...path] 프록시 → 클라이언트
```

### 핵심 설계 패턴

- **모든 모듈은 `run()` 함수**를 진입점으로 노출. `run_pipeline.py`가 순서대로 호출
- **이중 저장**: SQLite + JSON 동시 저장
- **JSON이 모듈 간 인터페이스**: 분석/리포트 모듈은 DB가 아닌 JSON을 읽음
- **`output/intel/`이 자비스/웹UI와의 유일한 인터페이스**
- **Graceful degradation**: 개별 실패 시 로깅 후 계속 진행, 파이프라인 중단 금지
- **alerts.json은 알림 있을 때만 생성**, 없으면 삭제
- **새 분석 모듈 추가 시 `web/api.py`의 INTEL_FILES 목록도 반드시 함께 추가** (누락 시 `/api/data`로 조회 불가)

---

## Flask API 엔드포인트 (web/server.py)

### GET

| 엔드포인트 | 역할 |
|-----------|------|
| `/api/data` | INTEL_FILES 전체 통합 조회 (메인 데이터) |
| `/api/status` | 파이프라인/Marcus 실행 상태 |
| `/api/events` | SSE 스트림 (intel/ 변경 감지 → 클라이언트 push, 30초 ping) |
| `/api/analysis-history` | Marcus 분석 이력 목록 |
| `/api/analysis-history?date=YYYY-MM-DD` | 특정 날짜 상세 |
| `/api/wealth?days=60` | 전재산 (금융+비금융, 1~365일 이력) |
| `/api/logs?name=marcus&lines=80` | 로그 마지막 N줄 (허용: marcus/pipeline/jarvis/alerts_watch/refresh_prices) |
| `/api/opportunities?strategy=composite` | 발굴 종목 (전략별) |
| `/api/solar?limit=100` | 태양광 매물 |
| `/api/strategies` | 스크리너 전략 메타 |
| `/api/file?name=X.md` | 마크다운/JSON 파일 조회 |
| `/api/investment-assets` | 투자 자산 정의 전체 조회 |
| `/api/advisor-strategies?limit=20` | 저장된 AI 어드바이저 전략 목록 |
| `/api/company?ticker=XXX` | 기업 프로필 + 펀더멘탈 + 최근 뉴스 병합 |
| `/api/regime-history?days=90` | 레짐 분류 이력 (DB) |
| `/api/sector-scores-history?days=90` | 섹터 점수 이력 (DB) |
| `/api/correction-notes-history?limit=30` | 자기교정 이력 (DB) |
| `/api/performance-report-history?days=90` | 성과 리포트 이력 (DB) |

이력 조회 함수: `web/api_history.py` (api.py 300줄 초과 방지용 분리 모듈)
기업 프로필 함수: `web/api_company.py`
어드바이저 함수: `web/api_advisor.py`

### POST

| 엔드포인트 | 역할 |
|-----------|------|
| `/api/run-pipeline` | 파이프라인 백그라운드 실행 (중복 방지) |
| `/api/run-marcus` | Marcus 백그라운드 실행 (중복 방지) |
| `/api/refresh-prices` | 가격 새로고침 |
| `/api/wealth/assets` | 비금융 자산 추가 |
| `/api/investment-advice` | AI 투자 어드바이스 (동기) |
| `/api/investment-advice-stream` | AI 투자 어드바이스 (SSE 스트리밍) |
| `/api/advisor-strategies` | AI 어드바이저 전략 저장 |

### PUT / DELETE

| 엔드포인트 | 메서드 | 역할 |
|-----------|--------|------|
| `/api/wealth/assets/{id}` | PUT | 비금융 자산 수정 |
| `/api/wealth/assets/{id}` | DELETE | 비금융 자산 삭제 |
| `/api/advisor-strategies/{id}` | DELETE | 저장된 어드바이저 전략 삭제 |

---

## INTEL_FILES (web/api.py)

`output/intel/` 에서 읽어 `/api/data`로 노출하는 파일 목록.
**새 분석 모듈 추가 시 반드시 이 목록에도 추가.**

```python
INTEL_FILES = [
    "prices.json", "macro.json", "portfolio_summary.json", "alerts.json",
    "regime.json", "price_analysis.json", "engine_status.json",
    "opportunities.json", "screener_results.json", "news.json",
    "fundamentals.json", "supply_data.json", "holdings_proposal.json",
    "performance_report.json", "simulation_report.json", "sector_scores.json",
    "proactive_alerts.json", "correction_notes.json",
]
MD_FILES = ["marcus-analysis.md", "cio-briefing.md", "daily_report.md"]
```

---

## ⚠️ 반복 실수 — 반드시 숙지

### 임포트 누락 (가장 많이 발생)

Python은 import 누락을 런타임 전까지 잡아주지 않는다. 아래 두 가지 상황에서 반복 발생했다:

1. **새 유틸리티 함수 생성 후 사용처에 import 빠뜨리기**
   - 예: `db/connection.py`에 `get_db_conn` 신설 → `web/api.py`에서 호출 코드는 추가했지만 `from db.connection import get_db_conn` 누락
   - **규칙: 새 함수를 만들고 다른 파일에서 쓰면, 그 파일 상단 import를 제일 먼저 추가한다**

2. **base 모듈에 함수 추가 후 import 목록 갱신 누락**
   - 예: `fetch_solar_base.py`에 `parse_deal_type` 추가 → `fetch_solar_onbid.py` 호출 코드는 넣었지만 import 목록에서 빠짐
   - **규칙: `from X import (A, B)` 목록을 수정할 때 사용하는 이름 전부 나열됐는지 확인**

3. **`server.py`에서 내부 모듈 선택 임포트 금지**
   - `from web.api import fn1, fn2` 대신 `import web.api as api` — 새 함수 추가 시 목록 갱신 실수 방지

### import 검증 — 코드 변경 후 반드시 실행

```bash
bash .claude/skills/deploy/scripts/pre-deploy-check.sh
```

21개 핵심 모듈 import + API 엔드포인트 + DB 테이블 자동 검사. 실패 시 exit 1.

실패 없이 통과해야 배포 진행.

### 모듈 참조 관계 (새 모듈 추가 시 이 관계 확인)

```
db/connection.py (get_db_conn)
  └─ import: web/api.py, db/ssot.py, db/ssot_wealth.py, db/aggregate.py, db/maintenance.py

db/ssot.py (get_holdings, ...)
  └─ import: data/fetch_news.py, analysis/*, scripts/*

utils/schema.py (validate_json)
  └─ import: web/api.py (load_intel_data 루프 안에서 호출)

utils/json_io.py (write_json_atomic)
  └─ import: analysis/alerts_io.py (알림 있을 때만 호출되는 경로)

data/fetch_fundamentals_sources.py (fetch_naver_per_pbr, fetch_yahoo_financials, ...)
  └─ import: data/fetch_universe_daily.py

data/fetch_gold_krx.py (fetch_kiwoom_investor, ...)
  └─ import: data/fetch_universe_daily.py

data/fetch_solar_base.py (SolarListing, parse_capacity, parse_location, parse_price, parse_deal_type, ...)
  └─ import: data/fetch_solar_allthatsolar.py, solarmarket.py, exchange.py, solartrade.py,
             solardirect.py, haetbit.py, ssunlab.py, koreari.py, onbid.py

web/api.py (load_intel_data, load_solar_listings, load_wealth, ...)
  └─ import: web/server.py (전체 모듈 임포트: import web.api as api)

config.py (DB_PATH, PORTFOLIO, ...)
  └─ import: 거의 모든 모듈
```

---

## 코드 규칙

- 모든 주석/docstring은 **한국어**
- 마크다운 리포트는 한국어 + 이모지
- 종목/지표 추가·수정은 **반드시 `config.py`만** 수정 (하드코딩 금지)
- HTTP 요청은 `urllib.request` 직접 사용 (외부 라이브러리 금지)
- 외부 패키지 추가 금지 (stdlib + pytest + ruff + yfinance만 허용)
  - **예외**: `scripts/sync_to_r2.py` → `boto3` (R2 업로드), `scripts/publish_blog.py` → `requests` (Sanity API)
- 시간대는 KST (`timezone(timedelta(hours=9))`)
- `sys.path.insert(0, ...)` 패턴으로 프로젝트 루트를 모듈 경로에 추가
- **`server.py`에서 내부 모듈 임포트는 반드시 모듈 전체 임포트** (`import web.api as api`). 함수 선택 임포트(`from web.api import ...`) 금지

---

## DB 스키마 (db/history.db)

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
| `total_wealth_history` | date, investment_value_krw, extra_assets_krw, total_wealth_krw, investment_pnl_krw, investment_pnl_pct, fx_rate |
| `portfolio_history` | date, total_value_krw, total_invested_krw, total_pnl_krw, total_pnl_pct, fx_rate, fx_pnl_krw, holdings_snapshot |

### 분석·발굴 테이블
| 테이블 | 주요 컬럼 |
|--------|---------|
| `ticker_master` | ticker(PK), name, name_en, market, sector, updated_at |
| `opportunities` | ticker, composite_score, discovered_at, discovered_via, score_return, score_rsi, score_sentiment, score_macro, score_value, score_quality, score_growth, price_at_discovery, outcome_1w, outcome_1m, status |
| `fundamentals` | ticker, per, pbr, roe, debt_ratio, revenue_growth, operating_margin, fcf, eps, dividend_yield, market_cap, sector, foreign_net, inst_net |
| `analysis_history` | date(UNIQUE), content, confidence_level, regime, today_call, created_at |
| `agent_keywords` | keyword, category, priority, reasoning, generated_at, used_at, results_count |
| `solar_listings` | source, listing_id, title, capacity_kw, location, price_krw, deal_type, url, status, first_seen_at, last_seen_at |
| `investment_assets` | id(PK), name, category, min_capital, min_capital_leveraged, expected_return_min/max, risk_level, liquidity, leverage_available, leverage_ratio, leverage_type, tax_benefit, status, description |
| `dart_corp_codes` | stock_code(PK), corp_code, corp_name, market |
| `company_profiles` | ticker(PK), name, sector, industry, description, name_kr, ceo, address, founded, market_cap, current_price, price_52w_high, price_52w_low, foreign_rate, screen_strategies, updated_at |
| `advisor_strategies` | id, capital, leverage_amt, risk_level, recommendation, loans_json, monthly_savings, saved_at |

### 파이프라인 이력 테이블 (JSON 덮어쓰기 보완)
매 실행마다 DB에 UPSERT(date UNIQUE).

| 테이블 | 주요 컬럼 | Writer 모듈 |
|--------|---------|------------|
| `regime_history` | date(UNIQUE), classified_at, regime, confidence, panic_signal, vix, fx_change, oil_change, strategy_json | `analysis/regime_classifier.py` |
| `sector_scores_history` | date(UNIQUE), regime, sectors_json, updated_at | `analysis/sector_intel.py` |
| `correction_notes_history` | date(UNIQUE), period, weak_factors_json, strong_factors_json, weight_adjustment_json, summary, generated_at | `analysis/self_correction.py` |
| `performance_report_history` | date(UNIQUE), outcome_summary_json, monthly_report_json, weight_suggestion_json, updated_at | `analysis/performance_report.py` |

---

## 환경 변수 (.env)

```bash
BRAVE_API_KEY=xxx           # 뉴스·기회 발굴 (Brave Search)
KIWOOM_APPKEY=xxx           # 키움증권 REST API (선택)
KIWOOM_SECRETKEY=xxx        # 키움증권 REST API (선택)
DISCORD_WEBHOOK_URL=xxx     # Discord 알림 웹훅 (단일 URL — 모든 알림 공통)
DART_API_KEY=xxx            # DART OpenAPI 인증키
GOOGLE_GEMINI_API_KEY=xxx   # 블로그 번역 (publish_blog.py)
SANITY_PROJECT_ID=xxx       # Sanity CMS 발행 (publish_blog.py)
SANITY_API_WRITE_TOKEN=xxx  # Sanity CMS 발행 (publish_blog.py)
```

## Discord 알림 구조

모든 Python 알림은 `DISCORD_WEBHOOK_URL` 단일 웹훅으로 전송된다. 채널 구분 없음.

| 발생 위치 | 트리거 | 메시지 형식 |
|----------|--------|-----------|
| `analysis/alerts_watch.py` | 임계값 초과 감지 (5분마다) | `[투자 알림] 종목 급등/급락 %` |
| `analysis/solar_alerts.py` | 신규 태양광 매물 발견 | `[태양광 새 매물 N건] 제목·위치·용량·가격·URL` |
| `scripts/run_marcus.py` | Marcus 분석 완료 | `마커스 ★★★☆☆ / 오늘의 판단 / 방향성` |
| `scripts/run_marcus.py` | Claude 실행 실패 | `❌ 마커스 분석 실패: {에러}` |
| `scripts/run_jarvis.py` | Jarvis 브리핑 완료 | `자비스 CIO | 리스크 점수 / 요약 / 액션` |
| `run_pipeline.py` | 분석 단계 실패 | `⚠️ 파이프라인 분석 단계 실패: {단계명}` |

## 주의사항
- `db/history.db`, `output/` — git 제외 (.gitignore)
- Yahoo Finance 과도한 요청 시 rate limit 주의 (10분 간격 권장)
- `.kiwoom_token.json` — 토큰 캐시 (git 제외)
- `config.py`의 `DISCORD_WEBHOOK_URL` 정의는 실제로 사용되지 않음 — 각 모듈이 `os.environ.get`으로 직접 읽음

---

## Claude CLI 사용처

컨테이너 내부에서 `claude` 바이너리를 직접 호출한다. 인증 토큰은 매 1분 호스트에서 자동 동기화.

| 스크립트 | 호출 방식 | 출력 |
|---------|----------|------|
| `scripts/run_marcus.py` | `subprocess.run([claude, "--output-format", "json", "-p", "-"])` — 최대 3회 (분석+키워드 2종) | `output/intel/marcus-analysis.md` + DB `analysis_history`, `agent_keywords` |
| `scripts/run_jarvis.py` | `subprocess.run([claude, "--print", "-p", "-"])` | `output/intel/cio-briefing.md` |
| `scripts/retranslate_descriptions.py` | `web/claude_caller.py` 경유 | DB `company_profiles` 한국어 설명 업데이트 |
| `web/api_company.py` (어드바이저) | `web/claude_caller.py` 경유 (API키 있으면 Messages API 직접) | HTTP 응답 스트리밍 |

---

## 웹 서비스 아키텍처

```
외부 클라이언트 (Tailscale VPN: 100.90.201.87)
        │ :3000
        ▼
┌─────────────────────────┐
│  mc-web (Next.js)       │  web-next/Dockerfile
│  standalone 서버        │
│  /api/[...path] → 프록시┼──────────────────────┐
│  /api/events → SSE 프록시  maxDuration=120      │
└─────────────────────────┘                      ▼
                               ┌─────────────────────────┐
                               │  investment-bot :8421   │  Dockerfile (루트)
                               │  Flask + cron 스케줄러  │
                               └─────────────────────────┘
```

**GitHub push는 코드 백업용 — 자동 배포 없음. 항상 수동 배포 명령 실행.**

### 컨테이너 구조

| 컨테이너 | 포트 | 역할 |
|---------|------|------|
| `investment-bot` | 8421 | Flask API + 내부 cron 스케줄러 |
| `mc-web` | 3000 | Next.js standalone 프론트엔드 |

### 볼륨 마운트 (이 목록 = docker restart만으로 반영)
`web/`, `analysis/`, `data/`, `reports/`, `scripts/`, `db/`, `utils/`,
`config.py`, `run_pipeline.py`, `crontab.docker`

### HOST launchd 전부 비활성화. 스케줄은 Docker 내부 cron만 사용.

### 스케줄 (KST)

| 잡 | 스케줄 | 스크립트 |
|----|--------|---------|
| credentials_sync | 매 1분 | `cp /root/.claude-host/.credentials.json /root/.claude/.credentials.json` |
| refresh_prices | 매 1분 | `scripts/refresh_prices.py` |
| alerts_watch | 매 5분 | `analysis/alerts_watch.py` |
| marcus | 평일 05:30 | `scripts/run_marcus.py` |
| jarvis | 평일 07:30 | `scripts/run_jarvis.py` |
| pipeline | 평일 07:40 | `run_pipeline.py` |
| sync_r2 | 평일 07:50 | `scripts/sync_to_r2.py` |
| publish_blog | 평일 07:55 | `scripts/publish_blog.py` |
| news | 평일 08:00 | `scripts/refresh_news.py` |
| company_profiles | 평일 08:10 | `data/fetch_company_profiles.py` |
| closing | 평일 16:00 | `reports/closing.py` |
| refresh_solar | 매일 08:30, 19:00 | `scripts/refresh_solar.py` |
| universe_cache | 매주 일요일 04:00 | `analysis/universe_cache.py` |
| db_maintenance | 매주 일요일 03:00 | `db/maintenance.py` |
| log_rotation | 매일 00:05 | find + gzip (10MB 초과 압축, 7일 이상 삭제) |
| monthly_deposit | 매월 1일 00:00 | `scripts/monthly_deposit_cron.py` |
| dart_corp_codes | 매월 1일 05:00 | `data/fetch_dart_corp_codes.py` |

---

## ⚠️ 배포 규칙 — 변경 파일에 따라 명령이 다르다

| 뭘 바꿨나 | 명령 |
|-----------|------|
| 볼륨 마운트 목록 안의 파일 (Python, crontab 등) | `docker restart investment-bot` |
| `docker-compose.yml` | `docker compose up -d --no-build --no-deps investment-bot` |
| `web-next/` (Next.js) | `npm run build` → `docker cp` → `docker restart mc-web` |
| `Dockerfile` / `requirements.txt` (매우 드묾) | `docker compose build` → `docker compose up -d` |

**헬스 체크 (curl 없음 — python 사용):**
```bash
docker exec investment-bot python3 -c \
  "import urllib.request; print(urllib.request.urlopen('http://localhost:8421/api/status').read().decode()[:80])"
docker inspect investment-bot --format='{{.State.Health.Status}}'
```

**Next.js 배포 (반드시 이 순서, 절대 변경 금지):**
```bash
cd web-next && npm run build && cd ..
docker exec mc-web rm -rf /app/.next/static/
docker cp web-next/.next/standalone/. mc-web:/app/
docker cp web-next/.next/static/. mc-web:/app/.next/static/
docker restart mc-web
```
⚠️ `rm -rf /app/.next/static/` 생략 금지 — docker cp는 덮어쓰지 않고 추가만 함. 구버전 JS chunk가 남으면 브라우저가 구버전 코드를 로드한다. 반드시 삭제 후 복사.

**Dockerfile 빌드 시 Keychain 잠겨 있으면 실패한다.**
이 경우 사용자가 직접 `! security -v unlock-keychain ~/Library/Keychains/login.keychain-db` 실행 후 진행.

---

## Next.js 프론트엔드 구조 (web-next/)

### 기술 스택
Next.js 16.2.4 · React 19.2.4 · TypeScript 5 · Tailwind CSS 4 · Zustand 5 · SWR 2 · Recharts 3 · shadcn · react-markdown 10

### 탭 구성 (11개)
**메인 탭 (하단 바):** `overview` · `portfolio` · `wealth` · `marcus` · `discovery`
**추가 탭 (메뉴):** `solar` · `advisor` · `saved-strategies` · `alerts` · `system` · `service-map`

### 핵심 파일
| 경로 | 역할 |
|------|------|
| `src/app/page.tsx` | 메인 SPA (탭 렌더링) |
| `src/app/api/[...path]/route.ts` | Flask 프록시 (SSE·스트리밍 특별처리, PUT/DELETE 포함, maxDuration=120) |
| `src/store/useMCStore.ts` | Zustand 전역 상태 (activeTab, pipelineRunning 등) |
| `src/hooks/useIntelData.ts` | SWR `/api/data` (SSE 트리거로 갱신) |
| `src/hooks/useSSE.ts` | EventSource 관리 → intel-data + process-status mutate |
| `src/hooks/useWealthData.ts` | SWR `/api/wealth` (1분 폴링) |
| `src/lib/api.ts` | fetcher 함수 모음 |
| `src/lib/format.ts` | `fmtKrw()`, `fmtPct()`, `pctColor()` |
| `src/lib/savedStrategies.ts` | 어드바이저 전략 저장/삭제/로드 API 유틸 |
| `src/types/api.ts` | Flask 응답 타입 (IntelData, PriceItem 등) |
| `src/types/advisor.ts` | InvestmentAsset, RiskLevel 등 |

### SWR 갱신 전략
| 키 | 갱신 방식 |
|----|---------|
| `intel-data` | 수동 + SSE 트리거 |
| `process-status` | 5초 폴링 + SSE 트리거 |
| `marcus-log` | 3초 폴링 (실행 중만) |
| `opportunities-*` | 5분 캐시 (dedupingInterval) |
| `/api/wealth` | 1분 폴링 |
| `solar-listings` | 5분 캐시 (dedupingInterval) |
| `analysis-history` | SWR 기본값 (포커스 시 재검증) |

### localStorage 키
| 키 | 내용 |
|----|------|
| `mc-active-tab` | 마지막 활성 탭 ID |
| `mc-advisor-settings` | capital, riskLevel, minusLoan, creditLoan, monthlySavings, portfolioMode |
| `solar_read_v1` | 읽은 태양광 매물 ID 집합 |
| `solar_starred_v1` | 즐겨찾기 태양광 매물 ID 집합 |

어드바이저 전략은 localStorage가 아닌 서버 DB(`advisor_strategies` 테이블)에 저장됨.

---

## gstack

For all web browsing, use the `/browse` skill from gstack. **Never use `mcp__claude-in-chrome__*` tools.**

Available skills:
- `/office-hours`, `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review`
- `/design-consultation`, `/review`, `/ship`, `/land-and-deploy`, `/canary`
- `/benchmark`, `/browse`, `/qa`, `/qa-only`, `/design-review`
- `/setup-browser-cookies`, `/setup-deploy`, `/retro`, `/investigate`
- `/document-release`, `/codex`, `/cso`, `/autoplan`
- `/careful`, `/freeze`, `/guard`, `/unfreeze`, `/gstack-upgrade`

---

## Deploy Configuration

- Platform: Docker Compose (self-hosted, Mac mini)
- Production URL: http://100.90.201.87:3000 (mc-web)
- API URL: http://100.90.201.87:8421 (Flask API)
- Merge method: merge
- Health check: `docker ps` + python urllib (curl 없음)

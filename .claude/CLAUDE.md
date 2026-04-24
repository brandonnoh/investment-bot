# CLAUDE.md

## 프로젝트 개요

개인 투자자를 위한 **기관급 금융 인텔리전스 엔진**.
수집/계산/저장은 이 엔진이, 해석/판단/전략/대화는 AI 에이전트(자비스/Marcus)가 담당.

### 3계층 아키텍처
- **수집 계층** `data/` — 다중 소스(Yahoo/Kiwoom/DART/Brave/RSS), 폴백, 이상값 감지
- **분석 계층** `analysis/` — 기술분석·포트폴리오·레짐·스크리닝·성과추적 (40개 모듈)
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

# 테스트 (43개 파일)
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
   ├─ fetch_prices()      → prices.json
   ├─ fetch_macro()       → macro.json
   ├─ fetch_news()        → news.json
   ├─ classify_regime()   → regime.json
   ├─ sector_intel()      → sector_scores.json
   ├─ fetch_fundamentals()→ fundamentals.json
   ├─ fetch_supply()      → supply_data.json
   ├─ fetch_universe_daily() → DB prices_daily
   └─ fetch_opportunities()  → opportunities.json
3. aggregate_daily() + maintain_db()
4. analyze_prices()      → price_analysis.json
   check_alerts()        → alerts.json
   run_screener()        → screener_results.json
   analyze_portfolio()   → portfolio_summary.json
5. _run_post_analysis()
   ├─ track_performance()     → performance_report.json
   ├─ run_self_correction()   → correction_notes.json
   ├─ run_proactive_alerts()  → proactive_alerts.json
   ├─ run_dynamic_holdings()  → holdings_proposal.json
   └─ run_simulation()        → simulation_report.json
6. validate_all_outputs() + save_engine_status() → engine_status.json
7. generate_daily()      → daily_report.md
8. [--weekly] generate_weekly() → cio-briefing.md
```

### 데이터 흐름

```
config.py (설정 SSoT)
    ↓
data/ → SQLite(history.db) + output/intel/*.json (이중 저장)
    ↓
analysis/ ← JSON 읽기 → 분석 결과 JSON 생성
    ↓
reports/ → daily_report.md, cio-briefing.md, closing_report.md
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
| `/api/events` | SSE 스트림 (intel/ 변경 감지 → 클라이언트 push) |
| `/api/analysis-history` | Marcus 분석 이력 목록 |
| `/api/analysis-history?date=YYYY-MM-DD` | 특정 날짜 상세 |
| `/api/wealth?days=60` | 전재산 (금융+비금융, 60일 이력) |
| `/api/logs?name=marcus&lines=80` | 로그 마지막 N줄 |
| `/api/opportunities?strategy=composite` | 발굴 종목 (전략별) |
| `/api/solar?limit=100` | 태양광 매물 |
| `/api/strategies` | 스크리너 전략 메타 |
| `/api/file?name=X.md` | 마크다운 파일 조회 |

### POST

| 엔드포인트 | 역할 |
|-----------|------|
| `/api/run-pipeline` | 파이프라인 백그라운드 실행 |
| `/api/run-marcus` | Marcus 백그라운드 실행 |
| `/api/refresh-prices` | 가격 새로고침 |
| `/api/wealth/assets` | 비금융 자산 추가 |
| `/api/investment-advice` | AI 투자 어드바이스 (동기) |
| `/api/investment-advice-stream` | AI 투자 어드바이스 (SSE 스트리밍) |

### PUT / DELETE

| 엔드포인트 | 역할 |
|-----------|------|
| `/api/wealth/assets/{id}` | 비금융 자산 수정 / 삭제 |

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

## 코드 규칙

- 모든 주석/docstring은 **한국어**
- 마크다운 리포트는 한국어 + 이모지
- 종목/지표 추가·수정은 **반드시 `config.py`만** 수정 (하드코딩 금지)
- HTTP 요청은 `urllib.request` 직접 사용 (외부 라이브러리 금지)
- 외부 패키지 추가 금지 (stdlib + pytest + ruff + yfinance만 허용)
- 시간대는 KST (`timezone(timedelta(hours=9))`)
- `sys.path.insert(0, ...)` 패턴으로 프로젝트 루트를 모듈 경로에 추가
- **`server.py`에서 내부 모듈 임포트는 반드시 모듈 전체 임포트** (`import web.api as api`). 함수 선택 임포트(`from web.api import ...`) 금지 — 새 함수 추가 시 임포트 목록 누락으로 런타임 NameError 반복 발생

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

---

## 환경 변수 (.env)

```bash
BRAVE_API_KEY=xxx        # 뉴스·기회 발굴 (Brave Search)
KIWOOM_APPKEY=xxx        # 키움증권 REST API (선택)
KIWOOM_SECRETKEY=xxx     # 키움증권 REST API (선택)
DISCORD_WEBHOOK_URL=xxx  # Discord 알림 웹훅
```

## ⚠️ Discord 전송 필수 규칙
- 긴급 투자 알림 → Discord 비서실: `--channel discord --to channel:1486905937225846956`
- 뉴스/일반 알림 → Discord 재테크 알림: `--channel discord --to channel:1486921732874047629`
- `--to` 빠지면 전송 실패 → 절대 빠뜨리지 말 것

## 주의사항
- `db/history.db`, `output/` — git 제외 (.gitignore)
- Yahoo Finance 과도한 요청 시 rate limit 주의 (10분 간격 권장)
- `.kiwoom_token.json` — 토큰 캐시 (git 제외)

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
│  /api/events → SSE 프록시                      │
└─────────────────────────┘                      ▼
                               ┌─────────────────────────┐
                               │  investment-bot :8421   │  Dockerfile (루트)
                               │  Flask + cron 스케줄러  │
                               └─────────────────────────┘
```

**GitHub push는 코드 백업용 — 자동 배포 없음. 항상 수동 smart-deploy.sh 실행.**

### 컨테이너 구조

| 컨테이너 | 포트 | 역할 |
|---------|------|------|
| `investment-bot` | 8421 | Flask API + 내부 cron 스케줄러 |
| `mc-web` | 3000 | Next.js standalone 프론트엔드 |

### 볼륨 마운트 (Python 소스 — restart만으로 반영)
`web/`, `analysis/`, `data/`, `reports/`, `scripts/`, `config.py`, `run_pipeline.py`

### HOST launchd 전부 비활성화. 스케줄은 Docker 내부 cron만 사용.

### 스케줄 (KST)

| 잡 | 스케줄 | 스크립트 |
|----|--------|---------|
| refresh_prices | 매 1분 | `scripts/refresh_prices.py` |
| alerts_watch | 매 5분 | `analysis/alerts_watch.py` |
| universe_daily | 평일 07:00 | `data/fetch_universe_daily.py` |
| marcus | 평일 05:30 | `scripts/run_marcus.py` |
| jarvis | 평일 07:30 | `scripts/run_jarvis.py` |
| pipeline | 평일 07:40 | `run_pipeline.py` |
| news | 평일 08:00 | `scripts/refresh_news.py` |
| refresh_solar | 매일 08:30, 19:00 | `scripts/refresh_solar.py` |
| monthly-deposit | 매월 1일 00:00 | `scripts/monthly_deposit_cron.py` |

---

## ⚠️ Next.js 배포 규칙 (docker cp 방식)

```bash
# 반드시 /. 형태로 — 없으면 static/static/ 중첩 경로 버그 발생
cd web-next && npm run build && cd ..
docker cp web-next/.next/standalone/. mc-web:/app/
docker cp web-next/.next/static/. mc-web:/app/.next/static/
docker restart mc-web
```

**smart-deploy.sh 사용 권장:**
```bash
bash .claude/skills/deploy/scripts/smart-deploy.sh auto  # 자동 감지
bash .claude/skills/deploy/scripts/smart-deploy.sh python  # Python만
bash .claude/skills/deploy/scripts/smart-deploy.sh web     # Next.js만
bash .claude/skills/deploy/scripts/smart-deploy.sh build   # Dockerfile 변경
```

---

## Next.js 프론트엔드 구조 (web-next/)

### 기술 스택
Next.js 16.2.4 · React 19 · TypeScript 5 · Tailwind CSS 4 · Zustand(상태) · SWR(데이터페칭) · Recharts(차트) · shadcn/ui · react-markdown

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
| `src/data/investment-assets.json` | 투자 자산 정의 (어드바이저용) |
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

### localStorage 키
| 키 | 내용 |
|----|------|
| `mc-active-tab` | 마지막 탭 |
| `mc-advisor-settings` | capital, leverageAmt, riskLevel |
| `mc-saved-strategies` | 저장된 AI 어드바이스 |

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
- Health check: `docker ps` + `docker exec investment-bot curl -sf http://localhost:8421/api/status`

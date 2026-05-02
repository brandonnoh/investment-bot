# Investment Bot 개발 로드맵

> 최종 업데이트: 2026-05-01  
> 기준: 실제 구현 코드 기반

---

## 완료된 기능 (구현 완료)

### 핵심 인프라

- [x] **3계층 아키텍처** — `data/` 수집 · `analysis/` 분석 · `web/` 서비스
- [x] **파이프라인 실행 순서** (`run_pipeline.py`) — init_db → 수집 → 집계 → 분석 → 후처리 → 리포트
- [x] **23개 DB 테이블** (`db/history.db`) — 원시/집계/SSoT/분석/이력 테이블
- [x] **DB 연결 팩토리** (`db/connection.py`) — WAL 모드 + busy_timeout=30초 통일
- [x] **Atomic JSON 쓰기** (`utils/json_io.py`) — 쓰기 중 truncated JSON 방지
- [x] **Docker Compose 아키텍처** — investment-bot:8421 + mc-web:3000, 헬스체크 포함
- [x] **Docker 내부 cron 스케줄러** — 17개 크론잡 (launchd 전면 제거)

### 데이터 수집 계층 (`data/`)

- [x] `fetch_prices.py` — 주가 수집 (네이버/Yahoo, 폴백 포함)
- [x] `fetch_macro.py` — VIX · 환율 · 유가 · 금리
- [x] `fetch_news.py` — RSS + Brave Search 뉴스 (DB SSoT 기반 종목 필터)
- [x] `fetch_fundamentals.py` — yfinance + DART + 네이버금융 PER/PBR
- [x] `fetch_supply.py` — Fear & Greed Index (Alternative.me) + KRX 수급
- [x] `fetch_opportunities.py` — value_screener 위임 (섹터 기반 스크리닝)
- [x] `fetch_universe_daily.py` — 일봉 사전 수집 (value_screener DB 스크리닝용)
- [x] `fetch_company_profiles.py` — 기업 설명 수집 (영문→한국어 자동 번역)
- [x] `fetch_dart_corp_codes.py` — DART 법인코드 월간 갱신
- [x] **태양광 매물 수집** — 9개 사이트 크롤러 (`fetch_solar_*.py`)

### 분석 계층 (`analysis/`) — 40개 모듈

- [x] `regime_classifier.py` — VIX·환율·유가 기반 시장 레짐 분류 + DB 이력 저장
- [x] `sector_intel.py` — 섹터 점수 계산 + DB 이력 저장
- [x] `composite_score.py` — 5팩터 복합 점수 (기술·펀더멘탈·수급·뉴스·12-1 모멘텀)
- [x] `value_screener.py` — 5개 전략 렌즈 (버핏·그레이엄·린치·그린블랫·퀀트)
- [x] `marcus_screener.py` — B+ 이상 통과 종목 30~70개 압축 (390KB→15KB)
- [x] `screener.py` + `screener_universe.py` — 코스피200 + S&P100 유니버스 스크리닝
- [x] `price_analysis.py` — MA·RSI·볼린저밴드 기술적 분석
- [x] `alerts.py` — 알림 감지 (알림 없으면 파일 삭제)
- [x] `alerts_watch.py` — 5분 주기 실시간 감시 → Discord 전송 (DB SSoT 기반)
- [x] `portfolio.py` — 포트폴리오 요약 + FX 손익
- [x] `performance_report.py` — 성과 추적 + 팩터 가중치 제안 + DB 이력 저장
- [x] `self_correction.py` — 자기 교정 + DB 이력 저장
- [x] `proactive_alerts.py` — 능동적 알림 생성
- [x] `dynamic_holdings.py` — 동적 보유 제안
- [x] `simulation.py` — 매매 시뮬레이션
- [x] `solar_alerts.py` — 신규 태양광 매물 Discord 알림
- [x] `universe_cache.py` — 유니버스 캐시 주간 갱신

### 서비스 계층 (`web/`)

- [x] **Flask API** — 18개 GET + 7개 POST + 3개 PUT/DELETE
- [x] **SSE 실시간 스트림** — `intel/` 변경 감지 → 클라이언트 push (큐 maxsize=100)
- [x] **보안 강화** — CORS ALLOWED_ORIGIN 환경변수, 보안 헤더, 로그 경로 순회 방지, 파라미터 검증
- [x] `api_history.py` — 4개 이력 조회 API (regime/sector/correction/performance)
- [x] `api_company.py` — 기업 상세 드로어 API
- [x] `api_advisor.py` — 어드바이저 전략 저장/조회 (DB)
- [x] `investment_advisor.py` — Anthropic API + Claude CLI 듀얼 모드 스트리밍
- [x] `portfolio_refresh.py` — 실시간 가격 반영 포트폴리오 갱신

### Next.js 프론트엔드 (`web-next/`)

- [x] **11개 탭** — overview · portfolio · marcus · discovery · wealth · solar · advisor · saved-strategies · alerts · system · service-map
- [x] **SSE 실시간 연결** — `useSSE.ts` → `intel-data` mutate 자동 갱신
- [x] **CompanyDrawer** — 기업 상세 드로어 (DART·네이버 데이터, 한국어 번역 설명)
- [x] **Marcus → 발굴 연동** — "발굴에서 보기 →" 버튼 + 종목 하이라이트 + 스크롤
- [x] **marcus_screener 통합** — B+ 풀 → 마커스 프롬프트 390KB→105KB 압축
- [x] **AI 어드바이저** — 전략 저장/조회 (서버 DB), AbortController 언마운트 처리
- [x] **태양광 탭** — 매물 카드 리스트 (즐겨찾기/읽음 처리)
- [x] **WealthSummary 타입** + `fmtAmt` 중복 제거 (`lib/format.ts` 통합)
- [x] `useWealthData.ts` 타입 강화

### 자동화 스크립트

- [x] `sync_to_r2.py` — Cloudflare R2 동기화 (평일 07:50)
- [x] `publish_blog.py` — Sanity 블로그 자동 발행 (평일 07:55)
- [x] `retranslate_descriptions.py` — 기업 설명 영문→한국어 재번역 (수동 실행)
- [x] `monthly_deposit_cron.py` — 월별 입금 자동 기록 (매월 1일)

### 운영

- [x] **Discord 알림 6종** — 긴급 투자 알림 + 뉴스/일반 (채널 구분)
- [x] **로그 로테이션** — 10MB 초과 자동 gzip + 7일 이상 삭제
- [x] **DB 유지보수** — 매주 일요일 purge + VACUUM + WAL 재설정
- [x] **파이프라인 에러 격리** — 단계별 독립 try/except, Graceful degradation

---

## 남은 태스크

### P2 — 품질 향상 (중기)

#### T-A: Atomic JSON 쓰기 전면 적용
**현황:** `utils/json_io.py` 생성 완료. `alerts_io.py`, `refresh_prices.py`에만 적용.  
**남은 작업:** `analysis/` 파이프라인 핵심 모듈에 전면 적용
- `analysis/regime_classifier.py` → `regime.json`
- `analysis/screener.py` → `screener_results.json`
- `analysis/price_analysis.py` → `price_analysis.json`
- `analysis/self_correction.py`, `simulation.py`, `dynamic_holdings.py` 등

#### T-B: CORS ALLOWED_ORIGIN 기본값 제한
**현황:** `web/server.py` 코드는 ALLOWED_ORIGIN 환경변수 참조로 수정 완료. 단 기본값이 `"*"` 이고 `.env`에 `ALLOWED_ORIGIN`이 미설정 상태.  
**남은 작업:** `.env`에 `ALLOWED_ORIGIN=http://100.90.201.87:3000` 추가

#### T-C: Discord 웹훅 URL .env 이전
**현황:** `.env`에 `DISCORD_WEBHOOK_URL`이 실제 URL로 설정돼 있어 동작 자체는 정상이나 URL이 .env 파일에 평문 저장됨 (git 제외 처리 확인 필요).  
**남은 작업:** `config.py`의 기본값 하드코딩 여부 최종 점검

#### T-D: 파이프라인 실패 Discord 알림
**현황:** `run_pipeline.py`는 단계별 에러 격리 완료. 단 `_notify_pipeline_failure()` 함수 미구현 — 실패 시 Discord 알림 없음.  
**남은 작업:** `_notify_pipeline_failure()` 함수 추가 + 핵심 단계에 적용

#### T-E: 기업 설명 한국어 재번역 크론 등록
**현황:** `scripts/retranslate_descriptions.py` 작성 완료. 현재 수동 실행만 가능.  
**남은 작업:** `crontab.docker`에 주간 스케줄 추가 (예: 매주 일요일 05:30)

### P3 — 장기 (1억+ 자산 규모 / 필요 시)

#### T-F: 백테스팅 엔진
- 과거 DB 데이터 기반 전략 검증 (Sharpe ratio, MDD)
- `backtest/` 폴더 신규 생성
- 현재: 미착수

#### T-G: 포트폴리오 최적화 (MVO)
- 마코위츠 평균-분산 최적화, 리스크 패리티
- 현재: 미착수 (scipy 사용 시 외부 패키지 예외 승인 필요)

#### T-H: Docker non-root 실행
- cron이 root 필요한 구조라 큰 리팩터링 필요
- 현재: 별도 계획 필요

---

## 현재 크론 스케줄 (17개)

| 스케줄 | 스크립트 |
|--------|---------|
| 매 1분 | `scripts/refresh_prices.py` |
| 매 1분 | Claude 크레덴셜 자동 동기화 |
| 매 5분 | `analysis/alerts_watch.py` |
| 평일 05:30 | `scripts/run_marcus.py` |
| 평일 07:30 | `scripts/run_jarvis.py` |
| 평일 07:40 | `run_pipeline.py` |
| 평일 07:50 | `scripts/sync_to_r2.py` |
| 평일 07:55 | `scripts/publish_blog.py` |
| 평일 08:00 | `scripts/refresh_news.py` |
| 평일 08:10 | `data/fetch_company_profiles.py` |
| 평일 16:00 | `reports/closing.py` |
| 매일 00:05 | 로그 로테이션 (gzip + 삭제) |
| 매일 08:30, 19:00 | `scripts/refresh_solar.py` |
| 매월 1일 00:00 | `scripts/monthly_deposit_cron.py` |
| 매월 1일 05:00 | `data/fetch_dart_corp_codes.py` |
| 매주 일요일 03:00 | `db/maintenance.py` |
| 매주 일요일 04:00 | `analysis/universe_cache.py` |

---

## 개발 시 주의사항

1. **DB 경로:** `from config import DB_PATH` 로 통일 (`db/history.db`)
2. **출력 경로:** `from config import OUTPUT_DIR` 로 통일 (`output/intel/`)
3. **시간대:** 모든 datetime은 KST (`timezone(timedelta(hours=9))`)
4. **JSON 쓰기:** `utils/json_io.write_json_atomic()` 사용 (새 모듈은 반드시 적용)
5. **DB 연결:** `db/connection.get_db_conn()` 사용 (raw `sqlite3.connect` 금지)
6. **새 분석 모듈 추가:** `web/api.py`의 `INTEL_FILES` 목록에 동시 추가 필수
7. **서버 임포트:** `web/server.py`에서 `import web.api as api` (선택 임포트 금지)

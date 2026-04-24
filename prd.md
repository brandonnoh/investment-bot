# PRD — Investment Intelligence Engine Phase 3

> 비전: 개인 투자자를 위한 기관급 금융 데이터 엔진
> 원칙: 수집/계산/저장 각 계층의 고품질 + 확장성 + 미래 자동매매 대비
>
> 참고: [CLAUDE.md](.claude/CLAUDE.md) | [ARCHITECTURE.md](ARCHITECTURE.md) | [AGENT_GUIDE.md](AGENT_GUIDE.md) | [JARVIS_INTEGRATION.md](JARVIS_INTEGRATION.md) | [tests.json](tests.json) | [LESSONS.md](LESSONS.md)

## 완료 기준
각 task는 다음을 모두 충족해야 [x] 처리:
- `python3 -m pytest tests/ -v` 통과
- `ruff check .` 경고 없음
- tests.json 해당 feature status → "passing"
- git commit 완료

---

## 🏗️ 1. 인프라 기반

- [x] **F01** 테스트 인프라 구축 — pytest 셋업, conftest.py, DB fixture, 전체 모듈 import 테스트

## 📐 2. 저장 계층 (Storage Layer) 고도화

- [x] **F02** DB 스키마 재설계 — prices_daily, macro_daily, portfolio_history 테이블 추가, 인덱스 최적화, 마이그레이션 안전
- [x] **F03** 일봉 자동 집계 — prices/macro 원시 데이터 → OHLCV 일봉 집계 모듈
- [x] **F04** DB 보존 정책 + 자동 정리 — 원시 3개월, 뉴스 1년 보존, VACUUM 자동화

## 🔬 3. 수집 계층 (Collection Layer) 강화

- [x] **F05** 수집 모듈 단위 테스트 — prices/macro/news API 모킹, 폴백, graceful degradation 검증
- [x] **F06** data_source 필드 — prices.json에 데이터 출처 (kiwoom/naver/yahoo/calculated) 명시
- [x] **F10** 에러 복구 강화 — HTTP 재시도 + 지수 백오프 + 서킷 브레이커 + 이상값 감지

## 📊 4. 분석 계층 (Analysis Layer) 구축

- [x] **F07** price_analysis.json — MA5/20/60, RSI, 52주 고저, 변동성, 추세, 지지/저항
- [x] **F08** portfolio_history — 일별 자산 스냅샷, 30일 수익률 추이
- [x] **F09** 환율 손익 분리 — 주식 손익 vs 환율 손익 분리, fx_pnl 별도 계산
- [x] **F13** 뉴스 감성 점수 — 한/영 키워드 기반 감성 분석 (stdlib만)

## 🔧 5. 코드 품질 + 안정성

- [x] **F11** JSON 스키마 검증 — output/intel/ 출력 파일 필수 필드 + 타입 검증
- [x] **F12** alerts.py 레거시 정리 — alerts_watch.py 통합, 중복 제거
- [x] **F14** engine_status.json — 엔진 상태 모니터링 (에러 횟수, 마지막 수집 시각, DB 용량)

## 📖 6. 문서 + 에이전트 인터페이스

- [x] **F15** 에이전트 가이드 최종 검증 + ERD — AGENT_GUIDE.md 실제 출력 일치 확인, DB ERD 동기화

## Phase 4 — AI 기반 능동적 종목 발굴

- [x] **F16** 종목 사전(ticker_master) — KRX/미국 종목 매핑 DB
- [x] **F17** fetch_opportunities.py — 키워드 기반 종목 발굴
- [x] **F18** 복합 점수 엔진 — 4팩터 Percentile Rank 스코어링
- [x] **F19** screener.py 고도화 — 복합 점수 통합 + 유니버스 확장
- [x] **F20** 뉴스 수집 목적 분리 — 모니터링 vs 발굴

## Phase 4.1 — 펀더멘탈 분석 + 전문 에이전트

- [x] **F21** 펀더멘탈 데이터 수집 — DART 재무제표 + Yahoo 재무 + fundamentals DB
- [x] **F22** 퀀트 스코어링 고도화 — 6팩터 복합 점수 (밸류/퀄리티/성장/타이밍/촉매/매크로)
- [x] **F23** 수급 데이터 수집 — KRX 외국인/기관 순매수 + Fear & Greed Index
- [x] **F24** 마커스 에이전트 설정 — 시니어 펀드매니저 전문 에이전트
- [x] **F25** 성과 추적 + 가중치 학습 — outcome 자동 기록, 월간 성적표, 팩터별 적중률

## Phase 5 — 자율 진화 완성 (Phase 2-3-4 완성)

- [x] **F26** Discovery Keywords Fallback — regime 기반 자동 fallback, is_keywords_fresh, ensure_fresh_keywords
- [x] **F27** 문맥 기반 감성 분석 — relevance_score 가중 평균 (aggregate_sentiment_by_ticker_weighted)
- [x] **F28** 자기 교정 시스템 — correction_notes.json 자동 생성
- [x] **F29** 포트폴리오 시뮬레이션 — simulation_report.json (가상 손익 계산)
- [x] **F30** 시장 국면 고도화 — confidence score + panic_signal 추가
- [x] **F31** 능동적 알림 — proactive_alerts.json (익절/손절 액션 알림)
- [x] **F32** 동적 종목 관리 — holdings_proposal.json (추가/제거 제안)

---

## 🔒 6. 시스템 강화 (Security & Hardening — 2026-04-24 감사 결과)

> 참조 계획: `docs/specs/plans/2026-04-24-system-hardening.md`
> 완료 기준: 구현 + tests.json passing + `docker restart investment-bot` (Python) 또는 `docker compose up -d --build` (인프라) 또는 `cd web-next && npm run build` (Next.js) 후 서비스 정상

### 🔐 보안
- [ ] **security-001**: config.py — Discord 웹훅 URL 토큰 하드코딩 기본값 제거
- [ ] **security-002**: server.py — 입력 검증 강화 (경로 순회 차단, int 파라미터 상한, body 크기 제한 10MB, AI rate limit 15초)
- [ ] **security-003**: server.py — CORS 와일드카드 제거 (ALLOWED_ORIGIN env), 보안 헤더 추가

### ⚙️ 서버
- [ ] **server-001**: server.py — SSE 큐 maxsize=100 설정 (dead client 메모리 누수 방지)
- [ ] **server-002**: web/investment_advisor.py — 스트리밍 중단 시 Claude CLI subprocess 종료 (finally cleanup)

### 🗄️ DB/데이터
- [ ] **db-001**: db/maintenance.py — VACUUM 후 WAL 모드 재설정 (journal_mode=WAL 복구)
- [ ] **db-002**: PORTFOLIO_LEGACY → DB SSoT 전환 (data/fetch_news.py, analysis/alerts_watch.py, reports/closing.py)
- [ ] **db-003**: db/connection.py 신설 — WAL + busy_timeout=30초 DB 연결 팩토리 (db/ssot.py, db/ssot_wealth.py, db/maintenance.py, db/aggregate.py, web/api.py 전환)

### 🔄 파이프라인
- [ ] **pipeline-001**: run_pipeline.py — 핵심 분석 단계 독립 try/except + 실패 시 Discord 웹훅 알림

### 📦 인프라
- [ ] **deploy-001**: utils/json_io.py 신설 + scripts/refresh_prices.py, analysis/alerts.py — atomic JSON 쓰기 적용
- [ ] **deploy-002**: scripts/run_jarvis.py — --dangerously-skip-permissions 제거 (root 컨테이너 호환, marcus 방식으로 통일)
- [ ] **deploy-003**: crontab.docker — 로그 로테이션 크론 + db/maintenance.py 주간 스케줄 등록
- [ ] **deploy-004**: docker-compose.yml — utils/ 볼륨 마운트 추가, healthcheck 설정, mc-web depends_on condition 강화

### 🎨 프론트엔드
- [ ] **ui-001**: web-next route.ts — SSE upstream 실패 에러 이벤트 전파, proxy try-catch 추가
- [ ] **ui-002**: AIAdvisorPanel.tsx — 컴포넌트 언마운트 시 진행 중인 fetch abort
- [ ] **ui-003**: useWealthData.ts WealthSummary 타입 추가, fmtAmt 중복 정의 lib/format.ts로 통합

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

- [ ] **F02** DB 스키마 재설계 — prices_daily, macro_daily, portfolio_history 테이블 추가, 인덱스 최적화, 마이그레이션 안전
- [ ] **F03** 일봉 자동 집계 — prices/macro 원시 데이터 → OHLCV 일봉 집계 모듈
- [ ] **F04** DB 보존 정책 + 자동 정리 — 원시 3개월, 뉴스 1년 보존, VACUUM 자동화

## 🔬 3. 수집 계층 (Collection Layer) 강화

- [ ] **F05** 수집 모듈 단위 테스트 — prices/macro/news API 모킹, 폴백, graceful degradation 검증
- [ ] **F06** data_source 필드 — prices.json에 데이터 출처 (kiwoom/naver/yahoo/calculated) 명시
- [ ] **F10** 에러 복구 강화 — HTTP 재시도 + 지수 백오프 + 서킷 브레이커 + 이상값 감지

## 📊 4. 분석 계층 (Analysis Layer) 구축

- [ ] **F07** price_analysis.json — MA5/20/60, RSI, 52주 고저, 변동성, 추세, 지지/저항
- [ ] **F08** portfolio_history — 일별 자산 스냅샷, 30일 수익률 추이
- [ ] **F09** 환율 손익 분리 — 주식 손익 vs 환율 손익 분리, fx_pnl 별도 계산
- [ ] **F13** 뉴스 감성 점수 — 한/영 키워드 기반 감성 분석 (stdlib만)

## 🔧 5. 코드 품질 + 안정성

- [ ] **F11** JSON 스키마 검증 — output/intel/ 출력 파일 필수 필드 + 타입 검증
- [ ] **F12** alerts.py 레거시 정리 — alerts_watch.py 통합, 중복 제거
- [ ] **F14** engine_status.json — 엔진 상태 모니터링 (에러 횟수, 마지막 수집 시각, DB 용량)

## 📖 6. 문서 + 에이전트 인터페이스

- [ ] **F15** 에이전트 가이드 최종 검증 + ERD — AGENT_GUIDE.md 실제 출력 일치 확인, DB ERD 동기화

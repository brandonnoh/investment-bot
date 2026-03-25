# PRD — Investment Bot Phase 3 태스크

> 참고: [CLAUDE.md](.claude/CLAUDE.md) | [ARCHITECTURE.md](ARCHITECTURE.md) | [JARVIS_INTEGRATION.md](JARVIS_INTEGRATION.md) | [tests.json](tests.json) | [LESSONS.md](LESSONS.md)

## 완료 기준
각 task는 다음을 모두 충족해야 [x] 처리:
- `python3 -m pytest tests/ -v` 통과
- `ruff check .` 경고 없음
- tests.json 해당 feature status → "passing"
- git commit 완료

---

## Phase 3 태스크 목록

### 🏗️ 인프라

- [ ] **F01** 테스트 인프라 구축 — tests/ 디렉토리, conftest.py, DB fixture, import 테스트
- [ ] **F02** fetch_prices 단위 테스트 — API 모킹, 폴백, 스키마 검증, graceful degradation
- [ ] **F03** fetch_macro 단위 테스트 — 지표별 모킹, 스키마 검증
- [ ] **F04** fetch_news 단위 테스트 — RSS 파싱, Brave 모킹, 중복 제거, 스키마 검증

### 📊 자비스 요청 기능 (JARVIS_INTEGRATION.md §6)

- [ ] **F05** price_analysis.json — MA5/MA20 이동평균, 52주 최고/최저, 변동성, 추세 판단
- [ ] **F06** portfolio_history 테이블 — 일별 총 손익 스냅샷, 수익률 추이
- [ ] **F07** data_source 필드 — prices.json에 데이터 출처 명시 (kiwoom/naver/yahoo/calculated)
- [ ] **F08** 환율 손익 분리 — USD 종목 매입환율 vs 현재환율, fx_pnl 별도 계산

### 🔧 코드 품질

- [ ] **F09** alerts.py 레거시 정리 — alerts_watch.py와 중복 제거, 호출 체인 정리
- [ ] **F10** 에러 복구 강화 — HTTP 재시도 + 지수 백오프, 공통 헬퍼
- [ ] **F11** JSON 스키마 검증 — output/intel/ 출력 파일 구조 검증
- [ ] **F12** 뉴스 감성 점수 — 키워드 기반 감성 분석 (stdlib만, 한/영 지원)

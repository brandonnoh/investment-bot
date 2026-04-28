# output/intel/ JSON → DB 마이그레이션 분석 (2026-04-24)

## 저장 형태 3계층 요약

### 1. SQLite DB (`db/history.db`) — 영구 저장
### 2. JSON 파일 (`output/intel/*.json`) — 파이프라인 중간 산출물 (매 실행마다 덮어씀)
### 3. localStorage (브라우저) — UI 상태만

---

## JSON 파일별 DB화 필요 여부

### 🔴 강력 추천 (완료)

| JSON | 이유 | 현재 문제 |
|------|------|----------|
| `regime.json` | 레짐이 언제 바뀌었는지 이력 없음 | 파이프라인 실행마다 덮어쓰여 과거 레짐 소실 |
| `performance_report.json` | 종목 발굴 성과(1주·1개월) 추적 데이터 | opportunities 테이블에 outcome 컬럼 있지만 집계 report는 누적 안 됨 |

### 🟡 추천 (완료)

| JSON | 이유 | 현재 문제 |
|------|------|----------|
| `sector_scores.json` | 섹터 로테이션 추이 추적 가치 있음 | 매일 덮어써서 에너지가 언제부터 강세였는지 볼 수 없음 |
| `correction_notes.json` | AI 자기교정 이력 — 어떤 팩터가 틀렸는지 학습 데이터 | 30일 누적이지만 파일 자체는 1개라 더 긴 이력 없음 |

### 🟢 DB화 불필요

| JSON | 이유 |
|------|------|
| `holdings_proposal.json` | holdings 테이블 기반 재계산. 이력보다 현재 추천이 중요 |
| `screener_results.json` | 핵심 데이터는 `opportunities` 테이블에 이미 저장 |
| `simulation_report.json` | 재계산 가능한 파생 데이터 |
| `proactive_alerts.json` | `alerts` 테이블이 있고 이건 집계본 |
| `price_analysis.json` | 재계산 가능 |
| `engine_status.json` | 운영 데이터, 이력 불필요 |
| `prices.json` / `macro.json` | 이미 `prices` / `macro` / `prices_daily` / `macro_daily` 테이블에 저장 |
| `news.json` | 이미 `news` 테이블에 저장 |
| `opportunities.json` | 이미 `opportunities` 테이블에 저장 |
| `fundamentals.json` | 이미 `fundamentals` 테이블에 저장 |

---

## 구현 결과

4개 이력 테이블 추가 및 dual-write 적용 완료.

| 테이블 | Writer | 조회 API |
|--------|--------|---------|
| `regime_history` | `analysis/regime_classifier.py` | `GET /api/regime-history?days=90` |
| `sector_scores_history` | `analysis/sector_intel.py` | `GET /api/sector-scores-history?days=90` |
| `correction_notes_history` | `analysis/self_correction.py` | `GET /api/correction-notes-history?limit=30` |
| `performance_report_history` | `analysis/performance_report.py` | `GET /api/performance-report-history?days=90` |

조회 함수 위치: `web/api_history.py`

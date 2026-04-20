# PRD — 섹터 인텔리전스 + 가치 스크리닝 기반 종목 발굴 재설계

## 개요
- 목표: 매크로·뉴스·레짐을 기반으로 유망 섹터를 예측하고, 해당 섹터 내 과매도·저평가 종목을 자동 발굴한다
- 범위: `analysis/`, `data/fetch_opportunities.py`, `run_pipeline.py`

## Phase 1 — 섹터 인텔리전스 레이어
- [ ] sector-map: 섹터 → 종목 매핑 + 매크로 신호 룰셋 정의
- [ ] sector-intel: macro.json + news.json + regime.json → sector_scores.json

## Phase 2 — 가치 스크리닝 레이어
- [ ] value-screener: 상위 섹터 종목에서 RSI 과매도 + PER/PBR 저평가 필터링
- [ ] opp-refactor: fetch_opportunities.py를 value_screener 기반으로 교체

## Phase 3 — 파이프라인 통합
- [ ] pipeline-wire: run_pipeline.py에 sector_intel + value_screener 단계 통합

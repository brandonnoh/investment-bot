# Investment Bot — 미해결 이슈 / 기술부채

> **최종 업데이트:** 2026-05-01  
> **기준:** 실제 코드 점검 결과

---

## 🟡 기술부채 — 운영 영향 있음

### ISSUE-10. Atomic JSON 쓰기 미적용 파일 다수

| 항목 | 내용 |
|------|------|
| **영향 범위** | 파이프라인 실행 중 읽기/쓰기 경쟁 (SSE 실시간 환경) |
| **현황** | `utils/json_io.write_json_atomic()` 유틸은 구현 완료. `alerts_io.py` · `refresh_prices.py`에만 적용 |
| **미적용 파일** | `analysis/regime_classifier.py` (regime.json) · `screener.py` (screener_results.json) · `price_analysis.py` · `self_correction.py` · `simulation.py` · `dynamic_holdings.py` 등 |
| **위험** | 파이프라인 실행 중 SSE 갱신으로 클라이언트가 truncated JSON 읽을 가능성 |
| **해결 방법** | 각 파일의 `json.dump` / `write_text` 호출을 `write_json_atomic()`으로 교체 |
| **관련 파일** | `utils/json_io.py`, `analysis/*.py` |

---

### ISSUE-11. CORS 와일드카드 기본값 미변경

| 항목 | 내용 |
|------|------|
| **영향 범위** | `web/server.py` CORS 정책 |
| **현황** | 코드는 `ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")` 로 환경변수 참조. 단 `.env`에 `ALLOWED_ORIGIN` 미설정 → 기본값 `"*"` 동작 중 |
| **해결 방법** | `.env`에 `ALLOWED_ORIGIN=http://100.90.201.87:3000` 추가 후 `docker restart investment-bot` |
| **관련 파일** | `web/server.py:37`, `.env` |

---

### ISSUE-12. 파이프라인 실패 Discord 알림 미구현

| 항목 | 내용 |
|------|------|
| **영향 범위** | `run_pipeline.py` 단계별 실패 감지 |
| **현황** | 단계별 독립 try/except 처리는 완료. 그러나 `_notify_pipeline_failure()` 함수 미구현 — 실패 시 Discord 알림 전송 불가 |
| **해결 방법** | `_notify_pipeline_failure(step, error)` 함수 추가 (`DISCORD_WEBHOOK_URL`로 알림 전송) |
| **관련 파일** | `run_pipeline.py` |

---

### ISSUE-13. 기업 설명 재번역 수동 실행만 가능

| 항목 | 내용 |
|------|------|
| **영향 범위** | `company_profiles` 테이블의 영문 description 한국어화 |
| **현황** | `scripts/retranslate_descriptions.py` 작성 완료. 크론에 미등록 — 수동 실행만 가능 |
| **해결 방법** | `crontab.docker`에 주간 스케줄 추가 (예: `30 5 * * 0 python3 scripts/retranslate_descriptions.py`) |
| **관련 파일** | `scripts/retranslate_descriptions.py`, `crontab.docker` |

---

## 🟢 데이터 축적 필요 (시간 경과로 자연 해결)

### ISSUE-07. 성과 추적 데이터 부족

| 항목 | 내용 |
|------|------|
| **영향 범위** | 성과 추적, 자기 교정 팩터 가중치 학습 |
| **현황** | `performance_report.py` · `self_correction.py` 구현 완료 + DB 이력 저장 정상 동작. 단 시스템 가동 초기라 1w/1m 성과 데이터가 충분하지 않음 |
| **해결** | 시간 경과로 자연 해결. 약 1개월 후부터 의미있는 팩터 학습 시작 |

---

## 📋 이슈 우선순위

| 순위 | 이슈 | 난이도 | 임팩트 |
|------|------|--------|--------|
| 1 | ISSUE-11 CORS 기본값 | 매우 쉬움 | 보안 |
| 2 | ISSUE-12 파이프라인 실패 알림 | 쉬움 | 운영 가시성 |
| 3 | ISSUE-13 재번역 크론 등록 | 매우 쉬움 | 자동화 |
| 4 | ISSUE-10 Atomic JSON 전면 적용 | 중간 | 안정성 |
| — | ISSUE-07 성과 추적 | 시간 필요 | — |

---

## 환경 변수 현황

| 변수 | 상태 | 비고 |
|------|------|------|
| `DISCORD_WEBHOOK_URL` | ✅ `.env` 등록 | 실제 웹훅 URL 설정됨 |
| `DART_API_KEY` | ✅ `.env` 등록 | 2026-04-03 발급 |
| `BRAVE_API_KEY` | ✅ `.env` 등록 | 뉴스·발굴 검색용 |
| `ANTHROPIC_API_KEY` | 선택 | 설정 시 Anthropic API 직접 호출, 없으면 Claude CLI |
| `ALLOWED_ORIGIN` | ❌ `.env` 미설정 | 기본값 `"*"` 동작 중 → ISSUE-11 |
| `KIWOOM_*` | ❌ 미설정 | 현재 미사용 |
| `R2_*` / `SANITY_*` | ✅ `.env` 등록 | sync_to_r2, publish_blog 동작 중 |

---

*이 문서는 해결된 이슈를 제거하고 현재 실제로 남아있는 항목만 유지합니다.*  
*이슈 해결 후 해당 항목을 삭제하거나 ROADMAP.md 완료 목록으로 이동하세요.*

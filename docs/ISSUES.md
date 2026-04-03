# Marcus Intelligence System — 미해결 이슈 목록

> **작성:** 마커스 (Marcus)  
> **최종 확인:** 2026-04-03  
> **파이프라인 실행 기준:** run_pipeline.py 직접 실행 결과

---

## 🔴 Critical — 핵심 팩터 미작동

### ✅ ISSUE-01. Yahoo Finance 펀더멘탈 401 Unauthorized — 해결 (2026-04-03)

| 항목 | 내용 |
|------|------|
| **영향 범위** | 미국 종목 전체 (TSLA, GOOGL, XOP, GS 등) |
| **증상** | `Yahoo Finance 호출 실패: HTTP Error 401: Unauthorized` |
| **결과** | fundamentals.json에서 미국 종목 PER/PBR/ROE = None |
| **원인** | Yahoo Finance quoteSummary API 인증 방식 변경 |
| **해결** | `yfinance>=0.2` 라이브러리로 교체 (`fetch_yahoo_financials` 전면 재작성) |
| **커밋** | `ff948d5` |

---

### ✅ ISSUE-02. DART 국내 펀더멘탈 파싱 오류 — 완전 해결 (2026-04-03)

| 항목 | 내용 |
|------|------|
| **영향 범위** | 삼성전자, 현대차, SK하이닉스 |
| **증상** | ROE=1005%, 부채비율=2966% 비정상값 + PER/PBR=None |
| **해결 1** | `_get_account(*names)` 계정과목명 fallback + 비정상값 필터링 (`ff948d5`) |
| **해결 2** | `fetch_naver_per_pbr()` 추가 — 네이버금융 API로 PER/PBR 보완 (`87ce088`) |
| **검증** | 삼성전자 PER=28.39, PBR=2.91 ✅ / 현대차 PER=13.3, PBR=1.07 ✅ |

---

### ✅ ISSUE-03. KRX 수급 데이터 400 Bad Request — 완전 해결 (2026-04-03)

| 항목 | 내용 |
|------|------|
| **영향 범위** | 전 보유 종목 외국인/기관 순매수 |
| **증상** | `HTTP Error 400: Bad Request` → 응답 본문 `LOGOUT` |
| **원인 1** | 주말/공휴일에 당일 날짜로 요청 |
| **원인 2** | KRX 사이트 세션 쿠키 미포함 (로그인 필요) |
| **해결 1** | `_latest_trading_date()` — 주말 → 직전 금요일 자동 보정 (`fbd2df6`) |
| **해결 2** | `CookieJar` + `build_opener` — 세션 쿠키 자동 획득 후 요청 (`87ce088`) |

---

### ✅ ISSUE-04. Fear & Greed Index 수집 실패 — 해결 (2026-04-03)

| 항목 | 내용 |
|------|------|
| **영향 범위** | 매크로 팩터 (macro_direction 계산) |
| **증상** | `Fear & Greed Index 수집 실패: HTTP Error 418` |
| **결과** | supply_data.json fear_greed = null |
| **원인** | CNN 직접 크롤링 차단됨 |
| **해결** | `https://api.alternative.me/fng/?limit=1` 로 교체. 테스트: `score=9, rating=Extreme Fear` 정상 수신 |
| **커밋** | `fbd2df6` |

---

### ✅ ISSUE-05. Brave Search 뉴스 0건 — 완전 해결 (2026-04-03)

| 항목 | 내용 |
|------|------|
| **영향 범위** | fetch_news.py Brave 뉴스 수집 |
| **증상** | `뉴스 수집 완료: RSS 91건, Brave 0건` |
| **원인 1** | `retry_request()`가 gzip 압축 응답 미처리 |
| **원인 2** | MACRO_KEYWORDS 전부 `method: "rss"` → Brave가 코드상 호출 자체가 안됨 |
| **해결 1** | `search_brave_news()` gzip 처리 추가 (`e740d2f`) |
| **해결 2** | `geopolitics`, `kr_politics` 키워드 그룹을 `method: "brave"` 로 전환 (`4f49c50`) |
| **검증** | "트럼프 관세" Brave 검색 2건 정상 수신 ✅ |

---

## 🟡 Warning — 품질 저하

### ✅ ISSUE-06. 시뮬레이션 매수가 null — 해결 (2026-04-03)

| 항목 | 내용 |
|------|------|
| **영향 범위** | simulation_report.json |
| **증상** | GS, SK하이닉스 `"error": "매수가 없음"` |
| **원인** | 종목 발굴 시 `price_at_discovery` 미저장 |
| **해결** | `run()` 내 DB 저장 직전 `fetch_yahoo_quote()`로 현재가 조회 후 `price_at_discovery` 설정. 실패해도 None으로 스킵 |
| **커밋** | `e740d2f` |

---

### ISSUE-07. 성과 추적 데이터 부족

| 항목 | 내용 |
|------|------|
| **영향 범위** | F25 성과 추적, F28 자기 교정 |
| **증상** | `성과 추적: 1w=0건, 1m=0건`, weak_factors/strong_factors 모두 비어있음 |
| **결과** | 팩터 가중치 자동 조정 미작동 (데이터 없어서 학습 불가) |
| **원인** | 시스템 가동 9일차, 성과 측정 최소 데이터 미달 |
| **해결** | 시간 경과로 자연 해결 (1개월 후부터 의미있는 학습 시작) |

---

### ISSUE-08. 능동적 알림 0건

| 항목 | 내용 |
|------|------|
| **영향 범위** | F31 proactive_alerts |
| **증상** | `능동적 알림: 0건 생성` |
| **결과** | 익절/손절 자동 알림 미발동 |
| **원인** | 임계값 조건 미충족 (정상 동작일 수 있음) |
| **확인 필요** | 임계값 설정이 적절한지 검토 (`config.py` → ALERT_CONFIG) |
| **관련 파일** | `analysis/proactive_alerts.py` |

---

### ✅ ISSUE-09. Marsh McLennan (MMC) 종목 404 — 확인 완료 (2026-04-03)

| 항목 | 내용 |
|------|------|
| **증상** | `Marsh McLennan (MMC): HTTP Error 404: Not Found` |
| **결과** | screener에서 MMC 데이터 수집 실패 (해당 실행만) |
| **원인** | Yahoo Finance `v8/finance/chart` 엔드포인트 간헐적 404 (티커 오류 아님) |
| **확인** | MMC는 NYSE 정규 티커 — 코드 변경 불필요. `analyze_ticker()`에서 이미 예외 처리됨 (실패 시 skip) |
| **조치** | 코드 변경 없음 — 기존 에러 처리 충분 |

---

## 📋 수정 우선순위

| 순위 | 이슈 | 난이도 | 임팩트 |
|------|------|--------|--------|
| 1 | ISSUE-04 Fear&Greed → Alternative.me | 쉬움 | 중 |
| 2 | ISSUE-03 KRX 수급 파라미터 수정 | 중간 | 높음 |
| 3 | ISSUE-01 yfinance 교체 | 쉬움 | 높음 |
| 4 | ISSUE-02 DART 파싱 수정 | 중간 | 높음 |
| 5 | ISSUE-05 Brave API 디버깅 | 쉬움 | 중 |
| 6 | ISSUE-06 price_at_discovery 수집 | 쉬움 | 중 |
| 7 | ISSUE-09 MMC 티커 수정 | 쉬움 | 낮음 |
| — | ISSUE-07 성과 추적 | 시간 필요 | — |
| — | ISSUE-08 알림 임계값 검토 | 검토 필요 | — |

---

## 🔧 환경 설정 현황

| 설정 | 상태 | 비고 |
|------|------|------|
| `DART_API_KEY` | ✅ `.env` 등록 | 2026-04-03 발급 |
| `BRAVE_API_KEY` | ✅ `.env` 등록 | 기존 |
| `KIWOOM_*` | ❌ 미설정 | 수급 API 연결 시 필요 |
| `.env` 자동 로드 | ✅ | `run_pipeline.py` 진입 시 자동 적용 |

---

*이 문서는 Claude Code로 개선 작업 시 참조하세요.*  
*이슈 해결 후 해당 항목에 ✅ 표시 및 해결일 기록.*

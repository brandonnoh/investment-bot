# progress.md — RALF 반복 진행 기록

> 각 RALF iteration 완료 시 기록합니다.

---

<!-- 형식:
## Iteration N — YYYY-MM-DD HH:MM
- **Task:** F0X — 기능 설명
- **변경 파일:** file1.py, file2.py
- **결과:** 성공/실패
- **메모:** 특이사항
-->

## Iteration 1 — 2026-03-25
- **Task:** F01 — 테스트 인프라 구축
- **변경 파일:** tests/conftest.py, tests/test_infra.py, tests/__init__.py, tests/fixtures/__init__.py, tests/fixtures/sample_prices.json, tests/fixtures/sample_macro.json, tests/fixtures/sample_news.json, requirements.txt
- **결과:** 성공 (32 tests passed)
- **메모:** pytest + ruff 설치, conftest.py에 인메모리 DB fixture + 샘플 데이터 fixture, 12개 기존 모듈 import 테스트 + DB CRUD 테스트 + 데이터 구조 검증 + config 테스트

## Iteration 2 — 2026-03-25
- **Task:** F02 — DB 스키마 재설계 — 다중 해상도 저장 체계
- **변경 파일:** db/init_db.py, tests/conftest.py, tests/test_f02_schema.py
- **결과:** 성공 (54 tests passed, F02 22개 + F01 32개)
- **메모:** init_db()에서 init_schema(conn) 분리하여 테스트/마이그레이션 유연성 확보. prices_daily/macro_daily/portfolio_history 신규 테이블, prices.data_source + news.sentiment 컬럼 추가, 유니크 인덱스, ALTER TABLE 기반 안전 마이그레이션. conftest.py를 init_schema() 호출로 단순화하여 스키마 중복 제거.

## Iteration 3 — 2026-03-25
- **Task:** F03 — 일봉 자동 집계 모듈
- **변경 파일:** db/aggregate.py, tests/test_f03_aggregate.py, run_pipeline.py
- **결과:** 성공 (71 tests passed, F03 17개 + F02 22개 + F01 32개)
- **메모:** prices→prices_daily OHLCV 집계 (open/high/low/close/volume), macro→macro_daily OHLC 집계, ON CONFLICT UPSERT로 중복 방지, target_date 파라미터로 특정 날짜만 집계 가능, run_pipeline.py에서 수집 후 분석 전 단계에 통합

## Iteration 4 — 2026-03-25
- **Task:** F04 — DB 보존 정책 + 자동 정리
- **변경 파일:** db/maintenance.py, config.py, run_pipeline.py, tests/test_f04_maintenance.py
- **결과:** 성공 (85 tests passed, F04 14개 + F03 17개 + F02 22개 + F01 32개)
- **메모:** config.py에 RETENTION_POLICY 추가 (raw_months=3, news_months=12). db/maintenance.py에서 보존 기간 초과 원시 데이터 삭제 시 집계 완료 여부를 확인하여 미집계 데이터 보호. 뉴스는 12개월 초과 시 삭제. VACUUM으로 용량 최적화. run_pipeline.py에서 집계 후 분석 전 단계에 통합.

## Iteration 5 — 2026-03-25
- **Task:** F05 — 수집 모듈 단위 테스트 (prices, macro, news)
- **변경 파일:** tests/test_f05_collectors.py
- **결과:** 성공 (125 tests passed, F05 40개 + 기존 85개)
- **메모:** fetch_prices: Yahoo/Naver API 모킹, 키움→네이버 폴백 검증, 금 현물 계산, 스키마 검증. fetch_macro: 네이버 지수/Yahoo 지표 모킹, 개별 실패 시 나머지 정상 수집. fetch_news: RSS XML 파싱, Brave 모킹, 중복 URL 제거, 관련도 스코어링. 공통: graceful degradation (일부 실패 시 에러 레코드 포함 반환).

## Iteration 6 — 2026-03-25
- **Task:** F07 — price_analysis.json 기술 분석 엔진
- **변경 파일:** analysis/price_analysis.py, tests/test_f07_price_analysis.py, run_pipeline.py
- **결과:** 성공 (165 tests passed, F07 29개 + 기존 136개)
- **메모:** 구현+테스트+파이프라인 통합이 이미 완료되어 있음을 확인. MA5/20/60 이동평균, RSI 14일, 52주 고저+현재 위치(%), 30일 변동성(연환산), 추세 판단(uptrend/downtrend/sideways)+지속일수, 지지/저항선 추정. config.py ANALYSIS_PARAMS 중앙 관리. 데이터 부족 시 graceful 처리(None 반환). 모든 acceptance criteria 충족.

## Iteration 7 — 2026-03-25
- **Task:** F08 — portfolio_history 일별 자산 스냅샷
- **변경 파일:** analysis/portfolio.py, tests/test_f08_portfolio_history.py
- **결과:** 성공 (178 tests passed, F08 13개 + 기존 165개)
- **메모:** save_snapshot() UPSERT로 일별 1행 저장 (ON CONFLICT(date)), load_history() 최근 N일 조회 (날짜 오름차순), _get_db_conn() 테스트 패치용 헬퍼, build_summary()에 history 파라미터 추가, run()에서 DB 스냅샷 자동 저장 + 이력 조회 + portfolio_summary.json에 30일 수익률 추이 포함. holdings_snapshot에 종목별 상세 JSON 저장.

## Iteration 8 — 2026-03-25
- **Task:** F09 — 환율 손익 분리 계산
- **변경 파일:** config.py, analysis/portfolio.py, data/fetch_prices.py, tests/test_f09_fx_pnl.py
- **결과:** 성공 (196 tests passed, F09 18개 + 기존 178개)
- **메모:** config.py PORTFOLIO에 USD 종목별 buy_fx_rate(매입 시점 환율) 추가. calculate_holdings에서 USD 종목 invested_krw를 매입환율 기반으로 계산, stock_pnl_krw = (현재가-평단)×수량×매입환율, fx_pnl_krw = 현재가×수량×(현재환율-매입환율), stock+fx=total 항등식 보장. build_summary에 총 fx_pnl_krw/stock_pnl_krw 합계 포함. save_snapshot에서 fx_pnl_krw 실제 저장. fetch_prices에서 buy_fx_rate를 prices.json에 전달. KRW 종목은 fx_pnl=0, stock_pnl=total_pnl.

## Iteration 9 — 2026-03-25
- **Task:** F10 — 에러 복구 강화 — HTTP 재시도 + 서킷 브레이커
- **변경 파일:** utils/http.py, utils/__init__.py, config.py, data/fetch_prices.py, data/fetch_macro.py, data/fetch_news.py, tests/test_f10_error_recovery.py
- **결과:** 성공 (228 tests passed, F10 32개 + 기존 196개)
- **메모:** utils/http.py 공통 모듈에 retry_request(지수 백오프 재시도), CircuitBreaker(closed/open/half_open 3상태 관리), validate_price_data(이상값 감지) 구현. 수집 모듈 3개(fetch_prices/macro/news)에서 retry_request와 validate_price_data import 연결. config.py에 HTTP_RETRY_CONFIG(max_retries=3, base_delay=1)와 CIRCUIT_BREAKER_CONFIG(failure_threshold=5, recovery_timeout=300) 중앙 관리. 테스트 32개: 재시도 로직 8개, 서킷 브레이커 8개, 이상값 감지 9개, config 통합 2개, fetch 통합 3개, 로깅 2개.

## Iteration 10 — 2026-03-25
- **Task:** F11 — JSON 출력 스키마 검증
- **변경 파일:** utils/schema.py, tests/test_f11_schema_validation.py, run_pipeline.py
- **결과:** 성공 (254 tests passed, F11 26개 + 기존 228개)
- **메모:** utils/schema.py에 SCHEMAS 딕셔너리로 6개 JSON 파일(prices/macro/news/portfolio_summary/alerts/price_analysis) 필수 필드+타입 정의. validate_json()으로 최상위 필드, 중첩 딕셔너리(total), 배열/딕셔너리 항목 검증. "number" 타입으로 int/float 모두 허용. error 항목 스킵(graceful degradation). validate_all_outputs()로 파일 시스템에서 JSON 읽어 일괄 검증. run_pipeline.py에서 분석 후 리포트 전 단계에 통합. 경고 로그만 기록, 파이프라인 중단 없음.

## Iteration 11 — 2026-03-25
- **Task:** F13 — 뉴스 감성 점수 (키워드 기반, stdlib)
- **변경 파일:** analysis/sentiment.py, data/fetch_news.py, utils/schema.py, tests/test_f13_sentiment.py, tests/test_f11_schema_validation.py
- **결과:** 성공 (286 tests passed, F13 32개 + 기존 254개)
- **메모:** 구현+테스트+파이프라인 통합이 이미 완료되어 있음을 확인. analysis/sentiment.py에 한/영 금융 키워드 사전(KO_POSITIVE/KO_NEGATIVE/EN_POSITIVE/EN_NEGATIVE 각 26~31개), calculate_sentiment(-1.0~1.0), analyze_news_sentiment 레코드 처리, save_sentiment_to_db DB 업데이트, aggregate_sentiment_by_ticker 종목별 평균. fetch_news.py run()에서 수집→감성분석→저장→DB업데이트 파이프라인 통합. news.json 스키마에 sentiment 필수 필드 추가로 F11 테스트 데이터 수정 필요했음. ruff 미사용 import 정리.

## Iteration 12 — 2026-03-25
- **Task:** F14 — engine_status.json 엔진 상태 모니터링
- **변경 파일:** utils/engine_status.py, tests/test_f14_engine_status.py, run_pipeline.py, utils/schema.py, tests/test_f11_schema_validation.py
- **결과:** 성공 (333 tests passed, F14 21개 + 기존 312개)
- **메모:** utils/engine_status.py에 EngineStatus 클래스(모듈별 success/item_count/error_count/last_run 기록), record_module_status(레코드 리스트 기반 자동 성공/실패 카운트), get_db_size_mb(DB 파일 용량), get_uptime_days(first_run 기반 연속 가동일), build_engine_status(pipeline_ok 판정 — fetch_prices/fetch_macro 핵심 모듈 실패 시 False), save_engine_status(JSON 저장). run_pipeline.py에서 수집 모듈 반환값을 record_module_status로 기록 후 스키마 검증 뒤 engine_status 저장. utils/schema.py에 engine_status.json 스키마 추가. F11 테스트에서 item_fields 없는 스키마(engine_status) 허용하도록 수정.

## Iteration 13 — 2026-03-25
- **Task:** F15 — 에이전트 가이드 최종 검증 + ERD 문서
- **변경 파일:** tests/test_f15_agent_guide.py, ARCHITECTURE.md, analysis/alerts.py, analysis/alerts_watch.py, analysis/screener.py, analysis/sentiment.py, data/fetch_gold_krx.py, data/realtime.py, db/aggregate.py, db/init_db.py, db/maintenance.py, reports/closing.py, reports/daily.py, reports/weekly.py, scripts/read_news.py, tests/test_f02_schema.py, tests/test_f09_fx_pnl.py, tests/test_infra.py, utils/engine_status.py, utils/http.py
- **결과:** 성공 (362 tests passed, F15 29개 + 기존 333개)
- **메모:** AGENT_GUIDE.md/ARCHITECTURE.md/JARVIS_INTEGRATION.md의 JSON 예시가 실제 utils/schema.py 스키마와 일치하는지 자동 검증(8개 테스트). DB 쿼리 예시가 실제 스키마에서 실행 가능한지 검증(5개). ERD 테이블/컬럼 일치 검증(5개). JARVIS_INTEGRATION.md 동기화 검증(5개). ARCHITECTURE.md 정확성 검증(6개). ARCHITECTURE.md의 portfolio_summary.json 예시를 실제 구조(exchange_rate+total nested 구조, sectors 배열, risk 필드명)에 맞게 수정. ruff 기존 경고 9개 정리(미사용 import 4개, 모호 변수명, lambda→def, 미사용 변수).

## Iteration 14 — 2026-03-26
- **Task:** F22 — 퀀트 스코어링 고도화 — 6팩터 복합 점수
- **변경 파일:** analysis/composite_score.py, config.py, db/init_db.py, tests/test_f22_quant_scoring.py
- **결과:** 성공 (459 tests passed, F22 23개 + 기존 436개)
- **메모:** composite_score.py에 6팩터 확장: calculate_value_score(PER/PBR 역순 percentile), calculate_quality_score(ROE/부채비율역순/FCF), calculate_growth_score(매출성장률/EPS성장률), calculate_composite_score_v2 6팩터 가중 합산. 기존 calculate_composite_score 4팩터 하위 호환 유지 (레거시 균등 가중치). config.py에 6팩터 가중치(value 0.20/quality 0.20/growth 0.15/timing 0.20/catalyst 0.10/macro 0.15). db/init_db.py에서 opportunities 테이블에 score_value/score_quality/score_growth 마이그레이션 컬럼 추가. build_universe_stats(펀더멘탈→유니버스 통계), calculate_eps_growth(EPS 성장률) 헬퍼 함수.

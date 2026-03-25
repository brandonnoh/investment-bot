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

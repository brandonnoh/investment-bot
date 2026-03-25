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

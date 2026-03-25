---
name: implement-next
description: tests.json에서 다음 eligible 기능을 선택하여 TDD로 구현
---

# implement-next

tests.json을 읽고 다음 규칙에 따라 구현할 기능을 선택하세요:

## 기능 선택
1. `status`가 `"failing"`인 기능만 대상
2. `depends_on`의 모든 기능이 `"passing"`이어야 함
3. 위 조건 중 `priority`가 가장 낮은 것 선택

## 워크플로우
1. CLAUDE.md, LESSONS.md, ARCHITECTURE.md, JARVIS_INTEGRATION.md 읽기
2. acceptance_criteria 확인
3. **테스트 먼저 작성 (TDD)** — tests/ 디렉토리에 pytest 테스트
4. 구현 코드 작성 (stdlib만 사용, config.py 중앙 관리)
5. `python3 -m pytest tests/ -v` 통과 확인
6. 통과하면: tests.json → passing, prd.md → [x], git commit
7. 실패 3회 시: LESSONS.md에 교훈 기록, 다른 접근법으로 재시도

## 주의사항
- 외부 패키지 추가 금지 (stdlib + pytest만)
- output/intel/ 파일 구조 변경 시 JARVIS_INTEGRATION.md도 업데이트
- 모든 모듈은 run() 함수 진입점 유지

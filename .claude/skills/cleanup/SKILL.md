---
name: cleanup
description: 코드베이스 전체 품질 점검 및 정리
---

# cleanup

## 체크리스트
1. ruff check로 린트 에러 전부 수정
2. 사용하지 않는 import/변수/함수 제거
3. 300줄 초과 파일 분리 검토
4. TODO 주석 확인 및 해결
5. alerts.py (레거시) vs alerts_watch.py 중복 코드 정리
6. CLAUDE.md와 실제 코드 구조 일치 확인
7. `python3 -m pytest tests/ -v` 전체 통과 확인
8. `git commit -m "refactor: 코드 품질 정리"`

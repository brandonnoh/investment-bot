---
globs: "tests/**/*.py"
---

# 테스트 규칙

- pytest 사용
- 테스트 파일명: test_{모듈명}.py
- 함수명: test_{기능}_{시나리오} 형식
- AAA 패턴: Arrange → Act → Assert
- 외부 API 호출은 unittest.mock으로 모킹
- DB 테스트는 :memory: SQLite 사용
- 테스트 데이터는 fixtures/ 디렉토리에 JSON으로 관리
- config.py의 실제 포트폴리오 데이터를 테스트에 하드코딩 금지

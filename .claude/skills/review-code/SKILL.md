---
name: review-code
description: 현재 브랜치 변경사항을 CLAUDE.md 컨벤션 기준으로 리뷰
---

# review-code

`git diff main...HEAD`로 변경사항을 리뷰합니다.

## 검토 관점
- CLAUDE.md 코딩 컨벤션 위반 (한국어 주석, config.py 중앙 관리 등)
- 아키텍처 위반 (모듈 간 직접 import, DB 직접 접근 등)
- 외부 패키지 사용 여부 (stdlib 전용 원칙)
- output/intel/ 인터페이스 변경 시 JARVIS_INTEGRATION.md 동기화
- Graceful degradation 패턴 준수
- 보안 이슈 (API 키 하드코딩, SQL 인젝션 등)

## 결과 분류
- 🔴 CRITICAL: 반드시 수정
- 🟡 WARNING: 수정 권장
- 🔵 INFO: 개선 제안

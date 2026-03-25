---
globs: "**/*.py"
---

# Python 코딩 규칙

- 모든 주석/docstring은 한국어로 작성
- f-string 사용 (format(), % 금지)
- 함수 파라미터 최대 5개
- 파일 300줄 초과 시 모듈 분리 검토
- 종목/지표 추가·수정은 반드시 config.py만 수정 (하드코딩 금지)
- HTTP 요청은 urllib.request 사용 (requests 라이브러리 금지)
- 시간대는 KST (timezone(timedelta(hours=9)))
- 외부 패키지 추가 금지 (stdlib만 사용)
- 모든 수집 모듈은 run() 함수를 진입점으로 노출
- Graceful degradation: 개별 항목 실패 시 로깅 후 계속 진행

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요
AI 에이전트(자비스/OpenClaw)가 읽을 투자 데이터 수집/분석 파이프라인.
프로그램이 정확한 데이터를 처리하고, AI는 해석/판단/대화에 집중하는 구조.

## 빌드 & 테스트 명령어
```bash
# 전체 파이프라인
python3 run_pipeline.py

# 개별 모듈 (각각 독립 실행 가능)
python3 data/fetch_prices.py
python3 data/fetch_macro.py
python3 data/fetch_news.py
python3 analysis/alerts.py
python3 analysis/alerts_watch.py
python3 analysis/screener.py
python3 analysis/portfolio.py
python3 reports/daily.py
python3 reports/weekly.py
python3 reports/closing.py

# 테스트
python3 -m pytest tests/ -v

# 린트
ruff check .
ruff format --check .

# 의존성 설치
pip3 install -r requirements.txt
```

## 아키텍처

상세 구조: [ARCHITECTURE.md](../ARCHITECTURE.md)
자비스 연동 명세: [JARVIS_INTEGRATION.md](../JARVIS_INTEGRATION.md)

### 데이터 흐름
```
config.py (포트폴리오/지표 정의)
    ↓
수집 (data/) → SQLite DB + JSON 파일 (이중 저장)
    ↓
분석 (analysis/) ← JSON 파일 → alerts/screener/portfolio
    ↓
리포트 (reports/) ← JSON 파일 → daily/weekly/closing .md
    ↓
output/intel/ → 자비스가 읽는 유일한 인터페이스
```

### 핵심 설계 패턴
- **모든 모듈은 `run()` 함수**를 진입점으로 노출. `run_pipeline.py`가 순서대로 호출
- **이중 저장**: SQLite(`db/history.db`) + JSON(`output/intel/`) 동시 저장
- **JSON이 모듈 간 인터페이스**: 분석/리포트 모듈은 DB가 아닌 JSON을 읽음
- **`output/intel/`이 자비스와의 유일한 인터페이스**
- **Graceful degradation**: 개별 실패 시 로깅 후 계속 진행, 파이프라인 중단 금지
- **alerts.json은 알림 있을 때만 생성**, 없으면 삭제

## 코드 규칙

- 모든 주석/docstring은 **한국어**
- 마크다운 리포트는 한국어 + 이모지
- 종목/지표 추가·수정은 **반드시 `config.py`만** 수정 (하드코딩 금지)
- HTTP 요청은 `urllib.request` 직접 사용 (외부 라이브러리 금지)
- 외부 패키지 추가 금지 (stdlib + pytest만 허용)
- 시간대는 KST (`timezone(timedelta(hours=9))`)
- `sys.path.insert(0, ...)` 패턴으로 프로젝트 루트를 모듈 경로에 추가

## 현재 개발 단계

**Phase 1 완료**: config, fetch_prices, fetch_macro, alerts, daily report, pipeline runner
**Phase 2 완료**: fetch_news (RSS+Brave), screener, portfolio, weekly report, Kiwoom API
**Phase 2.5 완료**: alerts_watch (실시간), closing report, realtime.py, 시스템 이벤트 트리거
**Phase 3 (진행 중)**: 기술 분석(price_analysis), 포트폴리오 이력, 뉴스 감성, 환율 손익

## DB 스키마 (db/init_db.py)
4개 테이블: `prices`, `macro`, `news`, `alerts`
- `prices`: ticker, name, price, prev_close, change_pct, volume, timestamp, market
- `macro`: indicator, value, change_pct, timestamp
- `news`: title, summary, source, url, published_at, relevance_score, tickers, category
- `alerts`: level, event_type, ticker, message, value, threshold, triggered_at, notified

## 환경 변수
```bash
BRAVE_API_KEY=xxx        # 뉴스 수집 (Brave Search)
KIWOOM_APPKEY=xxx        # 키움증권 REST API (선택)
KIWOOM_SECRETKEY=xxx     # 키움증권 REST API (선택)
```

## ⚠️ 텔레그램 전송 필수 규칙
- OpenClaw 크론잡에서 텔레그램 전송 시 **반드시 `--to 2111337920` 명시**
- `--announce --channel telegram --to 2111337920` 세트로 항상 같이 써야 함
- `--to` 빠지면 전송 실패 → 절대 빠뜨리지 말 것

## 주의사항
- `db/history.db`, `output/` — git 제외 (.gitignore)
- Yahoo Finance 과도한 요청 시 rate limit 주의 (10분 간격 권장)
- `.kiwoom_token.json` — 토큰 캐시 (git 제외)

## RALF 자율 개발 워크플로우

1. `tests.json`에서 다음 eligible 기능 선택 (failing + 의존성 충족 + 최소 priority)
2. 테스트 먼저 작성 (TDD)
3. 구현 → `python3 -m pytest tests/ -v` 통과 확인
4. 통과 시: tests.json → passing, prd.md → [x], git commit
5. 실패 시: LESSONS.md에 교훈 기록

참고 파일:
- `prd.md` — 태스크 체크리스트
- `tests.json` — 기능 목록 + 수락 기준
- `ARCHITECTURE.md` — 시스템 구조
- `JARVIS_INTEGRATION.md` — 자비스 연동 명세
- `LESSONS.md` — 학습된 교훈
- `progress.md` — 반복 진행 기록

## gstack

For all web browsing, use the `/browse` skill from gstack. **Never use `mcp__claude-in-chrome__*` tools.**

Available skills:
- `/office-hours`, `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review`
- `/design-consultation`, `/review`, `/ship`, `/land-and-deploy`, `/canary`
- `/benchmark`, `/browse`, `/qa`, `/qa-only`, `/design-review`
- `/setup-browser-cookies`, `/setup-deploy`, `/retro`, `/investigate`
- `/document-release`, `/codex`, `/cso`, `/autoplan`
- `/careful`, `/freeze`, `/guard`, `/unfreeze`, `/gstack-upgrade`

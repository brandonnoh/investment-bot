# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요
AI 에이전트(자비스/OpenClaw)가 읽을 투자 데이터 수집/분석 파이프라인.
프로그램이 정확한 데이터를 처리하고, AI는 해석/판단/대화에 집중하는 구조.

## 실행 명령어
```bash
# 전체 파이프라인 (DB초기화 → 주가수집 → 매크로수집 → 알림감지 → 리포트생성)
python3 run_pipeline.py

# 개별 모듈 (각각 독립 실행 가능)
python3 data/fetch_prices.py
python3 data/fetch_macro.py
python3 analysis/alerts.py
python3 reports/daily.py

# 의존성 설치
pip3 install -r requirements.txt
```

## 아키텍처

### 데이터 흐름
```
config.py (포트폴리오/지표 정의)
    ↓
Yahoo Finance API → fetch_prices.py → prices 테이블 + prices.json
Yahoo Finance API → fetch_macro.py  → macro 테이블 + macro.json
    ↓
alerts.py ← prices.json + macro.json → alerts 테이블 + alerts.json (알림 있을 때만)
    ↓
daily.py ← prices.json + macro.json + alerts.json → daily_report.md
```

### 핵심 설계 패턴
- **모든 모듈은 `run()` 함수**를 진입점으로 노출. `run_pipeline.py`가 순서대로 호출
- **이중 저장**: 모든 수집 데이터는 SQLite(`db/history.db`)와 JSON(`output/intel/`)에 동시 저장
- **JSON이 모듈 간 인터페이스**: `alerts.py`와 `daily.py`는 DB가 아닌 `output/intel/*.json`을 읽음
- **`output/intel/`이 자비스(AI)와의 유일한 인터페이스** — 자비스는 이 폴더만 읽음
- **Graceful degradation**: 개별 종목/지표 실패 시 에러 기록 후 나머지 계속 수집. 파이프라인 중단 금지
- **alerts.json은 알림 있을 때만 생성**, 없으면 기존 파일 삭제 (자비스가 파일 존재 여부로 알림 판단)

### 자비스 연동 스케줄
- 05:00 `run_pipeline.py` 실행 → 05:30 `daily_report.md` 분석 → 07:30 텔레그램 전송
- `alerts.json` 존재 시 즉시 텔레그램 전송

## 코드 규칙

- 모든 주석/docstring은 **한국어**
- 마크다운 리포트는 한국어 + 이모지
- 종목/지표 추가·수정은 **반드시 `config.py`만** 수정 (다른 파일에 하드코딩 금지)
- Yahoo Finance API는 `urllib.request` 직접 사용 (yfinance 라이브러리 아님)
- 시간대는 KST (`timezone(timedelta(hours=9))`)
- `sys.path.insert(0, ...)` 패턴으로 프로젝트 루트를 모듈 경로에 추가

## 현재 개발 단계

**Phase 1 완료**: config, fetch_prices, fetch_macro, alerts, daily report, pipeline runner

**Phase 2 (다음)**: fetch_news (Brave Search API), screener (종목 발굴), portfolio (리스크/리밸런싱), weekly report

**Phase 3**: 백테스트, 차트 이미지, 증권사 API 자동매매

## DB 스키마 (db/init_db.py)
4개 테이블: `prices`, `macro`, `news` (Phase 2), `alerts`
- `prices`: ticker, name, price, prev_close, change_pct, volume, timestamp, market
- `macro`: indicator, value, change_pct, timestamp
- `alerts`: level (RED/YELLOW/GREEN), event_type, ticker, message, value, threshold, triggered_at, notified

## 환경 변수
```bash
BRAVE_API_KEY=xxx   # Phase 2 뉴스 수집용
```

## 주의사항
- `db/history.db`, `output/` — git 제외 (.gitignore)
- Yahoo Finance 과도한 요청 시 rate limit 주의 (10분 간격 권장)

## gstack

For all web browsing, use the `/browse` skill from gstack. **Never use `mcp__claude-in-chrome__*` tools.**

Available skills:
- `/office-hours`, `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review`
- `/design-consultation`, `/review`, `/ship`, `/land-and-deploy`, `/canary`
- `/benchmark`, `/browse`, `/qa`, `/qa-only`, `/design-review`
- `/setup-browser-cookies`, `/setup-deploy`, `/retro`, `/investigate`
- `/document-release`, `/codex`, `/cso`, `/autoplan`
- `/careful`, `/freeze`, `/guard`, `/unfreeze`, `/gstack-upgrade`

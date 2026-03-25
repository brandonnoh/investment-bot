# 자비스(Jarvis) ↔ Investment Bot 상호작용 명세

> 작성: 자비스 | 2026-03-25
> 목적: investment-bot 고도화 시 참고할 AI-프로그램 경계 및 데이터 계약 문서

---

## 1. 역할 분리 원칙

```
investment-bot (Python 프로그램)
  → 데이터 수집 / 저장 / 계산 / 알림 트리거
  → AI 없음, 토큰 소모 없음
  → crontab이 자동 실행

자비스 (OpenClaw AI 에이전트)
  → 데이터 해석 / 판단 / 전략 / 대화
  → investment-bot이 만든 파일을 읽고 분석
  → 텔레그램으로 브리핑/알림 전송
```

---

## 2. 자비스가 읽는 파일들

### 📁 output/intel/ — 메인 인터페이스

| 파일 | 생성 주체 | 생성 시점 | 자비스 활용 |
|------|---------|---------|-----------|
| `prices.json` | fetch_prices.py | 장 중 10분마다 | 현재가 + data_source 참조 |
| `macro.json` | fetch_macro.py | 장 중 10분마다 | 매크로 지표 참조 |
| `news.json` | fetch_news.py | 하루 5회 | 뉴스 컨텍스트 + 감성 점수 |
| `price_analysis.json` | price_analysis.py | 장마감 후 | 기술 분석 (MA, RSI, 추세) |
| `portfolio_summary.json` | portfolio.py | 05:00 + 장마감 | 포트폴리오 손익 + 환율 손익 |
| `engine_status.json` | run_pipeline.py | 매 수집 시 | 데이터 신뢰성 판단 |
| `daily_report.md` | daily.py | 05:00 | 05:30 분석 파이프라인에서 읽기 |
| `closing_report.md` | closing.py | 15:40 | 16:00 장 마감 리포트에서 읽기 |
| `screener.md` | screener.py | 05:00 | 종목 발굴 결과 참조 |
| `weekly_report.md` | weekly.py | 월 04:00 | 주간 리포트에서 읽기 |

### ⚡ alerts.json — 긴급 알림 트리거

```json
{
  "triggered_at": "2026-03-24T15:02:00+09:00",
  "count": 1,
  "alerts": [
    {
      "level": "RED",
      "event_type": "stock_drop",
      "ticker": "005930.KS",
      "message": "🔴 긴급: 삼성전자 -5.72% 급락 (현재가: 178,000.00)",
      "value": -5.72,
      "threshold": -5.0
    }
  ]
}
```

> 알림이 없으면 alerts.json 파일 자체가 삭제됨. 파일 존재 = 알림 있음.

**자비스 동작:** alerts_watch.py가 `openclaw cron add --at 1m` 으로 즉시 텔레그램 전송 크론잡 생성

---

## 3. 자비스가 실행하는 스크립트

### data/realtime.py
- **목적:** 크론잡 프롬프트에서 직접 호출해 그 순간의 실시간 주가 획득
- **출력:** stdout 마크다운 (파일 저장 없음)
- **활용 시점:** 05:30 분석, 07:30 모닝 브리핑, 16:00 마감 리포트

### scripts/read_news.py
- **목적:** DB news 테이블을 카테고리별로 읽어 마크다운 출력
- **출력:** stdout (파일 저장 없음)
- **활용 시점:** 05:30 분석 파이프라인에서 뉴스 컨텍스트 획득

---

## 4. 자비스 크론잡 스케줄

| 시간 (KST) | 크론잡 이름 | 읽는 파일 | 실행 스크립트 | 출력 |
|-----------|-----------|---------|------------|------|
| 05:30 | 투자팀 분석 파이프라인 | daily_report.md, news.json | realtime.py, read_news.py | cio-briefing.md 저장 |
| 07:30 | 모닝 브리핑 | cio-briefing.md | realtime.py | 텔레그램 전송 |
| 16:00 | 장 마감 리포트 | closing_report.md | realtime.py | 텔레그램 전송 |
| 즉시 | 긴급 알림 | (alerts_watch.py가 직접 트리거) | — | 텔레그램 전송 |

---

## 5. 자비스가 생성하는 파일

| 파일 | 생성 시점 | 내용 |
|------|---------|------|
| `~/.openclaw/workspace/intel/cio-briefing.md` | 05:30 | 매크로+전략+종목발굴 종합 CIO 보고서 |
| `~/.openclaw/workspace/intel/pending_emails.md` | 새 메일 도착 시 | 나중에 읽을 메일 목록 |

---

## 6. 고도화 요청사항 — 구현 완료 현황

> Phase 3에서 아래 요청사항이 모두 구현 완료됨.

#### 6-1. ✅ 주가 기술 분석 (F07)
- `output/intel/price_analysis.json` — MA5/20/60, RSI 14일, 52주 고저, 변동성, 추세, 지지/저항
- `analysis/price_analysis.py` 모듈, prices_daily 기반 계산

#### 6-2. ✅ 뉴스 감성 점수 (F13)
- `analysis/sentiment.py` — 한/영 금융 키워드 사전 기반 감성 분석 (-1.0 ~ 1.0)
- `news` 테이블 `sentiment` 컬럼, `news.json`에 `sentiment` + `ticker_sentiment` 포함

#### 6-3. ✅ 포트폴리오 이력 (F08)
- `portfolio_history` 테이블 — 일별 자산 스냅샷 UPSERT
- `portfolio_summary.json`의 `history` 배열에 최근 30일 수익률 추이 포함

#### 6-4. ✅ 금 현물 데이터 소스 명시 (F06)
- `prices.json`에 `data_source` 필드 (kiwoom/naver/yahoo/calculated)
- 금 현물 장외 시간: `data_source="calculated"`, `calc_method="GC=F × KRW=X ÷ 31.1035"`

#### 6-5. ✅ 환율 손익 분리 (F09)
- `config.py` PORTFOLIO에 `buy_fx_rate` (매입 시점 환율) 추가
- `portfolio_summary.json`의 `total.stock_pnl_krw` / `total.fx_pnl_krw` 분리
- `stock_pnl + fx_pnl = total_pnl` 항등식 보장

---

## 7. alerts_watch.py 임계값 (config.py 참조)

```python
ALERT_THRESHOLDS = {
    "stock_drop":     {"threshold": -5.0, "level": "RED"},      # 종목 급락 (%)
    "stock_surge":    {"threshold": 5.0, "level": "GREEN"},     # 종목 급등 (%)
    "kospi_drop":     {"threshold": -3.0, "level": "RED"},      # 코스피 폭락 (%)
    "usd_krw_high":   {"threshold": 1550, "level": "RED"},      # 환율 급등 (원)
    "oil_surge":      {"threshold": 5.0, "level": "YELLOW"},    # 유가 급등 (%)
    "gold_swing":     {"threshold": 3.0, "level": "YELLOW"},    # 금 급변 (%)
    "vix_high":       {"threshold": 30.0, "level": "YELLOW"},   # VIX 급등
    "portfolio_loss": {"threshold": -10.0, "level": "RED"},     # 포트폴리오 전체 손실 (%)
}
```

---

## 8. 데이터 소스 현황

| 종목/지표 | 소스 | 방식 | 비용 |
|---------|------|------|------|
| 삼성전자, 현대차, TIGER ETF | 키움증권 REST (ka10007) | 장 중 실시간 | 무료 |
| 금 현물 | 키움증권 REST (ka50100) | 장 중 실시간 | 무료 |
| 테슬라, 알파벳, XOP | Yahoo Finance | 실시간 | 무료 |
| 코스피, 코스닥 | 네이버 금융 | 실시간 | 무료 |
| 환율, 유가, VIX | Yahoo Finance | 실시간 | 무료 |
| 종목/매크로 뉴스 | Google News RSS | 하루 5회 | 무료 |
| 투자기회 발굴 뉴스 | Brave Search API | 하루 5회 (8건) | 월 ~$2 |

---

## 9. 파일 경로 요약

```
~/Projects/investment-bot/
├── config.py              ← 포트폴리오 정의, 임계값 (수정 시 자비스에게 알릴 것)
├── data/
│   ├── realtime.py        ← 자비스가 직접 실행 (stdout만)
│   ├── fetch_prices.py    ← crontab 자동 실행
│   ├── fetch_macro.py     ← crontab 자동 실행
│   ├── fetch_news.py      ← crontab 자동 실행
│   └── fetch_gold_krx.py  ← fetch_prices에서 import
├── analysis/
│   ├── alerts.py          ← 공통 감지 로직 + 배치 모드
│   ├── alerts_watch.py    ← 임계값 감지 + 텔레그램 즉시 알림
│   ├── portfolio.py       ← 포트폴리오 손익 계산 + 이력 저장
│   ├── price_analysis.py  ← 기술 분석 (MA, RSI, 추세)
│   ├── screener.py        ← 종목 발굴
│   └── sentiment.py       ← 뉴스 감성 분석 (한/영 키워드)
├── reports/
│   ├── daily.py           ← daily_report.md 생성
│   ├── closing.py         ← closing_report.md 생성
│   └── weekly.py          ← weekly_report.md 생성
├── scripts/
│   ├── read_news.py       ← 자비스가 직접 실행 (stdout만)
│   └── run_news_notify.sh ← crontab에서 뉴스 수집 + 결과 알림
├── output/intel/          ← 자비스가 읽는 폴더 (git 제외)
└── db/history.db          ← SQLite 이력 DB (git 제외)
```

---

## 10. 개발 시 주의사항

1. **config.py 변경 시** 자비스에게 알릴 것 (포트폴리오/임계값 변경)
2. **output/intel/ 파일 구조 변경 시** 자비스 크론잡 프롬프트도 함께 수정 필요
3. **새 지표 추가 시** realtime.py stdout 형식 유지 (자비스가 파싱함)
4. **alerts.json 구조 변경 시** alerts_watch.py의 openclaw cron add 메시지도 수정
5. **Claude Code 실행 시** 민감한 키는 실행 후 .env에 추가

---

## 11. Phase 4: 종목 발굴 연동

### 자비스 → 엔진 인터페이스

자비스 05:30 크론잡에서 키워드 추론 후:

1. `output/intel/agent_commands/discovery_keywords.json` 생성:
```json
{
  "generated_at": "2026-03-26T05:30:00+09:00",
  "keywords": [
    {"keyword": "방산 수주 확대", "category": "sector", "priority": 1},
    {"keyword": "원전 르네상스", "category": "theme", "priority": 2}
  ]
}
```

2. Python 엔진 실행:
```bash
python3 /Users/jarvis/Projects/investment-bot/data/fetch_opportunities.py
```

3. 결과 확인: `output/intel/opportunities.json` 읽기

### 엔진 → 자비스 인터페이스 (신규)

- `output/intel/opportunities.json` — 발굴 종목 + 복합 점수
- `output/intel/screener.md` — 기존 스크리닝 + 발굴 종목 통합

### 복합 점수 구조
각 종목의 점수는 4개 팩터로 분해:
- return: 1개월 수익률 백분위
- rsi: RSI 과매도 백분위 (낮을수록 매수 기회)
- sentiment: 뉴스 감성 (-1~1 → 0~1)
- macro: 매크로 방향 (-1~1 → 0~1)

가중치: Equal Weight (각 0.25), 향후 성과 데이터 축적 후 최적화 예정.

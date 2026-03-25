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
| `prices.json` | fetch_prices.py | 장 중 10분마다 | 현재가 참조 |
| `macro.json` | fetch_macro.py | 장 중 10분마다 | 매크로 지표 참조 |
| `news.json` | fetch_news.py | 하루 5회 | 뉴스 컨텍스트 |
| `daily_report.md` | daily.py | 05:00 | 05:30 분석 파이프라인에서 읽기 |
| `closing_report.md` | closing.py | 15:40 | 16:00 장 마감 리포트에서 읽기 |
| `screener.md` | screener.py | 05:00 | 종목 발굴 결과 참조 |
| `portfolio_summary.json` | portfolio.py | 05:00 | 포트폴리오 손익 요약 |
| `weekly_report.md` | weekly.py | 월 04:00 | 주간 리포트에서 읽기 |

### ⚡ alerts.json — 긴급 알림 트리거

```json
// alerts_watch.py가 임계값 초과 시 생성
[
  {
    "level": "RED",
    "ticker": "005930.KS",
    "name": "삼성전자",
    "message": "삼성전자 -5.72% 급락",
    "notified": false,
    "triggered_at": "2026-03-24T15:02:00+09:00"
  }
]
```

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

## 6. 자비스가 원하는 데이터 (고도화 요청사항)

### 현재 부족한 것들

#### 6-1. 주가 이력 활용 미흡
- **현재:** 실시간 스냅샷만 사용
- **원하는 것:** `prices` 테이블에서 N일 이동평균, 최고/최저, 변동성 계산한 결과를 파일로 제공
- **제안 파일:** `output/intel/price_analysis.json`

```json
{
  "005930.KS": {
    "current": 188300,
    "ma5": 191200,
    "ma20": 195400,
    "high_52w": 223000,
    "low_52w": 52900,
    "volatility_30d": 8.3,
    "trend": "downtrend"
  }
}
```

#### 6-2. 뉴스 감성 점수 없음
- **현재:** 뉴스 제목+내용만 저장
- **원하는 것:** 종목별 뉴스 감성(긍정/부정) 스코어
- **제안 필드:** `news` 테이블에 `sentiment` 컬럼 (-1.0 ~ 1.0)

#### 6-3. 포트폴리오 이력 없음
- **현재:** 오늘 스냅샷만
- **원하는 것:** 일별 총 손익 이력 → 수익률 차트 가능
- **제안 테이블:** `portfolio_history` (date, total_krw, total_pnl, pnl_pct)

#### 6-4. 금 현물 실시간 신뢰도 문제
- **현재:** 키움증권 API (장 중만 데이터)
- **원하는 것:** 장외 시간에도 GC=F×KRW=X 환산값 fallback 명시
- **제안:** `prices.json`에 `data_source` 필드 추가

#### 6-5. 환율 기반 원화 환산 손익 계산
- **현재:** `portfolio.py`에서 USD/KRW 환산이 단순함
- **원하는 것:** 매입 시점 환율 vs 현재 환율 구분해서 환율 손익 별도 계산
- **제안 필드:** `portfolio_summary.json`에 `fx_pnl` (환율 손익) 추가

---

## 7. alerts_watch.py 임계값 (config.py 참조)

```python
ALERT_THRESHOLDS = {
    "stock_drop":     -5.0,   # 종목 급락 (%)
    "stock_surge":    +5.0,   # 종목 급등 (%)
    "kospi_drop":     -3.0,   # 코스피 폭락 (%)
    "usd_krw_high":   1550,   # 환율 급등 (원)
    "oil_surge":      +5.0,   # 유가 급등 (%)
    "gold_swing":     +3.0,   # 금 급변 (%)
    "vix_high":       30.0,   # VIX 급등
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
│   ├── alerts_watch.py    ← 임계값 감지 + 텔레그램 즉시 알림
│   ├── portfolio.py       ← 포트폴리오 손익 계산
│   └── screener.py        ← 종목 발굴
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

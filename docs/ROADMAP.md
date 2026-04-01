# Investment Bot 개발 로드맵

> 작성: 자비스 + 마커스 / 2026-04-01
> 목적: Claude Code에서 이 파일을 읽고 순서대로 개발

---

## 프로젝트 구조 참고

```
~/Projects/investment-bot/
├── config.py                  # 설정 (ALERT_THRESHOLDS, DB_PATH 등)
├── run_pipeline.py            # 일일 파이프라인 진입점
├── data/
│   ├── fetch_prices.py        # 주가 수집 (네이버/Yahoo)
│   ├── fetch_macro.py         # 매크로 수집 (VIX, 환율, 유가)
│   ├── fetch_news.py          # 뉴스 수집 → DB 저장
│   ├── fetch_opportunities.py # 키워드 기반 종목 발굴
│   ├── realtime.py            # 실시간 시세 출력
│   └── ticker_master.py       # 종목 사전 (KRX + 미국)
├── analysis/
│   ├── alerts.py              # 알림 감지 로직
│   ├── alerts_watch.py        # 실시간 알림 감시 → Discord 전송
│   ├── composite_score.py     # 종목 복합 점수 계산
│   ├── price_analysis.py      # 기술적 분석 (MA, RSI 등)
│   ├── screener.py            # 종목 스크리너
│   └── sentiment.py           # 뉴스 감성 분석
├── db/
│   ├── history.db             # 메인 SQLite DB
│   └── init_db.py             # DB 스키마 초기화
├── reports/
│   ├── closing.py             # 장 마감 리포트 생성
│   ├── daily.py               # 일일 리포트
│   └── weekly.py              # 주간 리포트
└── output/intel/              # AI가 읽는 JSON 스냅샷
    ├── prices.json
    ├── macro.json
    ├── portfolio_summary.json
    ├── portfolio_extra.json   # 비투자 자산 (전세, 청약 등)
    ├── marcus-analysis.md
    ├── opportunities.json
    └── agent_commands/
        └── discovery_keywords.json
```

---

## P1 — 이번 주 (즉시 효과 높음)

### T1: 유니버스 확장

**파일:** `analysis/screener.py`
**현재 문제:** 보유 8종목만 분석. 새 종목 발굴 불가.
**목표:** 코스피 200 + 미국 S&P 100 종목으로 유니버스 확장

**구현 내용:**
```python
# screener.py 상단에 유니버스 추가
UNIVERSE_KOSPI200 = [
    # 코스피 200 티커 리스트 (005930.KS, 000660.KS, 035420.KS ...)
    # ticker_master.py의 KRX_TICKERS 활용
]

UNIVERSE_SP100 = [
    # S&P 100 티커 (AAPL, MSFT, GOOGL, AMZN, META, NVDA ...)
]

def screen_universe(universe: list[str]) -> list[dict]:
    """유니버스 전체 종목 스크리닝 — composite_score 기준 상위 10개 반환"""
    pass
```

**요구사항:**
- `ticker_master.py`의 기존 KRX 사전 활용
- Yahoo Finance로 미국 주식 가격 수집 (fetch_prices.py 패턴 참고)
- `output/intel/screener_results.json`에 저장
- 기존 `screener.md` 파일도 업데이트

---

### T2: 포트폴리오 히스토리 자동 저장

**파일:** `reports/closing.py`
**현재 문제:** `db/history.db`의 `portfolio_history` 테이블에 8행밖에 없음. 매일 자동 저장 안 됨.
**목표:** 장 마감 시(15:40) 자동으로 당일 포트폴리오 스냅샷 저장

**구현 내용:**
```python
# closing.py 마지막 단계에 추가
def save_portfolio_snapshot(conn, portfolio_summary: dict):
    """
    portfolio_summary.json 데이터를 portfolio_history 테이블에 저장
    
    portfolio_history 스키마:
    - date TEXT (YYYY-MM-DD)
    - total_value_krw REAL
    - total_invested_krw REAL  
    - total_pnl_krw REAL
    - total_pnl_pct REAL
    - fx_rate REAL
    - snapshot_json TEXT (전체 JSON 저장)
    
    중복 저장 방지: 같은 날짜면 UPDATE
    """
    pass
```

**요구사항:**
- `output/intel/portfolio_summary.json` 읽어서 DB 저장
- crontab `40 15 * * 1-5` 에서 closing.py 실행 중이므로 기존 플로우에 통합
- 저장 후 콘솔 출력: `✅ 포트폴리오 스냅샷 저장: YYYY-MM-DD 총 X,XXX만원`

---

### T3: 동적 알림 임계값 (VIX 기반)

**파일:** `config.py`, `analysis/alerts.py`
**현재 문제:** 알림 임계값이 고정값. VIX 31처럼 공포 장에서는 -5% 알림이 너무 많이 발동.
**목표:** VIX 수준에 따라 임계값 자동 조정

**구현 내용:**
```python
# config.py에 추가
DYNAMIC_THRESHOLDS = {
    "calm":   {"vix_max": 20, "stock_drop": -5.0, "stock_surge": 5.0, "kospi_drop": -3.0},
    "normal": {"vix_max": 25, "stock_drop": -5.0, "stock_surge": 5.0, "kospi_drop": -3.0},
    "fear":   {"vix_max": 30, "stock_drop": -7.0, "stock_surge": 7.0, "kospi_drop": -4.0},
    "panic":  {"vix_max": 999,"stock_drop": -10.0,"stock_surge":10.0, "kospi_drop": -5.0},
}

def get_dynamic_thresholds(vix: float) -> dict:
    """현재 VIX 값에 따라 적절한 임계값 반환"""
    pass
```

**요구사항:**
- `alerts.py`의 `check_stock_alerts()`, `check_macro_alerts()` 함수에 적용
- `macro.json`에서 현재 VIX 읽어서 레짐 판단
- 적용된 임계값을 로그에 출력: `📊 현재 레짐: fear (VIX 31.05) — 임계값 -7% 적용`

---

## P2 — 다음 주

### T4: 매크로 레짐 분류기

**파일:** `analysis/regime_classifier.py` (신규 생성)
**목표:** VIX + 환율 + 유가 + 금리를 조합해 현재 시장 국면 자동 분류

**4가지 레짐:**
```
RISK_ON:      VIX < 20, 환율 안정, 유가 안정 → 적극 매수 가능
RISK_OFF:     VIX > 25, 환율 급등 → 방어 모드
INFLATIONARY: 유가 급등, 금리 상승 → 에너지/원자재 헤지
STAGFLATION:  VIX 높음 + 유가 높음 → 금/방산만 보유
```

**구현:**
```python
class RegimeClassifier:
    def classify(self, macro_data: dict) -> str:
        """
        입력: macro.json 데이터
        출력: "RISK_ON" | "RISK_OFF" | "INFLATIONARY" | "STAGFLATION"
        """
        pass
    
    def get_strategy(self, regime: str) -> dict:
        """
        레짐별 권고 전략 반환
        {
            "stance": "방어적/중립/공격적",
            "preferred_sectors": ["방산", "에너지"],
            "avoid_sectors": ["성장주"],
            "cash_ratio": 0.3
        }
        """
        pass
```

**요구사항:**
- `output/intel/regime.json` 저장 (마커스가 읽을 수 있도록)
- `run_pipeline.py`에 통합 (매일 05:00 실행)
- 레짐 변경 시 Discord 알림: `📊 레짐 변경: RISK_OFF → RISK_ON`

---

### T5: 12-1 모멘텀 팩터

**파일:** `analysis/composite_score.py`
**현재 문제:** 모멘텀 계산이 단기(RSI + 당일 수익률)만 봄.
**목표:** 12개월 수익률 - 1개월 수익률 = 중기 모멘텀 팩터 추가

**구현:**
```python
def calculate_12_1_momentum(ticker: str, conn) -> float:
    """
    DB에서 12개월 전 / 1개월 전 가격 조회
    → (현재가 / 12개월전가) - (현재가 / 1개월전가) 로 중기 모멘텀 산출
    → 0~100 점수로 정규화
    
    데이터 없으면 None 반환 (점수 제외 처리)
    """
    pass
```

**요구사항:**
- `history.db`의 `prices` 테이블에서 과거 가격 조회
- `composite_score`에 새 팩터로 추가 (기존 4팩터 → 5팩터)
- 데이터 부족 종목은 기존 4팩터만으로 계산

---

## P3 — 나중에 (1억+ 자산 규모 도달 시)

### T6: 백테스팅 엔진
- 과거 DB 데이터 기반 전략 검증
- Sharpe ratio, MDD 계산
- `backtest/` 폴더 신규 생성

### T7: 포트폴리오 최적화 (MVO)
- 마코위츠 평균-분산 최적화
- 리스크 패리티 배분
- `scipy` 활용

---

## 개발 시 주의사항

1. **DB 경로:** `from config import DB_PATH` 로 통일 (`db/history.db`)
2. **출력 경로:** `from config import OUTPUT_DIR` 로 통일 (`output/intel/`)
3. **시간대:** 모든 datetime은 KST (`Asia/Seoul`) 기준
4. **로깅:** `import logging` 사용, print() 남발 금지
5. **테스트:** `tests/` 폴더에 단위 테스트 추가 (기존 패턴 참고)
6. **오류 처리:** 데이터 없거나 API 실패해도 전체 파이프라인 중단 금지 — 해당 항목만 skip

# TradingView 차트·데이터 확장 설계

> 작성일: 2026-05-05  
> 순서: A (차트 UI) → C (FRED 매크로 확장) → B (TradingView Webhook 알림)  
> 각 서브프로젝트는 독립 구현 사이클을 가진다.

---

## 전체 아키텍처 맥락

```
[FRED API]  ────→  data/fetch_fred.py  ──→  output/intel/macro.json (확장)
[TradingView Webhook]  ──→  web/server.py /api/tv-alert  ──→  DB alerts
                                                    ↓
                               analysis/alerts_watch.py (기존 감지 루프와 병행)

[web-next]
  WealthTab          ──→  Lightweight Charts (전재산 추이)
  OverviewTab        ──→  Lightweight Charts (매크로 스파크라인)
  CompanyDrawer      ──→  TradingView Widget (종목 상세 차트)
  DiscoveryTab cards ──→  Lightweight Charts 미니 스파크라인 (가격 추이 N일)
```

---

## Sub-project A: 차트 UI 통합

### 목표

| 화면 | 현재 | 목표 |
|------|------|------|
| WealthTab | 숫자만 (데이터는 있음) | Lightweight Charts 전재산/투자/예비 3선 추이 |
| OverviewTab | 매크로 숫자 리스트 | 각 지표 소형 스파크라인 |
| CompanyDrawer | 텍스트만 | TradingView Widget 임베드 (공식 iframe) |
| DiscoveryTab 카드 | 점수 바만 | Lightweight Charts 30일 가격 미니 차트 |

### 기술 결정

**Lightweight Charts (`lightweight-charts`)**: 로컬 데이터 시각화에 사용.
- Apache 2.0 라이선스 (TradingView 공식 오픈소스)
- Recharts 대비 GPU 가속 Canvas 렌더링 → 60fps 보장
- 패키지: `npm install lightweight-charts`

**TradingView Widget (iframe)**: 종목 상세 차트에 사용.
- TradingView 공식 embed script (`https://s3.tradingview.com/tv.js`)
- 완전 무료, ToS 준수
- 자체 데이터 소스 (외부 시세 직접 렌더링 → Flask API 불필요)
- 한계: 커스텀 오버레이·매수가 마커 불가 (허용 범위)

### A-1. Lightweight Charts 설치

```bash
cd web-next
npm install lightweight-charts
```

`src/types/lightweight-charts.d.ts` — 별도 타입 선언 불필요 (패키지 내장 `.d.ts`).

---

### A-2. WealthTab 추이 차트

**대상 파일**: `web-next/src/components/tabs/WealthTab.tsx` (현재 303줄)

**데이터 소스**: `/api/wealth?days=90` 응답의 `history` 배열  
- 타입: `WealthHistoryEntry = { date: string, total_wealth_krw: number, investment_value_krw: number, extra_assets_krw: number }`  
- 이미 `useWealthData()` 훅이 가져오고 있음 → 추가 API 불필요

**컴포넌트 신설**: `src/components/charts/WealthLineChart.tsx`

```typescript
// Props
interface WealthLineChartProps {
  history: WealthHistoryEntry[]
  height?: number  // default 220
}

// 구현 전략
// - createChart() → 3개 LineSeries (total/investment/extra)
// - 색상: total=emerald-400, investment=blue-400, extra=amber-400
// - 오른쪽 Y축: 억 단위 (x / 1e8 + "억")
// - 크로스헤어 툴팁: 날짜 + 3개 값 동시 표시
// - useEffect cleanup: chart.remove()
// - ResizeObserver로 부모 너비 추적
```

**WealthTab 수정 포인트**:
- 기존 숫자 요약 카드 유지 (상단)
- 그 아래 `<WealthLineChart history={wealthData.history} />` 삽입
- 모바일: height=160, 데스크톱: height=220 (Tailwind `sm:` breakpoint)

---

### A-3. OverviewTab 매크로 스파크라인

**대상 파일**: `web-next/src/components/tabs/OverviewTab.tsx` (현재 257줄)

**데이터 소스**: `/api/data`의 `macro.indicators[]` (현재 change_pct만 있음)  
→ 스파크라인용 이력 데이터: `/api/macro-history?days=30&ticker=TICKER` 신설 필요 (Phase C 이후)  
→ **Phase A에서는 스파크라인 skeleton 컴포넌트만 준비**, 실 데이터는 C 완료 후 연결

**컴포넌트 신설**: `src/components/charts/MacroSparkline.tsx`

```typescript
interface MacroSparklineProps {
  data: { time: number, value: number }[]  // 최근 30일
  positive: boolean  // 색상 분기
  width?: number   // default 80
  height?: number  // default 32
}
// - createChart() → LineSeries, 축/격자 모두 숨김
// - positive → blue-400, negative → red-400
// - 마지막 값에 dot marker
```

**OverviewTab 수정 포인트**:
- 매크로 지표 행 오른쪽에 `<MacroSparkline />` 추가
- 데이터 없으면 `<div className="w-20 h-8 bg-white/5 rounded animate-pulse" />` skeleton

---

### A-4. CompanyDrawer TradingView Widget

**대상 파일**: `web-next/src/components/discovery/CompanyDrawer.tsx` (현재 104줄)

**컴포넌트 신설**: `src/components/charts/TradingViewWidget.tsx`

```typescript
interface TradingViewWidgetProps {
  ticker: string  // 예: "005930.KS", "AAPL"
  height?: number  // default 350
}
```

**구현 전략**:
- `useEffect`에서 `<script>` 태그 동적 삽입 (TradingView 공식 방식)
- `symbol` 변환: `.KS` → KOSPI:`ticker`, `.KQ` → KOSDAQ:`ticker`, 나머지 그대로
  ```typescript
  function toTvSymbol(ticker: string): string {
    if (ticker.endsWith('.KS')) return `KOSPI:${ticker.replace('.KS', '')}`
    if (ticker.endsWith('.KQ')) return `KOSDAQ:${ticker.replace('.KQ', '')}`
    if (ticker.endsWith('.KS') === false && /^\d{6}$/.test(ticker)) return `KOSPI:${ticker}`
    return ticker  // 미국주 그대로
  }
  ```
- 컨테이너 div에 `ref` 부착, 매 ticker 변경 시 innerHTML 초기화 후 재삽입
- 다크 테마: `theme: "dark"`, `colorTheme: "dark"`

**CompanyDrawer 수정 포인트**:
- 헤더(종목명/섹터/점수) 아래에 `<TradingViewWidget ticker={ticker} />` 삽입
- 그 아래 기존 설명문·펀더멘탈 텍스트 유지

---

### A-5. DiscoveryTab 카드 미니 스파크라인

**대상**: `web-next/src/components/discovery/OpportunityCard.tsx`

**데이터 소스 신설**: `/api/price-history?ticker=TICKER&days=30`

```python
# web/api.py 에 추가
def load_price_history(ticker: str, days: int = 30) -> list[dict]:
    """prices_daily 테이블에서 최근 N일 종가 반환."""
    with get_db_conn() as conn:
        rows = conn.execute(
            """SELECT date, close FROM prices_daily
               WHERE ticker = ?
               ORDER BY date DESC LIMIT ?""",
            (ticker, days),
        ).fetchall()
    return [{"date": r["date"], "close": r["close"]} for r in reversed(rows)]
```

```python
# web/server.py do_GET 추가
elif path == "/api/price-history":
    ticker = params.get("ticker", [""])[0]
    days = int(params.get("days", ["30"])[0])
    data = api.load_price_history(ticker, days)
    self._send_json(data)
```

**컴포넌트 신설**: `src/components/charts/PriceSparkline.tsx`
- OpportunityCard 내 `useSWR('/api/price-history?ticker='+ticker, fetcher, { dedupingInterval: 300_000 })`
- 데이터 없으면 placeholder 박스
- 너비 100%, height=48px, 선 색상: positive=emerald, negative=red

**OpportunityCard 수정 포인트**:
- 카드 상단 `<PriceSparkline ticker={ticker} />` 추가 (높이 48px 고정)
- 기존 점수 바는 아래 유지

---

### A 검증 기준

```bash
# 1. npm build 통과
cd web-next && npm run build

# 2. 배포 후 브라우저 확인 목록
# - WealthTab: 전재산 추이 3선 렌더링 (90일)
# - OverviewTab: 매크로 행마다 skeleton 박스 (C 완료 전)
# - CompanyDrawer: AAPL → TradingView Widget 로드
# - DiscoveryTab: 카드마다 가격 스파크라인 (DB에 데이터 있는 종목)

# 3. lighthouse mobile score ≥ 70 (차트 lazy-load 필수)
```

---

## Sub-project C: FRED 매크로 데이터 확장

### 목표

현재 8개 시장 지표(야후/네이버) → FRED API 추가로 경제 지표 8종 확장.

| FRED Series | 지표명 | 업데이트 주기 |
|-------------|--------|-------------|
| `FEDFUNDS` | 미국 기준금리 (Fed Funds Rate) | 월 |
| `DGS10` | 미국 10년 국채 금리 | 일 |
| `T10Y2Y` | 장단기 금리차 (10Y-2Y Spread) | 일 |
| `CPIAUCSL` | 미국 CPI (전년비) | 월 |
| `UNRATE` | 미국 실업률 | 월 |
| `GDPC1` | 미국 실질 GDP 성장률 (QoQ) | 분기 |
| `VIXCLS` | VIX (CBOE, FRED 버전) | 일 | ← 기존 `^VIX` (Yahoo)와 중복. FRED 버전은 `fred_macro.json`에만 저장, 기존 `macro.json`의 `^VIX`는 유지. |
| `DTWEXBGS` | 달러 인덱스 (Broad) | 일 |

> FRED는 API키 필요 (무료, https://fred.stlouisfed.org/docs/api/api_key.html).  
> 환경변수: `FRED_API_KEY`

---

### C-1. 환경변수 추가

`.env`:
```
FRED_API_KEY=xxx
```

`config.py`에 추가:
```python
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")

FRED_SERIES = {
    "FEDFUNDS":  {"name": "미국 기준금리",      "unit": "%",   "category": "금리"},
    "DGS10":     {"name": "미10년 국채",         "unit": "%",   "category": "금리"},
    "T10Y2Y":    {"name": "장단기 금리차",        "unit": "%p",  "category": "금리"},
    "CPIAUCSL":  {"name": "미국 CPI",            "unit": "%",   "category": "물가"},
    "UNRATE":    {"name": "미국 실업률",          "unit": "%",   "category": "노동"},
    "GDPC1":     {"name": "미 실질GDP 성장률",    "unit": "%",   "category": "성장"},
    "VIXCLS":    {"name": "VIX (FRED)",          "unit": "pt",  "category": "변동성"},
    "DTWEXBGS":  {"name": "달러 인덱스(Broad)",  "unit": "pt",  "category": "외환"},
}
```

---

### C-2. `data/fetch_fred.py` 신설

**규칙**: stdlib urllib만 사용, run() 진입점, graceful degradation.

```python
# 핵심 함수 구조 (300줄 이내)

def _fetch_series(series_id: str, limit: int = 1) -> list[dict]:
    """FRED API에서 최근 N개 관측값 반환."""
    # https://api.stlouisfed.org/fred/series/observations
    # params: series_id, api_key, limit, sort_order=desc, file_type=json

def _fetch_series_history(series_id: str, days: int = 90) -> list[dict]:
    """스파크라인용 최근 N일 이력 반환."""
    # observation_start=YYYY-MM-DD (오늘 - days)

def _build_indicator(series_id: str, meta: dict, obs: list[dict]) -> dict:
    """macro.json indicators 포맷으로 변환.
    DB indicator 컬럼 = series_id (예: 'DGS10') — /api/macro-history 조회 키와 일치.
    표시용 이름은 별도 name 필드 사용.
    """
    # {"indicator": series_id,        ← DB 저장 키 (FRED Series ID)
    #  "name": meta["name"],           ← 표시용 한국어명
    #  "ticker": series_id,
    #  "value": float, "prev_close": float, "change_pct": float,
    #  "category": meta["category"], "unit": meta["unit"],
    #  "timestamp": ..., "source": "FRED"}

def run() -> dict:
    """FRED 지표 수집 → output/intel/fred_macro.json 저장."""
```

**저장**: `output/intel/fred_macro.json`
```json
{
  "updated_at": "...",
  "source": "FRED",
  "indicators": [ {...}, ... ]
}
```

**DB 저장**: 기존 `macro` 테이블에 INSERT (source='FRED' 구분).

---

### C-3. `web/api.py` — INTEL_FILES 추가

```python
INTEL_FILES = [
    ...,
    "fred_macro.json",   # 추가
]
```

`/api/data` 응답의 `fred_macro` 키로 자동 노출됨.

---

### C-4. `/api/macro-history` 엔드포인트 신설

OverviewTab 스파크라인용.

```python
# web/api.py
def load_macro_history(series_id: str, days: int = 30) -> list[dict]:
    """macro 테이블에서 특정 지표 최근 N일 이력 반환."""
    with get_db_conn() as conn:
        rows = conn.execute(
            """SELECT timestamp, value FROM macro
               WHERE indicator = ?
               ORDER BY timestamp DESC LIMIT ?""",
            (series_id, days),
        ).fetchall()
    return [{"time": r["timestamp"], "value": r["value"]} for r in reversed(rows)]
```

```python
# web/server.py do_GET
elif path == "/api/macro-history":
    series_id = params.get("series_id", [""])[0]
    days = int(params.get("days", ["30"])[0])
    self._send_json(api.load_macro_history(series_id, days))
```

---

### C-5. 파이프라인 통합

`run_pipeline.py` `_collect_data()` 에 추가:
```python
from data.fetch_fred import run as fetch_fred
# ...
fetch_fred()   # fetch_fundamentals() 이후
```

**crontab.docker** — 별도 잡 추가 (하루 2회):
```
0 8,20 * * * cd /app && python3 data/fetch_fred.py >> /var/log/cron.log 2>&1
```

---

### C-6. OverviewTab 스파크라인 연결

Phase A에서 준비한 `MacroSparkline` 컴포넌트에 실 데이터 연결.

```typescript
// OverviewTab.tsx
const { data: hist } = useSWR(
  `/api/macro-history?series_id=${indicator.ticker}&days=30`,
  fetcher,
  { dedupingInterval: 3_600_000 }  // 1시간 캐시
)
```

---

### C 검증 기준

```bash
# 1. import 검사
bash .claude/skills/deploy/scripts/pre-deploy-check.sh

# 2. FRED 단건 수집
docker exec investment-bot python3 data/fetch_fred.py
# → output/intel/fred_macro.json 생성 확인

# 3. API 응답
docker exec investment-bot python3 -c "
import urllib.request, json
r = json.loads(urllib.request.urlopen(
    'http://localhost:8421/api/macro-history?series_id=DGS10&days=30'
).read())
print(len(r), 'rows')
"

# 4. 브라우저: OverviewTab 스파크라인 확인 (FRED 지표 행)
```

---

## Sub-project B: TradingView Webhook 알림

### 목표

TradingView Pine Script Alert → HTTPS POST → investment-bot `/api/tv-alert`  
→ DB `alerts` 테이블 저장 → Discord 웹훅 전송 (기존 채널 공용)

### 아키텍처

```
TradingView Alert (Pine Script)
    │  POST https://NGROK_OR_TAILSCALE/api/tv-alert
    │  Content-Type: application/json
    │  Body: { "ticker": "005930", "action": "BUY", "price": 72000, "strategy": "RSI오버솔드", "secret": "TVHOOK_SECRET" }
    ▼
investment-bot Flask /api/tv-alert
    ├─ 시크릿 검증 (TVHOOK_SECRET env)
    ├─ DB alerts 테이블 INSERT
    └─ Discord 웹훅 전송
```

**보안**: shared secret을 payload 또는 Authorization 헤더로 검증. HTTPS 필수 (Tailscale 또는 ngrok).

---

### B-1. 환경변수

```
TVHOOK_SECRET=랜덤_32자_문자열
```

---

### B-2. Webhook 수신 엔드포인트

**`web/server.py` do_POST 추가**:

```python
elif path == "/api/tv-alert":
    body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
    result = api.handle_tv_alert(json.loads(body))
    self._send_json(result)
```

**`web/api.py`**:

```python
import os as _os

_TVHOOK_SECRET = _os.environ.get("TVHOOK_SECRET", "")

def handle_tv_alert(payload: dict) -> dict:
    """TradingView Webhook 처리."""
    if not _TVHOOK_SECRET or payload.get("secret") != _TVHOOK_SECRET:
        return {"ok": False, "error": "unauthorized"}

    ticker   = payload.get("ticker", "")
    action   = payload.get("action", "")   # BUY / SELL / ALERT
    price    = float(payload.get("price", 0))
    strategy = payload.get("strategy", "")
    message  = f"[TV] {action} {ticker} @ {price:,.0f} — {strategy}"

    with get_db_conn() as conn:
        conn.execute(
            """INSERT INTO alerts (level, event_type, ticker, message, value, triggered_at, notified)
               VALUES (?, ?, ?, ?, ?, datetime('now','localtime'), 0)""",
            ("INFO", "tv_webhook", ticker, message, price),
        )
        conn.commit()

    _send_discord(message)
    return {"ok": True}
```

**`_send_discord()`**: 기존 alerts_watch.py의 디스코드 전송 로직과 동일 패턴 (os.environ.get("DISCORD_WEBHOOK_URL")).

---

### B-3. TradingView Pine Script 예시 (문서용)

```pine
//@version=5
strategy("RSI 전략", overlay=true)

rsi = ta.rsi(close, 14)
if ta.crossunder(rsi, 30)
    alert('{"ticker":"' + syminfo.ticker + '","action":"BUY","price":' + str.tostring(close) + ',"strategy":"RSI오버솔드","secret":"YOUR_SECRET"}',
          alert.freq_once_per_bar_close)
```

Alert URL 설정: `https://your-tailscale-host:8421/api/tv-alert`  
Method: POST, Body: `{{strategy.order.alert_message}}`

---

### B-4. AlertsTab 표시

**`web-next/src/components/tabs/AlertsTab.tsx`**:
- 기존 alerts.json 알림과 동일 테이블에 `event_type = 'tv_webhook'` 필터 추가
- "TradingView" 배지 표시

기존 `/api/data`의 `alerts` 필드가 `alerts.json`만 읽으므로,  
TV 알림은 별도 `/api/alerts-history?type=tv_webhook&limit=20` 엔드포인트로 조회.

```python
# web/api.py
def load_alerts_history(event_type: str = "", limit: int = 20) -> list[dict]:
    with get_db_conn() as conn:
        if event_type:
            rows = conn.execute(
                "SELECT * FROM alerts WHERE event_type=? ORDER BY triggered_at DESC LIMIT ?",
                (event_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM alerts ORDER BY triggered_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]
```

```python
# web/server.py
elif path == "/api/alerts-history":
    event_type = params.get("type", [""])[0]
    limit = int(params.get("limit", ["20"])[0])
    self._send_json(api.load_alerts_history(event_type, limit))
```

---

### B 검증 기준

```bash
# 1. 로컬 curl 테스트 (컨테이너 내부)
docker exec investment-bot python3 -c "
import urllib.request, json, os
secret = os.environ.get('TVHOOK_SECRET','test')
body = json.dumps({'ticker':'005930','action':'BUY','price':72000,'strategy':'테스트','secret':secret}).encode()
req = urllib.request.Request('http://localhost:8421/api/tv-alert', data=body,
      headers={'Content-Type':'application/json'}, method='POST')
print(urllib.request.urlopen(req).read().decode())
"
# → {"ok": true}

# 2. DB 확인
docker exec investment-bot python3 -c "
from db.connection import get_db_conn
with get_db_conn() as c:
    rows = c.execute(\"SELECT * FROM alerts WHERE event_type='tv_webhook' ORDER BY triggered_at DESC LIMIT 3\").fetchall()
    for r in rows: print(dict(r))
"

# 3. Discord 채널에 알림 메시지 수신 확인

# 4. AlertsTab 브라우저 확인 (TV 배지 표시)
```

---

## 구현 순서 & 의존 관계

```
A-1 npm install          (독립)
A-2 WealthLineChart      (A-1 이후)
A-3 MacroSparkline skeleton (A-1 이후)
A-4 TradingViewWidget    (A-1 이후)
A-5 PriceSparkline       (A-1 + /api/price-history 신설)
     ↓
C-1 FRED API키 설정      (독립)
C-2 fetch_fred.py        (C-1 이후)
C-3 INTEL_FILES 추가     (C-2 이후)
C-4 /api/macro-history   (C-2 이후)
C-5 파이프라인 통합       (C-2 이후)
C-6 OverviewTab 스파크라인 연결  (C-4 + A-3 이후)
     ↓
B-1 TVHOOK_SECRET 설정   (독립)
B-2 /api/tv-alert        (B-1 이후)
B-3 Pine Script 문서     (B-2 이후, 사용자 설정)
B-4 AlertsTab 표시       (B-2 이후)
```

---

## 파일 변경 목록 전체

### 신규 생성
| 파일 | 용도 |
|------|------|
| `data/fetch_fred.py` | FRED API 수집 |
| `web-next/src/components/charts/WealthLineChart.tsx` | 전재산 추이 |
| `web-next/src/components/charts/MacroSparkline.tsx` | 매크로 스파크라인 |
| `web-next/src/components/charts/TradingViewWidget.tsx` | TV iframe 위젯 |
| `web-next/src/components/charts/PriceSparkline.tsx` | 종목 미니 차트 |

### 기존 수정
| 파일 | 변경 내용 |
|------|---------|
| `config.py` | FRED_SERIES, FRED_API_KEY 추가 |
| `run_pipeline.py` | fetch_fred() 호출 추가 |
| `crontab.docker` | FRED 수집 잡 추가 |
| `web/api.py` | INTEL_FILES 추가, load_price_history, load_macro_history, handle_tv_alert, load_alerts_history |
| `web/server.py` | /api/price-history, /api/macro-history, /api/tv-alert, /api/alerts-history |
| `web-next/src/components/tabs/WealthTab.tsx` | WealthLineChart 삽입 |
| `web-next/src/components/tabs/OverviewTab.tsx` | MacroSparkline 연결 |
| `web-next/src/components/discovery/CompanyDrawer.tsx` | TradingViewWidget 삽입 |
| `web-next/src/components/discovery/OpportunityCard.tsx` | PriceSparkline 삽입 |
| `web-next/src/components/tabs/AlertsTab.tsx` | TV 알림 섹션 추가 |

### 환경변수 추가
```
FRED_API_KEY=...
TVHOOK_SECRET=...
```

---

## 비용 & 리스크

| 항목 | 비용 | 리스크 |
|------|------|--------|
| Lightweight Charts | 무료 (오픈소스) | 없음 |
| TradingView Widget iframe | 무료 (공식) | TradingView 서버 다운 시 위젯 불로드 |
| FRED API | 무료 (1000req/day) | 월 업데이트 지표는 최신값 지연 |
| TradingView Webhook | 무료 (Pro 플랜 이상 필요) | TradingView Pro 구독 필요 |

> **TradingView Webhook 주의**: Pine Script Alert의 Webhook URL 기능은 **TradingView Pro 이상**에서만 사용 가능. 무료 계정은 이메일/앱 알림만 가능. Sub-project B는 유료 플랜 전제.

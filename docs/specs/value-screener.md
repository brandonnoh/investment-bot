# value-screener: 상위 섹터 종목 RSI/PER/PBR 스크리닝

## 배경
현재 opportunities.json은 뉴스 텍스트 매칭으로 이미 보유 중인 종목만 발굴한다.
sector_scores.json 상위 섹터에서 실제 기술적/가치 지표로 스크리닝하여 진짜 매수 기회를 찾는다.

## 현재 코드 구조

### 재사용할 기존 함수
- `analysis/price_analysis_momentum.py`의 `calc_rsi(conn, ticker, period=14) -> float|None`
  - DB `prices_daily` 테이블에서 RSI 계산
  - 데이터 부족(< 15일) 시 None 반환
- `analysis/price_analysis_indicators.py`의 `calc_52w_range(conn, ticker) -> dict`
  - 반환: `{high_52w, low_52w, position_52w, current}`
- `data/fetch_fundamentals_sources.py`의 `fetch_yahoo_financials(ticker) -> dict`
  - 반환: `{per, pbr, roe, market_cap, ...}`
  - urllib.request 기반, 외부 라이브러리 없음

### sector_scores.json 포맷 (sector-intel에서 생성)
```json
{
  "sectors": [
    {"name": "방산", "score": 8.5, "signal": "favorable", "top_tickers": ["012450.KS", "LMT"]}
  ]
}
```

### SECTOR_MAP 포맷 (sector-map에서)
```python
SECTOR_MAP["방산"]["kr"] = ["012450.KS", "047810.KS", ...]
SECTOR_MAP["방산"]["us"] = ["LMT", "RTX", "GE", ...]
```

## 변경 범위
| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `analysis/value_screener.py` | 신규 생성 | RSI/PER/PBR 스크리닝 + run() |

## 구현 방향

### 스크리닝 조건
```python
# 종목이 다음 중 하나 이상 해당되면 opportunities에 포함
SCREEN_CONDITIONS = [
    # 조건명, 판단 함수, 설명
    ("oversold",   lambda m: m.get("rsi") and m["rsi"] < 35,                      "과매도(RSI<35)"),
    ("undervalue", lambda m: m.get("pbr") and m.get("roe") and m["pbr"] < 1.2 and m["roe"] > 8, "저평가(PBR<1.2+ROE>8%)"),
    ("52w_dip",    lambda m: m.get("pos_52w") is not None and m["pos_52w"] < 15,   "52주 저점근접(<15%)"),
]
```

### fetch_stock_metrics() 함수
```python
def _fetch_stock_metrics(conn, ticker: str) -> dict:
    """단일 종목 RSI + PER/PBR + 52주 범위 수집"""
    metrics = {"ticker": ticker}
    
    # RSI (DB 우선)
    try:
        metrics["rsi"] = calc_rsi(conn, ticker)
    except Exception:
        metrics["rsi"] = None
    
    # 52주 범위 (DB)
    try:
        range_data = calc_52w_range(conn, ticker)
        metrics["pos_52w"] = range_data.get("position_52w_pct")  # 0~100
        metrics["current"] = range_data.get("current")
    except Exception:
        metrics["pos_52w"] = None
    
    # PER/PBR/ROE (Yahoo Finance, DB 캐시 우선)
    try:
        fund = _load_cached_fundamentals(ticker)
        if not fund:
            fund = fetch_yahoo_financials(ticker)
        metrics["per"] = fund.get("per")
        metrics["pbr"] = fund.get("pbr")
        metrics["roe"] = fund.get("roe")
        metrics["name"] = fund.get("name", ticker)
    except Exception:
        metrics["per"] = metrics["pbr"] = metrics["roe"] = None
    
    return metrics
```

### run() 함수 구조
```python
def run() -> list:
    """섹터 기반 가치 스크리닝 → opportunities.json"""
    # 1. sector_scores.json 로드
    sector_scores_path = OUTPUT_DIR / "sector_scores.json"
    if not sector_scores_path.exists():
        print("  ⚠️  sector_scores.json 없음 — sector_intel 먼저 실행 필요")
        return []
    
    scores_data = json.loads(sector_scores_path.read_text(encoding="utf-8"))
    top_sectors = [s for s in scores_data["sectors"] if s["signal"] in ("favorable", "neutral")][:3]
    
    # 2. 대상 종목 수집 (top 3 섹터 × KR + US 종목)
    target_tickers = []
    for sector in top_sectors:
        smap = SECTOR_MAP.get(sector["name"], {})
        for t in smap.get("kr", [])[:5] + smap.get("us", [])[:5]:
            target_tickers.append({"ticker": t, "sector": sector["name"]})
    
    # 3. DB 연결 후 각 종목 지표 수집
    conn = sqlite3.connect(str(DB_PATH))
    opportunities = []
    for item in target_tickers:
        ticker = item["ticker"]
        metrics = _fetch_stock_metrics(conn, ticker)
        
        # 4. 스크리닝
        reasons = []
        for cond_name, cond_fn, cond_label in SCREEN_CONDITIONS:
            if cond_fn(metrics):
                reasons.append(cond_label)
        
        if not reasons:
            continue
        
        opportunities.append({
            "ticker": ticker,
            "name": metrics.get("name", ticker),
            "sector": item["sector"],
            "screen_reason": " + ".join(reasons),
            "rsi": metrics.get("rsi"),
            "per": metrics.get("per"),
            "pbr": metrics.get("pbr"),
            "roe": metrics.get("roe"),
            "pos_52w": metrics.get("pos_52w"),
            "composite_score": _calc_composite_score(metrics),
            "discovered_via": f"섹터스크리닝:{item['sector']}",
            "source": "value_screener",
        })
    
    conn.close()
    
    # 5. composite_score 내림차순 정렬
    opportunities.sort(key=lambda x: x.get("composite_score", 0), reverse=True)
    
    # 6. opportunities.json 저장 (기존 포맷 호환)
    out = {
        "updated_at": datetime.now(KST).isoformat(),
        "keywords": [{"keyword": s["name"], "category": "sector"} for s in top_sectors],
        "opportunities": opportunities,
        "total_count": len(opportunities),
        "summary": {
            "total_count": len(opportunities),
            "by_sector": {s: sum(1 for o in opportunities if o["sector"]==s) for s in {o["sector"] for o in opportunities}},
            "top_reason": _top_reason(opportunities),
        },
    }
    (OUTPUT_DIR / "opportunities.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  ✅ 가치 스크리닝 완료: {len(opportunities)}건")
    return opportunities
```

### _calc_composite_score() 함수
```python
def _calc_composite_score(metrics: dict) -> float:
    """RSI 과매도 + PBR 저평가 + 52주 저점 기반 0~1 점수"""
    score = 0.5  # 기본
    rsi = metrics.get("rsi")
    pbr = metrics.get("pbr")
    roe = metrics.get("roe")
    pos = metrics.get("pos_52w")
    
    if rsi is not None:
        # RSI 30 이하 → +0.3, 35 이하 → +0.15
        if rsi <= 30:
            score += 0.3
        elif rsi <= 35:
            score += 0.15
    
    if pbr is not None and pbr > 0:
        # PBR 1.0 이하 → +0.25, 1.5 이하 → +0.1
        if pbr <= 1.0:
            score += 0.25
        elif pbr <= 1.5:
            score += 0.1
    
    if pos is not None:
        # 52주 저점 15% 이내 → +0.2
        if pos <= 15:
            score += 0.2
    
    return round(min(1.0, score), 4)
```

## 의존 관계
- import: `analysis.sector_map.SECTOR_MAP`, `analysis.sector_intel` (간접)
- import: `analysis.price_analysis_momentum.calc_rsi`
- import: `analysis.price_analysis_indicators.calc_52w_range`
- import: `data.fetch_fundamentals_sources.fetch_yahoo_financials`
- 읽는 파일: `output/intel/sector_scores.json`, `output/intel/fundamentals.json` (캐시)
- 쓰는 파일: `output/intel/opportunities.json`

## 수락 조건
tasks.json의 acceptance_criteria와 동일.

## 검증 명령
```bash
cd /Users/jarvis/Projects/investment-bot
python3 analysis/value_screener.py
cat output/intel/opportunities.json | python3 -c "import json,sys; d=json.load(sys.stdin); [print(o['ticker'], o['screen_reason'], o['composite_score']) for o in d['opportunities'][:5]]"
ruff check analysis/value_screener.py
```

# sector-intel: 매크로/뉴스/레짐 기반 섹터 점수화

## 배경
Marcus가 뉴스/매크로를 읽고 search_keywords.json을 생성하지만, 그 키워드가 "어떤 섹터가 유망한가"로 
변환되지 않는다. sector_scores.json을 통해 파이프라인에 구조적 섹터 인텔리전스를 추가한다.

## 현재 코드 구조
- `output/intel/regime.json`: `{regime, confidence, vix, fx_change, oil_change, strategy.preferred_sectors}`
- `output/intel/macro.json`: `{indicators: [{indicator, ticker, value, change_pct, category}]}`
  - COMMODITY: WTI 유가(CL=F, change_pct=-16.64), 금(GC=F, change_pct=+2.89)
  - FX: 원달러(KRW=X, value=1465), 달러인덱스(DX-Y.NYB)
  - VOLATILITY: VIX(^VIX, value=17.48)
  - INDEX: KOSPI, KOSDAQ
- `output/intel/news.json`: 기사 리스트 `[{title, category, tickers}]`
- `analysis/sector_map.py` (task-001에서 생성): SECTOR_MAP, MACRO_SECTOR_RULES

## 변경 범위
| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `analysis/sector_intel.py` | 신규 생성 | 섹터 점수화 로직 + run() |

## 구현 방향

### sector_scores.json 출력 포맷
```json
{
  "updated_at": "2026-04-19T05:01:00+09:00",
  "regime": "RISK_OFF",
  "sectors": [
    {
      "name": "방산",
      "score": 8.5,
      "signal": "favorable",
      "reasoning": "VIX 17.5(관망), 유가 -16.6%(지정학 이슈), 레짐 RISK_OFF",
      "top_tickers": ["012450.KS", "047810.KS", "LMT", "RTX"],
      "macro_boost": ["vix_high", "oil_crash"],
      "news_count": 3
    }
  ]
}
```

### 점수 계산 로직

```python
def _score_from_macro(macro_data: dict, regime_data: dict) -> dict[str, float]:
    """매크로 지표 → 섹터별 점수 딕셔너리 반환"""
    scores: dict[str, float] = {s: 5.0 for s in SECTOR_MAP}  # 기본 5점
    
    # 1. 레짐 preferred/avoid 반영
    regime = regime_data.get("regime", "")
    strategy = regime_data.get("strategy", {})
    for s in strategy.get("preferred_sectors", []):
        if s in scores:
            scores[s] += 2.0
    for s in strategy.get("avoid_sectors", []):
        if s in scores:
            scores[s] -= 2.0
    
    # 2. 매크로 룰셋 적용
    indicators = {ind["ticker"]: ind for ind in macro_data.get("indicators", [])}
    vix = indicators.get("^VIX", {}).get("value", 0)
    wti_change = indicators.get("CL=F", {}).get("change_pct", 0)
    krw_value = indicators.get("KRW=X", {}).get("value", 0)
    gold_change = indicators.get("GC=F", {}).get("change_pct", 0)
    
    for rule_name, rule in MACRO_SECTOR_RULES.items():
        triggered = False
        if rule["direction"] == "above" and _get_signal_value(rule_name, vix, krw_value) > rule["threshold"]:
            triggered = True
        elif rule["direction"] == "below" and _get_signal_value(rule_name, vix, krw_value) < rule["threshold"]:
            triggered = True
        elif rule["direction"] == "above_change" and _get_change_value(rule_name, wti_change, gold_change) > rule["threshold"]:
            triggered = True
        elif rule["direction"] == "below_change" and _get_change_value(rule_name, wti_change, gold_change) < rule["threshold"]:
            triggered = True
        
        if triggered:
            for s in rule.get("favorable", []):
                if s in scores:
                    scores[s] += 1.5
            for s in rule.get("unfavorable", []):
                if s in scores:
                    scores[s] -= 1.5
    
    return scores


def _score_from_news(news_data: list) -> dict[str, float]:
    """뉴스 제목 → 섹터별 언급 빈도 점수 (최대 +2점)"""
    counts: dict[str, int] = {s: 0 for s in SECTOR_MAP}
    for article in news_data[:50]:  # 최신 50건만
        title = article.get("title", "") + " " + article.get("summary", "")
        for sector, info in SECTOR_MAP.items():
            for kw in info.get("keywords", []):
                if kw in title:
                    counts[sector] += 1
                    break
    # 정규화: 최대 언급 섹터 = +2점
    max_count = max(counts.values()) if counts else 1
    return {s: min(2.0, (c / max(max_count, 1)) * 2.0) for s, c in counts.items()}
```

### run() 함수 구조
```python
def run() -> dict:
    """섹터 점수화 실행 → sector_scores.json 저장"""
    # 1. 데이터 로드
    macro_data = _load_json(OUTPUT_DIR / "macro.json")
    regime_data = _load_json(OUTPUT_DIR / "regime.json")
    news_data = _load_news(OUTPUT_DIR / "news.json")
    
    # 2. 점수 계산
    macro_scores = _score_from_macro(macro_data, regime_data)
    news_scores = _score_from_news(news_data)
    
    # 3. 합산 + 정렬
    final_scores = {}
    for sector in SECTOR_MAP:
        final_scores[sector] = round(
            macro_scores.get(sector, 5.0) + news_scores.get(sector, 0.0), 2
        )
    
    # 4. 섹터별 상세 정보 생성
    sorted_sectors = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
    sectors_out = []
    for name, score in sorted_sectors:
        signal = "favorable" if score >= 6.5 else "unfavorable" if score < 4.0 else "neutral"
        top_tickers = SECTOR_MAP[name]["kr"][:2] + SECTOR_MAP[name]["us"][:2]
        sectors_out.append({
            "name": name,
            "score": score,
            "signal": signal,
            "reasoning": _build_reasoning(name, macro_data, regime_data),
            "top_tickers": top_tickers,
        })
    
    # 5. 저장
    out = {
        "updated_at": datetime.now(KST).isoformat(),
        "regime": regime_data.get("regime", "UNKNOWN"),
        "sectors": sectors_out,
    }
    (OUTPUT_DIR / "sector_scores.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  ✅ 섹터 점수화 완료: top={sectors_out[0]['name']}({sectors_out[0]['score']})")
    return out
```

## 의존 관계
- 읽는 파일: `output/intel/macro.json`, `output/intel/regime.json`, `output/intel/news.json`
- 쓰는 파일: `output/intel/sector_scores.json`
- import: `from analysis.sector_map import SECTOR_MAP, MACRO_SECTOR_RULES`

## 수락 조건
tasks.json의 acceptance_criteria와 동일.

## 검증 명령
```bash
cd /Users/jarvis/Projects/investment-bot
python3 analysis/sector_intel.py
cat output/intel/sector_scores.json | python3 -c "import json,sys; d=json.load(sys.stdin); print([(s['name'],s['score']) for s in d['sectors'][:3]])"
ruff check analysis/sector_intel.py
```

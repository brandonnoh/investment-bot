# pipeline-wire: run_pipeline.py에 sector_intel 단계 통합

## 배경
sector_intel.run()이 macro.json, regime.json, news.json을 읽어 sector_scores.json을 생성한다.
이 파일이 value_screener(→fetch_opportunities)의 입력으로 필요하므로, 
파이프라인에서 opportunities 수집 직전에 sector_intel을 실행해야 한다.

## 현재 코드 구조
- `run_pipeline.py`
  - 줄 100-115: `_collect_opportunities()` — `fetch_opportunities.run()` 호출
  - 줄 60-100: `_collect_data(engine)` — prices → macro → news → fundamentals → supply → opportunities 순서

현재 순서:
```
_collect_data():
  fetch_prices()
  fetch_macro()
  fetch_news()
  _collect_fundamentals()
  _collect_supply()
  _collect_opportunities()  ← 여기 직전에 sector_intel 추가
```

## 변경 범위
| 파일 | 변경 유형 | 줄 범위 | 내용 |
|------|----------|---------|------|
| `run_pipeline.py` | 수정 | `_collect_data()` 함수 | `_collect_opportunities()` 전에 `_run_sector_intel()` 호출 추가 |
| `run_pipeline.py` | 추가 | 신규 함수 | `_run_sector_intel()` 함수 |

## 구현 방향

### _run_sector_intel() 신규 함수
```python
def _run_sector_intel():
    """섹터 인텔리전스: macro/news/regime → sector_scores.json"""
    try:
        from analysis.sector_intel import run as run_sector_intel
        result = run_sector_intel()
        top = result.get("sectors", [{}])[0]
        print(f"  섹터 점수화: top={top.get('name')}({top.get('score')})")
    except Exception as e:
        print(f"  ⚠️ sector_intel 실패: {e}")
```

### _collect_data() 수정

#### Before (현재)
```python
def _collect_data(engine: EngineStatus):
    # ...
    _collect_supply()
    _collect_opportunities(engine)
```

#### After
```python
def _collect_data(engine: EngineStatus):
    # ...
    _collect_supply()
    _run_sector_intel()       # ← 추가: sector_scores.json 생성
    _collect_opportunities(engine)
```

## 의존 관계
- 이 변경이 영향받는 파일: 없음 (추가만)
- `_run_sector_intel()` → `analysis.sector_intel.run()` 호출

## 수락 조건
tasks.json의 acceptance_criteria와 동일.

## 검증 명령
```bash
cd /Users/jarvis/Projects/investment-bot
python3 -c "
import run_pipeline
# _collect_data 함수 소스에 sector_intel 포함 확인
import inspect
src = inspect.getsource(run_pipeline._collect_data)
assert 'sector_intel' in src or '_run_sector_intel' in src
print('OK')
"
ruff check run_pipeline.py
```

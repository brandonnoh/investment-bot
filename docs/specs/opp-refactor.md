# opp-refactor: fetch_opportunities.py를 value_screener 위임으로 교체

## 배경
`data/fetch_opportunities.py`의 `run()`이 파이프라인에서 종목 발굴 진입점이다.
기존 Brave 텍스트 매칭 로직은 보존하되, `run()`은 새 `value_screener.run()`에 위임한다.

## 현재 코드 구조
- `data/fetch_opportunities.py`
  - 줄 1-20: imports
  - 줄 185-220: `run()` 함수 — 키워드 로드 → Brave 검색 → 텍스트 매칭 → 저장
  - 줄 130-180: `_process_keywords()` — 키워드별 뉴스 검색 + 종목 추출
  - 줄 100-130: `_load_keywords()`, `_load_master()` 등 헬퍼

## 변경 범위
| 파일 | 변경 유형 | 줄 범위 | 내용 |
|------|----------|---------|------|
| `data/fetch_opportunities.py` | 수정 | run() 함수 | value_screener 위임으로 교체 |
| `data/fetch_opportunities.py` | 수정 | run() | 기존 로직을 _legacy_run()으로 rename |

## 구현 방향

### Before (현재 run() 함수 시그니처)
```python
def run(conn=None, keywords_path=None, output_dir=None) -> list:
    """종목 발굴 파이프라인 실행."""
    kw_path = Path(keywords_path) if keywords_path else KEYWORDS_PATH
    # ... Brave 검색 + 텍스트 매칭 로직 ...
```

### After
```python
def run(conn=None, keywords_path=None, output_dir=None) -> list:
    """종목 발굴 — value_screener 기반 (섹터 스크리닝)으로 위임."""
    try:
        from analysis.value_screener import run as screener_run
        return screener_run()
    except Exception as e:
        print(f"  ⚠️  value_screener 실패, legacy로 폴백: {e}")
        return _legacy_run(conn=conn, keywords_path=keywords_path, output_dir=output_dir)


def _legacy_run(conn=None, keywords_path=None, output_dir=None) -> list:
    """기존 Brave 키워드 검색 기반 종목 발굴 (fallback용)."""
    # 현재 run() 함수 내용을 그대로 이동
    kw_path = Path(keywords_path) if keywords_path else KEYWORDS_PATH
    # ... 기존 로직 ...
```

## 의존 관계
- 변경 후 `run()` → `analysis.value_screener.run()` 호출
- 실패 시 `_legacy_run()` fallback

## 수락 조건
tasks.json의 acceptance_criteria와 동일.

## 검증 명령
```bash
cd /Users/jarvis/Projects/investment-bot
python3 data/fetch_opportunities.py
ruff check data/fetch_opportunities.py
```

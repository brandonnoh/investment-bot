# Phase 4: AI 기반 능동적 종목 발굴 시스템 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 자비스(AI)가 키워드를 추론하면 Python 엔진이 검색/매칭/점수화하고, 성과를 추적하는 능동적 종목 발굴 파이프라인 구축

**Architecture:** 자비스→엔진 인터페이스로 `discovery_keywords.json`을 사용하고, 엔진이 Naver/Brave 검색 → ticker_master 매칭 → 복합 점수 계산 → `opportunities.json` 출력. DB에 모든 이력을 저장하여 성과 추적 루프를 형성.

**Tech Stack:** Python 3 stdlib only, SQLite (WAL mode), urllib.request, concurrent.futures, json, difflib

---

## 파일 구조

```
신규 생성:
  data/ticker_master.py          — KRX/미국 종목 사전 관리
  data/fetch_opportunities.py    — 키워드 기반 종목 발굴 (F16)
  analysis/composite_score.py    — 복합 점수 계산 엔진
  tests/test_f16_ticker_master.py
  tests/test_f17_opportunities.py
  tests/test_f18_composite_score.py
  tests/test_f19_screener_v2.py
  tests/test_f20_news_split.py
  tests/fixtures/sample_brave_response.json
  tests/fixtures/sample_naver_news_response.json
  tests/fixtures/sample_ticker_master.json
  tests/fixtures/sample_discovery_keywords.json
  output/intel/agent_commands/    — 디렉토리 (자비스→엔진)

수정:
  config.py                      — OPPORTUNITY_CONFIG, NAVER_API 설정 추가
  db/init_db.py                  — 3개 신규 테이블 + 마이그레이션
  analysis/screener.py           — 복합 점수 통합, 유니버스 확장 (F17)
  data/fetch_news.py             — 발굴 뉴스 분리 (F18)
  run_pipeline.py                — fetch_opportunities 단계 추가
  utils/schema.py                — opportunities.json 스키마 추가
  tests.json                     — F16~F20 추가
  prd.md                         — F16~F20 체크리스트 추가
```

---

## Task 0: tests.json / prd.md 업데이트

**Files:**
- Modify: `tests.json`
- Modify: `prd.md`

- [ ] **Step 1: tests.json의 `features` 배열 끝(F15 뒤)에 F16~F20 추가, summary 업데이트**

`"total": 20, "passing": 15, "failing": 5`로 summary 변경 후, features 배열에 append:

```json
{
  "id": "F16",
  "description": "종목 사전(ticker_master) — KRX/미국 종목 매핑 DB",
  "status": "failing",
  "summary": "",
  "priority": 1,
  "depends_on": ["F01", "F02"],
  "acceptance_criteria": [
    "ticker_master 테이블 생성 (ticker, name, market, sector, updated_at)",
    "KRX 종목 리스트 수집 함수 (공공데이터포털 또는 정적 시드)",
    "difflib 기반 퍼지 매칭 함수 (threshold=0.6)",
    "별칭 매핑 (삼전→삼성전자 등)",
    "정규식 종목코드 추출 (뉴스에서 (012450) 패턴)",
    "미국 종목 정적 사전 (S&P500 주요 100개)",
    "테스트: 정확 매칭, 퍼지 매칭, 별칭, 미매칭 케이스"
  ]
},
{
  "id": "F17",
  "description": "fetch_opportunities.py — 키워드 기반 종목 발굴",
  "status": "failing",
  "summary": "",
  "priority": 2,
  "depends_on": ["F16"],
  "acceptance_criteria": [
    "agent_keywords 테이블 생성",
    "opportunities 테이블 생성 (sub_scores 포함)",
    "discovery_keywords.json 읽기 → Naver/Brave 검색",
    "검색 결과에서 종목 추출 (ticker_master 매칭)",
    "opportunities.json 출력",
    "run_pipeline.py 통합",
    "Graceful degradation (API 실패 시 빈 결과)",
    "테스트: 키워드 파싱, 검색 모킹, 종목 추출, JSON 스키마"
  ]
},
{
  "id": "F18",
  "description": "복합 점수 엔진 — 4팩터 Percentile Rank 스코어링",
  "status": "failing",
  "summary": "",
  "priority": 2,
  "depends_on": ["F17"],
  "acceptance_criteria": [
    "percentile_rank 정규화 함수",
    "복합 점수 계산 (수익률/RSI/감성/매크로 Equal Weight)",
    "매크로 방향 지수 계산 (-1.0~1.0)",
    "sub_scores 분해 (각 팩터별 0~1 점수)",
    "opportunities 테이블에 점수 기록",
    "테스트: 정규화 경계, 동일값, 이상치, 가중치 합산"
  ]
},
{
  "id": "F19",
  "description": "screener.py 고도화 — 복합 점수 통합 + 유니버스 확장",
  "status": "failing",
  "summary": "",
  "priority": 3,
  "depends_on": ["F18"],
  "acceptance_criteria": [
    "기존 15종목 + opportunities 통합 유니버스",
    "price_analysis.py의 get_history_data/analyze_from_history 재사용",
    "복합 점수 기반 TOP 10 선별",
    "screener.md 포맷 개선 (점수 분해 포함)",
    "테스트: 유니버스 병합, 점수 정렬, 리포트 생성"
  ]
},
{
  "id": "F20",
  "description": "뉴스 수집 목적 분리 — 모니터링 vs 발굴",
  "status": "failing",
  "summary": "",
  "priority": 3,
  "depends_on": ["F17"],
  "acceptance_criteria": [
    "fetch_news.py에서 opportunity 카테고리 뉴스 수집 제거",
    "fetch_opportunities.py가 발굴 뉴스 전담",
    "기존 테스트 통과 유지",
    "테스트: 뉴스 카테고리 분리 검증"
  ]
}
```

summary 업데이트: `"total": 20, "passing": 15, "failing": 5`

- [ ] **Step 2: prd.md에 Phase 4 체크리스트 추가**

```markdown
## Phase 4 — AI 기반 능동적 종목 발굴

- [ ] **F16** 종목 사전(ticker_master) — KRX/미국 종목 매핑 DB
- [ ] **F17** fetch_opportunities.py — 키워드 기반 종목 발굴
- [ ] **F18** 복합 점수 엔진 — 4팩터 Percentile Rank 스코어링
- [ ] **F19** screener.py 고도화 — 복합 점수 통합 + 유니버스 확장
- [ ] **F20** 뉴스 수집 목적 분리 — 모니터링 vs 발굴
```

- [ ] **Step 3: 커밋**

```bash
git add tests.json prd.md
git commit -m "docs: Phase 4 F16~F20 태스크 정의"
```

---

## Task 1: DB 스키마 확장 (3개 신규 테이블)

**Files:**
- Modify: `db/init_db.py`
- Modify: `tests/conftest.py` (필요 시)

- [ ] **Step 1: init_db.py에 3개 테이블 추가하는 테스트 작성**

```python
# tests/test_f16_ticker_master.py
import sqlite3
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db.init_db import init_schema

def test_ticker_master_table_created(db_conn):
    """ticker_master 테이블이 생성되는지 확인"""
    cursor = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='ticker_master'"
    )
    assert cursor.fetchone() is not None

def test_agent_keywords_table_created(db_conn):
    """agent_keywords 테이블이 생성되는지 확인"""
    cursor = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_keywords'"
    )
    assert cursor.fetchone() is not None

def test_opportunities_table_created(db_conn):
    """opportunities 테이블이 생성되는지 확인"""
    cursor = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='opportunities'"
    )
    assert cursor.fetchone() is not None

def test_opportunities_columns(db_conn):
    """opportunities 테이블에 sub_scores 컬럼이 있는지"""
    cursor = db_conn.execute("PRAGMA table_info(opportunities)")
    columns = {row[1] for row in cursor.fetchall()}
    expected = {"id", "ticker", "name", "discovered_at", "discovered_via",
                "source", "composite_score", "score_return", "score_rsi",
                "score_sentiment", "score_macro", "price_at_discovery",
                "outcome_1w", "outcome_1m", "status"}
    assert expected.issubset(columns)
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `python3 -m pytest tests/test_f16_ticker_master.py -v`
Expected: FAIL (테이블 미존재)

- [ ] **Step 3: init_db.py에 3개 테이블 DDL 추가**

`init_schema(conn)` 함수 내부, 기존 테이블 생성 코드 뒤에 추가:

```python
# ── Phase 4: 종목 발굴 ──
cursor.execute("""
    CREATE TABLE IF NOT EXISTS ticker_master (
        ticker TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        name_en TEXT,
        market TEXT,
        sector TEXT,
        updated_at TEXT NOT NULL
    )
""")
cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_ticker_master_name
    ON ticker_master (name)
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS agent_keywords (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword TEXT NOT NULL,
        category TEXT,
        priority INTEGER DEFAULT 5,
        reasoning TEXT,
        generated_at TEXT NOT NULL,
        used_at TEXT,
        results_count INTEGER DEFAULT 0
    )
""")
cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_agent_keywords_date
    ON agent_keywords (generated_at)
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS opportunities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        name TEXT,
        discovered_at TEXT NOT NULL,
        discovered_via TEXT,
        source TEXT,
        composite_score REAL,
        score_return REAL,
        score_rsi REAL,
        score_sentiment REAL,
        score_macro REAL,
        price_at_discovery REAL,
        outcome_1w REAL,
        outcome_1m REAL,
        status TEXT DEFAULT 'discovered'
    )
""")
cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_opp_ticker_date
    ON opportunities (ticker, discovered_at)
""")
cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_opp_score
    ON opportunities (composite_score DESC)
""")
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python3 -m pytest tests/test_f16_ticker_master.py -v`
Expected: PASS

- [ ] **Step 5: 기존 전체 테스트도 통과 확인**

Run: `python3 -m pytest tests/ -v`
Expected: 362+ tests PASS

- [ ] **Step 6: 커밋**

```bash
git add db/init_db.py tests/test_f16_ticker_master.py
git commit -m "feat(F16): ticker_master/agent_keywords/opportunities DB 테이블 추가"
```

---

## Task 2: config.py 확장

**Files:**
- Modify: `config.py`

- [ ] **Step 1: config.py에 Phase 4 설정 추가**

기존 설정 블록 뒤에 추가:

```python
# ── Phase 4: 종목 발굴 설정 ──
OPPORTUNITY_CONFIG = {
    "composite_weights": {
        "return": 0.25,
        "rsi": 0.25,
        "sentiment": 0.25,
        "macro": 0.25,
    },
    "min_composite_score": 0.4,
    "max_candidates": 100,
    "search_count": 10,
    "cache_ttl_seconds": 600,
}

# 종목 사전 — 주요 한국 종목 별칭
TICKER_ALIASES = {
    "삼전": "삼성전자",
    "현차": "현대차",
    "하에스": "한화에어로스페이스",
    "SK하닉": "SK하이닉스",
    "카카오뱅": "카카오뱅크",
    "네이버": "NAVER",
}

# 미국 주요 종목 정적 사전 (ticker → 일반명)
US_TICKER_MAP = {
    "AAPL": "Apple", "MSFT": "Microsoft", "GOOGL": "Alphabet",
    "AMZN": "Amazon", "NVDA": "NVIDIA", "TSLA": "Tesla",
    "META": "Meta", "AVGO": "Broadcom", "LLY": "Eli Lilly",
    "JPM": "JPMorgan", "V": "Visa", "UNH": "UnitedHealth",
    "XOM": "Exxon Mobil", "MA": "Mastercard", "PG": "Procter & Gamble",
    "COST": "Costco", "HD": "Home Depot", "ABBV": "AbbVie",
    "CRM": "Salesforce", "AMD": "AMD", "MRK": "Merck",
    "NFLX": "Netflix", "LMT": "Lockheed Martin", "RTX": "RTX",
    "BA": "Boeing", "CAT": "Caterpillar", "GS": "Goldman Sachs",
}

# Naver API (선택사항 — 없으면 Brave로 폴백)
# 환경변수: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
# 네이버 개발자센터에서 앱 등록 후 발급
```

**주의:** CLAUDE.md의 환경변수 섹션에도 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` 추가 (선택사항 표시).

- [ ] **Step 2: 기존 테스트 통과 확인**

Run: `python3 -m pytest tests/ -v`
Expected: 362+ tests PASS

- [ ] **Step 3: 커밋**

```bash
git add config.py
git commit -m "feat(F16): Phase 4 종목 발굴 설정 추가 (OPPORTUNITY_CONFIG, TICKER_ALIASES)"
```

---

## Task 3: ticker_master.py — 종목 사전 모듈

**Files:**
- Create: `data/ticker_master.py`
- Create: `tests/fixtures/sample_ticker_master.json`
- Modify: `tests/test_f16_ticker_master.py` (테스트 추가)

- [ ] **Step 1: fixture 데이터 작성**

```json
// tests/fixtures/sample_ticker_master.json
[
  {"ticker": "005930.KS", "name": "삼성전자", "market": "KOSPI", "sector": "반도체"},
  {"ticker": "000660.KS", "name": "SK하이닉스", "market": "KOSPI", "sector": "반도체"},
  {"ticker": "012450.KS", "name": "한화에어로스페이스", "market": "KOSPI", "sector": "방산"},
  {"ticker": "034020.KS", "name": "두산에너빌리티", "market": "KOSPI", "sector": "에너지"},
  {"ticker": "006400.KS", "name": "삼성SDI", "market": "KOSPI", "sector": "2차전지"},
  {"ticker": "003670.KS", "name": "포스코퓨처엠", "market": "KOSPI", "sector": "소재"},
  {"ticker": "035420.KS", "name": "NAVER", "market": "KOSPI", "sector": "IT"},
  {"ticker": "005380.KS", "name": "현대차", "market": "KOSPI", "sector": "자동차"},
  {"ticker": "051910.KS", "name": "LG화학", "market": "KOSPI", "sector": "화학"},
  {"ticker": "207940.KS", "name": "삼성바이오로직스", "market": "KOSPI", "sector": "바이오"}
]
```

- [ ] **Step 2: 매칭 함수 테스트 작성 (Task 1의 테스트 파일에 이어서 추가)**

Task 1에서 만든 `tests/test_f16_ticker_master.py` 파일 상단에 import 추가하고, 기존 DB 테스트 아래에 append:

```python
# tests/test_f16_ticker_master.py 상단 import 블록에 추가:
import json
from pathlib import Path

def _load_fixture():
    p = Path(__file__).parent / "fixtures" / "sample_ticker_master.json"
    with open(p) as f:
        return json.load(f)

# ── 기존 DB 테이블 테스트 (Task 1) 아래에 추가 ──

def test_exact_match():
    """정확한 종목명 매칭"""
    from data.ticker_master import find_tickers
    master = _load_fixture()
    results = find_tickers("삼성전자", master)
    assert len(results) >= 1
    assert results[0]["ticker"] == "005930.KS"

def test_fuzzy_match():
    """부분 종목명 퍼지 매칭"""
    from data.ticker_master import find_tickers
    master = _load_fixture()
    results = find_tickers("한화에어로", master)
    assert any(r["ticker"] == "012450.KS" for r in results)

def test_alias_match():
    """별칭 매칭 (삼전→삼성전자)"""
    from data.ticker_master import resolve_alias
    assert resolve_alias("삼전") == "삼성전자"
    assert resolve_alias("존재안함") == "존재안함"

def test_no_match():
    """매칭 불가 시 빈 리스트"""
    from data.ticker_master import find_tickers
    master = _load_fixture()
    results = find_tickers("완전히없는종목", master)
    assert results == []

def test_extract_codes_from_text():
    """뉴스 텍스트에서 종목코드 추출"""
    from data.ticker_master import extract_ticker_codes
    text = "한화에어로스페이스(012450)가 수주를 발표했다"
    codes = extract_ticker_codes(text)
    assert "012450" in codes

def test_extract_us_tickers():
    """영문 텍스트에서 미국 티커 추출"""
    from data.ticker_master import extract_us_tickers
    text = "NVDA surged 5% on AI demand, while TSLA dropped"
    tickers = extract_us_tickers(text)
    assert "NVDA" in tickers
    assert "TSLA" in tickers

def test_extract_companies_from_text():
    """텍스트에서 종목명 직접 매칭 (사전 기반)"""
    from data.ticker_master import extract_companies
    master = _load_fixture()
    text = "삼성전자와 SK하이닉스가 반도체 투자를 확대한다"
    found = extract_companies(text, master)
    tickers = [f["ticker"] for f in found]
    assert "005930.KS" in tickers
    assert "000660.KS" in tickers

def test_save_and_load_master(db_conn):
    """DB에 종목 사전 저장/로드"""
    from data.ticker_master import save_master_to_db, load_master_from_db
    master = _load_fixture()
    save_master_to_db(db_conn, master)
    loaded = load_master_from_db(db_conn)
    assert len(loaded) == len(master)
    assert loaded[0]["ticker"] == master[0]["ticker"]
```

- [ ] **Step 3: 테스트 실행 — 실패 확인**

Run: `python3 -m pytest tests/test_f16_ticker_master.py -v`
Expected: FAIL (data.ticker_master 모듈 없음)

- [ ] **Step 4: data/ticker_master.py 구현**

```python
"""종목 사전 관리 — KRX/미국 종목 매핑, 퍼지 매칭, 코드 추출"""
import difflib
import json
import re
import sqlite3
import sys
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

KST = timezone(timedelta(hours=9))
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "db" / "history.db"


def resolve_alias(name: str) -> str:
    """별칭을 정식 종목명으로 변환. 별칭 없으면 원본 반환."""
    return config.TICKER_ALIASES.get(name, name)


def find_tickers(query: str, master: list, threshold: float = 0.6) -> list:
    """종목명 퍼지 매칭. 반환: [{"ticker": ..., "name": ..., "score": ...}]"""
    query = resolve_alias(query)
    name_map = {item["name"]: item for item in master}

    # 1. 정확 매칭
    if query in name_map:
        return [name_map[query]]

    # 2. 부분 문자열 매칭 (query가 종목명에 포함)
    partial = [item for item in master if query in item["name"]]
    if partial:
        return partial

    # 3. difflib 퍼지 매칭
    matches = difflib.get_close_matches(query, name_map.keys(), n=3, cutoff=threshold)
    return [name_map[m] for m in matches]


def extract_ticker_codes(text: str) -> list:
    """텍스트에서 한국 종목코드(6자리) 추출"""
    pattern = re.compile(r'[\(\[]\s*(\d{6})\s*[\)\]]')
    return pattern.findall(text)


def extract_us_tickers(text: str) -> list:
    """텍스트에서 미국 티커($TSLA 또는 대문자 1~5자) 추출"""
    # $TSLA 패턴
    dollar_pattern = re.compile(r'\$([A-Z]{1,5})\b')
    dollar_matches = dollar_pattern.findall(text)
    if dollar_matches:
        return [t for t in dollar_matches if t in config.US_TICKER_MAP]

    # 대문자 단어 중 US_TICKER_MAP에 있는 것
    word_pattern = re.compile(r'\b([A-Z]{1,5})\b')
    candidates = word_pattern.findall(text)
    # 일반 영단어 제외
    common_words = {"AI", "CEO", "IPO", "ETF", "IT", "US", "UK", "EU", "GDP",
                    "API", "THE", "AND", "FOR", "BUT", "NOT", "ALL", "NEW",
                    "TOP", "BIG", "LOW", "HIGH", "SEC", "FED", "IMF"}
    return [t for t in candidates
            if t in config.US_TICKER_MAP and t not in common_words]


def extract_companies(text: str, master: list) -> list:
    """텍스트에서 종목명 직접 매칭 (긴 이름부터 매칭, 중복 방지)"""
    found = []
    remaining = text
    sorted_items = sorted(master, key=lambda x: len(x["name"]), reverse=True)
    for item in sorted_items:
        if item["name"] in remaining:
            found.append(item)
            remaining = remaining.replace(item["name"], " ")
    return found


def save_master_to_db(conn: sqlite3.Connection, master: list):
    """종목 사전을 DB에 저장 (UPSERT)"""
    now = datetime.now(KST).isoformat()
    for item in master:
        conn.execute(
            """INSERT OR REPLACE INTO ticker_master
               (ticker, name, name_en, market, sector, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (item["ticker"], item["name"], item.get("name_en", ""),
             item.get("market", ""), item.get("sector", ""), now)
        )
    conn.commit()


def load_master_from_db(conn: sqlite3.Connection) -> list:
    """DB에서 종목 사전 로드"""
    cursor = conn.execute(
        "SELECT ticker, name, name_en, market, sector FROM ticker_master ORDER BY ticker"
    )
    return [{"ticker": r[0], "name": r[1], "name_en": r[2],
             "market": r[3], "sector": r[4]} for r in cursor.fetchall()]


def get_seed_master() -> list:
    """초기 시드 종목 사전 (PORTFOLIO + SCREENING_TARGETS에서 추출)"""
    seen = set()
    master = []

    # config.PORTFOLIO에서 추출
    for p in config.PORTFOLIO:
        if p["ticker"] not in seen:
            seen.add(p["ticker"])
            market = "COMMODITY" if "GOLD" in p["ticker"] else (
                "KR" if p["ticker"].endswith((".KS", ".KQ")) else "US"
            )
            master.append({
                "ticker": p["ticker"], "name": p["name"],
                "market": market, "sector": ""
            })

    # SCREENING_TARGETS에서 추출
    # SCREENING_TARGETS는 analysis/screener.py에 정의됨 (config.py가 아님)
    # 존재하면 추출, 없으면 건너뜀
    screening_targets = getattr(config, "SCREENING_TARGETS", None)
    if screening_targets is None:
        try:
            from analysis.screener import SCREENING_TARGETS as screening_targets
        except ImportError:
            screening_targets = None
    if screening_targets:
        for sector_name, sector_data in screening_targets.items():
            for t in sector_data.get("tickers", []):
                if t["ticker"] not in seen:
                    seen.add(t["ticker"])
                    market = "KR" if t["ticker"].endswith((".KS", ".KQ")) else "US"
                    master.append({
                        "ticker": t["ticker"], "name": t["name"],
                        "market": market, "sector": sector_name
                    })

    return master


def run(conn=None):
    """종목 사전 초기화/갱신. 시드 데이터를 DB에 저장."""
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH))
    master = get_seed_master()
    save_master_to_db(conn, master)
    return master
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python3 -m pytest tests/test_f16_ticker_master.py -v`
Expected: PASS

- [ ] **Step 6: 전체 테스트 통과 확인**

Run: `python3 -m pytest tests/ -v`
Expected: 362+ tests PASS

- [ ] **Step 7: tests.json F16 status → passing, prd.md 체크**

- [ ] **Step 8: 커밋**

```bash
git add data/ticker_master.py tests/test_f16_ticker_master.py tests/fixtures/sample_ticker_master.json config.py
git commit -m "feat(F16): 종목 사전 모듈 — 퍼지 매칭, 별칭, 코드 추출"
```

---

## Task 4: fetch_opportunities.py — 키워드 기반 종목 발굴 (F17)

**Files:**
- Create: `data/fetch_opportunities.py`
- Create: `tests/test_f17_opportunities.py`
- Create: `tests/fixtures/sample_discovery_keywords.json`
- Create: `tests/fixtures/sample_brave_response.json`
- Create: `tests/fixtures/sample_naver_news_response.json`

- [ ] **Step 1: fixture 데이터 작성**

```json
// tests/fixtures/sample_discovery_keywords.json
{
  "generated_at": "2026-03-25T05:30:00+09:00",
  "keywords": [
    {"keyword": "방산 수주 확대 2026", "category": "sector", "priority": 1},
    {"keyword": "원전 르네상스 수혜주", "category": "theme", "priority": 2}
  ]
}
```

```json
// tests/fixtures/sample_brave_response.json
{
  "results": [
    {
      "title": "한화에어로스페이스(012450), 폴란드 K9 추가 수주 임박",
      "description": "방산 수출 사상 최대 기록 예상",
      "url": "https://example.com/1",
      "age": "2h"
    },
    {
      "title": "두산에너빌리티, 체코 원전 수주 확정",
      "description": "SMR 원전 건설 본격화",
      "url": "https://example.com/2",
      "age": "5h"
    }
  ]
}
```

```json
// tests/fixtures/sample_naver_news_response.json
{
  "items": [
    {
      "title": "<b>한화에어로스페이스</b> 방산 수출 급증",
      "description": "글로벌 방산 수요 확대",
      "link": "https://example.com/3",
      "pubDate": "Wed, 25 Mar 2026 10:00:00 +0900"
    }
  ]
}
```

- [ ] **Step 2: 테스트 작성**

```python
# tests/test_f17_opportunities.py
import json
import sqlite3
import sys, os
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

FIXTURES = Path(__file__).parent / "fixtures"

def _load_fixture(name):
    with open(FIXTURES / name) as f:
        return json.load(f)

def test_parse_discovery_keywords():
    """discovery_keywords.json 파싱"""
    from data.fetch_opportunities import parse_keywords
    data = _load_fixture("sample_discovery_keywords.json")
    keywords = parse_keywords(data)
    assert len(keywords) == 2
    assert keywords[0]["keyword"] == "방산 수주 확대 2026"
    assert keywords[0]["category"] == "sector"

def test_search_brave_news(monkeypatch):
    """Brave 뉴스 검색 모킹"""
    from data.fetch_opportunities import search_brave
    fixture = _load_fixture("sample_brave_response.json")
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(fixture).encode()
    mock_resp.status = 200
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr("data.fetch_opportunities.urllib.request.urlopen", lambda req, **kw: mock_resp)
    results = search_brave("방산 수주", count=5)
    assert len(results) >= 1
    assert "title" in results[0]

def test_extract_opportunities_from_news():
    """뉴스 결과에서 종목 후보 추출"""
    from data.fetch_opportunities import extract_opportunities
    master = _load_fixture("sample_ticker_master.json")
    news = [
        {"title": "한화에어로스페이스(012450), 방산 수주 임박", "url": "https://ex.com/1"},
        {"title": "두산에너빌리티, 원전 수주 확정", "url": "https://ex.com/2"},
        {"title": "날씨 좋은 하루", "url": "https://ex.com/3"},
    ]
    opps = extract_opportunities(news, master, "방산 수주")
    tickers = [o["ticker"] for o in opps]
    assert "012450.KS" in tickers

def test_save_keywords_to_db(db_conn):
    """agent_keywords DB 저장"""
    from data.fetch_opportunities import save_keywords_to_db
    keywords = [
        {"keyword": "방산 수주", "category": "sector", "priority": 1, "reasoning": "테스트"}
    ]
    save_keywords_to_db(db_conn, keywords, "2026-03-25T05:30:00+09:00")
    row = db_conn.execute("SELECT keyword FROM agent_keywords").fetchone()
    assert row[0] == "방산 수주"

def test_save_opportunities_to_db(db_conn):
    """opportunities DB 저장"""
    from data.fetch_opportunities import save_opportunities_to_db
    opps = [{
        "ticker": "012450.KS", "name": "한화에어로스페이스",
        "discovered_via": "방산 수주", "source": "brave",
        "price_at_discovery": 350000
    }]
    save_opportunities_to_db(db_conn, opps)
    row = db_conn.execute("SELECT ticker FROM opportunities").fetchone()
    assert row[0] == "012450.KS"

def test_generate_opportunities_json():
    """opportunities.json 생성"""
    from data.fetch_opportunities import generate_json
    keywords = [{"keyword": "방산", "category": "sector", "priority": 1}]
    opps = [{"ticker": "012450.KS", "name": "한화에어로스페이스",
             "discovered_via": "방산", "composite_score": None}]
    result = generate_json(keywords, opps)
    assert "updated_at" in result
    assert "keywords" in result
    assert "opportunities" in result
    assert len(result["opportunities"]) == 1

def test_run_with_no_keywords(tmp_path):
    """키워드 파일 없을 때 graceful 빈 결과"""
    from data.fetch_opportunities import run
    result = run(keywords_path=tmp_path / "nonexistent.json",
                 output_dir=tmp_path)
    assert result == []
```

- [ ] **Step 3: 테스트 실행 — 실패 확인**

Run: `python3 -m pytest tests/test_f17_opportunities.py -v`
Expected: FAIL

- [ ] **Step 4: data/fetch_opportunities.py 구현**

```python
"""키워드 기반 종목 발굴 — 자비스가 추론한 키워드로 Naver/Brave 검색, 종목 추출"""
import json
import logging
import os
import re
import sqlite3
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
from data.ticker_master import (
    find_tickers, extract_ticker_codes, extract_us_tickers,
    extract_companies, load_master_from_db
)
try:
    from analysis.sentiment import calculate_sentiment
except ImportError:
    def calculate_sentiment(title, summary):
        return 0.0

KST = timezone(timedelta(hours=9))
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "db" / "history.db"
OUTPUT_DIR = PROJECT_ROOT / "output" / "intel"
KEYWORDS_PATH = OUTPUT_DIR / "agent_commands" / "discovery_keywords.json"

logger = logging.getLogger(__name__)


def parse_keywords(data: dict) -> list:
    """discovery_keywords.json 파싱"""
    return data.get("keywords", [])


def search_brave(query: str, count: int = 10) -> list:
    """Brave News Search API 호출"""
    api_key = os.environ.get("BRAVE_API_KEY", getattr(config, "BRAVE_API_KEY", ""))
    if not api_key:
        logger.warning("BRAVE_API_KEY 미설정, Brave 검색 건너뜀")
        return []
    try:
        params = urllib.parse.urlencode({
            "q": query, "count": count, "freshness": "pw"
        })
        url = f"https://api.search.brave.com/res/v1/news/search?{params}"
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "X-Subscription-Token": api_key
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return data.get("results", [])
    except Exception as e:
        logger.warning(f"Brave 검색 실패: {query} — {e}")
        return []


def search_naver_news(query: str, count: int = 10) -> list:
    """네이버 뉴스 검색 API 호출"""
    client_id = os.environ.get("NAVER_CLIENT_ID", "")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return []
    try:
        params = urllib.parse.urlencode({
            "query": query, "display": count, "sort": "date"
        })
        url = f"https://openapi.naver.com/v1/search/news.json?{params}"
        req = urllib.request.Request(url, headers={
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        items = data.get("items", [])
        # Brave 형식으로 정규화
        return [{"title": re.sub(r"<[^>]+>", "", i["title"]),
                 "description": re.sub(r"<[^>]+>", "", i.get("description", "")),
                 "url": i.get("link", ""),
                 "age": ""} for i in items]
    except Exception as e:
        logger.warning(f"Naver 검색 실패: {query} — {e}")
        return []


def extract_opportunities(news: list, master: list, keyword: str) -> list:
    """뉴스 결과에서 종목 후보 추출"""
    found = []
    seen_tickers = set()

    for article in news:
        title = article.get("title", "")
        text = f"{title} {article.get('description', '')}"

        # 방법 1: 종목코드 직접 추출
        codes = extract_ticker_codes(text)
        for code in codes:
            ticker = f"{code}.KS"
            if ticker not in seen_tickers:
                seen_tickers.add(ticker)
                name_match = [m for m in master if m["ticker"] == ticker]
                found.append({
                    "ticker": ticker,
                    "name": name_match[0]["name"] if name_match else code,
                    "discovered_via": keyword,
                    "source": "code_extract",
                    "news_title": title,
                    "url": article.get("url", ""),
                    "sentiment": calculate_sentiment(title, article.get("description", "")),
                })

        # 방법 2: 종목명 사전 매칭
        companies = extract_companies(text, master)
        for comp in companies:
            if comp["ticker"] not in seen_tickers:
                seen_tickers.add(comp["ticker"])
                found.append({
                    "ticker": comp["ticker"],
                    "name": comp["name"],
                    "discovered_via": keyword,
                    "source": "name_match",
                    "news_title": title,
                    "url": article.get("url", ""),
                    "sentiment": calculate_sentiment(title, article.get("description", "")),
                })

        # 방법 3: 미국 티커 추출
        us_tickers = extract_us_tickers(text)
        for t in us_tickers:
            if t not in seen_tickers:
                seen_tickers.add(t)
                found.append({
                    "ticker": t,
                    "name": config.US_TICKER_MAP.get(t, t),
                    "discovered_via": keyword,
                    "source": "us_ticker",
                    "news_title": title,
                    "url": article.get("url", ""),
                    "sentiment": calculate_sentiment(title, article.get("description", "")),
                })

    return found


def save_keywords_to_db(conn, keywords: list, generated_at: str):
    """agent_keywords 테이블에 저장"""
    for kw in keywords:
        conn.execute(
            """INSERT INTO agent_keywords (keyword, category, priority, reasoning, generated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (kw["keyword"], kw.get("category", ""),
             kw.get("priority", 5), kw.get("reasoning", ""), generated_at)
        )
    conn.commit()


def save_opportunities_to_db(conn, opportunities: list):
    """opportunities 테이블에 저장"""
    now = datetime.now(KST).isoformat()
    for opp in opportunities:
        conn.execute(
            """INSERT OR IGNORE INTO opportunities
               (ticker, name, discovered_at, discovered_via, source,
                composite_score, score_return, score_rsi, score_sentiment, score_macro,
                price_at_discovery, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'discovered')""",
            (opp["ticker"], opp.get("name", ""), now,
             opp.get("discovered_via", ""), opp.get("source", ""),
             opp.get("composite_score"), opp.get("score_return"),
             opp.get("score_rsi"), opp.get("score_sentiment"),
             opp.get("score_macro"), opp.get("price_at_discovery"))
        )
    conn.commit()


def generate_json(keywords: list, opportunities: list) -> dict:
    """opportunities.json 생성"""
    return {
        "updated_at": datetime.now(KST).isoformat(),
        "keywords": keywords,
        "opportunities": opportunities,
        "summary": {
            "total_keywords": len(keywords),
            "total_candidates": len(opportunities),
        }
    }


def run(conn=None, keywords_path=None, output_dir=None) -> list:
    """종목 발굴 실행. 반환: 발굴된 종목 리스트"""
    keywords_path = Path(keywords_path) if keywords_path else KEYWORDS_PATH
    output_dir = Path(output_dir) if output_dir else OUTPUT_DIR

    # 1. 키워드 파일 읽기
    if not keywords_path.exists():
        logger.info(f"키워드 파일 없음: {keywords_path}")
        return []

    with open(keywords_path) as f:
        kw_data = json.load(f)
    keywords = parse_keywords(kw_data)
    if not keywords:
        return []

    # 2. DB 연결
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH))

    # 3. 종목 사전 로드
    master = load_master_from_db(conn)
    if not master:
        from data.ticker_master import run as init_master
        master = init_master(conn)

    # 4. 키워드 DB 저장
    save_keywords_to_db(conn, keywords, kw_data.get("generated_at", ""))

    # 5. 키워드별 검색 + 종목 추출
    all_opportunities = []
    for kw in keywords:
        query = kw["keyword"]
        # Naver 우선, Brave 보조
        news = search_naver_news(query)
        if not news:
            news = search_brave(query)
        if not news:
            continue

        opps = extract_opportunities(news, master, query)
        all_opportunities.extend(opps)

    # 6. 중복 제거 (같은 ticker는 첫 발견만)
    seen = set()
    unique = []
    for opp in all_opportunities:
        if opp["ticker"] not in seen:
            seen.add(opp["ticker"])
            unique.append(opp)
    all_opportunities = unique

    # 7. DB 저장
    save_opportunities_to_db(conn, all_opportunities)

    # 8. JSON 출력
    result = generate_json(keywords, all_opportunities)
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "opportunities.json", "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info(f"종목 발굴 완료: {len(keywords)}개 키워드 → {len(all_opportunities)}개 후보")
    return all_opportunities


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python3 -m pytest tests/test_f17_opportunities.py -v`
Expected: PASS

- [ ] **Step 6: tests.json F17 → passing, prd.md 체크, 커밋**

```bash
git add data/fetch_opportunities.py tests/test_f17_opportunities.py tests/fixtures/sample_*.json
git commit -m "feat(F17): 키워드 기반 종목 발굴 — Naver/Brave 검색, 종목 매칭, DB 저장"
```

---

## Task 5: composite_score.py — 복합 점수 엔진 (F18)

**Files:**
- Create: `analysis/composite_score.py`
- Create: `tests/test_f18_composite_score.py`

- [ ] **Step 1: 테스트 작성**

```python
# tests/test_f18_composite_score.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def test_percentile_rank_basic():
    """기본 percentile rank 계산"""
    from analysis.composite_score import percentile_rank
    values = [10, 20, 30, 40, 50]
    assert percentile_rank(values, 50) == 0.9
    assert percentile_rank(values, 10) == 0.1
    assert percentile_rank(values, 30) == 0.5

def test_percentile_rank_empty():
    """빈 리스트일 때 0.5 반환"""
    from analysis.composite_score import percentile_rank
    assert percentile_rank([], 42) == 0.5

def test_percentile_rank_all_same():
    """모든 값이 같을 때"""
    from analysis.composite_score import percentile_rank
    assert percentile_rank([5, 5, 5], 5) == 0.5

def test_calculate_macro_direction():
    """매크로 방향 지수 계산"""
    from analysis.composite_score import calculate_macro_direction
    macro = {
        "KOSPI": {"change_pct": 1.0},
        "KRW=X": {"change_pct": -0.5},
        "CL=F": {"change_pct": 2.0},
        "^VIX": {"change_pct": -3.0},
    }
    direction = calculate_macro_direction(macro)
    assert -1.0 <= direction <= 1.0
    assert direction > 0  # 전체적으로 긍정

def test_calculate_composite_score():
    """복합 점수 계산"""
    from analysis.composite_score import calculate_composite_score
    candidate = {"month_return": 10.0, "rsi_14": 55.0, "sentiment": 0.5}
    universe_returns = [-5, 0, 5, 10, 15]
    universe_rsi = [30, 40, 50, 55, 70]
    macro_direction = 0.3
    score, sub = calculate_composite_score(
        candidate, universe_returns, universe_rsi, macro_direction
    )
    assert 0 <= score <= 1
    assert "return" in sub
    assert "rsi" in sub
    assert "sentiment" in sub
    assert "macro" in sub

def test_composite_score_weights_sum():
    """가중치 합이 1.0"""
    import config
    weights = config.OPPORTUNITY_CONFIG["composite_weights"]
    assert abs(sum(weights.values()) - 1.0) < 0.001

def test_score_all_extremes():
    """최고/최저 극단값 테스트"""
    from analysis.composite_score import calculate_composite_score
    best = {"month_return": 50.0, "rsi_14": 99.0, "sentiment": 1.0}
    worst = {"month_return": -50.0, "rsi_14": 1.0, "sentiment": -1.0}
    returns = [-50, 0, 50]
    rsis = [1, 50, 99]

    best_score, _ = calculate_composite_score(best, returns, rsis, 1.0)
    worst_score, _ = calculate_composite_score(worst, returns, rsis, -1.0)
    assert best_score > worst_score
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `python3 -m pytest tests/test_f18_composite_score.py -v`
Expected: FAIL

- [ ] **Step 3: analysis/composite_score.py 구현**

```python
"""복합 점수 계산 엔진 — 4팩터 Percentile Rank 기반 스코어링"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


def percentile_rank(values: list, value: float) -> float:
    """0~1 사이 백분위 순위. 이상치에 강건."""
    if not values:
        return 0.5
    count_below = sum(1 for v in values if v < value)
    count_equal = sum(1 for v in values if v == value)
    n = len(values)
    if n == 0:
        return 0.5
    return (count_below + 0.5 * count_equal) / n


def calculate_macro_direction(macro: dict) -> float:
    """매크로 환경을 -1.0~1.0 지수로 변환"""
    scores = []

    # 코스피: 상승 → 긍정
    kospi = macro.get("KOSPI", {}).get("change_pct", 0)
    scores.append(max(-1, min(1, kospi / 5)))

    # 환율: 하락 → 긍정 (원화 강세 = 수출 제외 긍정)
    krw = macro.get("KRW=X", {}).get("change_pct", 0)
    scores.append(max(-1, min(1, -krw / 3)))

    # 유가: 방향성 중립 (에너지주에는 긍정, 나머지에는 부정)
    oil = macro.get("CL=F", {}).get("change_pct", 0)
    scores.append(max(-1, min(1, oil / 10)))

    # VIX: 하락 → 긍정
    vix = macro.get("^VIX", {}).get("change_pct", 0)
    scores.append(max(-1, min(1, -vix / 15)))

    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 4)


def calculate_composite_score(
    candidate: dict,
    universe_returns: list,
    universe_rsi: list,
    macro_direction: float,
) -> tuple:
    """
    복합 점수 계산.

    Args:
        candidate: {"month_return": float, "rsi_14": float, "sentiment": float}
        universe_returns: 유니버스 전체의 1개월 수익률 리스트
        universe_rsi: 유니버스 전체의 RSI 리스트
        macro_direction: -1.0 ~ 1.0

    Returns:
        (score: float 0~1, sub_scores: dict)
    """
    weights = config.OPPORTUNITY_CONFIG["composite_weights"]

    # 1. 수익률 점수 (모멘텀: 높을수록 좋음)
    ret_val = candidate.get("month_return", 0) or 0
    score_return = percentile_rank(universe_returns, ret_val)

    # 2. RSI 점수 (중립 선호: 40~60이 최고, 극단은 감점)
    rsi_val = candidate.get("rsi_14", 50) or 50
    # RSI를 "매수 기회" 관점으로: 낮을수록(과매도) 높은 점수
    rsi_inverted = 100 - rsi_val
    score_rsi = percentile_rank(
        [100 - r for r in universe_rsi], rsi_inverted
    )

    # 3. 감성 점수 (-1~1 → 0~1)
    sentiment_val = candidate.get("sentiment", 0) or 0
    score_sentiment = (sentiment_val + 1.0) / 2.0

    # 4. 매크로 방향 (-1~1 → 0~1)
    score_macro = (macro_direction + 1.0) / 2.0

    # 가중 합산
    composite = (
        score_return * weights["return"]
        + score_rsi * weights["rsi"]
        + score_sentiment * weights["sentiment"]
        + score_macro * weights["macro"]
    )

    sub_scores = {
        "return": round(score_return, 4),
        "rsi": round(score_rsi, 4),
        "sentiment": round(score_sentiment, 4),
        "macro": round(score_macro, 4),
    }

    return round(composite, 4), sub_scores
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python3 -m pytest tests/test_f18_composite_score.py -v`
Expected: PASS

- [ ] **Step 5: tests.json F18 → passing, prd.md 체크, 커밋**

```bash
git add analysis/composite_score.py tests/test_f18_composite_score.py
git commit -m "feat(F18): 복합 점수 엔진 — Percentile Rank, 4팩터 Equal Weight"
```

---

## Task 6: screener.py 고도화 (F19)

**Files:**
- Modify: `analysis/screener.py`
- Create: `tests/test_f19_screener_v2.py`

- [ ] **Step 1: 테스트 작성**

```python
# tests/test_f19_screener_v2.py
import json
import sys, os
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def test_merge_universe():
    """기존 스크리닝 + opportunities 통합"""
    from analysis.screener import merge_universe
    existing = [{"ticker": "NVDA", "name": "NVIDIA", "sector": "AI"}]
    opps = [{"ticker": "012450.KS", "name": "한화에어로스페이스",
             "discovered_via": "방산 수주"}]
    merged = merge_universe(existing, opps)
    tickers = [m["ticker"] for m in merged]
    assert "NVDA" in tickers
    assert "012450.KS" in tickers

def test_merge_universe_dedup():
    """중복 종목 제거"""
    from analysis.screener import merge_universe
    existing = [{"ticker": "NVDA", "name": "NVIDIA"}]
    opps = [{"ticker": "NVDA", "name": "NVIDIA", "discovered_via": "AI"}]
    merged = merge_universe(existing, opps)
    assert len(merged) == 1

def test_screener_report_has_scores(tmp_path):
    """리포트에 복합 점수가 포함되는지"""
    from analysis.screener import generate_screener_report
    highlights = [
        {"ticker": "012450.KS", "name": "한화에어로스페이스",
         "sector": "방산", "market": "KR", "price": 350000,
         "change_pct": 2.5, "day_change": 2.5,
         "composite_score": 0.82,
         "sub_scores": {"return": 0.8, "rsi": 0.7, "sentiment": 0.9, "macro": 0.85},
         "month_return": 12.5, "volume": 1000000}
    ]
    # 기존 시그니처: generate_screener_report(sector_results: dict, highlights: list)
    report = generate_screener_report({}, highlights)
    assert "한화에어로스페이스" in report
    # 복합 점수가 리포트에 포함되어야 함 (기존 포맷 유지하되 점수 추가)
    assert "82" in report or "0.82" in report or "점수" in report
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `python3 -m pytest tests/test_f19_screener_v2.py -v`
Expected: FAIL

- [ ] **Step 3: screener.py에 merge_universe, 복합 점수 통합, 리포트 개선 구현**

기존 `run()` 함수 수정 + 신규 함수 추가:

```python
def merge_universe(existing: list, opportunities: list) -> list:
    """기존 스크리닝 대상 + 발굴 종목 병합 (중복 제거)"""
    seen = set()
    merged = []
    for item in existing + opportunities:
        if item["ticker"] not in seen:
            seen.add(item["ticker"])
            merged.append(item)
    return merged
```

`generate_screener_report(sector_results, highlights)` 수정 — highlights에 composite_score가 있으면 점수 행 추가:

```python
# generate_screener_report 함수 내, 하이라이트 테이블 생성부 수정:
# 기존: | 순위 | 종목 | 섹터 | 현재가 | 1개월 수익률 | 일간 등락 |
# 변경: | 순위 | 종목 | 섹터 | 현재가 | 수익률 | 점수 |
for i, h in enumerate(highlights, 1):
    score_str = ""
    if h.get("composite_score") is not None:
        score_str = f"{h['composite_score']:.0%}" if h['composite_score'] <= 1 else f"{h['composite_score']}"
    lines.append(
        f"| {i} | {h.get('name', '')} ({h.get('ticker', '')}) "
        f"| {h.get('sector', '')} | {h.get('price', '')} "
        f"| {h.get('month_return', ''):.1f}% | {score_str} |"
    )
    # sub_scores가 있으면 분해 표시
    sub = h.get("sub_scores", {})
    if sub:
        lines.append(
            f"|   | ↳ 수익률 {sub.get('return', 0):.0%} "
            f"| RSI {sub.get('rsi', 0):.0%} "
            f"| 감성 {sub.get('sentiment', 0):.0%} "
            f"| 매크로 {sub.get('macro', 0):.0%} | |"
        )
```

`run()` 함수 수정 — opportunities.json 읽어서 통합:

```python
# run() 내부, screen_sectors() 호출 후:
opp_path = OUTPUT_DIR / "opportunities.json"
opp_tickers = []
if opp_path.exists():
    with open(opp_path) as f:
        opp_data = json.load(f)
    opp_tickers = [
        {"ticker": o["ticker"], "name": o.get("name", ""),
         "sector": "발굴", "discovered_via": o.get("discovered_via", "")}
        for o in opp_data.get("opportunities", [])
    ]

# 유니버스 병합
all_tickers = merge_universe(existing_tickers, opp_tickers)
```

- [ ] **Step 4: 테스트 통과 + 기존 screener 테스트도 통과 확인**

Run: `python3 -m pytest tests/test_f19_screener_v2.py tests/test_f05_collectors.py -v`
Expected: PASS

- [ ] **Step 5: tests.json F19 → passing, prd.md 체크, 커밋**

```bash
git add analysis/screener.py tests/test_f19_screener_v2.py
git commit -m "feat(F19): screener 고도화 — 복합 점수 통합, 유니버스 확장"
```

---

## Task 7: 뉴스 수집 목적 분리 (F20)

**Files:**
- Modify: `data/fetch_news.py`
- Create: `tests/test_f20_news_split.py`

- [ ] **Step 1: 테스트 작성**

```python
# tests/test_f20_news_split.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def test_fetch_news_no_opportunity_keywords():
    """fetch_news의 collect_news가 opportunity 키워드를 사용하지 않는지"""
    import inspect
    from data.fetch_news import collect_news
    source = inspect.getsource(collect_news)
    # opportunity 카테고리 Brave 검색이 제거되었는지 확인
    # fetch_news는 stock/macro/geopolitics만 담당해야 함
    assert "opportunity" not in source.lower() or "skip" in source.lower() or "제외" in source

def test_fetch_news_output_categories():
    """fetch_news 출력의 카테고리가 모니터링 전용인지"""
    from unittest.mock import patch, MagicMock
    from data.fetch_news import run
    # API 호출을 모킹하여 결과 확인
    with patch("data.fetch_news.fetch_google_news_rss", return_value=[]):
        with patch("data.fetch_news.search_brave_news", return_value=[]):
            result = run()
            # opportunity 카테고리가 결과에 없어야 함
            for item in result:
                assert item.get("category", "") != "opportunity", \
                    f"fetch_news가 opportunity 카테고리를 반환함: {item}"

def test_opportunity_handled_by_fetch_opportunities():
    """발굴 뉴스는 fetch_opportunities가 전담하는지"""
    from data.fetch_opportunities import run as opp_run
    assert callable(opp_run)
```

- [ ] **Step 2: fetch_news.py에서 opportunity 카테고리 수집 코드를 fetch_opportunities.py로 이관**

config.py의 `MACRO_KEYWORDS`에서 `"category": "opportunity"` 항목이 있다면 해당 키워드의 Brave 검색을 fetch_news에서 제거. fetch_opportunities.py가 이제 발굴 전담.

- [ ] **Step 3: 기존 뉴스 테스트 + 새 테스트 통과 확인**

Run: `python3 -m pytest tests/test_f20_news_split.py tests/test_f05_collectors.py -v`
Expected: PASS

- [ ] **Step 4: tests.json F20 → passing, prd.md 체크, 커밋**

```bash
git add data/fetch_news.py tests/test_f20_news_split.py config.py
git commit -m "feat(F20): 뉴스 수집 목적 분리 — fetch_news는 모니터링 전용"
```

---

## Task 8: run_pipeline.py 통합 + 스키마 검증

**Files:**
- Modify: `run_pipeline.py`
- Modify: `utils/schema.py`

- [ ] **Step 1: run_pipeline.py에 fetch_opportunities 단계 추가**

`fetch_news()` 호출 뒤, `aggregate_daily()` 전에:

```python
# Phase 4: 종목 발굴
try:
    from data.fetch_opportunities import run as fetch_opportunities
    opp_results = fetch_opportunities()
    record_module_status(engine, "fetch_opportunities", opp_results,
                         success_key="ticker")
except Exception as e:
    logger.error(f"fetch_opportunities 실패: {e}")
```

- [ ] **Step 2: schema.py에 opportunities.json 스키마 추가**

```python
"opportunities.json": {
    "top_level": {"updated_at": str, "keywords": list, "opportunities": list},
    "items_key": "opportunities",
    "item_fields": {
        "ticker": str, "name": str, "discovered_via": str,
    }
},
```

- [ ] **Step 3: 전체 테스트 통과 확인**

Run: `python3 -m pytest tests/ -v`
Expected: 모든 테스트 PASS

- [ ] **Step 4: 커밋**

```bash
git add run_pipeline.py utils/schema.py
git commit -m "feat(F17): run_pipeline에 fetch_opportunities 통합 + 스키마 검증"
```

---

## Task 9: agent_commands 디렉토리 + 문서 업데이트

**Files:**
- Create: `output/intel/agent_commands/.gitkeep`
- Modify: `PHASE4_DISCUSSION.md`
- Modify: `JARVIS_INTEGRATION.md`
- Modify: `AGENT_GUIDE.md`

- [ ] **Step 1: agent_commands 디렉토리 생성 + .gitignore 예외 추가**

```bash
mkdir -p output/intel/agent_commands
touch output/intel/agent_commands/.gitkeep
# output/은 .gitignore에 있으므로 예외 추가
echo '!output/intel/agent_commands/.gitkeep' >> .gitignore
git add -f output/intel/agent_commands/.gitkeep
```

- [ ] **Step 2: JARVIS_INTEGRATION.md에 Phase 4 연동 명세 추가**

자비스 05:30 크론잡이 `discovery_keywords.json`을 생성하고 `fetch_opportunities.py`를 실행하는 방법 문서화.

- [ ] **Step 3: AGENT_GUIDE.md에 opportunities.json 구조 추가**

에이전트가 읽을 수 있는 JSON 인터페이스에 opportunities.json 추가.

- [ ] **Step 4: 커밋**

```bash
git add output/intel/agent_commands/.gitkeep JARVIS_INTEGRATION.md AGENT_GUIDE.md PHASE4_DISCUSSION.md
git commit -m "docs: Phase 4 연동 명세 + 에이전트 가이드 업데이트"
```

---

## Task 10: 최종 통합 테스트 + tests.json/prd.md 최종 업데이트

- [ ] **Step 1: 전체 테스트 실행**

Run: `python3 -m pytest tests/ -v`
Expected: 모든 테스트 PASS (362 + 신규 ~60개 = 420+)

- [ ] **Step 2: ruff 린트 확인**

Run: `ruff check . && ruff format --check .`
Expected: 경고 없음

- [ ] **Step 3: tests.json summary 최종 업데이트**

```json
"summary": {
  "total": 20,
  "passing": 20,
  "failing": 0,
  "last_updated": "2026-03-26"
}
```

- [ ] **Step 4: prd.md 전체 체크 확인**

F16~F20 모두 `[x]` 체크

- [ ] **Step 5: 최종 커밋**

```bash
git add tests.json prd.md
git commit -m "feat: Phase 4 종목 발굴 고도화 완료 — F16~F20 전체 통과"
```

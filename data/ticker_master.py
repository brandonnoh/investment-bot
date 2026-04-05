#!/usr/bin/env python3
"""
종목 사전 관리 — KRX/미국 종목 매핑, 퍼지 매칭, 코드 추출
시드 데이터(PORTFOLIO + SCREENING_TARGETS)를 DB에 저장하고,
텍스트에서 종목명/코드를 추출하는 유틸리티 제공.
"""

import difflib
import re
import sqlite3
import sys
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

KST = timezone(timedelta(hours=9))
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "db" / "history.db"


def resolve_alias(name: str) -> str:
    """별칭을 정식 종목명으로 변환. 별칭 없으면 원본 반환."""
    return config.TICKER_ALIASES.get(name, name)


def find_tickers(query: str, master: list, threshold: float = 0.6) -> list:
    """종목명 퍼지 매칭.

    Args:
        query: 검색할 종목명 (별칭 가능)
        master: 종목 사전 리스트 [{"ticker": ..., "name": ...}, ...]
        threshold: difflib 매칭 임계값 (기본 0.6)

    Returns:
        매칭된 종목 정보 리스트
    """
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
    """텍스트에서 한국 종목코드(6자리) 추출.

    괄호 안의 6자리 숫자를 종목코드로 인식.
    예: '한화에어로스페이스(012450)' → ['012450']
    """
    pattern = re.compile(r"[\(\[]\s*(\d{6})\s*[\)\]]")
    return pattern.findall(text)


def extract_us_tickers(text: str) -> list:
    """텍스트에서 미국 티커 추출.

    $TSLA 패턴 우선, 없으면 대문자 단어 중 US_TICKER_MAP에 있는 것 추출.
    일반 영어 약어(AI, CEO 등)는 제외.
    """
    # $TSLA 패턴
    dollar_pattern = re.compile(r"\$([A-Z]{1,5})\b")
    dollar_matches = dollar_pattern.findall(text)
    if dollar_matches:
        return [t for t in dollar_matches if t in config.US_TICKER_MAP]

    # 대문자 단어 중 US_TICKER_MAP에 있는 것
    word_pattern = re.compile(r"\b([A-Z]{1,5})\b")
    candidates = word_pattern.findall(text)
    # 일반 영단어 제외
    common_words = {
        "AI",
        "CEO",
        "IPO",
        "ETF",
        "IT",
        "US",
        "UK",
        "EU",
        "GDP",
        "API",
        "THE",
        "AND",
        "FOR",
        "BUT",
        "NOT",
        "ALL",
        "NEW",
        "TOP",
        "BIG",
        "LOW",
        "HIGH",
        "SEC",
        "FED",
        "IMF",
    }
    return [
        t for t in candidates if t in config.US_TICKER_MAP and t not in common_words
    ]


def extract_companies(text: str, master: list) -> list:
    """텍스트에서 종목명 직접 매칭 (긴 이름부터 매칭, 중복 방지).

    Args:
        text: 검색 대상 텍스트
        master: 종목 사전 리스트

    Returns:
        텍스트에서 발견된 종목 정보 리스트
    """
    found = []
    remaining = text
    # 긴 이름부터 매칭하여 '삼성전자'가 '삼성'보다 먼저 매칭되도록
    sorted_items = sorted(master, key=lambda x: len(x["name"]), reverse=True)
    for item in sorted_items:
        if item["name"] in remaining:
            found.append(item)
            remaining = remaining.replace(item["name"], " ")
    return found


def save_master_to_db(conn: sqlite3.Connection, master: list):
    """종목 사전을 DB에 저장 (UPSERT).

    Args:
        conn: SQLite 연결 객체
        master: 종목 사전 리스트
    """
    now = datetime.now(KST).isoformat()
    for item in master:
        conn.execute(
            """INSERT OR REPLACE INTO ticker_master
               (ticker, name, name_en, market, sector, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                item["ticker"],
                item["name"],
                item.get("name_en", ""),
                item.get("market", ""),
                item.get("sector", ""),
                now,
            ),
        )
    conn.commit()


def load_master_from_db(conn: sqlite3.Connection) -> list:
    """DB에서 종목 사전 로드.

    Returns:
        종목 사전 리스트 [{"ticker": ..., "name": ..., ...}, ...]
    """
    cursor = conn.execute(
        "SELECT ticker, name, name_en, market, sector FROM ticker_master ORDER BY ticker"
    )
    return [
        {
            "ticker": r[0],
            "name": r[1],
            "name_en": r[2],
            "market": r[3],
            "sector": r[4],
        }
        for r in cursor.fetchall()
    ]


def get_seed_master() -> list:
    """초기 시드 종목 사전 생성 (PORTFOLIO + SCREENING_TARGETS에서 추출).

    Returns:
        종목 사전 리스트 (중복 제거)
    """
    seen = set()
    master = []

    # config.PORTFOLIO에서 추출
    for p in config.PORTFOLIO_LEGACY:
        if p["ticker"] not in seen:
            seen.add(p["ticker"])
            market = (
                "COMMODITY"
                if "GOLD" in p["ticker"]
                else ("KR" if p["ticker"].endswith((".KS", ".KQ")) else "US")
            )
            master.append(
                {
                    "ticker": p["ticker"],
                    "name": p["name"],
                    "market": market,
                    "sector": "",
                }
            )

    # SCREENING_TARGETS에서 추출
    # analysis/screener.py에 정의됨 (config.py가 아님)
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
                    master.append(
                        {
                            "ticker": t["ticker"],
                            "name": t["name"],
                            "market": market,
                            "sector": sector_name,
                        }
                    )

    return master


def run(conn=None):
    """종목 사전 초기화/갱신. 시드 데이터를 DB에 저장.

    Args:
        conn: SQLite 연결 객체 (None이면 기본 DB 사용)

    Returns:
        종목 사전 리스트
    """
    own_conn = False
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH))
        own_conn = True
    master = get_seed_master()
    save_master_to_db(conn, master)
    print(f"  ✅ 종목 사전 저장 완료: {len(master)}개 종목")
    if own_conn:
        conn.close()
    return master


if __name__ == "__main__":
    result = run()
    print(f"\n종목 사전 ({len(result)}개):")
    for item in result:
        print(
            f"  {item['ticker']:15s} {item['name']:20s} {item['market']:5s} {item['sector']}"
        )

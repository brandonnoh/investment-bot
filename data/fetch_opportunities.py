#!/usr/bin/env python3
"""
키워드 기반 종목 발굴 — 파이프라인 오케스트레이션
에이전트가 생성한 discovery_keywords.json을 읽어
뉴스를 검색하고, 종목 사전과 매칭하여 투자 후보를 발굴.

검색/추출 로직: data.fetch_opportunities_search
"""

import json
import logging
import os
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

# 검색/추출 레이어 — re-export (외부 코드가 fetch_opportunities에서 직접 임포트 가능)
from data.fetch_opportunities_search import (  # noqa: F401
    search_brave,
    search_naver_news,
    extract_opportunities,
)

try:
    from data.ticker_master import (
        load_master_from_db,
    )
except ImportError:
    pass

try:
    from analysis.fallback_keywords import ensure_fresh_keywords
except ImportError:
    ensure_fresh_keywords = None

KST = timezone(timedelta(hours=9))
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "db" / "history.db"
OUTPUT_DIR = PROJECT_ROOT / "output" / "intel"
KEYWORDS_PATH = OUTPUT_DIR / "discovery_keywords.json"


def parse_keywords(data: dict) -> list:
    """discovery_keywords.json 데이터에서 키워드 리스트 추출.

    Args:
        data: discovery_keywords.json 파싱 결과

    Returns:
        키워드 딕셔너리 리스트 (priority 순 정렬)
    """
    keywords = data.get("keywords", [])
    # priority 기준 정렬 (낮을수록 높은 우선순위)
    keywords.sort(key=lambda k: k.get("priority", 99))
    return keywords


def save_keywords_to_db(conn, keywords: list, generated_at: str):
    """에이전트 키워드를 DB에 저장.

    Args:
        conn: sqlite3.Connection
        keywords: 키워드 리스트
        generated_at: 키워드 생성 시각 (ISO 형식)
    """
    cursor = conn.cursor()
    for kw in keywords:
        cursor.execute(
            """INSERT INTO agent_keywords
               (keyword, category, priority, reasoning, generated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                kw.get("keyword", ""),
                kw.get("category", ""),
                kw.get("priority", 5),
                kw.get("reasoning", ""),
                generated_at,
            ),
        )
    conn.commit()
    logger.info(f"에이전트 키워드 DB 저장: {len(keywords)}건")


def save_opportunities_to_db(conn, opportunities: list):
    """발굴 종목을 DB에 저장.

    Args:
        conn: sqlite3.Connection
        opportunities: 종목 후보 리스트
    """
    now = datetime.now(KST).isoformat()
    cursor = conn.cursor()
    for opp in opportunities:
        cursor.execute(
            """INSERT INTO opportunities
               (ticker, name, discovered_at, discovered_via, source,
                composite_score, score_sentiment, score_macro, price_at_discovery, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'discovered')""",
            (
                opp.get("ticker", ""),
                opp.get("name", ""),
                now,
                opp.get("discovered_via", ""),
                opp.get("source", ""),
                opp.get("composite_score"),
                opp.get("score_sentiment"),
                opp.get("score_macro"),
                opp.get("price_at_discovery"),
            ),
        )
    conn.commit()
    logger.info(f"발굴 종목 DB 저장: {len(opportunities)}건")


def generate_json(keywords: list, opportunities: list) -> dict:
    """opportunities.json 생성용 딕셔너리 반환.

    Args:
        keywords: 사용된 키워드 리스트
        opportunities: 발굴된 종목 리스트

    Returns:
        JSON 직렬화 가능한 딕셔너리
    """
    now = datetime.now(KST).isoformat()

    # 키워드별 발굴 건수 집계
    by_keyword: dict = {}
    for opp in opportunities:
        kw = opp.get("discovered_via", "unknown")
        by_keyword[kw] = by_keyword.get(kw, 0) + 1

    # 평균 복합 점수 계산
    scores = [
        opp["composite_score"]
        for opp in opportunities
        if opp.get("composite_score") is not None
    ]
    avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0

    summary = {
        "total_count": len(opportunities),
        "by_keyword": by_keyword,
        "avg_score": avg_score,
    }

    return {
        "updated_at": now,
        "keywords": keywords,
        "opportunities": opportunities,
        "total_count": len(opportunities),
        "summary": summary,
    }


def run(conn=None, keywords_path=None, output_dir=None) -> list:
    """종목 발굴 파이프라인 실행.

    1. discovery_keywords.json 읽기
    2. 키워드별 Brave/Naver 뉴스 검색
    3. 종목 사전과 매칭하여 후보 추출
    4. DB + JSON 저장

    Args:
        conn: sqlite3.Connection (None이면 기본 DB)
        keywords_path: 키워드 파일 경로 (None이면 기본 경로)
        output_dir: 출력 디렉토리 (None이면 기본 경로)

    Returns:
        발굴된 종목 리스트
    """
    kw_path = Path(keywords_path) if keywords_path else KEYWORDS_PATH
    out_dir = Path(output_dir) if output_dir else OUTPUT_DIR

    # 1. 키워드 freshness 확인 (없거나 25h 경과 시 fallback 자동 생성)
    if ensure_fresh_keywords is not None:
        ensure_fresh_keywords(kw_path, out_dir)

    if not kw_path.exists():
        logger.warning("Fallback 키워드 생성 실패 — 종목 발굴 건너뜀")
        return []

    try:
        with open(kw_path) as f:
            kw_data = json.load(f)
    except Exception as e:
        logger.error(f"키워드 파일 읽기 실패: {e}")
        return []

    keywords = parse_keywords(kw_data)
    if not keywords:
        logger.info("키워드 없음 — 종목 발굴 건너뜀")
        return []

    generated_at = kw_data.get("generated_at", datetime.now(KST).isoformat())

    # 2. DB 연결
    own_conn = False
    if conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH))
        own_conn = True

    # 3. 종목 사전 로드
    try:
        master = load_master_from_db(conn)
    except Exception:
        master = []
    if not master:
        # DB에 없으면 시드 데이터로 초기화
        try:
            from data.ticker_master import run as init_master

            master = init_master(conn)
        except Exception as e:
            logger.warning(f"종목 사전 초기화 실패: {e}")
            master = []

    # 4. 키워드 DB 저장
    try:
        save_keywords_to_db(conn, keywords, generated_at)
    except Exception as e:
        logger.warning(f"키워드 DB 저장 실패: {e}")

    # 5. 키워드별 뉴스 검색 + 종목 추출
    search_count = config.OPPORTUNITY_CONFIG.get("search_count", 10)
    all_opportunities = []
    seen_tickers = set()

    for kw_info in keywords:
        keyword = kw_info["keyword"]
        logger.info(f"🔍 키워드 검색: {keyword}")

        # Brave 검색
        brave_results = search_brave(keyword, count=search_count)

        # Naver 검색 (선택)
        naver_results = search_naver_news(keyword, count=search_count)

        # 합산
        all_news = brave_results + naver_results

        if not all_news:
            logger.info(f"  뉴스 없음: {keyword}")
            continue

        # 종목 추출
        opps = extract_opportunities(all_news, master, keyword)

        # 글로벌 중복 제거
        for opp in opps:
            if opp["ticker"] not in seen_tickers:
                seen_tickers.add(opp["ticker"])
                all_opportunities.append(opp)

    # 6. 후보 수 제한
    max_candidates = config.OPPORTUNITY_CONFIG.get("max_candidates", 100)
    all_opportunities = all_opportunities[:max_candidates]

    # 6.5 복합 점수 계산 (기본 팩터만 — 감성 + 매크로)
    try:
        from analysis.composite_score import calculate_macro_direction

        # 매크로 데이터 로드
        macro_path = out_dir / "macro.json"
        macro_data = {}
        if macro_path.exists():
            with open(macro_path) as f:
                macro_json = json.load(f)
                for ind in macro_json.get("indicators", []):
                    macro_data[ind["ticker"]] = {
                        "value": ind.get("value"),
                        "change_pct": ind.get("change_pct"),
                    }
        macro_direction = calculate_macro_direction(macro_data)

        for opp in all_opportunities:
            sentiment = opp.get("sentiment") or 0
            # 단순 점수: 감성(50%) + 매크로(50%)
            sentiment_score = (sentiment + 1.0) / 2.0
            macro_score = (macro_direction + 1.0) / 2.0
            opp["composite_score"] = round(sentiment_score * 0.5 + macro_score * 0.5, 4)
            opp["score_sentiment"] = round(sentiment_score, 4)
            opp["score_macro"] = round(macro_score, 4)
        logger.info(
            f"복합 점수 계산 완료: {len(all_opportunities)}건 (macro={macro_direction:.2f})"
        )
    except Exception as e:
        logger.warning(f"복합 점수 계산 실패: {e}")

    # 6.9 price_at_discovery 수집 — Yahoo Finance 현재가
    try:
        from data.fetch_prices import fetch_yahoo_quote as _fetch_quote

        for opp in all_opportunities:
            if opp.get("price_at_discovery") is None:
                try:
                    meta = _fetch_quote(opp["ticker"])
                    opp["price_at_discovery"] = meta.get("regularMarketPrice")
                except Exception:
                    pass  # 가격 조회 실패 시 None 유지
    except ImportError:
        pass

    # 7. DB 저장
    if all_opportunities:
        try:
            save_opportunities_to_db(conn, all_opportunities)
        except Exception as e:
            logger.warning(f"발굴 종목 DB 저장 실패: {e}")

    # 8. JSON 파일 저장
    out_dir.mkdir(parents=True, exist_ok=True)
    json_data = generate_json(
        [
            {
                "keyword": k["keyword"],
                "category": k.get("category", ""),
                "priority": k.get("priority", 5),
            }
            for k in keywords
        ],
        all_opportunities,
    )
    json_path = out_dir / "opportunities.json"
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        print(f"  ✅ 종목 발굴 완료: {len(all_opportunities)}건 → {json_path}")
    except Exception as e:
        logger.error(f"opportunities.json 저장 실패: {e}")

    if own_conn:
        conn.close()

    return all_opportunities


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(f"\n발굴 종목 ({len(result)}건):")
    for opp in result:
        print(f"  {opp['ticker']:15s} {opp['name']:20s} via {opp['discovered_via']}")

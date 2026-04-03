#!/usr/bin/env python3
"""
키워드 기반 종목 발굴 — Brave/Naver 뉴스 검색, 종목 매칭, DB 저장
에이전트가 생성한 discovery_keywords.json을 읽어
뉴스를 검색하고, 종목 사전과 매칭하여 투자 후보를 발굴.
"""

import gzip
import json
import logging
import os
import re
import sqlite3
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

try:
    from analysis.sentiment import calculate_sentiment
except ImportError:

    def calculate_sentiment(title, summary):
        return 0.0


try:
    from data.ticker_master import (
        extract_ticker_codes,
        extract_companies,
        extract_us_tickers,
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


def search_brave(query: str, count: int = 10) -> list:
    """Brave Search API로 뉴스 검색.

    Args:
        query: 검색 키워드
        count: 결과 수 (기본 10)

    Returns:
        뉴스 결과 리스트 [{"title", "description", "url"}, ...]
    """
    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        logger.warning("BRAVE_API_KEY 미설정 — Brave 검색 건너뜀")
        return []

    encoded_q = urllib.parse.quote(query)
    url = (
        f"https://api.search.brave.com/res/v1/news/search"
        f"?q={encoded_q}&count={count}&search_lang=ko"
    )
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key,
        },
    )

    try:
        resp = urllib.request.urlopen(req, timeout=15)
        raw = resp.read()
        # gzip 압축 응답 자동 처리
        if resp.headers.get("Content-Encoding") == "gzip" or raw[:2] == b'\x1f\x8b':
            raw = gzip.decompress(raw)
        data = json.loads(raw)
        results = data.get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "description": r.get("description", ""),
                "url": r.get("url", ""),
                "source": "brave",
            }
            for r in results
        ]
    except Exception as e:
        logger.error(f"Brave 검색 실패: {e}")
        return []


def search_naver_news(query: str, count: int = 10) -> list:
    """Naver 뉴스 검색 API (선택사항 — 환경변수 없으면 빈 결과).

    Args:
        query: 검색 키워드
        count: 결과 수 (기본 10)

    Returns:
        뉴스 결과 리스트 [{"title", "description", "url"}, ...]
    """
    client_id = os.environ.get("NAVER_CLIENT_ID", "")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return []

    encoded_q = urllib.parse.quote(query)
    url = (
        f"https://openapi.naver.com/v1/search/news.json"
        f"?query={encoded_q}&display={count}&sort=date"
    )
    req = urllib.request.Request(
        url,
        headers={
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
        },
    )

    try:
        resp = urllib.request.urlopen(req, timeout=15)
        raw = resp.read()
        data = json.loads(raw)
        items = data.get("items", [])
        # HTML 태그 제거
        tag_re = re.compile(r"<[^>]+>")
        return [
            {
                "title": tag_re.sub("", item.get("title", "")),
                "description": tag_re.sub("", item.get("description", "")),
                "url": item.get("link", ""),
                "source": "naver",
            }
            for item in items
        ]
    except Exception as e:
        logger.error(f"Naver 뉴스 검색 실패: {e}")
        return []


def extract_opportunities(news: list, master: list, keyword: str) -> list:
    """뉴스 결과에서 종목 후보 추출.

    각 뉴스에서 종목코드(6자리)와 종목명을 매칭하여 후보 리스트 생성.

    Args:
        news: 뉴스 결과 리스트
        master: 종목 사전 리스트
        keyword: 발굴 키워드

    Returns:
        종목 후보 리스트 [{"ticker", "name", "discovered_via", ...}, ...]
    """
    opportunities = []
    seen_tickers = set()

    for article in news:
        title = article.get("title", "")
        desc = article.get("description", "")
        url = article.get("url", "")
        source = article.get("source", "unknown")
        text = f"{title} {desc}"

        matched_items = []

        # 1. 종목코드(6자리) 추출
        codes = extract_ticker_codes(text)
        for code in codes:
            ticker = f"{code}.KS"
            # master에서 이름 찾기
            name = ""
            for item in master:
                if item["ticker"] == ticker:
                    name = item["name"]
                    break
            if not name:
                # .KQ도 시도
                ticker_kq = f"{code}.KQ"
                for item in master:
                    if item["ticker"] == ticker_kq:
                        ticker = ticker_kq
                        name = item["name"]
                        break
            if name:
                matched_items.append({"ticker": ticker, "name": name})

        # 2. 종목명 직접 매칭
        company_matches = extract_companies(text, master)
        for item in company_matches:
            matched_items.append({"ticker": item["ticker"], "name": item["name"]})

        # 3. 미국 티커 추출
        us_tickers = extract_us_tickers(text)
        for t in us_tickers:
            name = config.US_TICKER_MAP.get(t, t)
            matched_items.append({"ticker": t, "name": name})

        # 중복 제거 후 추가
        for m in matched_items:
            ticker = m["ticker"]
            if ticker not in seen_tickers:
                seen_tickers.add(ticker)
                sentiment = calculate_sentiment(title, desc)
                opportunities.append(
                    {
                        "ticker": ticker,
                        "name": m["name"],
                        "discovered_via": keyword,
                        "source": source,
                        "url": url,
                        "sentiment": sentiment,
                        "title": title,
                        "composite_score": None,
                        "price_at_discovery": None,
                    }
                )

    return opportunities


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
    return {
        "updated_at": now,
        "keywords": keywords,
        "opportunities": opportunities,
        "total_count": len(opportunities),
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
        logger.info(f"복합 점수 계산 완료: {len(all_opportunities)}건 (macro={macro_direction:.2f})")
    except Exception as e:
        logger.warning(f"복합 점수 계산 실패: {e}")

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

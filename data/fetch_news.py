#!/usr/bin/env python3
"""
뉴스 수집 모듈 — 포트폴리오 모니터링 전용 (RSS)
- RSS: 종목별 뉴스 + 매크로 키워드 (무료, 무제한)
- 투자 기회 발굴은 fetch_opportunities.py가 전담 (Brave Search)
출력: output/intel/news.json
"""

import json
import os
import sqlite3
import sys
import urllib.request
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import PORTFOLIO_LEGACY as PORTFOLIO, DB_PATH, OUTPUT_DIR, HTTP_RETRY_CONFIG
from db.init_db import init_db
from utils.http import retry_request

KST = timezone(timedelta(hours=9))
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/news/search"

# ── RSS로 수집할 종목 키워드 ──
TICKER_KEYWORDS = {
    "005930.KS": ["삼성전자 주가", "삼성전자 실적", "삼성전자 HBM"],
    "005380.KS": ["현대차 주가", "현대차 실적", "현대자동차 전기차"],
    "0117V0.KS": ["TIGER AI전력", "국내 AI전력 ETF", "한국 전력 AI"],
    "458730.KS": ["방산ETF", "한국 방위산업 주가", "방산주"],
    "TSLA": ["테슬라 주가", "테슬라 실적"],
    "GOOGL": ["알파벳 구글 주가", "구글 AI"],
    "XOP": ["XOP ETF", "미국 에너지 ETF", "유가 ETF"],
    "GOLD_KRW_G": ["금 현물 시세", "금값 전망", "골드 투자"],
}

# ── 매크로 키워드 — 카테고리별 수집 방식 ──
MACRO_KEYWORDS = {
    # RSS로 수집 (무료)
    "geopolitics": {
        "relevance": 0.9,
        "method": "rss",
        "keywords": [
            "이란 전쟁",
            "미중 무역전쟁",
            "트럼프 관세",
        ],
    },
    "macro": {
        "relevance": 0.8,
        "method": "rss",
        "keywords": [
            "코스피",
            "코스닥",
            "원달러 환율",
            "WTI 유가",
            "연준 금리",
            "한국 경제",
            "미국 증시",
        ],
    },
    # 국내 정정닸스 — 재테크에 직접 영향을 주는 정책/정세
    "kr_policy": {
        "relevance": 0.85,
        "method": "rss",
        "keywords": [
            "한국은행 금리",
            "기준금리 결정",
            "정부 예산 지출",
            "부동산 정책",
            "추경예산",
        ],
    },
    # 국내 정치 정세 — 시장 심리에 영향
    "kr_politics": {
        "relevance": 0.75,
        "method": "rss",
        "keywords": [
            "탄핵 선거",
            "대통령 선거",
            "국회 정급",
            "에코 시장",
        ],
    },
}  # end MACRO_KEYWORDS

# discovery_keywords.json 연동 함수
def load_discovery_keywords() -> list[dict]:
    """fetch_opportunities가 생성한 discovery_keywords.json 로드.
    기존 파일이 없으면 빈 리스트 반환."""
    keywords_path = OUTPUT_DIR / "agent_commands" / "discovery_keywords.json"
    if not keywords_path.exists():
        return []
    try:
        with open(keywords_path, encoding="utf-8") as f:
            data = json.load(f)
        kws = data.get("keywords", [])
        kws.sort(key=lambda k: k.get("priority", 99))
        return kws
    except Exception:
        return []


# ── Google News RSS (무료) ──


def fetch_google_news_rss(query: str, count: int = 5, lang: str = "ko") -> list[dict]:
    """Google News RSS로 무료 뉴스 수집 (자동 재시도)"""
    encoded = urllib.parse.quote(query)
    url = (
        f"https://news.google.com/rss/search?q={encoded}&hl={lang}&gl=KR&ceid=KR:{lang}"
    )
    body = retry_request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=10,
        max_retries=HTTP_RETRY_CONFIG["max_retries"],
        base_delay=HTTP_RETRY_CONFIG["base_delay"],
    )
    root = ET.fromstring(body)

    items = []
    for item in root.findall(".//item")[:count]:
        title = item.findtext("title", "")
        link = item.findtext("link", "")
        pub_date = item.findtext("pubDate", "")
        source = item.findtext("source", "")
        items.append(
            {
                "title": title,
                "url": link,
                "source": source,
                "published_at": pub_date,
            }
        )
    return items


# ── Brave Search API (유료) ──


def search_brave_news(query: str, count: int = 2) -> list[dict]:
    """Brave Search API로 뉴스 검색"""
    if not BRAVE_API_KEY:
        raise ValueError("BRAVE_API_KEY 환경변수가 설정되지 않았습니다")

    params = urllib.parse.urlencode(
        {
            "q": query,
            "count": count,
            "freshness": "pd",  # 최근 24시간
        }
    )
    url = f"{BRAVE_SEARCH_URL}?{params}"

    try:
        import gzip as _gzip
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": BRAVE_API_KEY,
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
                raw = _gzip.decompress(raw)
        data = json.loads(raw)
        return data.get("results", [])
    except urllib.error.URLError as e:
        raise ConnectionError(f"Brave Search 네트워크 오류: {e}")


# ── 관련도 스코어링 ──


def calculate_relevance(title: str, keywords: list[str]) -> float:
    """기사 제목 기반 관련도 스코어 계산 (0.0 ~ 1.0)"""
    title_lower = title.lower()
    matched = sum(1 for kw in keywords if kw.lower() in title_lower)
    if not keywords:
        return 0.5
    return round(min(matched / len(keywords), 1.0), 2)


# ── 뉴스 수집 ──


def collect_news() -> tuple[list[dict], int, int]:
    """하이브리드 뉴스 수집: RSS + Brave. (records, rss_count, brave_count) 반환"""
    now = datetime.now(KST).isoformat()
    all_news = []
    seen_urls = set()
    rss_count = 0
    brave_count = 0

    # 1. 종목별 뉴스 — RSS
    for stock in PORTFOLIO:
        ticker = stock["ticker"]
        name = stock["name"]
        keywords = TICKER_KEYWORDS.get(ticker)
        if not keywords:
            continue

        query = keywords[0]
        try:
            results = fetch_google_news_rss(query, count=3)
            for article in results:
                url = article.get("url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                news_item = {
                    "title": article["title"],
                    "summary": "",
                    "source": article["source"],
                    "url": url,
                    "published_at": article["published_at"],
                    "relevance_score": calculate_relevance(article["title"], keywords),
                    "category": "stock",
                    "tickers": [ticker],
                    "ticker_name": name,
                    "fetch_method": "rss",
                    "timestamp": now,
                }
                all_news.append(news_item)
                rss_count += 1

            print(f"  ✅ [RSS] {name}: {len(results)}건")

        except Exception as e:
            print(f"  ❌ [RSS] {name}: {e}")

    # 2. 매크로 키워드 — 방식에 따라 분기
    for category, info in MACRO_KEYWORDS.items():
        base_relevance = info["relevance"]
        method = info["method"]

        for kw in info["keywords"]:
            try:
                if method == "rss":
                    results = fetch_google_news_rss(kw, count=3)
                    for article in results:
                        url = article.get("url", "")
                        if url in seen_urls:
                            continue
                        seen_urls.add(url)

                        news_item = {
                            "title": article["title"],
                            "summary": "",
                            "source": article["source"],
                            "url": url,
                            "published_at": article["published_at"],
                            "relevance_score": base_relevance,
                            "category": category,
                            "tickers": [],
                            "ticker_name": kw,
                            "fetch_method": "rss",
                            "timestamp": now,
                        }
                        all_news.append(news_item)
                        rss_count += 1

                    print(f"  ✅ [RSS] {category} [{kw}]: {len(results)}건")

                elif method == "brave":
                    if not BRAVE_API_KEY:
                        print(f"  ⚠️  [Brave] {category} [{kw}]: API 키 없음 — 스킵")
                        continue

                    results = search_brave_news(kw, count=2)
                    for article in results:
                        url = article.get("url", "")
                        if url in seen_urls:
                            continue
                        seen_urls.add(url)

                        source = ""
                        meta_url = article.get("meta_url")
                        if isinstance(meta_url, dict):
                            source = meta_url.get("hostname", "")

                        news_item = {
                            "title": article.get("title", ""),
                            "summary": article.get("description", ""),
                            "source": source,
                            "url": url,
                            "published_at": article.get("age", ""),
                            "relevance_score": base_relevance,
                            "category": category,
                            "tickers": [],
                            "ticker_name": kw,
                            "fetch_method": "brave",
                            "timestamp": now,
                        }
                        all_news.append(news_item)
                        brave_count += 1

                    print(f"  ✅ [Brave] {category} [{kw}]: {len(results)}건")

            except Exception as e:
                print(f"  ❌ [{method.upper()}] {category} [{kw}]: {e}")

    # 3. discovery_keywords.json 연동 — 종목 발굴 키워드도 뉴스 수집
    discovery_kws = load_discovery_keywords()
    for kw_item in discovery_kws[:5]:  # 상위 5개만
        kw = kw_item.get("keyword", "")
        category = kw_item.get("category", "opportunity")
        if not kw:
            continue
        try:
            results = fetch_google_news_rss(kw, count=3)
            for article in results:
                url = article.get("url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                news_item = {
                    "title": article["title"],
                    "summary": "",
                    "source": article["source"],
                    "url": url,
                    "published_at": article["published_at"],
                    "relevance_score": 0.7,
                    "category": f"discovery_{category}",
                    "tickers": [],
                    "ticker_name": kw,
                    "fetch_method": "rss",
                    "timestamp": now,
                }
                all_news.append(news_item)
                rss_count += 1
            print(f"  ✅ [RSS] discovery [{kw[:20]}]: {len(results)}건")
        except Exception as e:
            print(f"  ❌ [RSS] discovery [{kw[:20]}]: {e}")

    # 관련도 높은 순으로 정렬
    all_news.sort(key=lambda x: x["relevance_score"], reverse=True)

    return all_news, rss_count, brave_count


def ensure_category_column():
    """news 테이블에 category 컬럼이 없으면 추가"""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(news)")
        columns = [row[1] for row in cursor.fetchall()]
        if "category" not in columns:
            cursor.execute("ALTER TABLE news ADD COLUMN category TEXT")
            conn.commit()
            print("  🔧 news 테이블에 category 컬럼 추가")
    finally:
        conn.close()


def save_to_db(records: list[dict]):
    """뉴스를 SQLite에 저장 (title+source 중복 무시)"""
    if not records:
        return

    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()
        # UNIQUE 인덱스가 없으면 기존 중복 정리 후 생성
        try:
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_news_title_source ON news (title, source)"
            )
        except sqlite3.IntegrityError:
            cursor.execute("""
                DELETE FROM news WHERE id NOT IN (
                    SELECT MIN(id) FROM news GROUP BY title, source
                )
            """)
            conn.commit()
            removed = cursor.rowcount
            print(f"  🧹 기존 중복 {removed}건 정리")
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_news_title_source ON news (title, source)"
            )
        inserted = 0
        skipped = 0
        for r in records:
            cursor.execute(
                """INSERT OR IGNORE INTO news (title, summary, source, url, published_at, relevance_score, sentiment, tickers, category)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    r["title"],
                    r["summary"],
                    r["source"],
                    r["url"],
                    r["published_at"],
                    r["relevance_score"],
                    r.get("sentiment"),
                    json.dumps(r["tickers"], ensure_ascii=False),
                    r.get("category", "stock"),
                ),
            )
            if cursor.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        conn.commit()
        print(f"  💾 뉴스 DB 저장: {inserted}건 (중복 {skipped}건 스킵)")
    finally:
        conn.close()


def save_to_json(records: list[dict], ticker_sentiment: Optional[dict] = None):
    """뉴스를 JSON 파일로 출력 (감성 집계 포함)"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "news.json"

    output = {
        "updated_at": datetime.now(KST).isoformat(),
        "count": len(records),
        "news": records,
    }
    if ticker_sentiment:
        output["ticker_sentiment"] = ticker_sentiment
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  📄 뉴스 JSON 저장: {output_path}")


def run():
    """뉴스 수집 파이프라인 실행"""
    from analysis.sentiment import (
        aggregate_sentiment_by_ticker_weighted,
        analyze_news_sentiment,
        save_sentiment_to_db,
    )

    print(f"\n📰 뉴스 수집 시작 — {datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}")

    # DB 초기화 확인
    if not DB_PATH.exists():
        init_db()
    ensure_category_column()

    # 뉴스 수집
    records, rss_count, brave_count = collect_news()

    # 감성 분석
    records = analyze_news_sentiment(records)
    ticker_sentiment = aggregate_sentiment_by_ticker_weighted(records)
    print(f"  🧠 감성 분석 완료: {len(records)}건, 종목별 {len(ticker_sentiment)}개")

    # 저장
    save_to_db(records)
    save_to_json(records, ticker_sentiment)

    # DB에 감성 점수 업데이트 (이미 INSERT된 레코드에 대해)
    try:
        conn = sqlite3.connect(str(DB_PATH))
        updates = [
            {
                "title": r["title"],
                "source": r["source"],
                "sentiment": r.get("sentiment"),
            }
            for r in records
            if r.get("sentiment") is not None
        ]
        save_sentiment_to_db(conn, updates)
        conn.close()
    except Exception as e:
        print(f"  ⚠️ 감성 점수 DB 업데이트 실패: {e}")

    print(
        f"\n✅ 뉴스 수집 완료: RSS {rss_count}건, Brave {brave_count}건 (합계 {len(records)}건)\n"
    )
    return records


if __name__ == "__main__":
    run()

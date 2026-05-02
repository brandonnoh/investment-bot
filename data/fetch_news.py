#!/usr/bin/env python3
"""
뉴스 수집 모듈 — 포트폴리오 모니터링 전용 (RSS)
- RSS: 종목별 뉴스 + 매크로 키워드 (무료, 무제한)
- 투자 기회 발굴은 fetch_opportunities.py가 전담 (Brave Search)
출력: output/intel/news.json
"""

import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, OUTPUT_DIR
from data.fetch_news_db import (  # noqa: F401  re-export
    ensure_category_column,
    save_to_db,
)
from data.fetch_news_sources import (  # noqa: F401  re-export
    BRAVE_API_KEY,
    calculate_relevance,
    fetch_google_news_rss,
    search_brave_news,
)
from db import ssot
from db.init_db import init_db

KST = timezone(timedelta(hours=9))


def _load_dynamic_keywords() -> list[str]:
    """Marcus가 생성한 오늘의 동적 키워드 로드 (없으면 빈 리스트)"""
    path = OUTPUT_DIR / "search_keywords.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        today = datetime.now(KST).strftime("%Y-%m-%d")
        if data.get("date") != today:
            return []  # 오늘 생성된 것만 사용
        keywords = data.get("keywords", [])
        if keywords:
            print(f"  📌 동적 키워드 {len(keywords)}개 로드: {keywords[:3]}...")
        return keywords
    except Exception:
        return []


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
        with keywords_path.open(encoding="utf-8") as f:
            data = json.load(f)
        kws = data.get("keywords", [])
        kws.sort(key=lambda k: k.get("priority", 99))
        return kws
    except Exception:
        return []


# ── 뉴스 수집 ──


def _collect_rss_stock_news(now: str, seen_urls: set) -> tuple[list[dict], int]:
    """종목별 RSS 뉴스 수집. (items, count) 반환"""
    items = []
    count = 0
    for stock in ssot.get_holdings():
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
                items.append(
                    {
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
                )
                count += 1
            print(f"  ✅ [RSS] {name}: {len(results)}건")
        except Exception as e:
            print(f"  ❌ [RSS] {name}: {e}")
    return items, count


def _collect_rss_macro_keyword(
    kw: str, category: str, base_relevance: float, now: str, seen_urls: set
) -> tuple[list[dict], int]:
    """RSS 방식 단일 매크로 키워드 수집. (items, count) 반환"""
    items = []
    count = 0
    results = fetch_google_news_rss(kw, count=3)
    for article in results:
        url = article.get("url", "")
        if url in seen_urls:
            continue
        seen_urls.add(url)
        items.append(
            {
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
        )
        count += 1
    print(f"  ✅ [RSS] {category} [{kw}]: {len(results)}건")
    return items, count


def _collect_brave_macro_keyword(
    kw: str, category: str, base_relevance: float, now: str, seen_urls: set
) -> tuple[list[dict], int]:
    """Brave 방식 단일 매크로 키워드 수집. (items, count) 반환"""
    items = []
    count = 0
    if not BRAVE_API_KEY:
        print(f"  ⚠️  [Brave] {category} [{kw}]: API 키 없음 — 스킵")
        return items, count
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
        items.append(
            {
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
        )
        count += 1
    print(f"  ✅ [Brave] {category} [{kw}]: {len(results)}건")
    return items, count


def _collect_macro_news(now: str, seen_urls: set) -> tuple[list[dict], int, int]:
    """매크로 키워드 뉴스 수집 (RSS + Brave). (items, rss_count, brave_count) 반환"""
    items = []
    rss_count = 0
    brave_count = 0
    for category, info in MACRO_KEYWORDS.items():
        base_relevance = info["relevance"]
        method = info["method"]
        for kw in info["keywords"]:
            try:
                if method == "rss":
                    new_items, cnt = _collect_rss_macro_keyword(
                        kw, category, base_relevance, now, seen_urls
                    )
                    items.extend(new_items)
                    rss_count += cnt
                elif method == "brave":
                    new_items, cnt = _collect_brave_macro_keyword(
                        kw, category, base_relevance, now, seen_urls
                    )
                    items.extend(new_items)
                    brave_count += cnt
            except Exception as e:
                print(f"  ❌ [{method.upper()}] {category} [{kw}]: {e}")
    return items, rss_count, brave_count


def _collect_discovery_news(now: str, seen_urls: set) -> tuple[list[dict], int]:
    """discovery_keywords.json 연동 뉴스 수집. (items, count) 반환"""
    items = []
    count = 0
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
                items.append(
                    {
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
                )
                count += 1
            print(f"  ✅ [RSS] discovery [{kw[:20]}]: {len(results)}건")
        except Exception as e:
            print(f"  ❌ [RSS] discovery [{kw[:20]}]: {e}")
    return items, count


def _collect_dynamic_keyword_news(now: str, seen_urls: set) -> tuple[list[dict], int]:
    """Marcus 동적 키워드로 RSS 뉴스 수집. (items, count) 반환"""
    items = []
    count = 0
    dynamic_keywords = _load_dynamic_keywords()
    for kw in dynamic_keywords:
        try:
            results = fetch_google_news_rss(kw, count=3)
            for article in results:
                url = article.get("url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                items.append(
                    {
                        "title": article["title"],
                        "summary": "",
                        "source": article["source"],
                        "url": url,
                        "published_at": article["published_at"],
                        "relevance_score": 0.85,
                        "category": "marcus_dynamic",
                        "tickers": [],
                        "ticker_name": kw,
                        "fetch_method": "rss",
                        "timestamp": now,
                    }
                )
                count += 1
            print(f"  ✅ [RSS] dynamic [{kw[:25]}]: {len(results)}건")
        except Exception as e:
            print(f"  ❌ [RSS] dynamic [{kw[:25]}]: {e}")
    return items, count


def collect_news() -> tuple[list[dict], int, int]:
    """하이브리드 뉴스 수집: RSS + Brave. (records, rss_count, brave_count) 반환"""
    now = datetime.now(KST).isoformat()
    all_news = []
    seen_urls: set = set()
    rss_count = 0
    brave_count = 0

    # 1. 종목별 뉴스 — RSS
    stock_items, stock_rss = _collect_rss_stock_news(now, seen_urls)
    all_news.extend(stock_items)
    rss_count += stock_rss

    # 2. 매크로 키워드 — 방식에 따라 분기
    macro_items, macro_rss, macro_brave = _collect_macro_news(now, seen_urls)
    all_news.extend(macro_items)
    rss_count += macro_rss
    brave_count += macro_brave

    # 3. discovery_keywords.json 연동 — 종목 발굴 키워드도 뉴스 수집
    disc_items, disc_rss = _collect_discovery_news(now, seen_urls)
    all_news.extend(disc_items)
    rss_count += disc_rss

    # 4. Marcus 동적 키워드 — 오늘 생성된 키워드로 추가 수집
    dynamic_items, dynamic_rss = _collect_dynamic_keyword_news(now, seen_urls)
    all_news.extend(dynamic_items)
    rss_count += dynamic_rss

    # 관련도 높은 순으로 정렬
    all_news.sort(key=lambda x: x["relevance_score"], reverse=True)

    return all_news, rss_count, brave_count


def save_to_json(records: list[dict], ticker_sentiment: dict | None = None):
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
    with output_path.open("w", encoding="utf-8") as f:
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
    # sentiment가 None인 레코드는 0.0으로 폴백 (DB NULL 방지)
    null_count = sum(1 for r in records if r.get("sentiment") is None)
    if null_count:
        print(f"  ⚠️ sentiment None {null_count}건 → 0.0 폴백")
        for r in records:
            if r.get("sentiment") is None:
                r["sentiment"] = 0.0
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

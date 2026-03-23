#!/usr/bin/env python3
"""
뉴스 수집 모듈 — Brave Search API
포트폴리오 종목별 최신 뉴스 수집 + 관련도 스코어링
출력: output/intel/news.json
"""
import json
import os
import sqlite3
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import PORTFOLIO, DB_PATH, OUTPUT_DIR
from db.init_db import init_db

KST = timezone(timedelta(hours=9))
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/news/search"

# 종목별 검색 키워드 매핑
TICKER_KEYWORDS = {
    "005930.KS": ["삼성전자", "Samsung Electronics"],
    "005380.KS": ["현대차", "현대자동차", "Hyundai Motor"],
    "0117V0.KS": ["AI 전력", "코리아AI전력", "AI 인프라 전력"],
    "458730.KS": ["미국 방산", "방산 ETF", "defense ETF"],
    "TSLA":      ["Tesla", "테슬라"],
    "GOOGL":     ["Google", "Alphabet", "구글", "알파벳"],
    "XOP":       ["oil gas ETF", "에너지 ETF", "유가"],
    "GC=F":      ["금 시세", "gold price", "금값"],
}

# 매크로 키워드 — 카테고리별 관련도 스코어
MACRO_KEYWORDS = {
    "geopolitics": {
        "relevance": 0.9,
        "keywords": [
            "미국 이란 전쟁 최신", "호르무즈 해협 봉쇄", "중동 전쟁 확전",
            "트럼프 이란 협상",
        ],
    },
    "macro": {
        "relevance": 0.8,
        "keywords": [
            "연준 Fed 금리 결정", "달러 인덱스 전망", "WTI 유가 전망",
            "원달러 환율 전망", "코스피 전망 분석",
        ],
    },
    "sector": {
        "relevance": 0.7,
        "keywords": [
            "에너지 ETF 강세 전망", "방산주 투자 전망", "AI 반도체 전망",
            "한국 방산 수출",
        ],
    },
    "opportunity": {
        "relevance": 0.85,
        "keywords": [
            "저평가 종목 발굴 추천", "외국인 순매수 종목", "52주 신저가 반등",
            "섹터 로테이션 전략",
        ],
    },
}


def search_brave_news(query: str, count: int = 5) -> list[dict]:
    """Brave Search API로 뉴스 검색"""
    if not BRAVE_API_KEY:
        raise ValueError("BRAVE_API_KEY 환경변수가 설정되지 않았습니다")

    params = urllib.parse.urlencode({
        "q": query,
        "count": count,
        "freshness": "pd",  # 최근 24시간
    })
    url = f"{BRAVE_SEARCH_URL}?{params}"
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "X-Subscription-Token": BRAVE_API_KEY,
    })

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
            return data.get("results", [])
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print(f"    ⚠️  Rate limit 초과 — 잠시 후 재시도")
        raise
    except urllib.error.URLError as e:
        raise ConnectionError(f"Brave Search 네트워크 오류: {e}")


def calculate_relevance(article: dict, keywords: list[str]) -> float:
    """기사의 종목 관련도 스코어 계산 (0.0 ~ 1.0)"""
    title = (article.get("title") or "").lower()
    description = (article.get("description") or "").lower()
    text = f"{title} {description}"

    score = 0.0
    matched = 0
    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower in title:
            score += 0.4  # 제목에 키워드 있으면 높은 점수
            matched += 1
        elif kw_lower in text:
            score += 0.2  # 본문에만 있으면 낮은 점수
            matched += 1

    # 매칭된 키워드 비율 반영
    if len(keywords) > 0:
        coverage = matched / len(keywords)
        score = min(score * (0.5 + 0.5 * coverage), 1.0)

    return round(score, 2)


def collect_news() -> list[dict]:
    """포트폴리오 종목별 뉴스 수집"""
    now = datetime.now(KST).isoformat()
    all_news = []
    seen_urls = set()

    # 1. 종목별 뉴스 수집
    for stock in PORTFOLIO:
        ticker = stock["ticker"]
        name = stock["name"]
        keywords = TICKER_KEYWORDS.get(ticker, [name])

        # 첫 번째 키워드로 검색
        query = keywords[0] if keywords else name
        try:
            results = search_brave_news(f"{query} 뉴스", count=3)
            for article in results:
                url = article.get("url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                relevance = calculate_relevance(article, keywords)
                news_item = {
                    "title": article.get("title", ""),
                    "summary": article.get("description", ""),
                    "source": article.get("meta_url", {}).get("hostname", "") if isinstance(article.get("meta_url"), dict) else "",
                    "url": url,
                    "published_at": article.get("age", ""),
                    "relevance_score": relevance,
                    "category": "stock",
                    "tickers": [ticker],
                    "ticker_name": name,
                    "timestamp": now,
                }
                all_news.append(news_item)

            print(f"  ✅ {name}: {len(results)}건 수집")

        except Exception as e:
            print(f"  ❌ {name} ({ticker}): {e}")

    # 2. 매크로 키워드 뉴스 수집 (카테고리별)
    for category, info in MACRO_KEYWORDS.items():
        base_relevance = info["relevance"]
        for kw in info["keywords"]:
            try:
                results = search_brave_news(kw, count=2)
                for article in results:
                    url = article.get("url", "")
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    news_item = {
                        "title": article.get("title", ""),
                        "summary": article.get("description", ""),
                        "source": article.get("meta_url", {}).get("hostname", "") if isinstance(article.get("meta_url"), dict) else "",
                        "url": url,
                        "published_at": article.get("age", ""),
                        "relevance_score": base_relevance,
                        "category": category,
                        "tickers": [],
                        "ticker_name": kw,
                        "timestamp": now,
                    }
                    all_news.append(news_item)

                print(f"  ✅ {category} [{kw}]: {len(results)}건 수집")

            except Exception as e:
                print(f"  ❌ {category} [{kw}]: {e}")

    # 관련도 높은 순으로 정렬
    all_news.sort(key=lambda x: x["relevance_score"], reverse=True)

    return all_news


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
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_news_title_source ON news (title, source)")
        except sqlite3.IntegrityError:
            # 기존 중복 데이터 정리: 같은 title+source 중 id가 작은 것만 남김
            cursor.execute("""
                DELETE FROM news WHERE id NOT IN (
                    SELECT MIN(id) FROM news GROUP BY title, source
                )
            """)
            conn.commit()
            removed = cursor.rowcount
            print(f"  🧹 기존 중복 {removed}건 정리")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_news_title_source ON news (title, source)")
        inserted = 0
        skipped = 0
        for r in records:
            cursor.execute(
                """INSERT OR IGNORE INTO news (title, summary, source, url, published_at, relevance_score, tickers, category)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (r["title"], r["summary"], r["source"], r["url"],
                 r["published_at"], r["relevance_score"],
                 json.dumps(r["tickers"], ensure_ascii=False),
                 r.get("category", "stock")),
            )
            if cursor.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        conn.commit()
        print(f"  💾 뉴스 DB 저장: {inserted}건 (중복 {skipped}건 스킵)")
    finally:
        conn.close()


def save_to_json(records: list[dict]):
    """뉴스를 JSON 파일로 출력"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "news.json"

    output = {
        "updated_at": datetime.now(KST).isoformat(),
        "count": len(records),
        "news": records,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  📄 뉴스 JSON 저장: {output_path}")


def run():
    """뉴스 수집 파이프라인 실행"""
    print(f"\n📰 뉴스 수집 시작 — {datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}")

    if not BRAVE_API_KEY:
        print("  ⚠️  BRAVE_API_KEY 미설정 — 뉴스 수집 건너뜀")
        print("  💡 설정 방법: export BRAVE_API_KEY=your_api_key")
        return []

    # DB 초기화 확인
    if not DB_PATH.exists():
        init_db()
    ensure_category_column()

    # 뉴스 수집
    records = collect_news()

    # 저장
    save_to_db(records)
    save_to_json(records)

    print(f"\n✅ 뉴스 수집 완료: {len(records)}건\n")
    return records


if __name__ == "__main__":
    run()

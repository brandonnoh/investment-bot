#!/usr/bin/env python3
"""자비스가 DB 뉴스를 읽기 위한 헬퍼 스크립트"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "history.db"

conn = sqlite3.connect(DB_PATH)

# category 컬럼 존재 여부 확인
cols = [r[1] for r in conn.execute("PRAGMA table_info(news)").fetchall()]
has_category = "category" in cols

# 중복 제거: title+source 기준 최신 것만, 관련도 높은 순 최대 20개
if has_category:
    rows = conn.execute("""
        SELECT category, title, source, published_at, relevance_score
        FROM news
        GROUP BY title, source
        ORDER BY relevance_score DESC, published_at DESC
        LIMIT 20
    """).fetchall()
else:
    rows = conn.execute("""
        SELECT 'general', title, source, published_at, relevance_score
        FROM news
        GROUP BY title, source
        ORDER BY relevance_score DESC, published_at DESC
        LIMIT 20
    """).fetchall()

conn.close()

if not rows:
    print("뉴스 없음")
else:
    current_cat = None
    for cat, title, source, pub, score in rows:
        display_cat = cat if cat else "기타"
        if display_cat != current_cat:
            cat_label = {
                "geopolitics": "🌍 지정학",
                "macro": "📊 매크로",
                "opportunity": "💡 투자기회",
                "sector": "📈 섹터",
                "stock": "🏢 종목",
                "general": "📰 일반",
                "기타": "📋 기타",
            }.get(display_cat, f"📋 {display_cat}")
            print(f"\n## {cat_label}")
            current_cat = display_cat
        print(f"- [{source}] {title} ({str(pub)[:10]}, 관련도:{score})")

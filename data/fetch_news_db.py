#!/usr/bin/env python3
"""
뉴스 DB 저장 레이어 — fetch_news.py에서 분리된 SQLite 저장 담당
- category 컬럼 마이그레이션
- title+source 기준 중복 제거 후 INSERT
- published_at ISO 8601 정규화 (RFC2822 → '%Y-%m-%d %H:%M:%S')
"""

import json
import sqlite3
import sys
from email.utils import parsedate_to_datetime
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH


def normalize_date(raw: str) -> str:
    """RFC2822 날짜 문자열을 SQLite 호환 ISO 8601 형식으로 변환.
    파싱 실패 시 원본 문자열 반환."""
    if not raw:
        return raw
    try:
        return parsedate_to_datetime(raw).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return raw  # 파싱 실패 시 원본 유지


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
            # published_at: RFC2822 → ISO 8601 정규화 (SQLite datetime() 호환)
            pub_at = normalize_date(r.get("published_at", "") or "")
            # sentiment: None이면 0.0으로 폴백 (NULL 방지)
            sentiment = r.get("sentiment")
            if sentiment is None:
                sentiment = 0.0
            cursor.execute(
                """INSERT OR IGNORE INTO news (title, summary, source, url, published_at, relevance_score, sentiment, tickers, category)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    r["title"],
                    r["summary"],
                    r["source"],
                    r["url"],
                    pub_at,
                    r["relevance_score"],
                    sentiment,
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

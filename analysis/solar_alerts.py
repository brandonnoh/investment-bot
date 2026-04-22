#!/usr/bin/env python3
"""
태양광 발전소 매물 모니터링 — 신규 매물 감지 + DB 저장 + Discord 알림

9개 크롤러 순차 실행 → INSERT OR IGNORE로 신규 감지 → Discord 전송
"""

import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH
from db.init_db import init_schema

KST = timezone(timedelta(hours=9))
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

# 사이트별 한국어 이름 매핑
SOURCE_NAMES = {
    "allthatsolar": "올댓솔라",
    "solarmarket": "솔라마켓",
    "exchange": "태양광발전거래소",
    "solartrade": "솔라트레이드",
    "solardirect": "솔라다이렉트",
    "haetbit": "햇빛길",
    "ssunlab": "썬랩",
    "koreari": "한국재생에너지",
    "onbid": "온비드",
}


def _get_crawlers():
    """9개 크롤러 모듈의 run() 함수 목록 반환"""
    crawlers = []
    modules = [
        "data.fetch_solar_allthatsolar",
        "data.fetch_solar_solarmarket",
        "data.fetch_solar_exchange",
        "data.fetch_solar_solartrade",
        "data.fetch_solar_solardirect",
        "data.fetch_solar_haetbit",
        "data.fetch_solar_ssunlab",
        "data.fetch_solar_koreari",
        "data.fetch_solar_onbid",
    ]
    for mod_name in modules:
        try:
            mod = __import__(mod_name, fromlist=["run"])
            crawlers.append(mod.run)
        except ImportError as e:
            print(f"  [solar] 모듈 로드 실패: {mod_name} — {e}")
    return crawlers


def _ensure_db() -> sqlite3.Connection:
    """DB 연결 생성 + 스키마 보장"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    init_schema(conn)
    return conn


def _save_listings(conn, listings) -> list[dict]:
    """매물 DB 저장. 신규 매물만 반환. 기존 매물은 파싱 필드 덮어쓰기."""
    now = datetime.now(KST).isoformat()
    new_items = []
    cursor = conn.cursor()

    for item in listings:
        raw = json.dumps(item, ensure_ascii=False)
        try:
            # 신규 여부 먼저 확인
            exists = cursor.execute(
                "SELECT 1 FROM solar_listings WHERE source=? AND listing_id=?",
                (item["source"], item["listing_id"]),
            ).fetchone()

            if not exists:
                cursor.execute(
                    """INSERT INTO solar_listings
                       (source, listing_id, title, capacity_kw, location,
                        price_krw, deal_type, url, status, first_seen_at, last_seen_at, raw_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
                    (
                        item["source"],
                        item["listing_id"],
                        item.get("title"),
                        item.get("capacity_kw"),
                        item.get("location"),
                        item.get("price_krw"),
                        item.get("deal_type"),
                        item.get("url"),
                        now,
                        now,
                        raw,
                    ),
                )
                new_items.append(item)
            else:
                # 기존 매물 — 파싱 결과 + last_seen_at 갱신 (first_seen_at 유지)
                cursor.execute(
                    """UPDATE solar_listings SET
                       title=?, capacity_kw=?, location=?, price_krw=?,
                       deal_type=?, url=?, status='active', last_seen_at=?, raw_json=?
                       WHERE source=? AND listing_id=?""",
                    (
                        item.get("title"),
                        item.get("capacity_kw"),
                        item.get("location"),
                        item.get("price_krw"),
                        item.get("deal_type"),
                        item.get("url"),
                        now,
                        raw,
                        item["source"],
                        item["listing_id"],
                    ),
                )
        except sqlite3.Error as e:
            print(f"  [solar] DB 저장 오류: {e}")

    conn.commit()
    return new_items


def _format_price(price_krw: int | None) -> str:
    """가격을 읽기 좋은 형태로 포맷"""
    if not price_krw:
        return "가격 미공개"
    eok = price_krw // 1_0000_0000
    remainder = (price_krw % 1_0000_0000) // 1_0000
    if eok and remainder:
        return f"{eok}억 {remainder}만원"
    if eok:
        return f"{eok}억원"
    if remainder:
        return f"{remainder}만원"
    return f"{price_krw:,}원"


def _send_discord(new_items: list[dict]):
    """신규 매물 Discord 알림 전송"""
    if not new_items or not DISCORD_WEBHOOK_URL:
        if new_items and not DISCORD_WEBHOOK_URL:
            print("  [solar] DISCORD_WEBHOOK_URL 미설정 — 알림 생략")
        return

    lines = []
    for item in new_items[:10]:  # 최대 10건
        source_name = SOURCE_NAMES.get(item["source"], item["source"])
        loc = item.get("location") or "지역 미상"
        cap = f"{item['capacity_kw']:.0f}kW" if item.get("capacity_kw") else "용량 미상"
        price = _format_price(item.get("price_krw"))
        url = item.get("url", "")

        lines.append(
            f"**{source_name}** — {item.get('title', '제목 없음')}\n{loc} | {cap} | {price}\n{url}"
        )

    if len(new_items) > 10:
        lines.append(f"... 외 {len(new_items) - 10}건")

    message = f"[태양광 새 매물 {len(new_items)}건]\n\n" + "\n\n".join(lines)

    try:
        payload = json.dumps({"content": message}).encode("utf-8")
        req = urllib.request.Request(
            DISCORD_WEBHOOK_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "investment-bot/solar-monitor",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status in (200, 204):
                print(f"  [solar] Discord 전송 완료 ({len(new_items)}건)")
            else:
                print(f"  [solar] Discord 전송 실패: HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        print(f"  [solar] Discord HTTP 오류: {e.code}")
    except Exception as e:
        print(f"  [solar] Discord 전송 오류: {e}")


def run() -> dict:
    """태양광 매물 모니터링 파이프라인 실행"""
    now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    print(f"\n[solar] 태양광 매물 모니터링 시작 — {now_str}")

    conn = _ensure_db()
    all_listings = []
    crawlers = _get_crawlers()

    # 9개 크롤러 순차 실행 (Graceful degradation)
    for crawler in crawlers:
        try:
            items = crawler()
            all_listings.extend(items)
        except Exception as e:
            print(f"  [solar] 크롤러 오류: {e}")

    print(f"\n  [solar] 총 {len(all_listings)}건 수집")

    # DB 저장 + 신규 감지
    new_items = _save_listings(conn, all_listings)
    conn.close()

    print(f"  [solar] 신규 매물: {len(new_items)}건")

    # Discord 알림 (신규만)
    _send_discord(new_items)

    result = {
        "timestamp": now_str,
        "total_crawled": len(all_listings),
        "new_listings": len(new_items),
        "new_items": new_items,
    }
    print("[solar] 모니터링 완료\n")
    return result


if __name__ == "__main__":
    run()

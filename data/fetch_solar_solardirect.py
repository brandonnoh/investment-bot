#!/usr/bin/env python3
"""
솔라다이렉트 (solardirect.co.kr) 태양광 매물 크롤러

인증서 만료 사이트 — SSL 검증 비활성화.
매물 게시판에서 목록 추출.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.fetch_solar_base import (
    SolarListing,
    fetch_html,
    make_listing_id,
    parse_capacity,
    parse_price,
)

BASE_URL = "http://www.solardirect.co.kr"
SOURCE = "solardirect"

_LIST_URLS = [
    f"{BASE_URL}/bbs/board.php?bo_table=sale",
    f"{BASE_URL}/bbs/board.php?bo_table=solar_sale",
    f"{BASE_URL}/bbs/board.php?bo_table=market",
    BASE_URL,
]


def _parse_gnuboard(html: str) -> list[SolarListing]:
    """그누보드 게시판 HTML에서 매물 추출"""
    listings: list[SolarListing] = []

    for m in re.finditer(
        r'href="[^"]*(?:bo_table=\w+)&(?:amp;)?wr_id=(\d+)"[^>]*>([^<]+)', html
    ):
        wr_id, title = m.group(1), m.group(2).strip()
        if not title or len(title) < 3:
            continue

        table_m = re.search(r'bo_table=(\w+)', m.group(0))
        bo_table = table_m.group(1) if table_m else "sale"
        url = f"{BASE_URL}/bbs/board.php?bo_table={bo_table}&wr_id={wr_id}"

        listings.append(
            SolarListing(
                source=SOURCE,
                listing_id=wr_id,
                title=title,
                capacity_kw=parse_capacity(title),
                location=_extract_location(title),
                price_krw=parse_price(title),
                url=url,
            )
        )

    return listings


def _extract_location(text: str) -> str | None:
    """텍스트에서 지역명 추출"""
    m = re.search(
        r"((?:서울|경기|인천|충[남북]|전[남북]|경[남북]|강원|제주|세종|대전|대구|부산|광주|울산)"
        r"[^\s<,]{0,15})",
        text,
    )
    return m.group(1) if m else None


def _parse_generic(html: str) -> list[SolarListing]:
    """범용 링크 파서 (그누보드 패턴 실패 시 폴백)"""
    listings: list[SolarListing] = []
    for m in re.finditer(r'<a\s+[^>]*href="([^"]+)"[^>]*>([^<]{5,100})</a>', html):
        href, title = m.group(1), m.group(2).strip()
        if not any(kw in title for kw in ("kW", "kw", "태양광", "발전소", "MW")):
            continue
        lid = make_listing_id(SOURCE, href)
        url = href if href.startswith("http") else f"{BASE_URL}{href}"
        listings.append(
            SolarListing(
                source=SOURCE,
                listing_id=lid,
                title=title,
                capacity_kw=parse_capacity(title),
                location=_extract_location(title),
                price_krw=parse_price(title),
                url=url,
            )
        )
    return listings


def run() -> list[SolarListing]:
    """솔라다이렉트 매물 수집"""
    print(f"  [solar] {SOURCE} 크롤링 시작...")
    for url in _LIST_URLS:
        try:
            html = fetch_html(url)
            if not html:
                continue
            items = _parse_gnuboard(html)
            if not items:
                items = _parse_generic(html)
            if items:
                seen = set()
                unique = [x for x in items if x["listing_id"] not in seen and not seen.add(x["listing_id"])]
                print(f"  [solar] {SOURCE}: {len(unique)}건 수집")
                return unique
        except Exception as e:
            print(f"  [solar] {SOURCE} ({url}) 오류: {e}")

    print(f"  [solar] {SOURCE}: 수집 실패")
    return []


if __name__ == "__main__":
    for item in run():
        print(f"  {item['title']} | {item.get('location')} | {item.get('capacity_kw')}kW")

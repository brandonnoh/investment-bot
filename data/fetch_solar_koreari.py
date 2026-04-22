#!/usr/bin/env python3
"""
한국재생에너지 (koreari.org) 태양광 매물 크롤러

그누보드 기반
- 태양광 분양: /bbs/board.php?bo_table=tl_product02
- 태양광 양도양수: /bbs/board.php?bo_table=sail
링크 패턴: /bbs/board.php?bo_table={게시판}&wr_id={번호}
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.fetch_solar_base import (
    SolarListing,
    fetch_html,
    parse_capacity,
    parse_price,
)

BASE_URL = "https://koreari.org"
SOURCE = "koreari"

_BOARDS = [
    ("tl_product02", "분양"),
    ("sail", "양도양수"),
]


def _parse_board(html: str, table: str) -> list[SolarListing]:
    """그누보드 게시판에서 wr_id 기반 매물 추출"""
    listings: list[SolarListing] = []

    # bo_tit 클래스 링크에서 wr_id + 제목 추출
    pattern = (
        rf'href="[^"]*bo_table={table}&(?:amp;)?wr_id=(\d+)"[^>]*class="bo_tit"[^>]*>([\s\S]*?)</a>'
    )
    for m in re.finditer(pattern, html):
        wr_id = m.group(1)
        title = re.sub(r"<[^>]+>", " ", m.group(2)).strip()
        title = re.sub(r"\s+", " ", title).strip()
        if not title or len(title) < 5:
            continue
        if "분양완료" in title or "거래완료" in title or "매매완료" in title:
            continue

        url = f"{BASE_URL}/bbs/board.php?bo_table={table}&wr_id={wr_id}"
        capacity = parse_capacity(title)
        price = parse_price(title)
        loc_m = re.search(
            r"((?:서울|경기|인천|충[남북]|전[남북]|경[남북]|강원|제주|세종|대전|대구|부산|광주|울산"
            r"|경상[남북]도|전라[남북]도|충청[남북]도|강원도)"
            r"[^\s/<,]{0,20})",
            title,
        )
        listings.append(
            SolarListing(
                source=SOURCE,
                listing_id=f"{table}_{wr_id}",
                title=title[:100],
                capacity_kw=capacity,
                location=loc_m.group(1) if loc_m else None,
                price_krw=price,
                url=url,
            )
        )

    return listings


def run() -> list[SolarListing]:
    """한국재생에너지 매물 수집 (분양 + 양도양수)"""
    print(f"  [solar] {SOURCE} 크롤링 시작...")
    all_listings: list[SolarListing] = []

    for table, label in _BOARDS:
        url = f"{BASE_URL}/bbs/board.php?bo_table={table}"
        try:
            html = fetch_html(url)
            if html:
                items = _parse_board(html, table)
                print(f"  [solar] {SOURCE} {label}: {len(items)}건")
                all_listings.extend(items)
        except Exception as e:
            print(f"  [solar] {SOURCE} {label} 오류: {e}")

    seen: set[str] = set()
    unique = [
        x for x in all_listings if x["listing_id"] not in seen and not seen.add(x["listing_id"])
    ]
    print(f"  [solar] {SOURCE}: 합계 {len(unique)}건 수집")
    return unique


if __name__ == "__main__":
    for item in run():
        print(f"  {item['title']} | {item.get('location')} | {item.get('capacity_kw')}kW")

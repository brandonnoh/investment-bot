#!/usr/bin/env python3
"""
솔라마켓 (solar-market.co.kr) 태양광 매물 크롤러

매도물건 게시판: /board/free/list.html?board_no=5
분양물건 게시판: /board/free/list.html?board_no=6
링크 패턴: /article/태양광-발전소-매도-물건/5/{번호}/
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

BASE_URL = "https://solar-market.co.kr"
SOURCE = "solarmarket"

# 매도 + 분양 게시판
_BOARD_URLS = [
    f"{BASE_URL}/board/free/list.html?board_no=5",
    f"{BASE_URL}/board/free/list.html?board_no=6",
]


def _parse_board(html: str) -> list[SolarListing]:
    """게시판 HTML에서 매물 목록 추출"""
    listings: list[SolarListing] = []

    # 링크 + 제목 추출: /article/.../{board_no}/{id}/
    pattern = r'href="(/article/[^"]*?/(\d+)/(\d+)/)"[^>]*>([^<]+)'
    for match in re.finditer(pattern, html):
        path, _board, post_id, title = match.groups()
        title = title.strip()
        if not title or title in ("공지", "필독"):
            continue

        url = f"{BASE_URL}{path}"
        capacity = parse_capacity(title)
        price = parse_price(title)

        # 제목에서 지역 추출 (첫 번째 한글 지명 패턴)
        loc_m = re.search(
            r"((?:서울|경기|인천|충남|충북|전남|전북|경남|경북|강원|제주|세종|대전|대구|부산|광주|울산)"
            r"[^\s,|/]{0,10})",
            title,
        )
        location = loc_m.group(1) if loc_m else None

        listings.append(
            SolarListing(
                source=SOURCE,
                listing_id=post_id,
                title=title,
                capacity_kw=capacity,
                location=location,
                price_krw=price,
                url=url,
            )
        )

    return listings


def run() -> list[SolarListing]:
    """솔라마켓 매물 수집"""
    print(f"  [solar] {SOURCE} 크롤링 시작...")
    all_listings: list[SolarListing] = []

    for board_url in _BOARD_URLS:
        try:
            html = fetch_html(board_url)
            if html:
                items = _parse_board(html)
                all_listings.extend(items)
        except Exception as e:
            print(f"  [solar] {SOURCE} 게시판 파싱 오류: {e}")

    # listing_id 중복 제거
    seen = set()
    unique = []
    for item in all_listings:
        if item["listing_id"] not in seen:
            seen.add(item["listing_id"])
            unique.append(item)

    print(f"  [solar] {SOURCE}: {len(unique)}건 수집")
    return unique


if __name__ == "__main__":
    for item in run():
        print(f"  {item['title']} | {item.get('location')} | {item.get('capacity_kw')}kW")

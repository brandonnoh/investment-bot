#!/usr/bin/env python3
"""
솔라다이렉트 (solardirect.co.kr) 태양광 매물 크롤러

발전소팝니다 게시판: /2
발전소분양 게시판: /33
링크 패턴: /2/?q=...&bmode=view&idx={번호}&t=board
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

BASE_URL = "http://www.solardirect.co.kr"
SOURCE = "solardirect"

_BOARDS = [
    (f"{BASE_URL}/2", "2"),
    (f"{BASE_URL}/33", "33"),
]


def _parse_board(html: str, board: str) -> list[SolarListing]:
    """게시판 HTML에서 매물 링크 + 제목 추출"""
    listings: list[SolarListing] = []

    # list_text_title 클래스 링크에서 idx + 제목 추출
    # 패턴: href="...bmode=view&idx=XXXXXX&t=board" ... <span>제목</span>
    pattern = (
        r'class="list_text_title[^"]*"\s+href="([^"]*bmode=view&(?:amp;)?idx=(\d+)&(?:amp;)?t=board[^"]*)"[^>]*>'
        r"\s*<span>\s*([^<]+?)\s*</span>"
    )
    for m in re.finditer(pattern, html, re.DOTALL):
        href, idx, title = m.group(1), m.group(2), m.group(3).strip()
        if not title or len(title) < 3:
            continue

        # href가 상대 경로면 절대 경로로 변환
        url = href if href.startswith("http") else f"{BASE_URL}{href}"

        capacity = parse_capacity(title)
        price = parse_price(title)
        loc_m = re.search(
            r"((?:서울|경기|인천|충[남북]|전[남북]|경[남북]|강원|제주|세종|대전|대구|부산|광주|울산)"
            r"[^\s,|/]{0,10})",
            title,
        )
        listings.append(
            SolarListing(
                source=SOURCE,
                listing_id=f"{board}_{idx}",
                title=title[:100],
                capacity_kw=capacity,
                location=loc_m.group(1) if loc_m else None,
                price_krw=price,
                url=url,
            )
        )

    return listings


def run() -> list[SolarListing]:
    """솔라다이렉트 매물 수집 (발전소팝니다 + 분양)"""
    print(f"  [solar] {SOURCE} 크롤링 시작...")
    all_listings: list[SolarListing] = []

    for board_url, board_id in _BOARDS:
        try:
            html = fetch_html(board_url)
            if html:
                all_listings.extend(_parse_board(html, board_id))
        except Exception as e:
            print(f"  [solar] {SOURCE} 게시판 {board_id} 오류: {e}")

    seen: set[str] = set()
    unique = [
        x for x in all_listings if x["listing_id"] not in seen and not seen.add(x["listing_id"])
    ]
    print(f"  [solar] {SOURCE}: {len(unique)}건 수집")
    return unique


if __name__ == "__main__":
    for item in run():
        print(f"  {item['title']} | {item.get('location')} | {item.get('capacity_kw')}kW")

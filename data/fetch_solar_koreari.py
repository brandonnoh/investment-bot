#!/usr/bin/env python3
"""
한국재생에너지 (koreari.org) 태양광 매물 크롤러

그누보드 기반, 분양물건 게시판: /bbs/board.php?bo_table=tl_product02
링크 패턴: /bbs/board.php?bo_table=tl_product02&wr_id={번호}
분양중/분양완료 상태 구분
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
_LIST_URL = f"{BASE_URL}/bbs/board.php?bo_table=tl_product02"


def _parse_list(html: str) -> list[SolarListing]:
    """게시판 HTML에서 매물 목록 추출"""
    listings: list[SolarListing] = []

    # wr_id 기반 링크 + 제목 추출
    pattern = (
        r'href="[^"]*bo_table=tl_product02&(?:amp;)?wr_id=(\d+)"[^>]*>'
        r'\s*([^<]+)'
    )
    for m in re.finditer(pattern, html):
        wr_id, title = m.group(1), m.group(2).strip()
        if not title or len(title) < 3:
            continue

        url = f"{BASE_URL}/bbs/board.php?bo_table=tl_product02&wr_id={wr_id}"

        # 분양완료 건은 status만 표시하고 포함
        status = "active"
        if "분양완료" in title:
            status = "sold"
            continue  # 분양완료 건은 스킵

        # 제목에서 정보 추출
        # 예: "경상북도 김천시 어모면 다남리 / 토지형 태양광발전소 100㎾ 5구좌"
        capacity = parse_capacity(title)
        price = parse_price(title)

        loc_m = re.search(
            r"((?:서울|경기|인천|충[남북]|전[남북]|경[남북]|강원|제주|세종|대전|대구|부산|광주|울산"
            r"|경상[남북]도|전라[남북]도|충청[남북]도|강원도)"
            r"[^\s/<,]{0,20})",
            title,
        )
        location = loc_m.group(1) if loc_m else None

        listings.append(
            SolarListing(
                source=SOURCE,
                listing_id=wr_id,
                title=title[:100],
                capacity_kw=capacity,
                location=location,
                price_krw=price,
                url=url,
            )
        )

    return listings


def run() -> list[SolarListing]:
    """한국재생에너지 매물 수집"""
    print(f"  [solar] {SOURCE} 크롤링 시작...")
    try:
        html = fetch_html(_LIST_URL)
        if not html:
            return []
        items = _parse_list(html)
        seen = set()
        unique = [x for x in items if x["listing_id"] not in seen and not seen.add(x["listing_id"])]
        print(f"  [solar] {SOURCE}: {len(unique)}건 수집")
        return unique
    except Exception as e:
        print(f"  [solar] {SOURCE} 오류: {e}")
        return []


if __name__ == "__main__":
    for item in run():
        print(f"  {item['title']} | {item.get('location')} | {item.get('capacity_kw')}kW")

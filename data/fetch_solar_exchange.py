#!/usr/bin/env python3
"""
태양광발전거래소 (xn--v69ayl04xcue64hjogqven8v.com) 매물 크롤러

그누보드 기반, 매물 게시판: /bbs/board.php?bo_table=m01_01
링크 패턴: /bbs/board.php?bo_table=m01_01&wr_id={번호}
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.fetch_solar_base import (
    SolarListing,
    fetch_html,
    parse_capacity,
    parse_location,
    parse_price,
)

BASE_URL = "https://xn--v69ayl04xcue64hjogqven8v.com"
SOURCE = "exchange"
_LIST_URL = f"{BASE_URL}/bbs/board.php?bo_table=m01_01"


def _parse_list(html: str) -> list[SolarListing]:
    """게시판 HTML에서 매물 목록 추출"""
    listings: list[SolarListing] = []

    # wr_id 기반 링크 + 주변 텍스트 추출
    pattern = r'href="[^"]*bo_table=m01_01&(?:amp;)?wr_id=(\d+)"'
    ids_found = set()
    for m in re.finditer(pattern, html):
        ids_found.add(m.group(1))

    # 각 매물 블록에서 정보 추출
    # 카드형 레이아웃: 제목(h4/h5), 가격, 용량 텍스트
    blocks = re.split(r"wr_id=", html)
    for block in blocks[1:]:
        id_m = re.match(r"(\d+)", block)
        if not id_m:
            continue
        wr_id = id_m.group(1)
        url = f"{BASE_URL}/bbs/board.php?bo_table=m01_01&wr_id={wr_id}"

        # 제목 추출 (h4, h5, 또는 링크 텍스트)
        title_m = re.search(r"<h[45][^>]*>([^<]+)</h[45]>", block)
        if not title_m:
            title_m = re.search(r">([^<]{5,80})</", block)
        title = title_m.group(1).strip() if title_m else f"매물 #{wr_id}"

        # 판매완료 체크
        if "판매완료" in block[:500]:
            continue

        # 가격 추출
        price_m = re.search(r"(?:매도가격|가격|매매)[^0-9]*([0-9억천만원\s.]+)", block[:1000])
        price = parse_price(price_m.group(1)) if price_m else parse_price(title)

        # 용량 추출
        cap_m = re.search(r"[Kk][Ww]\s*[:\s]*([0-9,.]+)", block[:1000])
        if cap_m:
            capacity = float(cap_m.group(1).replace(",", ""))
        else:
            capacity = parse_capacity(block[:500]) or parse_capacity(title)

        location = parse_location(block[:500]) or parse_location(title)

        listings.append(
            SolarListing(
                source=SOURCE,
                listing_id=wr_id,
                title=title,
                capacity_kw=capacity,
                location=location,
                price_krw=price,
                url=url,
            )
        )

    return listings


def run() -> list[SolarListing]:
    """태양광발전거래소 매물 수집"""
    print(f"  [solar] {SOURCE} 크롤링 시작...")
    try:
        html = fetch_html(_LIST_URL)
        if not html:
            return []
        items = _parse_list(html)
        # wr_id 중복 제거
        seen = set()
        unique = []
        for item in items:
            if item["listing_id"] not in seen:
                seen.add(item["listing_id"])
                unique.append(item)
        print(f"  [solar] {SOURCE}: {len(unique)}건 수집")
        return unique
    except Exception as e:
        print(f"  [solar] {SOURCE} 오류: {e}")
        return []


if __name__ == "__main__":
    for item in run():
        print(f"  {item['title']} | {item.get('location')} | {item.get('capacity_kw')}kW")

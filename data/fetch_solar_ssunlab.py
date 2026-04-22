#!/usr/bin/env python3
"""
썬랩 (ssunlab.com) 태양광 매물 크롤러

매물 비공개 원칙 사이트 — 공개된 거래완료 매물만 수집 가능.
/market/market_3 페이지에서 최근 거래완료 매물 목록 추출.
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
)

BASE_URL = "https://www.ssunlab.com"
SOURCE = "ssunlab"
_LIST_URL = f"{BASE_URL}/market/market_3"


def _parse_page(html: str) -> list[SolarListing]:
    """썬랩 페이지에서 매물 정보 추출 (공개된 것만)"""
    listings: list[SolarListing] = []

    # 텍스트에서 발전소명 + 용량 패턴 탐색
    # 예: "남성리 태양광(450kW)", "가산리 태양광(702kW)"
    for m in re.finditer(
        r'([가-힣]{2,10})\s*태양광\s*[\(（]?\s*(\d+(?:\.\d+)?)\s*[Kk][Ww]',
        html,
    ):
        name, cap_str = m.group(1), m.group(2)
        capacity = float(cap_str)
        title = f"{name} 태양광({capacity:.0f}kW)"
        lid = make_listing_id(SOURCE, title)

        listings.append(
            SolarListing(
                source=SOURCE,
                listing_id=lid,
                title=title,
                capacity_kw=capacity,
                location=None,  # 구체적 지역 비공개
                price_krw=None,  # 가격 비공개
                url=_LIST_URL,
            )
        )

    # 링크 기반 매물 탐색 (상세 페이지가 공개된 경우)
    for m in re.finditer(r'href="(/market/[^"]*)"[^>]*>([^<]*태양광[^<]*)</a>', html):
        path, text = m.group(1), m.group(2).strip()
        if not text:
            continue
        lid = make_listing_id(SOURCE, path)
        url = f"{BASE_URL}{path}"
        capacity = parse_capacity(text)

        listings.append(
            SolarListing(
                source=SOURCE,
                listing_id=lid,
                title=text[:100],
                capacity_kw=capacity,
                location=None,
                price_krw=None,
                url=url,
            )
        )

    return listings


def run() -> list[SolarListing]:
    """썬랩 매물 수집"""
    print(f"  [solar] {SOURCE} 크롤링 시작...")
    try:
        html = fetch_html(_LIST_URL)
        if not html:
            return []
        items = _parse_page(html)
        seen = set()
        unique = [x for x in items if x["listing_id"] not in seen and not seen.add(x["listing_id"])]
        print(f"  [solar] {SOURCE}: {len(unique)}건 수집 (거래완료 포함)")
        return unique
    except Exception as e:
        print(f"  [solar] {SOURCE} 오류: {e}")
        return []


if __name__ == "__main__":
    for item in run():
        print(f"  {item['title']} | {item.get('capacity_kw')}kW")

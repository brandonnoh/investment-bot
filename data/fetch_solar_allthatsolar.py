#!/usr/bin/env python3
"""
올댓솔라 (allthatsolar.com) 태양광 매물 크롤러

메인 페이지에서 매물 목록 추출. 사이트 접속 불안정할 수 있음.
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

BASE_URL = "https://www.allthatsolar.com"
SOURCE = "allthatsolar"

# 매물 목록 후보 URL
_LIST_URLS = [
    f"{BASE_URL}/market",
    f"{BASE_URL}/sell",
    f"{BASE_URL}/listing",
    BASE_URL,
]


def _parse_page(html: str) -> list[SolarListing]:
    """HTML에서 매물 정보 추출 (범용 파서)"""
    listings: list[SolarListing] = []

    # 링크 + 제목 조합 탐색 (다양한 패턴 대응)
    # 패턴 1: href와 제목이 a 태그 안에 있는 경우
    for m in re.finditer(r'<a\s+[^>]*href="(/[^"]*)"[^>]*>(.*?)</a>', html, re.DOTALL):
        path, inner = m.group(1), m.group(2)
        # HTML 태그 제거
        text = re.sub(r'<[^>]+>', ' ', inner).strip()
        text = re.sub(r'\s+', ' ', text)

        # 태양광/발전소 관련 키워드 포함 여부
        if not any(kw in text for kw in ("kW", "kw", "KW", "㎾", "태양광", "발전소", "MW", "mw")):
            continue
        if len(text) < 5 or len(text) > 200:
            continue

        # ID 추출 시도
        id_m = re.search(r'[/=](\d+)', path)
        lid = id_m.group(1) if id_m else make_listing_id(SOURCE, path)

        url = f"{BASE_URL}{path}" if path.startswith("/") else path
        capacity = parse_capacity(text)
        price = parse_price(text)

        loc_m = re.search(
            r"((?:서울|경기|인천|충[남북]|전[남북]|경[남북]|강원|제주|세종|대전|대구|부산|광주|울산)"
            r"[^\s<,]{0,15})",
            text,
        )
        location = loc_m.group(1) if loc_m else None

        listings.append(
            SolarListing(
                source=SOURCE,
                listing_id=lid,
                title=text[:100],
                capacity_kw=capacity,
                location=location,
                price_krw=price,
                url=url,
            )
        )

    return listings


def run() -> list[SolarListing]:
    """올댓솔라 매물 수집"""
    print(f"  [solar] {SOURCE} 크롤링 시작...")
    for url in _LIST_URLS:
        try:
            html = fetch_html(url)
            if not html:
                continue
            items = _parse_page(html)
            if items:
                # 중복 제거
                seen = set()
                unique = [x for x in items if x["listing_id"] not in seen and not seen.add(x["listing_id"])]
                print(f"  [solar] {SOURCE}: {len(unique)}건 수집")
                return unique
        except Exception as e:
            print(f"  [solar] {SOURCE} ({url}) 오류: {e}")

    print(f"  [solar] {SOURCE}: 수집 실패 (사이트 접속 불가)")
    return []


if __name__ == "__main__":
    for item in run():
        print(f"  {item['title']} | {item.get('location')} | {item.get('capacity_kw')}kW")

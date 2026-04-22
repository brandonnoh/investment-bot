#!/usr/bin/env python3
"""
올댓솔라 (allthatsolar.co.kr) 태양광 매물 크롤러

Firebase Firestore 기반 SPA — 서버사이드 HTML 크롤링 불가.
메인 랜딩 HTML에서 스크립트 태그 내 매물 정보 추출 시도.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.fetch_solar_base import (
    SolarListing,
    fetch_html,
    parse_capacity,
    parse_deal_type,
    parse_price,
)

BASE_URL = "https://allthatsolar.co.kr"
SOURCE = "allthatsolar"


def _parse_page(html: str) -> list[SolarListing]:
    """HTML/JS에서 매물 정보 추출 시도"""
    listings: list[SolarListing] = []

    # Firebase 데이터가 인라인 JS로 포함되어 있을 경우 추출 시도
    # kW/용량 정보가 있는 텍스트 블록 탐색
    for m in re.finditer(
        r'"(?:title|name|location|address|region)"\s*:\s*"([^"]+태양광[^"]*)"',
        html,
    ):
        text = m.group(1)
        capacity = parse_capacity(text)
        price = parse_price(text)
        loc_m = re.search(
            r"((?:서울|경기|인천|충[남북]|전[남북]|경[남북]|강원|제주|세종|대전|대구|부산|광주|울산)"
            r"[^\s\"]{0,15})",
            text,
        )
        listing_id = re.sub(r"[^a-z0-9]", "", text.lower())[:20] or f"allthatsolar_{len(listings)}"
        listings.append(
            SolarListing(
                source=SOURCE,
                listing_id=listing_id,
                title=text[:100],
                capacity_kw=capacity,
                location=loc_m.group(1) if loc_m else None,
                price_krw=price,
                deal_type=parse_deal_type(text),

                url=f"{BASE_URL}/market.html",
            )
        )

    return listings


def run() -> list[SolarListing]:
    """올댓솔라 매물 수집 (Firebase SPA — HTML 한계 있음)"""
    print(f"  [solar] {SOURCE} 크롤링 시작...")
    for url in [f"{BASE_URL}/market.html", BASE_URL]:
        try:
            html = fetch_html(url)
            if not html:
                continue
            items = _parse_page(html)
            if items:
                seen: set[str] = set()
                unique = [x for x in items if x["listing_id"] not in seen and not seen.add(x["listing_id"])]
                print(f"  [solar] {SOURCE}: {len(unique)}건 수집")
                return unique
        except Exception as e:
            print(f"  [solar] {SOURCE} ({url}) 오류: {e}")

    print(f"  [solar] {SOURCE}: Firebase SPA — HTML 크롤링 불가, 0건")
    return []


if __name__ == "__main__":
    for item in run():
        print(f"  {item['title']} | {item.get('location')} | {item.get('capacity_kw')}kW")

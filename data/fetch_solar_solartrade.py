#!/usr/bin/env python3
"""
솔라트레이드 (solartrade.co.kr) 태양광 매물 크롤러

매물 목록: /trade/solarsale.php
테이블 구조: ST-번호 | 지역(링크) | 용량(KW) | REC | 준공일 | 가중치 | 설치타입
상세: /board/solar_download.php?upload=1&no={번호} (PDF)
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.fetch_solar_base import (
    SolarListing,
    fetch_html,
    parse_capacity,
)

BASE_URL = "http://www.solartrade.co.kr"
SOURCE = "solartrade"
_LIST_URL = f"{BASE_URL}/trade/solarsale.php"


def _parse_table(html: str) -> list[SolarListing]:
    """테이블 행 파싱: ST-번호 | 지역 | 용량(KW) | REC | 준공일 | 가중치 | 설치타입"""
    listings: list[SolarListing] = []

    for tr_m in re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL | re.IGNORECASE):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr_m.group(1), re.DOTALL | re.IGNORECASE)
        if len(cells) < 4:
            continue

        cell0 = re.sub(r"<[^>]+>", "", cells[0]).strip()
        if not re.match(r"ST-\d+", cell0):
            continue

        listing_id = cell0
        no_m = re.search(r"no=(\d+)", cells[1])
        loc_text = re.sub(r"<[^>]+>", " ", cells[1]).strip()
        location = loc_text.split()[0] if loc_text else None
        url = (
            f"{BASE_URL}/board/solar_download.php?upload=1&no={no_m.group(1)}"
            if no_m
            else _LIST_URL
        )

        cap_text = re.sub(r"<[^>]+>", "", cells[2]).strip()
        capacity = parse_capacity(cap_text)
        title = f"{location} {cap_text}".strip() if location else cap_text

        listings.append(
            SolarListing(
                source=SOURCE,
                listing_id=listing_id,
                title=title[:100],
                capacity_kw=capacity,
                location=location,
                price_krw=None,
                url=url,
            )
        )

    return listings


def run() -> list[SolarListing]:
    """솔라트레이드 매물 수집"""
    print(f"  [solar] {SOURCE} 크롤링 시작...")
    try:
        html = fetch_html(_LIST_URL)
        if not html:
            print(f"  [solar] {SOURCE}: HTML 수신 실패")
            return []
        items = _parse_table(html)
        seen: set[str] = set()
        unique = [x for x in items if x["listing_id"] not in seen and not seen.add(x["listing_id"])]
        print(f"  [solar] {SOURCE}: {len(unique)}건 수집")
        return unique
    except Exception as e:
        print(f"  [solar] {SOURCE} 오류: {e}")
        return []


if __name__ == "__main__":
    for item in run():
        print(f"  {item['title']} | {item.get('location')} | {item.get('capacity_kw')}kW")

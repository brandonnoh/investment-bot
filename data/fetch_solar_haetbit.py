#!/usr/bin/env python3
"""
햇빛길 (haetbit-gil.com) 태양광 중고 매물 크롤러

매물 목록: /used/index.php
상세 링크: /used/view.php?seq={번호}
카드형 레이아웃, 판매중/판매완료 상태 표시
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
    parse_location,
    parse_price,
)

BASE_URL = "https://haetbit-gil.com"
SOURCE = "haetbit"
_LIST_URL = f"{BASE_URL}/used/index.php"


def _parse_list(html: str) -> list[SolarListing]:
    """매물 목록 HTML에서 데이터 추출"""
    listings: list[SolarListing] = []

    # view.php?seq={번호} 링크 패턴
    # 주변 텍스트에서 제목/가격/용량/위치 추출
    blocks = re.split(r"view\.php\?seq=", html)
    for block in blocks[1:]:
        seq_m = re.match(r"(\d+)", block)
        if not seq_m:
            continue
        seq = seq_m.group(1)
        url = f"{BASE_URL}/used/view.php?seq={seq}"

        # 판매완료 건은 제외
        snippet = block[:2000]
        if "판매완료" in snippet:
            continue

        # 텍스트 정리 (HTML 태그 제거)
        text = re.sub(r"<[^>]+>", " ", snippet)
        text = re.sub(r"\s+", " ", text).strip()

        # 용량 추출 (예: "989.82 kw")
        capacity = parse_capacity(text)

        # 가격 추출 (예: "40억", "매매 3억5천")
        price_m = re.search(r"(?:매매|가격|매도)[^0-9]*([0-9억천만원\s.]+)", text)
        price = parse_price(price_m.group(1)) if price_m else parse_price(text)

        location = parse_location(text)

        # 제목 추출 (첫 번째 의미 있는 텍스트)
        title_candidates = [t.strip() for t in text.split('"') if len(t.strip()) > 5]
        if not title_candidates:
            title_candidates = [t.strip() for t in text.split("  ") if len(t.strip()) > 5]
        title = title_candidates[0][:100] if title_candidates else f"햇빛길 매물 #{seq}"

        # 지역+용량 조합이 제목에 있으면 그것 사용
        if location and capacity:
            title = f"{location} {capacity}kW"

        listings.append(
            SolarListing(
                source=SOURCE,
                listing_id=seq,
                title=title,
                capacity_kw=capacity,
                location=location,
                price_krw=price,
                deal_type=parse_deal_type(title) or "매매",

                url=url,
            )
        )

    return listings


def run() -> list[SolarListing]:
    """햇빛길 매물 수집"""
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

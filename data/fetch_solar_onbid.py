#!/usr/bin/env python3
"""
온비드 (onbid.co.kr) 태양광 관련 공매 크롤러

POST API: /op/cltrpbancinf/cltr/cltrcdtnsrch/CltrCdtnSrchController/srchCltrCdtn.do
- srchCltrType=0001: 부동산 (태양광 발전소 포함)
- srchCltrType=0003: 동산 (기타 설비)
클라이언트 측 키워드 필터링으로 태양광 관련 항목 추출
"""

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.fetch_solar_base import (
    SolarListing,
    parse_capacity,
    parse_location,
    parse_price,
)

BASE_URL = "https://www.onbid.co.kr"
SOURCE = "onbid"
_SEARCH_URL = f"{BASE_URL}/op/cltrpbancinf/cltr/cltrcdtnsrch/CltrCdtnSrchController/srchCltrCdtn.do"
_SOLAR_KEYWORDS = ("태양광", "발전소", "발전기", "태양열")
_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": f"{BASE_URL}/op/cltrpbancinf/cltr/cltrcdtnsrch/CltrCdtnSrchController/mvmnCltrCdtnSrchClg.do",
}


def _fetch_page(cltr_type: str, page: int) -> list[dict]:
    """한 페이지 조회"""
    page_size = 30
    params = urllib.parse.urlencode(
        {
            "pageIndex": str(page),
            "pageUnit": str(page_size),
            "pageSize": str(page_size),
            "firstIndex": str((page - 1) * page_size),
            "lastIndex": str(page * page_size),
            "recordCountPerPage": str(page_size),
            "srchCltrType": cltr_type,
            "srchDspsMthod": "ALL",
            "srchBidPerdType": "ALL",
            "srchSortType": "DESC",
        }
    )
    req = urllib.request.Request(_SEARCH_URL, params.encode("utf-8"), _HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read()).get("cltrInfVOList", [])


def _is_solar(name: str) -> bool:
    return any(kw in name for kw in _SOLAR_KEYWORDS)


def _to_listing(item: dict) -> SolarListing:
    cltr_no = str(item.get("onbidCltrno", ""))
    name = item.get("onbidCltrNm", "")
    url = f"{BASE_URL}/op/cltrpbancinf/cltr/cltrcdtninq/CltrCdtnInqController/mvmnCltrCdtnDtl.do?onbidCltrno={cltr_no}"
    capacity = parse_capacity(name)
    price_raw = item.get("cltrApslEvlAvgAmt", 0)
    price = int(price_raw) if price_raw and int(price_raw) > 0 else parse_price(name)
    return SolarListing(
        source=SOURCE,
        listing_id=cltr_no,
        title=name[:100],
        capacity_kw=capacity,
        location=parse_location(name),
        price_krw=price,
        deal_type=parse_deal_type(name),

        url=url,
    )


def run() -> list[SolarListing]:
    """온비드 태양광 공매 매물 수집 (부동산 + 동산 최신 3페이지 필터링)"""
    print(f"  [solar] {SOURCE} 크롤링 시작...")
    solar: list[SolarListing] = []
    seen: set[str] = set()

    for cltr_type in ("0001", "0003"):
        label = "부동산" if cltr_type == "0001" else "동산"
        for page in range(1, 4):
            try:
                items = _fetch_page(cltr_type, page)
                if not items:
                    break
                for item in items:
                    name = item.get("onbidCltrNm", "")
                    cltr_no = str(item.get("onbidCltrno", ""))
                    if _is_solar(name) and cltr_no not in seen:
                        seen.add(cltr_no)
                        solar.append(_to_listing(item))
            except Exception as e:
                print(f"  [solar] {SOURCE} {label} p{page} 오류: {e}")
                break

    print(f"  [solar] {SOURCE}: {len(solar)}건 수집 (전체 목록 필터링)")
    return solar


if __name__ == "__main__":
    for item in run():
        print(f"  {item['title']} | {item.get('location')} | {item.get('capacity_kw')}kW")

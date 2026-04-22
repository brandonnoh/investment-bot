#!/usr/bin/env python3
"""
온비드 (onbid.co.kr) 태양광 관련 공매 매물 크롤러

검색 API: POST /op/ppa/selectPublicPropList.do
검색어: "태양광"
JSON 응답에서 매물 목록 추출
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.fetch_solar_base import (
    SolarListing,
    _HEADERS,
    _SSL_UNVERIFIED,
    _TIMEOUT,
    fetch_html,
    make_listing_id,
    parse_capacity,
    parse_price,
)

BASE_URL = "https://www.onbid.co.kr"
SOURCE = "onbid"

# 검색 결과 페이지 URL
_SEARCH_URL = (
    f"{BASE_URL}/op/ppa/selectPublicPropList.do"
    "?searchKeyword=%ED%83%9C%EC%96%91%EA%B4%91"
    "&currentPage=1&pageSize=20"
)


def _fetch_via_api() -> list[SolarListing] | None:
    """온비드 검색 API 시도 (POST 방식)"""
    try:
        form_data = (
            "searchKeyword=%ED%83%9C%EC%96%91%EA%B4%91"
            "&currentPage=1&pageSize=20"
        ).encode("utf-8")
        hdrs = {
            **_HEADERS,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": BASE_URL,
        }
        req = urllib.request.Request(
            f"{BASE_URL}/op/ppa/selectPublicPropList.do",
            data=form_data,
            headers=hdrs,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT, context=_SSL_UNVERIFIED) as resp:
            content = resp.read().decode("utf-8", errors="replace")

        # JSON 응답인지 확인
        if content.strip().startswith("{"):
            data = json.loads(content)
            items = data.get("list") or data.get("resultList") or []
            return _parse_api_items(items) if items else None

        # HTML 응답이면 HTML 파서로 전환
        if "<html" in content.lower():
            return _parse_search_html(content) or None

    except Exception as e:
        print(f"  [solar] {SOURCE} API 요청 실패: {e}")
    return None


def _parse_api_items(items: list[dict]) -> list[SolarListing]:
    """API JSON 응답에서 매물 추출"""
    listings: list[SolarListing] = []
    for item in items:
        # 온비드 API 필드명은 다양할 수 있음
        prop_nm = item.get("PLNM_NM") or item.get("propNm") or item.get("title", "")
        prop_no = str(item.get("PLNM_NO") or item.get("propNo") or "")
        if not prop_no:
            prop_no = make_listing_id(SOURCE, prop_nm)

        addr = item.get("ADDR") or item.get("addr") or ""
        price_str = str(item.get("MIN_BID_PRC") or item.get("minBidPrc") or "")

        url = f"{BASE_URL}/op/ppa/selectPublicPropDtl.do?propNo={prop_no}"

        listings.append(
            SolarListing(
                source=SOURCE,
                listing_id=prop_no,
                title=prop_nm[:100],
                capacity_kw=parse_capacity(prop_nm),
                location=addr[:50] if addr else None,
                price_krw=int(price_str) if price_str.isdigit() else parse_price(price_str),
                url=url,
            )
        )
    return listings


def _parse_search_html(html: str) -> list[SolarListing]:
    """검색 결과 HTML에서 매물 추출"""
    listings: list[SolarListing] = []

    # 테이블 행에서 매물 정보 추출
    # 온비드는 보통 테이블 형식으로 결과 표시
    for m in re.finditer(
        r'selectPublicPropDtl[^"]*propNo=([^"&]+)[^>]*>([^<]+)', html
    ):
        prop_no, title = m.group(1), m.group(2).strip()
        if not title:
            continue

        url = f"{BASE_URL}/op/ppa/selectPublicPropDtl.do?propNo={prop_no}"

        listings.append(
            SolarListing(
                source=SOURCE,
                listing_id=prop_no,
                title=title[:100],
                capacity_kw=parse_capacity(title),
                location=None,
                price_krw=None,
                url=url,
            )
        )

    # 링크 기반 폴백
    if not listings:
        for m in re.finditer(r'href="([^"]*태양광[^"]*)"[^>]*>([^<]+)', html):
            href, title = m.group(1), m.group(2).strip()
            lid = make_listing_id(SOURCE, href)
            url = href if href.startswith("http") else f"{BASE_URL}{href}"
            listings.append(
                SolarListing(
                    source=SOURCE,
                    listing_id=lid,
                    title=title[:100],
                    capacity_kw=parse_capacity(title),
                    location=None,
                    price_krw=None,
                    url=url,
                )
            )

    return listings


def run() -> list[SolarListing]:
    """온비드 태양광 매물 수집"""
    print(f"  [solar] {SOURCE} 크롤링 시작...")
    try:
        result = _fetch_via_api()
        if result:
            print(f"  [solar] {SOURCE}: {len(result)}건 수집 (API)")
            return result
    except Exception:
        pass

    try:
        html = fetch_html(_SEARCH_URL)
        if html:
            items = _parse_search_html(html)
            if items:
                print(f"  [solar] {SOURCE}: {len(items)}건 수집 (HTML)")
                return items
    except Exception as e:
        print(f"  [solar] {SOURCE} HTML 파싱 오류: {e}")

    print(f"  [solar] {SOURCE}: 수집 실패")
    return []


if __name__ == "__main__":
    for item in run():
        print(f"  {item['title']} | {item.get('location')} | {item.get('price_krw')}")

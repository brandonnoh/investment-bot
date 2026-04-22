#!/usr/bin/env python3
"""
태양광 발전소 매물 크롤링 공통 유틸리티

- SolarListing TypedDict: 매물 데이터 표준 구조
- fetch_json / fetch_html: urllib 기반 HTTP 헬퍼
- parse_price / parse_capacity: 한국어 가격/용량 파싱
"""

import hashlib
import json
import re
import ssl
import urllib.request
from typing import TypedDict


class SolarListing(TypedDict, total=False):
    """태양광 매물 표준 데이터 구조"""

    source: str  # 사이트 식별자 (예: "solarmarket")
    listing_id: str  # 사이트 내 고유 ID
    title: str  # 매물 제목
    capacity_kw: float | None  # 용량 (kW)
    location: str | None  # 소재지
    price_krw: int | None  # 가격 (원)
    url: str  # 매물 상세 URL


# SSL 검증 비활성화 컨텍스트 (인증서 만료 사이트 대응)
_SSL_UNVERIFIED = ssl.create_default_context()
_SSL_UNVERIFIED.check_hostname = False
_SSL_UNVERIFIED.verify_mode = ssl.CERT_NONE

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

_TIMEOUT = 15


def fetch_json(url: str, headers: dict | None = None) -> dict | None:
    """URL에서 JSON 응답을 가져온다. 실패 시 None 반환."""
    try:
        hdrs = {**_HEADERS, **(headers or {})}
        req = urllib.request.Request(url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=_TIMEOUT, context=_SSL_UNVERIFIED) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  [solar] JSON 요청 실패 ({url[:60]}): {e}")
        return None


def fetch_html(url: str, headers: dict | None = None) -> str | None:
    """URL에서 HTML 텍스트를 가져온다. 실패 시 None 반환."""
    try:
        hdrs = {**_HEADERS, **(headers or {})}
        req = urllib.request.Request(url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=_TIMEOUT, context=_SSL_UNVERIFIED) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except Exception as e:
        print(f"  [solar] HTML 요청 실패 ({url[:60]}): {e}")
        return None


def parse_price(text: str) -> int | None:
    """한국어 가격 텍스트 → 원 단위 정수 변환

    지원 형식: "1억 2천만원", "2.5억", "120,000,000원", "3억6천만"
    """
    if not text:
        return None
    text = text.replace(",", "").replace(" ", "").strip()

    # "1억2천만원" 패턴
    m = re.search(r"(\d+(?:\.\d+)?)억", text)
    eok = float(m.group(1)) if m else 0
    m = re.search(r"(\d+(?:\.\d+)?)천만", text)
    cheon = float(m.group(1)) if m else 0
    m = re.search(r"(\d+(?:\.\d+)?)백만", text)
    baek = float(m.group(1)) if m else 0

    if eok or cheon or baek:
        total = eok * 1_0000_0000 + cheon * 1000_0000 + baek * 100_0000
        return int(total)

    # 순수 숫자 (원 단위)
    m = re.search(r"(\d{6,})", text)
    if m:
        return int(m.group(1))

    # "만원" 단위
    m = re.search(r"(\d+(?:\.\d+)?)만", text)
    if m:
        return int(float(m.group(1)) * 1_0000)

    return None


def parse_capacity(text: str) -> float | None:
    """용량 텍스트 → kW 단위 실수 변환

    지원 형식: "100kW", "100 kW", "100킬로와트", "99.8kw", "1MW"
    """
    if not text:
        return None
    text = text.replace(",", "").strip()

    # MW 단위
    m = re.search(r"(\d+(?:\.\d+)?)\s*[Mm][Ww]", text)
    if m:
        return float(m.group(1)) * 1000

    # kW 단위 (kw, KW, kW, ㎾, 킬로와트)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:[Kk][Ww]|㎾|킬로와트)", text)
    if m:
        return float(m.group(1))

    return None


def make_listing_id(source: str, *parts: str) -> str:
    """URL이나 제목 조합으로 고유 listing_id 생성 (해시)"""
    raw = f"{source}:{'|'.join(parts)}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]

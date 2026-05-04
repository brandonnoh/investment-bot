#!/usr/bin/env python3
"""
태양광 발전소 매물 크롤링 공통 유틸리티

- SolarListing TypedDict: 매물 데이터 표준 구조
- fetch_json / fetch_html: urllib 기반 HTTP 헬퍼
- parse_price / parse_capacity: 한국어 가격/용량 파싱
"""

import hashlib
import json
import logging
import re
import ssl
import urllib.request
from typing import TypedDict

logger = logging.getLogger(__name__)

_PROVINCE_RE = re.compile(
    r"((?:서울|경기|인천|충[남북]|전[남북]|경[남북]|강원|제주|세종|대전|대구|부산|광주|울산|"
    r"경상[남북]도|전라[남북]도|충청[남북]도|강원도)[^\s/<,\[\]（）()]{0,20})"
)


class SolarListing(TypedDict, total=False):
    """태양광 매물 표준 데이터 구조"""

    source: str  # 사이트 식별자 (예: "solarmarket")
    listing_id: str  # 사이트 내 고유 ID
    title: str  # 매물 제목
    capacity_kw: float | None  # 용량 (kW)
    location: str | None  # 소재지
    price_krw: int | None  # 가격 (원)
    deal_type: str | None  # 거래 유형: '매매' | '분양' | None
    url: str  # 매물 상세 URL


# 기본 SSL 컨텍스트 (인증서 검증 활성화)
_SSL_DEFAULT = ssl.create_default_context()

# 인증서 문제 사이트용 폴백 (경고 로그 전제)
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
    """URL에서 JSON 응답을 가져온다. SSL 검증 실패 시 경고 후 재시도. 실패 시 None 반환."""
    hdrs = {**_HEADERS, **(headers or {})}
    try:
        req = urllib.request.Request(url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=_TIMEOUT, context=_SSL_DEFAULT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except ssl.SSLError:
        logger.warning("SSL 인증서 검증 실패, 비검증 모드로 재시도: %s", url[:80])
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=_TIMEOUT, context=_SSL_UNVERIFIED) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.error("JSON 요청 실패 (비검증 재시도): %s — %s", url[:60], e)
            return None
    except Exception as e:
        print(f"  [solar] JSON 요청 실패 ({url[:60]}): {e}")
        return None


def fetch_html(url: str, headers: dict | None = None) -> str | None:
    """URL에서 HTML 텍스트를 가져온다. SSL 검증 실패 시 경고 후 재시도. 실패 시 None 반환."""
    hdrs = {**_HEADERS, **(headers or {})}
    try:
        req = urllib.request.Request(url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=_TIMEOUT, context=_SSL_DEFAULT) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except ssl.SSLError:
        logger.warning("SSL 인증서 검증 실패, 비검증 모드로 재시도: %s", url[:80])
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=_TIMEOUT, context=_SSL_UNVERIFIED) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                return resp.read().decode(charset, errors="replace")
        except Exception as e:
            logger.error("HTML 요청 실패 (비검증 재시도): %s — %s", url[:60], e)
            return None
    except Exception as e:
        print(f"  [solar] HTML 요청 실패 ({url[:60]}): {e}")
        return None


_DEAL_TYPE_SALE = re.compile(r"매매|매도|판매|팝니다|팔아|매각|양도|양도양수")
_DEAL_TYPE_DIST = re.compile(r"분양")


def parse_deal_type(text: str) -> str | None:
    """제목에서 거래 유형 추출: '매매' 또는 '분양' 또는 None"""
    if not text:
        return None
    if _DEAL_TYPE_DIST.search(text):
        return "분양"
    if _DEAL_TYPE_SALE.search(text):
        return "매매"
    return None


def parse_location(text: str) -> str | None:
    """제목 텍스트에서 지역명 추출.

    1) 시/도 prefix 패턴 우선 (경기, 전남 등)
    2) 제목 앞 2-4자 한글 단어가 숫자/용량 앞에 있으면 도시명으로 간주
    """
    if not text:
        return None
    m = _PROVINCE_RE.search(text)
    if m:
        loc = m.group(1).strip()
        loc = re.sub(r"[\[\]()（）].*$", "", loc).strip()
        return loc or None
    # 제목 시작부분 "나주 99kw" / "천안 72k" 패턴 — 도시명 추출
    m = re.match(r"^([가-힣]{2,4})\s+(?:\d|\S*[Kk][Ww]|\S*태양광|\S*발전)", text)
    if m:
        return m.group(1)
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

    # kW 단위 (kw, KW, kW, kwh, ㎾, 킬로와트)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:[Kk][Ww][Hh]?|㎾|킬로와트)", text)
    if m:
        return float(m.group(1))

    # k만 있는 경우 — "100k", "77k" (W 생략 표기)
    m = re.search(r"(\d+(?:\.\d+)?)\s*[Kk](?![A-Za-z가-힣])", text)
    if m:
        return float(m.group(1))

    return None


def make_listing_id(source: str, *parts: str) -> str:
    """URL이나 제목 조합으로 고유 listing_id 생성 (해시)"""
    raw = f"{source}:{'|'.join(parts)}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]

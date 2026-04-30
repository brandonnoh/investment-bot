#!/usr/bin/env python3
"""DART 전체 법인코드 다운로드 → dart_corp_codes DB 저장 (월 1회 수준)"""

import io
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.connection import get_db_conn  # noqa: E402

# DART corp_cls → 내부 market 코드 매핑
_CORP_CLS_MAP = {"Y": "KS", "K": "KQ", "N": "KN", "E": "ETC"}


def _download_corp_code_zip(api_key: str) -> bytes:
    """DART 법인코드 ZIP 파일 다운로드."""
    url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={api_key}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def _parse_corp_codes(zip_bytes: bytes) -> list[tuple]:
    """ZIP 내 CORPCODE.xml 파싱 → (stock_code, corp_code, corp_name, market) 리스트."""
    results = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        with zf.open("CORPCODE.xml") as xml_file:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            for item in root.iter("list"):
                stock_code = (item.findtext("stock_code") or "").strip()
                if not stock_code:
                    continue
                corp_code = (item.findtext("corp_code") or "").strip()
                corp_name = (item.findtext("corp_name") or "").strip()
                corp_cls = (item.findtext("corp_cls") or "").strip()
                market = _CORP_CLS_MAP.get(corp_cls, "")
                results.append((stock_code, corp_code, corp_name, market))
    return results


def _save_to_db(rows: list[tuple]):
    """dart_corp_codes 테이블에 UPSERT."""
    with get_db_conn() as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO dart_corp_codes
               (stock_code, corp_code, corp_name, market)
               VALUES (?, ?, ?, ?)""",
            rows,
        )
        conn.commit()
    print(f"[dart_corp_codes] {len(rows)}개 법인코드 저장 완료")


def run():
    """DART 법인코드 다운로드 → DB 저장 메인."""
    api_key = os.environ.get("DART_API_KEY", "")
    if not api_key:
        print("[dart_corp_codes] DART_API_KEY 미설정 — 법인코드 다운로드 건너뜀")
        return

    print("[dart_corp_codes] DART 법인코드 ZIP 다운로드 중...")
    zip_bytes = _download_corp_code_zip(api_key)
    rows = _parse_corp_codes(zip_bytes)
    print(f"[dart_corp_codes] 상장사 {len(rows)}개 파싱 완료")
    _save_to_db(rows)


if __name__ == "__main__":
    run()

#!/usr/bin/env python3
"""
수급 데이터 수집 — KRX 외국인/기관 순매수 + CNN Fear & Greed Index

한국 종목: KRX Open API로 외국인/기관 순매수 수량 수집
시장 심리: CNN Fear & Greed Index 수집 → 매크로 방향 팩터에 반영
"""

import json
import logging
import os
import sqlite3
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

KST = timezone(timedelta(hours=9))
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "db" / "history.db"
OUTPUT_DIR = PROJECT_ROOT / "output" / "intel"


def _parse_int(val: str) -> int:
    """문자열을 정수로 변환 (콤마, 공백 제거)"""
    if not val:
        return 0
    cleaned = val.replace(",", "").replace(" ", "").strip()
    if not cleaned or cleaned == "-":
        return 0
    try:
        return int(float(cleaned))
    except ValueError:
        return 0


def parse_krx_response(data: dict) -> dict:
    """KRX 투자자별 매매동향 API 응답 파싱.

    Args:
        data: KRX API JSON 응답

    Returns:
        {종목코드: {"foreign_net": int, "inst_net": int}} 딕셔너리
    """
    items = data.get("OutBlock_1", [])
    if not items:
        return {}

    result = {}
    for item in items:
        code = item.get("ISU_CD", "").strip()
        if not code:
            continue
        foreign_net = _parse_int(item.get("FRGN_NET_BUY_QTY", "0"))
        inst_net = _parse_int(item.get("INST_NET_BUY_QTY", "0"))
        result[code] = {
            "foreign_net": foreign_net,
            "inst_net": inst_net,
        }

    return result


def fetch_krx_supply() -> dict:
    """KRX Open API로 외국인/기관 순매수 수집.

    Returns:
        {종목코드: {"foreign_net": int, "inst_net": int}} 또는 빈 딕셔너리
    """
    now = datetime.now(KST)
    trd_date = now.strftime("%Y%m%d")

    # KRX 정보데이터시스템 — 투자자별 매매동향 (전체)
    url = (
        "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
    )
    params = {
        "bld": "dbms/MDC/STAT/standard/MDCSTAT02301",
        "locale": "ko_KR",
        "mktId": "STK",  # 코스피
        "trdDd": trd_date,
        "share": "1",
        "csvxls_isNo": "false",
    }

    try:
        post_data = urllib.parse.urlencode(params).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=post_data,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "http://data.krx.co.kr/contents/MDC/MDI/mdiLoader",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            data = json.loads(raw)
        return parse_krx_response(data)
    except Exception as e:
        logger.warning(f"KRX 수급 데이터 수집 실패: {e}")
        return {}


def fetch_fear_greed() -> dict | None:
    """CNN Fear & Greed Index 수집.

    Returns:
        {"score": float, "rating": str, "previous_close": float} 또는 None
    """
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            data = json.loads(raw)

        fg = data.get("fear_and_greed", {})
        score = fg.get("score")
        if score is None:
            logger.warning("Fear & Greed 점수 누락")
            return None

        return {
            "score": float(score),
            "rating": fg.get("rating", ""),
            "previous_close": float(fg.get("previous_close", 0)),
        }
    except Exception as e:
        logger.warning(f"Fear & Greed Index 수집 실패: {e}")
        return None


def fear_greed_to_score(score: float | None) -> float:
    """Fear & Greed 점수(0~100)를 매크로 방향 점수(-1.0~1.0)로 변환.

    0 = 극도의 공포 → -1.0
    50 = 중립 → 0.0
    100 = 극도의 탐욕 → 1.0

    Args:
        score: Fear & Greed 점수 (0~100) 또는 None

    Returns:
        -1.0 ~ 1.0 사이 점수
    """
    if score is None:
        return 0.0
    return round((score - 50) / 50, 4)


def save_supply_to_db(conn: sqlite3.Connection, supply_data: dict):
    """수급 데이터를 fundamentals 테이블에 업데이트.

    종목코드 6자리 → .KS 티커로 매핑하여 UPDATE.

    Args:
        conn: SQLite 연결 객체
        supply_data: {종목코드: {"foreign_net": int, "inst_net": int}}
    """
    for code, data in supply_data.items():
        # 종목코드 → 티커 매핑 (코스피: .KS, 코스닥: .KQ)
        ticker_ks = f"{code}.KS"
        ticker_kq = f"{code}.KQ"

        # fundamentals에 매칭되는 티커 찾기
        row = conn.execute(
            "SELECT ticker FROM fundamentals WHERE ticker IN (?, ?)",
            (ticker_ks, ticker_kq),
        ).fetchone()

        if row:
            conn.execute(
                "UPDATE fundamentals SET foreign_net=?, inst_net=? WHERE ticker=?",
                (data["foreign_net"], data["inst_net"], row[0]),
            )

    conn.commit()


def _save_json(out_dir: Path, krx_supply: dict, fear_greed: dict | None):
    """supply_data.json 파일 저장"""
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(KST).isoformat()

    json_data = {
        "updated_at": now,
        "fear_greed": fear_greed,
        "krx_supply": krx_supply,
    }

    json_path = out_dir / "supply_data.json"
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"supply_data.json 저장 실패: {e}")


def run(conn=None, output_dir=None) -> dict:
    """수급 데이터 수집 파이프라인.

    1. KRX 외국인/기관 순매수 수집
    2. CNN Fear & Greed Index 수집
    3. DB 업데이트 (fundamentals 테이블)
    4. supply_data.json 출력

    Args:
        conn: SQLite 연결 (None이면 기본 DB)
        output_dir: 출력 디렉토리 (None이면 기본)

    Returns:
        {"krx_supply": dict, "fear_greed": dict|None}
    """
    out_dir = Path(output_dir) if output_dir else OUTPUT_DIR

    own_conn = False
    if conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH))
        own_conn = True

    # 1. KRX 수급 수집
    krx_supply = fetch_krx_supply()
    if krx_supply:
        print(f"  ✅ KRX 수급 수집: {len(krx_supply)}개 종목")
        save_supply_to_db(conn, krx_supply)
    else:
        print("  ⚠️ KRX 수급 데이터 없음 (스킵)")

    # 2. Fear & Greed 수집
    fear_greed = fetch_fear_greed()
    if fear_greed:
        print(f"  ✅ Fear & Greed: {fear_greed['score']:.0f} ({fear_greed['rating']})")
    else:
        print("  ⚠️ Fear & Greed 수집 실패 (스킵)")

    # 3. JSON 저장
    _save_json(out_dir, krx_supply, fear_greed)

    if own_conn:
        conn.close()

    return {
        "krx_supply": krx_supply,
        "fear_greed": fear_greed,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(f"\nKRX 수급: {len(result['krx_supply'])}개 종목")
    if result["fear_greed"]:
        fg = result["fear_greed"]
        print(f"Fear & Greed: {fg['score']:.0f} ({fg['rating']})")

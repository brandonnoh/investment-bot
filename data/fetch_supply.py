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
from typing import Optional

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


def _latest_trading_date() -> str:
    """가장 최근 거래일 (주말 제외) 반환. 형식: YYYYMMDD"""
    from datetime import date, timedelta
    d = date.today()
    # 토요일(5) → 금요일, 일요일(6) → 금요일
    if d.weekday() == 5:
        d -= timedelta(days=1)
    elif d.weekday() == 6:
        d -= timedelta(days=2)
    return d.strftime("%Y%m%d")


def fetch_krx_supply() -> dict:
    """KRX Open API로 외국인/기관 순매수 수집.

    Returns:
        {종목코드: {"foreign_net": int, "inst_net": int}} 또는 빈 딕셔너리
    """
    import http.cookiejar
    trd_date = _latest_trading_date()

    url = "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
    params = {
        "bld": "dbms/MDC/STAT/standard/MDCSTAT02301",
        "locale": "ko_KR",
        "mktId": "STK",
        "trdDd": trd_date,
        "share": "1",
        "csvxls_isNo": "false",
    }

    try:
        # 1. 세션 쿠키 획득
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        opener.addheaders = [("User-Agent", "Mozilla/5.0")]
        opener.open("http://data.krx.co.kr/", timeout=10)

        # 2. 데이터 요청 (쿠키 포함)
        post_data = urllib.parse.urlencode(params).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=post_data,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "http://data.krx.co.kr/contents/MDC/MDI/mdiLoader",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        with opener.open(req, timeout=15) as resp:
            raw = resp.read()
            data = json.loads(raw)
        return parse_krx_response(data)
    except Exception as e:
        err_str = str(e)
        if "400" in err_str or "LOGOUT" in err_str:
            logger.info(f"KRX 수급 데이터 없음 (비거래일 또는 세션 오류): {trd_date}")
        else:
            logger.warning(f"KRX 수급 데이터 수집 실패: {e}")
        return {}


def fetch_fear_greed() -> Optional[dict]:
    """Alternative.me Fear & Greed Index 수집 (CNN 대체).

    Returns:
        {"score": float, "rating": str} 또는 None
    """
    url = "https://api.alternative.me/fng/?limit=1"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            data = json.loads(raw)

        items = data.get("data", [])
        if not items:
            logger.warning("Fear & Greed 데이터 없음")
            return None

        item = items[0]
        score = float(item.get("value", 0))
        rating = item.get("value_classification", "")

        return {
            "score": score,
            "rating": rating,
            "previous_close": None,
        }
    except Exception as e:
        logger.warning(f"Fear & Greed Index 수집 실패: {e}")
        return None


def fear_greed_to_score(score: Optional[float]) -> float:
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


def _save_json(out_dir: Path, krx_supply: dict, fear_greed: Optional[dict]):
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

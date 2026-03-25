#!/usr/bin/env python3
"""
키움증권 REST API — 한국 주식 현재가 + KRX 금 현물 조회
토큰 캐시: .kiwoom_token.json (프로젝트 루트)

단독 실행:
    python3 data/fetch_gold_krx.py          # 금 현물
    python3 data/fetch_gold_krx.py 005930   # 삼성전자
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import BASE_DIR

KST = timezone(timedelta(hours=9))
TOKEN_CACHE_PATH = BASE_DIR / ".kiwoom_token.json"

KIWOOM_TOKEN_URL = "https://api.kiwoom.com/oauth2/token"
KIWOOM_QUOTE_URL = "https://api.kiwoom.com/api/dostk/mrkcond"
GOLD_KRX_CODE = "M04020000"


def _get_env():
    """환경변수에서 키움 인증 정보 로드"""
    appkey = os.environ.get("KIWOOM_APPKEY")
    secret = os.environ.get("KIWOOM_SECRETKEY")
    if not appkey or not secret:
        raise EnvironmentError("KIWOOM_APPKEY / KIWOOM_SECRETKEY 환경변수 필요")
    return appkey, secret


def _load_cached_token() -> str | None:
    """캐시된 토큰이 유효하면 반환, 아니면 None"""
    if not TOKEN_CACHE_PATH.exists():
        return None
    try:
        with open(TOKEN_CACHE_PATH, "r") as f:
            cache = json.load(f)
        expires_at = datetime.fromisoformat(cache["expires_at"])
        if datetime.now(KST) < expires_at - timedelta(minutes=5):
            return cache["access_token"]
    except (KeyError, ValueError, json.JSONDecodeError):
        pass
    return None


def _save_token(token: str, expires_in: int):
    """토큰을 파일에 캐시"""
    expires_at = datetime.now(KST) + timedelta(seconds=expires_in)
    with open(TOKEN_CACHE_PATH, "w") as f:
        json.dump(
            {
                "access_token": token,
                "expires_at": expires_at.isoformat(),
            },
            f,
        )


def get_token() -> str:
    """키움 OAuth 토큰 발급 (캐시 우선)"""
    cached = _load_cached_token()
    if cached:
        return cached

    appkey, secret = _get_env()
    body = json.dumps(
        {
            "grant_type": "client_credentials",
            "appkey": appkey,
            "secretkey": secret,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        KIWOOM_TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.load(resp)

    token = data["token"]
    expires_in = int(data.get("expires_in", 86400))
    _save_token(token, expires_in)
    print(f"  🔑 키움 토큰 발급 완료 (만료: {expires_in}s)")
    return token


def _strip_sign(s: str) -> str:
    """부호(+/-)를 제거하고 숫자 문자열만 반환"""
    return s.lstrip("+-").strip()


def fetch_gold_krx() -> dict:
    """
    KRX 금 현물(M04020000) 시세 조회.
    반환: {price, prev_close, change, change_pct, high, low, volume, source}
    """
    appkey, _ = _get_env()
    token = get_token()

    body = json.dumps({"stk_cd": GOLD_KRX_CODE}).encode("utf-8")
    req = urllib.request.Request(
        KIWOOM_QUOTE_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "appkey": appkey,
            "api-id": "ka50100",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.load(resp)

    if data.get("return_code") != 0:
        raise ValueError(f"키움 API 오류: {data.get('return_msg', 'unknown')}")

    # 응답 필드 파싱
    pred_close_raw = data.get("pred_close_pric", "")  # 전일종가
    pred_pre_raw = data.get("pred_pre", "")  # 전일대비 (부호 포함)
    flu_rt_raw = data.get("flu_rt", "")  # 등락율 (부호 포함)
    high_raw = data.get("high_pric", "")  # 고가 (부호 포함)
    low_raw = data.get("low_pric", "")  # 저가 (부호 포함)
    trde_qty_raw = data.get("trde_qty", "")  # 거래량

    if not pred_close_raw:
        raise ValueError("장외 시간 — 시세 데이터 없음")

    prev_close = int(pred_close_raw)

    # 현재가 = 전일종가 + 전일대비
    if pred_pre_raw:
        change = int(pred_pre_raw.replace("+", "").replace(",", ""))
    else:
        change = 0
    price = prev_close + change

    # 등락율
    if flu_rt_raw:
        change_pct = float(flu_rt_raw.replace("+", "").replace(",", ""))
    else:
        change_pct = round(change / prev_close * 100, 2) if prev_close else 0.0

    high = int(_strip_sign(high_raw)) if high_raw else price
    low = int(_strip_sign(low_raw)) if low_raw else price
    volume = int(trde_qty_raw) if trde_qty_raw else 0

    return {
        "price": price,
        "prev_close": prev_close,
        "change": change,
        "change_pct": change_pct,
        "high": high,
        "low": low,
        "volume": volume,
        "source": "kiwoom_krx",
    }


def fetch_kiwoom_stock(code: str) -> dict:
    """
    키움증권 REST API로 한국 주식 현재가 조회 (ka10007 시세표성정보요청).
    code: 6자리 종목코드 (예: '005930')
    반환: {price, prev_close, change_pct, volume, high, low}
    """
    appkey, _ = _get_env()
    token = get_token()

    body = json.dumps({"stk_cd": code}).encode("utf-8")
    req = urllib.request.Request(
        KIWOOM_QUOTE_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "appkey": appkey,
            "api-id": "ka10007",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.load(resp)

    if data.get("return_code") != 0:
        raise ValueError(f"키움 API 오류: {data.get('return_msg', 'unknown')}")

    cur_prc = data.get("cur_prc", "")
    pred_close = data.get("pred_close_pric", "")
    flu_rt = data.get("flu_rt", "")
    trde_qty = data.get("trde_qty", "")
    high_pric = data.get("high_pric", "")
    low_pric = data.get("low_pric", "")

    if not cur_prc or not pred_close:
        raise ValueError("장외 시간 — 시세 데이터 없음")

    price = int(_strip_sign(cur_prc))
    prev_close = int(pred_close)
    change_pct = (
        float(flu_rt.replace("+", ""))
        if flu_rt
        else (round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0)
    )
    volume = int(trde_qty) if trde_qty else 0
    high = int(_strip_sign(high_pric)) if high_pric else price
    low = int(_strip_sign(low_pric)) if low_pric else price

    return {
        "price": price,
        "prev_close": prev_close,
        "change_pct": change_pct,
        "volume": volume,
        "high": high,
        "low": low,
    }


if __name__ == "__main__":
    import sys as _sys

    code = _sys.argv[1] if len(_sys.argv) > 1 else None
    try:
        if code:
            result = fetch_kiwoom_stock(code)
            print(f"✅ {code} 현재가:")
        else:
            result = fetch_gold_krx()
            print("✅ KRX 금 현물 시세:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except EnvironmentError as e:
        print(f"❌ 환경변수 오류: {e}")
        _sys.exit(1)
    except Exception as e:
        print(f"⚠️ 조회 실패 (장외 시간일 수 있음): {e}")
        print("  → 장중(09:00~15:30 KST)에 다시 시도하세요.")
        _sys.exit(1)

#!/usr/bin/env python3
"""
KRX 금 현물(종목코드 4001) 시세 조회 — 키움증권 REST API
토큰 캐시: .kiwoom_token.json (프로젝트 루트)

단독 실행:
    python3 data/fetch_gold_krx.py
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
GOLD_KRX_CODE = "4001"


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
        json.dump({
            "access_token": token,
            "expires_at": expires_at.isoformat(),
        }, f)


def get_token() -> str:
    """키움 OAuth 토큰 발급 (캐시 우선)"""
    cached = _load_cached_token()
    if cached:
        return cached

    appkey, secret = _get_env()
    body = json.dumps({
        "grant_type": "client_credentials",
        "appkey": appkey,
        "secretkey": secret,
    }).encode("utf-8")

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


def fetch_gold_krx() -> dict:
    """
    KRX 금 현물(4001) 시세 조회.
    반환: {price, prev_close, change_pct, high, low, volume, timestamp}
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

    # 장외 시간이면 값이 빈 문자열 → 전일종가 기반 반환
    lst_pric = data.get("lst_pric", "")         # 현재가(최종체결가)
    pred_close = data.get("pred_close_pric", "")  # 전일종가
    high_pric = data.get("high_pric", "")       # 고가
    low_pric = data.get("low_pric", "")         # 저가
    trde_qty = data.get("trde_qty", "")         # 거래량

    if not lst_pric and not pred_close:
        raise ValueError("장외 시간 — 시세 데이터 없음")

    # 장외 시간: 현재가 없으면 전일종가를 현재가로 사용
    if pred_close:
        prev_close = float(pred_close)
    else:
        prev_close = 0.0

    if lst_pric:
        price = float(lst_pric)
    else:
        price = prev_close

    high = float(high_pric) if high_pric else price
    low = float(low_pric) if low_pric else price
    volume = int(trde_qty) if trde_qty else 0

    change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0

    return {
        "price": price,
        "prev_close": prev_close,
        "change_pct": change_pct,
        "high": high,
        "low": low,
        "volume": volume,
        "timestamp": datetime.now(KST).isoformat(),
    }


if __name__ == "__main__":
    try:
        result = fetch_gold_krx()
        print("✅ KRX 금 현물 시세:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except EnvironmentError as e:
        print(f"❌ 환경변수 오류: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"⚠️ 조회 실패 (장외 시간일 수 있음): {e}")
        print("  → 장중(09:00~15:30 KST)에 다시 시도하세요.")
        sys.exit(1)

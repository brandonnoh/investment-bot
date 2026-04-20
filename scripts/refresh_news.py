#!/usr/bin/env python3
"""
장전 뉴스+매크로 갱신 스크립트

평일 08:00 KST(launchd: UTC 전날 23:00)에 실행되어
당일 장 시작 전 뉴스와 매크로 지표를 갱신한다.
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# .env 파일 자동 로드
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    with _env_path.open() as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

KST = timezone(timedelta(hours=9))


def _now_kst() -> str:
    """현재 KST 시각 문자열 반환"""
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")


def _step(name: str, fn):
    """단계 실행 — 실패해도 다음 단계 계속 진행 (graceful degradation)"""
    print(f"[{_now_kst()}] {name} 시작...")
    try:
        result = fn()
        count = len(result) if isinstance(result, (list, dict)) else "완료"
        print(f"[{_now_kst()}] {name} 완료 ({count})")
        return True
    except Exception as e:
        print(f"[{_now_kst()}] {name} 실패: {e}")
        return False


def main():
    """장전 뉴스+매크로 갱신 2단계 실행"""
    print("=" * 50)
    print(f"[{_now_kst()}] 장전 뉴스 갱신 시작")
    print("=" * 50)

    from data.fetch_news import run as fetch_news
    from data.fetch_macro import run as fetch_macro

    results = {
        "fetch_news":  _step("뉴스 수집 (fetch_news)", fetch_news),
        "fetch_macro": _step("매크로 수집 (fetch_macro)", fetch_macro),
    }

    success = sum(results.values())
    total = len(results)
    print("=" * 50)
    print(f"[{_now_kst()}] 장전 뉴스 갱신 완료 ({success}/{total} 성공)")
    print("=" * 50)


if __name__ == "__main__":
    main()

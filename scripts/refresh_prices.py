#!/usr/bin/env python3
"""
장중 가격/매크로/포트폴리오 갱신 스크립트

10분마다 launchd가 호출하되, 장중이 아닌 시간엔 스스로 조기 종료한다.
- KRX 장중: 평일 09:00~15:30 KST
- 미국장: 평일 22:30~ 및 다음날 ~06:00 KST (일요일 22:30~ 포함)
전체 파이프라인(run_pipeline.py)과 달리 뉴스·분석·리포트는 실행하지 않음.
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from datetime import time as dt_time
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


def _now_kst_iso() -> str:
    """현재 KST 시각 ISO 8601 문자열 반환"""
    return datetime.now(KST).isoformat()


def _is_market_hours(now: datetime | None = None) -> bool:
    """장중 여부 반환. now 생략 시 현재 KST 시각 사용.

    수집 구간:
    - KRX 정규장:   평일 09:00~15:30
    - 국내 장외:    평일 15:40~18:00
    - 미국 프리마켓: 평일 20:00~22:30
    - 미국 정규장:  평일 22:30~다음날 06:00 (일요일 22:30 포함)
    """
    if now is None:
        now = datetime.now(KST)
    weekday = now.weekday()  # 0=월 ... 6=일
    t = now.time()

    if weekday < 5:
        # KRX 정규장: 09:00~15:30
        if dt_time(9, 0) <= t <= dt_time(15, 30):
            return True
        # 국내 장외: 15:40~18:00
        if dt_time(15, 40) <= t <= dt_time(18, 0):
            return True
        # 미국 프리마켓: 20:00~22:30
        if dt_time(20, 0) <= t <= dt_time(22, 30):
            return True
        # 미국 정규장: 22:30~자정
        if t >= dt_time(22, 30):
            return True

    # 미국 정규장: 자정~06:00 (화~토 새벽)
    if 1 <= weekday <= 6 and t <= dt_time(6, 0):
        return True

    # 일요일 22:30~자정 (월요일 미국장 이어짐)
    if weekday == 6 and t >= dt_time(22, 30):
        return True

    return False


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
    """장중 여부 확인 후 가격 갱신 3단계 실행"""
    # 장중 시간 게이트 — 장외 시간엔 즉시 종료
    if not _is_market_hours():
        print(f"[{_now_kst()}] 장중 아님 — 스킵")
        return

    print("=" * 50)
    print(f"[{_now_kst()}] 장중 가격 갱신 시작")
    print("=" * 50)

    # 수집 시작 시각을 먼저 기록 — SSE가 prices.json 저장을 감지해 mutate()를 호출할 때
    # engine_status가 이미 최신 시각이어야 대시보드가 올바른 시각을 표시함
    _touch_engine_status()

    from analysis.portfolio import run as analyze_portfolio
    from data.fetch_macro import run as fetch_macro
    from data.fetch_prices import run as fetch_prices

    results = {
        "fetch_prices": _step("가격 수집 (fetch_prices)", fetch_prices),
        "fetch_macro": _step("매크로 수집 (fetch_macro)", fetch_macro),
        "analyze_portfolio": _step("포트폴리오 분석 (analyze_portfolio)", analyze_portfolio),
    }

    success = sum(results.values())
    total = len(results)

    print("=" * 50)
    print(f"[{_now_kst()}] 장중 가격 갱신 완료 ({success}/{total} 성공)")
    print("=" * 50)


def _touch_engine_status():
    """engine_status.json의 updated_at을 현재 시각으로 갱신"""
    import json

    from utils.json_io import write_json_atomic

    status_path = Path(__file__).resolve().parent.parent / "output" / "intel" / "engine_status.json"
    if not status_path.exists():
        return
    try:
        data = json.loads(status_path.read_text())
        data["updated_at"] = _now_kst_iso()
        write_json_atomic(status_path, data)
    except Exception as e:
        print(f"[{_now_kst()}] engine_status 갱신 실패: {e}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Discord 알림 공통 모듈 — 마커스/자비스 크론잡 완료 알림
analysis/alerts_watch_notify.py 패턴 재사용
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Discord Webhook URL (환경변수 우선, fallback: 하드코딩)
DISCORD_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_URL",
    "https://discord.com/api/webhooks/1490306786870165624/0JjO5i_BNWCmIDnFJXQZ0OcDGeWdYsryKnUFGXvoKlqALza6mFPqcjbFz40fWltCIkRR",
)


def _send_discord(message: str) -> bool:
    """Discord Webhook으로 메시지 전송 (내부 공통 함수)"""
    # 2000자 Discord 제한 적용
    if len(message) > 2000:
        message = message[:1997] + "..."

    try:
        payload = json.dumps({"content": message}).encode("utf-8")
        req = urllib.request.Request(
            DISCORD_WEBHOOK_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "investment-bot/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status in (200, 204):
                return True
            print(f"  ⚠️  Discord 전송 실패: HTTP {resp.status}")
            return False
    except urllib.error.HTTPError as e:
        print(f"  ⚠️  Discord HTTP 오류: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        print(f"  ⚠️  Discord 네트워크 오류: {e.reason}")
    except TimeoutError:
        print("  ⚠️  Discord 전송 타임아웃 (30초)")
    except Exception as e:
        print(f"  ⚠️  Discord 전송 오류: {e}")
    return False


def notify_marcus_complete(md_path: Path) -> None:
    """
    marcus-analysis.md에서 TODAY'S CALL 섹션 파싱 후 Discord 전송.
    실패 시 예외 없이 print만 (graceful degradation).
    """
    try:
        # scripts/marcus_analysis.py의 extract_sections() 재사용
        from scripts.marcus_analysis import extract_sections, extract_confidence_level

        if not md_path.exists():
            print(f"  ⚠️  marcus-analysis.md 없음: {md_path}")
            return

        md_text = md_path.read_text(encoding="utf-8")
        sections = extract_sections(md_text)
        confidence = extract_confidence_level(md_text)

        # 확신 레벨 별 표시 (1~5)
        level = confidence if confidence else 0
        stars = "★" * level + "☆" * (5 - level)

        # TODAY'S CALL 섹션 추출
        todays_call = sections.get("TODAY'S CALL", "분석 내용 없음")
        # 1500자 이내로 자르기 (헤더 공간 확보)
        if len(todays_call) > 1500:
            todays_call = todays_call[:1497] + "..."

        message = f"📊 마커스 분석 완료\n확신레벨: {stars}\n\n> {todays_call}"
        ok = _send_discord(message)
        if ok:
            print("  📡 마커스 분석 Discord 전송 완료")
    except Exception as e:
        print(f"  ⚠️  notify_marcus_complete 오류: {e}")


def notify_jarvis_complete(briefing_path: Path) -> None:
    """
    cio-briefing.md 첫 50줄을 Discord 전송.
    실패 시 예외 없이 print만 (graceful degradation).
    """
    try:
        if not briefing_path.exists():
            print(f"  ⚠️  cio-briefing.md 없음: {briefing_path}")
            return

        lines = briefing_path.read_text(encoding="utf-8").splitlines()
        summary = "\n".join(lines[:50])
        if len(summary) > 1800:
            summary = summary[:1797] + "..."

        message = f"🌅 자비스 CIO 브리핑 완료\n\n> {summary}"
        ok = _send_discord(message)
        if ok:
            print("  📡 자비스 CIO 브리핑 Discord 전송 완료")
    except Exception as e:
        print(f"  ⚠️  notify_jarvis_complete 오류: {e}")

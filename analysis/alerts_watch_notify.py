#!/usr/bin/env python3
"""
Discord 알림 발송 모듈 (alerts_watch 분리)
Discord Webhook URL로 직접 POST 전송

- 알림 있을 때만 전송 (빈 리스트 전달 시 조용히 종료)
- 전송 실패 시 예외 없이 로깅만 (Graceful degradation)
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Discord Webhook URL — .env의 DISCORD_WEBHOOK_URL 필수
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")


def fire_discord_alert(alerts: list[dict]):
    """Discord Webhook으로 투자 알림 직접 전송 (중복 없이 단건)"""
    if not alerts:
        return

    # 알림 목록 생성
    alert_lines = []
    for a in alerts:
        level_emoji = {"RED": "🔴", "YELLOW": "🟡", "GREEN": "🟢"}.get(a["level"], "⚪")
        alert_lines.append(f"{level_emoji} {a['message']}")

    alerts_text = "\n".join(alert_lines)
    message = f"🚨 투자 알림\n{alerts_text}"

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
                print(f"  📡 긴급알림 Discord 전송 완료 ({len(alerts)}건)")
            else:
                print(f"  ⚠️  전송 실패: HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        print(f"  ⚠️  Discord HTTP 오류: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        print(f"  ⚠️  Discord 네트워크 오류: {e.reason}")
    except TimeoutError:
        print("  ⚠️  전송 타임아웃 (30초)")
    except Exception as e:
        print(f"  ⚠️  전송 오류: {e}")

#!/usr/bin/env python3
"""
Discord 알림 공통 모듈 — 마커스/자비스 크론잡 완료 알림
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")


def _send_discord(message: str) -> bool:
    """Discord Webhook으로 메시지 전송"""
    if len(message) > 2000:
        message = message[:1997] + "..."
    try:
        payload = json.dumps({"content": message}).encode("utf-8")
        req = urllib.request.Request(
            DISCORD_WEBHOOK_URL,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "investment-bot/1.0"},
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


def _extract_marcus_summary(md_text: str) -> tuple[str, str, int]:
    """marcus-analysis.md에서 (판단, 핵심근거, 확신레벨) 추출"""
    # 확신 레벨
    m = re.search(r"확신\s*레벨[^\d]*(\d)", md_text)
    confidence = int(m.group(1)) if m else 0

    # 오늘의 판단 (한 줄)
    call = ""
    for pattern in [
        r"## TODAY'S CALL\s*\n+(.+?)(?:\n\n|\n##|$)",
        r"> \*\*오늘의 판단:\*\*\s*(.+)",
        r"\*\*TODAY'S CALL[^*]*\*\*[:\s]*(.+)",
        r"오늘의 판단[:\s]+(.+)",
    ]:
        m = re.search(pattern, md_text, re.DOTALL)
        if m:
            call = m.group(1).strip().split("\n")[0].strip()
            break

    # 핵심 근거 (리스크 온/오프 방향성)
    basis = ""
    m = re.search(r"방향성[^:]*:\s*\*?\*?(.+?)(?:\n|$)", md_text)
    if m:
        basis = m.group(1).strip().lstrip("*").strip()

    return call or "분석 없음", basis, confidence


def _extract_jarvis_summary(md_text: str) -> tuple[str, str, list[str]]:
    """cio-briefing.md에서 (한줄요약, 리스크점수, 액션리스트) 추출"""
    # EXECUTIVE SUMMARY 한 줄
    summary = ""
    m = re.search(r"## EXECUTIVE SUMMARY\s*\n+> \*\*(.+?)\*\*", md_text)
    if m:
        summary = m.group(1).strip()

    # 리스크 점수
    risk = ""
    m = re.search(r"지정학 리스크 점수:\s*\*\*(.+?)\*\*", md_text)
    if m:
        risk = m.group(1).strip()

    # 종목별 액션 — 익절/추가매수/금지 위주로 추출
    actions = []
    for line in md_text.splitlines():
        if "|" in line and ("익절" in line or "추가" in line or "금지" in line or "매수" in line):
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 5:
                name = parts[0]
                action = re.sub(r"\*+|⚡", "", parts[4]).strip()
                if name and action and name not in ("종목", "---"):
                    actions.append(f"• {name}: {action}")

    return summary, risk, actions[:6]  # 최대 6종목


def notify_marcus_complete(md_path: Path) -> None:
    """marcus-analysis.md 핵심 요약 Discord 전송"""
    try:
        if not md_path.exists():
            print(f"  ⚠️  marcus-analysis.md 없음: {md_path}")
            return

        md_text = md_path.read_text(encoding="utf-8")
        call, basis, confidence = _extract_marcus_summary(md_text)

        stars = "★" * confidence + "☆" * (5 - confidence)
        lines = [f"📊 마커스 | 확신 {stars}"]
        lines.append("")
        lines.append(f"💡 {call}")
        if basis:
            lines.append(f"📌 {basis[:120]}")

        ok = _send_discord("\n".join(lines))
        if ok:
            print("  📡 마커스 분석 Discord 전송 완료")
    except Exception as e:
        print(f"  ⚠️  notify_marcus_complete 오류: {e}")


def notify_jarvis_complete(briefing_path: Path) -> None:
    """cio-briefing.md 핵심 요약 Discord 전송"""
    try:
        if not briefing_path.exists():
            print(f"  ⚠️  cio-briefing.md 없음: {briefing_path}")
            return

        md_text = briefing_path.read_text(encoding="utf-8")
        summary, risk, actions = _extract_jarvis_summary(md_text)

        lines = [f"🧠 자비스 CIO | 리스크 {risk}" if risk else "🧠 자비스 CIO"]
        lines.append("")
        if summary:
            lines.append(f"**{summary[:150]}**")
        if actions:
            lines.append("")
            lines.append("⚡ 액션")
            lines.extend(actions)

        ok = _send_discord("\n".join(lines))
        if ok:
            print("  📡 자비스 CIO 브리핑 Discord 전송 완료")
    except Exception as e:
        print(f"  ⚠️  notify_jarvis_complete 오류: {e}")

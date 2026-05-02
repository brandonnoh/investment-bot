#!/usr/bin/env python3
"""
알림 저장 레이어 — DB 저장 + JSON 저장
alerts.py에서 분리된 I/O 전용 모듈
"""

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, OUTPUT_DIR
from utils.json_io import write_json_atomic

KST = timezone(timedelta(hours=9))


def save_alerts_to_db(alerts: list[dict], conn=None, notified: bool = False):
    """알림을 SQLite에 저장

    Args:
        alerts: 알림 리스트
        conn: DB 연결 (None이면 DB_PATH로 새 연결 생성)
        notified: True면 notified=1로 저장 (Discord 전송 시)
    """
    if not alerts:
        return

    own_conn = False
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH))
        own_conn = True

    try:
        cursor = conn.cursor()
        now = datetime.now(KST).isoformat()
        notified_val = 1 if notified else 0

        for a in alerts:
            cursor.execute(
                """INSERT INTO alerts (level, event_type, ticker, message, value, threshold, triggered_at, notified)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    a["level"],
                    a["event_type"],
                    a.get("ticker"),
                    a["message"],
                    a["value"],
                    a["threshold"],
                    now,
                    notified_val,
                ),
            )

        conn.commit()
        flag_msg = " (notified=1)" if notified else ""
        print(f"  💾 알림 DB 저장: {len(alerts)}건{flag_msg}")
    finally:
        if own_conn:
            conn.close()


def save_alerts_to_json(alerts: list[dict], output_dir=None):
    """알림을 JSON 파일로 출력 (알림 있을 때만 생성, 없으면 삭제)

    Args:
        alerts: 알림 리스트
        output_dir: 출력 디렉토리 (기본: config.OUTPUT_DIR)
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR
    output_dir = Path(output_dir)
    alerts_path = output_dir / "alerts.json"

    if not alerts:
        # 알림 없으면 기존 파일 제거
        if alerts_path.exists():
            alerts_path.unlink()
            print("  🟢 알림 없음 — alerts.json 제거")
        else:
            print("  🟢 알림 없음")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    output = {
        "triggered_at": datetime.now(KST).isoformat(),
        "count": len(alerts),
        "alerts": alerts,
    }
    write_json_atomic(alerts_path, output)
    print(f"  🚨 알림 JSON 저장: {alerts_path} ({len(alerts)}건)")

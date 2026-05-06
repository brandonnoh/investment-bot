#!/usr/bin/env python3
"""
DB 연결 팩토리 — WAL 모드 + busy_timeout 표준 설정.
모든 모듈은 sqlite3.connect() 직접 호출 대신 이 함수를 사용한다.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH


def get_db_conn(timeout: float = 30.0) -> sqlite3.Connection:
    """WAL 모드 + 30초 busy_timeout DB 연결 반환."""
    conn = sqlite3.connect(str(DB_PATH), timeout=timeout)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    # 300 페이지(~1.2MB)마다 자동 체크포인트 — 기본 1000(4MB)이면 WAL이 너무 커져 오류 발생
    conn.execute("PRAGMA wal_autocheckpoint=300")
    conn.row_factory = sqlite3.Row
    return conn

#!/usr/bin/env python3
"""
비금융 자산 CRUD 서버 핸들러 TDD 테스트
버그: server.py가 create/update/delete_extra_asset 함수를 import하지 않아 NameError 발생
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _create_test_db(path: str) -> None:
    """테스트용 SQLite DB 스키마 초기화"""
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE extra_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            asset_type TEXT NOT NULL DEFAULT '기타',
            current_value_krw REAL NOT NULL DEFAULT 0,
            monthly_deposit_krw REAL NOT NULL DEFAULT 0,
            is_fixed INTEGER NOT NULL DEFAULT 0,
            maturity_date TEXT,
            note TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()


class TestServerImports(unittest.TestCase):
    """server.py가 CRUD 함수를 올바르게 import하는지 검증 — 핵심 버그 재현"""

    def test_create_extra_asset_imported(self):
        """server 모듈에 create_extra_asset이 임포트되어야 한다"""
        import web.server as mod
        self.assertTrue(
            hasattr(mod, "create_extra_asset"),
            "server.py에 create_extra_asset이 import되지 않음 — POST 시 NameError 발생",
        )

    def test_update_extra_asset_by_id_imported(self):
        """server 모듈에 update_extra_asset_by_id가 임포트되어야 한다"""
        import web.server as mod
        self.assertTrue(
            hasattr(mod, "update_extra_asset_by_id"),
            "server.py에 update_extra_asset_by_id가 import되지 않음 — PUT 시 NameError 발생",
        )

    def test_delete_extra_asset_by_id_imported(self):
        """server 모듈에 delete_extra_asset_by_id가 임포트되어야 한다"""
        import web.server as mod
        self.assertTrue(
            hasattr(mod, "delete_extra_asset_by_id"),
            "server.py에 delete_extra_asset_by_id가 import되지 않음 — DELETE 시 NameError 발생",
        )


class TestWealthCrudFunctions(unittest.TestCase):
    """ssot_wealth CRUD 함수 동작 검증 (임시 DB 파일 사용)"""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        _create_test_db(self.db_path)
        self._patcher = patch(
            "db.ssot_wealth.get_conn",
            lambda: sqlite3.connect(self.db_path),
        )
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self.db_path)

    def test_create_extra_asset_returns_id(self):
        """create_extra_asset이 생성된 row의 id를 반환해야 한다"""
        from db.ssot_wealth import create_extra_asset
        asset_id = create_extra_asset(
            name="테스트현금",
            asset_type="현금",
            current_value_krw=1_000_000,
        )
        self.assertIsInstance(asset_id, int)
        self.assertGreater(asset_id, 0)

    def test_create_extra_asset_persists_to_db(self):
        """create_extra_asset 후 DB에서 조회 가능해야 한다"""
        from db.ssot_wealth import create_extra_asset, get_extra_assets
        create_extra_asset(
            name="국민은행 통장",
            asset_type="현금",
            current_value_krw=5_000_000,
        )
        assets = get_extra_assets()
        self.assertIn("국민은행 통장", [a["name"] for a in assets])

    def test_update_extra_asset_by_id_changes_value(self):
        """update_extra_asset_by_id가 금액을 올바르게 수정해야 한다"""
        from db.ssot_wealth import create_extra_asset, update_extra_asset_by_id, get_extra_assets
        asset_id = create_extra_asset(
            name="적금계좌",
            asset_type="적금",
            current_value_krw=3_000_000,
        )
        ok = update_extra_asset_by_id(
            asset_id=asset_id,
            name="적금계좌",
            asset_type="적금",
            current_value_krw=4_000_000,
            monthly_deposit_krw=0,
            is_fixed=False,
        )
        self.assertTrue(ok)
        assets = get_extra_assets()
        updated = next(a for a in assets if a["id"] == asset_id)
        self.assertEqual(updated["current_value_krw"], 4_000_000)

    def test_update_extra_asset_by_id_nonexistent_returns_false(self):
        """존재하지 않는 id로 update 시 False를 반환해야 한다"""
        from db.ssot_wealth import update_extra_asset_by_id
        ok = update_extra_asset_by_id(
            asset_id=9999,
            name="없는자산",
            asset_type="기타",
            current_value_krw=0,
            monthly_deposit_krw=0,
            is_fixed=False,
        )
        self.assertFalse(ok)

    def test_delete_extra_asset_by_id_removes_asset(self):
        """delete_extra_asset_by_id 후 해당 자산이 목록에서 사라져야 한다"""
        from db.ssot_wealth import create_extra_asset, delete_extra_asset_by_id, get_extra_assets
        asset_id = create_extra_asset(
            name="삭제할자산",
            asset_type="기타",
            current_value_krw=0,
        )
        ok = delete_extra_asset_by_id(asset_id)
        self.assertTrue(ok)
        ids = [a["id"] for a in get_extra_assets()]
        self.assertNotIn(asset_id, ids)

    def test_delete_extra_asset_by_id_nonexistent_returns_false(self):
        """존재하지 않는 id 삭제 시 False를 반환해야 한다"""
        from db.ssot_wealth import delete_extra_asset_by_id
        ok = delete_extra_asset_by_id(9999)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()

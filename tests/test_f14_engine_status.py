"""
F14 — engine_status.json 엔진 상태 모니터링 테스트
각 수집 모듈 실행 후 상태 기록, 에러 횟수, DB 용량, 연속 가동일 등
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.engine_status import (
    EngineStatus,
    record_module_status,
    get_db_size_mb,
    get_uptime_days,
    build_engine_status,
    save_engine_status,
    run,
)

KST = timezone(timedelta(hours=9))


# ── EngineStatus 클래스 테스트 ──


class TestEngineStatus:
    """EngineStatus 싱글턴 상태 관리 테스트"""

    def test_record_success(self):
        """성공 상태 기록"""
        status = EngineStatus()
        status.reset()
        status.record("fetch_prices", success=True, item_count=8, error_count=0)

        result = status.get("fetch_prices")
        assert result["success"] is True
        assert result["item_count"] == 8
        assert result["error_count"] == 0
        assert "last_run" in result

    def test_record_failure(self):
        """실패 상태 기록"""
        status = EngineStatus()
        status.reset()
        status.record(
            "fetch_macro",
            success=False,
            item_count=5,
            error_count=3,
            error_msg="API 타임아웃",
        )

        result = status.get("fetch_macro")
        assert result["success"] is False
        assert result["error_count"] == 3
        assert result["error_msg"] == "API 타임아웃"

    def test_record_overwrites_previous(self):
        """동일 모듈 재기록 시 덮어쓰기"""
        status = EngineStatus()
        status.reset()
        status.record("fetch_prices", success=False, item_count=0, error_count=8)
        status.record("fetch_prices", success=True, item_count=8, error_count=0)

        result = status.get("fetch_prices")
        assert result["success"] is True
        assert result["error_count"] == 0

    def test_get_nonexistent_module(self):
        """존재하지 않는 모듈 조회 시 None 반환"""
        status = EngineStatus()
        status.reset()
        assert status.get("nonexistent") is None

    def test_total_errors(self):
        """전체 에러 횟수 합산"""
        status = EngineStatus()
        status.reset()
        status.record("fetch_prices", success=True, item_count=8, error_count=1)
        status.record("fetch_macro", success=True, item_count=6, error_count=2)
        status.record("fetch_news", success=False, item_count=0, error_count=5)

        assert status.total_errors() == 8

    def test_all_modules(self):
        """전체 모듈 상태 조회"""
        status = EngineStatus()
        status.reset()
        status.record("fetch_prices", success=True, item_count=8, error_count=0)
        status.record("fetch_macro", success=True, item_count=6, error_count=0)

        all_status = status.all()
        assert "fetch_prices" in all_status
        assert "fetch_macro" in all_status
        assert len(all_status) == 2


# ── record_module_status 헬퍼 테스트 ──


class TestRecordModuleStatus:
    """record_module_status 래퍼 함수 테스트"""

    def test_record_with_records_list(self):
        """레코드 리스트 기반 자동 성공/실패 카운트"""
        status = EngineStatus()
        status.reset()

        records = [
            {"ticker": "005930.KS", "price": 55000},
            {"ticker": "TSLA", "price": 250.0},
            {"ticker": "GOOGL", "error": "API 타임아웃"},
        ]

        record_module_status(
            status,
            "fetch_prices",
            records,
            success_key="price",
        )

        result = status.get("fetch_prices")
        assert result["success"] is True  # 일부 성공이면 True
        assert result["item_count"] == 2
        assert result["error_count"] == 1

    def test_record_all_failed(self):
        """전부 실패 시 success=False"""
        status = EngineStatus()
        status.reset()

        records = [
            {"ticker": "A", "error": "실패1"},
            {"ticker": "B", "error": "실패2"},
        ]

        record_module_status(status, "fetch_prices", records, success_key="price")

        result = status.get("fetch_prices")
        assert result["success"] is False
        assert result["item_count"] == 0
        assert result["error_count"] == 2

    def test_record_empty_records(self):
        """빈 레코드 리스트"""
        status = EngineStatus()
        status.reset()

        record_module_status(status, "fetch_news", [], success_key="title")

        result = status.get("fetch_news")
        assert result["success"] is False
        assert result["item_count"] == 0
        assert result["error_count"] == 0


# ── DB 용량 조회 테스트 ──


class TestGetDbSize:
    """DB 파일 용량 조회 테스트"""

    def test_db_size_existing_file(self, tmp_path):
        """실제 DB 파일 용량 측정"""
        db_file = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_file))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        size = get_db_size_mb(db_file)
        assert isinstance(size, float)
        assert size >= 0

    def test_db_size_nonexistent_file(self, tmp_path):
        """존재하지 않는 DB 파일 → 0.0"""
        db_file = tmp_path / "nonexistent.db"
        assert get_db_size_mb(db_file) == 0.0


# ── 연속 가동일 계산 테스트 ──


class TestGetUptimeDays:
    """연속 가동일 계산 테스트"""

    def test_uptime_with_status_file(self, tmp_path):
        """기존 engine_status.json에서 first_run 읽기"""
        status_file = tmp_path / "engine_status.json"
        # 3일 전 시작
        three_days_ago = (datetime.now(KST) - timedelta(days=3)).isoformat()
        data = {"first_run": three_days_ago}
        status_file.write_text(json.dumps(data), encoding="utf-8")

        days = get_uptime_days(status_file)
        assert days >= 3

    def test_uptime_no_status_file(self, tmp_path):
        """engine_status.json 없으면 0일"""
        status_file = tmp_path / "nonexistent.json"
        assert get_uptime_days(status_file) == 0

    def test_uptime_no_first_run_field(self, tmp_path):
        """first_run 필드 없으면 0일"""
        status_file = tmp_path / "engine_status.json"
        status_file.write_text("{}", encoding="utf-8")
        assert get_uptime_days(status_file) == 0


# ── build_engine_status 테스트 ──


class TestBuildEngineStatus:
    """엔진 상태 JSON 빌드 테스트"""

    def test_build_with_modules(self, tmp_path):
        """모듈 상태 포함 빌드"""
        status = EngineStatus()
        status.reset()
        status.record("fetch_prices", success=True, item_count=8, error_count=0)
        status.record("fetch_macro", success=True, item_count=6, error_count=2)

        db_file = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_file))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        result = build_engine_status(status, db_path=db_file, output_dir=tmp_path)

        # 최상위 필드 확인
        assert "updated_at" in result
        assert "pipeline_ok" in result
        assert "total_errors" in result
        assert "db_size_mb" in result
        assert "uptime_days" in result
        assert "modules" in result
        assert "first_run" in result

        # 값 검증
        assert result["pipeline_ok"] is True
        assert result["total_errors"] == 2
        assert isinstance(result["db_size_mb"], float)
        assert "fetch_prices" in result["modules"]
        assert "fetch_macro" in result["modules"]

    def test_build_pipeline_not_ok_when_critical_fails(self, tmp_path):
        """핵심 모듈 실패 시 pipeline_ok=False"""
        status = EngineStatus()
        status.reset()
        status.record("fetch_prices", success=False, item_count=0, error_count=8)

        result = build_engine_status(
            status, db_path=tmp_path / "nonexistent.db", output_dir=tmp_path
        )

        assert result["pipeline_ok"] is False

    def test_build_preserves_first_run(self, tmp_path):
        """기존 first_run 보존"""
        status = EngineStatus()
        status.reset()

        # 기존 상태 파일에 first_run 설정
        status_file = tmp_path / "engine_status.json"
        original_first_run = "2026-03-20T10:00:00+09:00"
        status_file.write_text(
            json.dumps({"first_run": original_first_run}), encoding="utf-8"
        )

        result = build_engine_status(
            status, db_path=tmp_path / "test.db", output_dir=tmp_path
        )

        assert result["first_run"] == original_first_run


# ── save_engine_status 테스트 ──


class TestSaveEngineStatus:
    """engine_status.json 파일 저장 테스트"""

    def test_save_creates_file(self, tmp_path):
        """JSON 파일 생성 확인"""
        data = {
            "updated_at": "2026-03-25T10:00:00+09:00",
            "pipeline_ok": True,
            "total_errors": 0,
            "db_size_mb": 1.5,
            "uptime_days": 5,
            "first_run": "2026-03-20T10:00:00+09:00",
            "modules": {},
        }

        save_engine_status(data, output_dir=tmp_path)

        saved_file = tmp_path / "engine_status.json"
        assert saved_file.exists()

        saved = json.loads(saved_file.read_text(encoding="utf-8"))
        assert saved["pipeline_ok"] is True
        assert saved["total_errors"] == 0

    def test_save_overwrites_existing(self, tmp_path):
        """기존 파일 덮어쓰기"""
        old_data = {"pipeline_ok": False}
        (tmp_path / "engine_status.json").write_text(
            json.dumps(old_data), encoding="utf-8"
        )

        new_data = {
            "updated_at": "2026-03-25T12:00:00+09:00",
            "pipeline_ok": True,
            "total_errors": 0,
            "db_size_mb": 2.0,
            "uptime_days": 5,
            "first_run": "2026-03-20T10:00:00+09:00",
            "modules": {},
        }

        save_engine_status(new_data, output_dir=tmp_path)

        saved = json.loads(
            (tmp_path / "engine_status.json").read_text(encoding="utf-8")
        )
        assert saved["pipeline_ok"] is True


# ── run() 통합 테스트 ──


class TestRun:
    """run() 진입점 통합 테스트"""

    def test_run_returns_status_data(self, tmp_path):
        """run() 호출 시 상태 데이터 반환"""
        status = EngineStatus()
        status.reset()
        status.record("fetch_prices", success=True, item_count=8, error_count=0)

        db_file = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_file))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        result = run(status, db_path=db_file, output_dir=tmp_path)

        assert result["pipeline_ok"] is True
        assert (tmp_path / "engine_status.json").exists()

    def test_run_without_status_creates_minimal(self, tmp_path):
        """빈 상태로 run() 호출"""
        status = EngineStatus()
        status.reset()

        result = run(status, db_path=tmp_path / "test.db", output_dir=tmp_path)

        assert "updated_at" in result
        assert result["total_errors"] == 0
        assert result["modules"] == {}

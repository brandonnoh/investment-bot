"""
엔진 상태 모니터링 모듈
각 수집/분석 모듈 실행 후 상태 기록, DB 용량, 연속 가동일 등
출력: output/intel/engine_status.json
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


class EngineStatus:
    """파이프라인 내 모듈별 실행 상태를 수집하는 컨테이너"""

    def __init__(self):
        self._modules = {}

    def reset(self):
        """상태 초기화 (테스트용)"""
        self._modules = {}

    def record(
        self, module_name, *, success, item_count=0, error_count=0, error_msg=None
    ):
        """모듈 실행 결과 기록

        Args:
            module_name: 모듈 이름 (예: "fetch_prices")
            success: 실행 성공 여부
            item_count: 성공 항목 수
            error_count: 에러 항목 수
            error_msg: 대표 에러 메시지 (선택)
        """
        entry = {
            "success": success,
            "item_count": item_count,
            "error_count": error_count,
            "last_run": datetime.now(KST).isoformat(),
        }
        if error_msg:
            entry["error_msg"] = error_msg
        self._modules[module_name] = entry

    def get(self, module_name):
        """특정 모듈 상태 조회 (없으면 None)"""
        return self._modules.get(module_name)

    def total_errors(self):
        """전체 에러 횟수 합산"""
        return sum(m["error_count"] for m in self._modules.values())

    def all(self):
        """전체 모듈 상태 딕셔너리 반환"""
        return dict(self._modules)


def record_module_status(status, module_name, records, *, success_key="price"):
    """레코드 리스트 기반으로 모듈 상태 자동 기록

    Args:
        status: EngineStatus 인스턴스
        module_name: 모듈 이름
        records: 수집 결과 리스트
        success_key: 성공 판별 키 (해당 키에 값이 있으면 성공)
    """
    if not records:
        status.record(module_name, success=False, item_count=0, error_count=0)
        return

    success_count = sum(1 for r in records if r.get(success_key) is not None)
    error_count = len(records) - success_count

    status.record(
        module_name,
        success=success_count > 0,
        item_count=success_count,
        error_count=error_count,
    )


def get_db_size_mb(db_path):
    """DB 파일 용량 (MB) 반환. 파일 없으면 0.0"""
    db_path = Path(db_path)
    if not db_path.exists():
        return 0.0
    return round(db_path.stat().st_size / (1024 * 1024), 2)


def get_uptime_days(status_file):
    """engine_status.json의 first_run으로부터 연속 가동일 계산"""
    status_file = Path(status_file)
    if not status_file.exists():
        return 0

    try:
        data = json.loads(status_file.read_text(encoding="utf-8"))
        first_run = data.get("first_run")
        if not first_run:
            return 0
        first_dt = datetime.fromisoformat(first_run)
        now = datetime.now(KST)
        return (now - first_dt).days
    except (json.JSONDecodeError, ValueError):
        return 0


def build_engine_status(status, *, db_path=None, output_dir=None):
    """엔진 상태 JSON 데이터 빌드

    Args:
        status: EngineStatus 인스턴스
        db_path: DB 파일 경로 (기본: config.DB_PATH)
        output_dir: 출력 디렉토리 (기본: config.OUTPUT_DIR)

    Returns:
        dict: engine_status.json에 저장할 데이터
    """
    if db_path is None:
        from config import DB_PATH

        db_path = DB_PATH
    if output_dir is None:
        from config import OUTPUT_DIR

        output_dir = OUTPUT_DIR

    output_dir = Path(output_dir)
    status_file = output_dir / "engine_status.json"

    # 기존 first_run 보존
    first_run = None
    if status_file.exists():
        try:
            existing = json.loads(status_file.read_text(encoding="utf-8"))
            first_run = existing.get("first_run")
        except (json.JSONDecodeError, ValueError):
            pass

    if not first_run:
        first_run = datetime.now(KST).isoformat()

    # 핵심 모듈 중 하나라도 실패하면 pipeline_ok=False
    modules = status.all()
    critical_modules = ["fetch_prices", "fetch_macro"]
    pipeline_ok = True
    for cm in critical_modules:
        if cm in modules and not modules[cm]["success"]:
            pipeline_ok = False
            break

    return {
        "updated_at": datetime.now(KST).isoformat(),
        "pipeline_ok": pipeline_ok,
        "total_errors": status.total_errors(),
        "db_size_mb": get_db_size_mb(db_path),
        "uptime_days": get_uptime_days(status_file),
        "first_run": first_run,
        "modules": modules,
    }


def save_engine_status(data, *, output_dir=None):
    """engine_status.json 파일 저장

    Args:
        data: 저장할 딕셔너리
        output_dir: 출력 디렉토리 (기본: config.OUTPUT_DIR)
    """
    if output_dir is None:
        from config import OUTPUT_DIR

        output_dir = OUTPUT_DIR

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filepath = output_dir / "engine_status.json"
    filepath.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"엔진 상태 저장: {filepath}")


def run(status=None, *, db_path=None, output_dir=None):
    """엔진 상태 모니터링 실행 — 빌드 + 저장

    Args:
        status: EngineStatus 인스턴스 (None이면 빈 상태)
        db_path: DB 파일 경로
        output_dir: 출력 디렉토리

    Returns:
        dict: 저장된 상태 데이터
    """
    if status is None:
        status = EngineStatus()

    data = build_engine_status(status, db_path=db_path, output_dir=output_dir)
    save_engine_status(data, output_dir=output_dir)

    ok_str = "✅" if data["pipeline_ok"] else "⚠️"
    print(
        f"\n{ok_str} 엔진 상태: 에러 {data['total_errors']}건, DB {data['db_size_mb']}MB"
    )

    return data

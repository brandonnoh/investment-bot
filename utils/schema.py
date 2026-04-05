"""
JSON 출력 스키마 검증 모듈
output/intel/ 파일의 필수 필드 + 타입 검증
파이프라인 중단 없이 경고 로그만 기록
"""

import json
import logging
from pathlib import Path

from utils.schema_defs import SCHEMAS  # noqa: F401  하위 호환 re-export

logger = logging.getLogger(__name__)


def _check_type(value, expected_type):
    """값이 기대 타입과 일치하는지 확인"""
    if expected_type == "number":
        return isinstance(value, (int, float))
    return isinstance(value, expected_type)


def _type_name(expected_type) -> str:
    """기대 타입의 이름 문자열 반환"""
    return expected_type if isinstance(expected_type, str) else expected_type.__name__


def _validate_top_level(filename, data, schema) -> list:
    """최상위 필드 검증 — 누락/타입 불일치 경고 반환"""
    warnings = []
    for field, expected_type in schema["top_level"].items():
        if field not in data:
            warnings.append(f"[{filename}] 필수 필드 '{field}' 누락")
        elif data[field] is not None and not _check_type(data[field], expected_type):
            warnings.append(
                f"[{filename}] 필드 '{field}' 타입 불일치: "
                f"기대={_type_name(expected_type)}, 실제={type(data[field]).__name__}"
            )
    return warnings


def _validate_nested(filename, data, schema) -> list:
    """중첩 딕셔너리 필드 검증 (예: portfolio_summary.total)"""
    warnings = []
    for nested_key, nested_fields in schema.get("nested", {}).items():
        nested_data = data.get(nested_key)
        if not isinstance(nested_data, dict):
            continue
        for field, expected_type in nested_fields.items():
            if field not in nested_data:
                warnings.append(f"[{filename}] {nested_key}.'{field}' 누락")
            elif nested_data[field] is not None and not _check_type(
                nested_data[field], expected_type
            ):
                warnings.append(
                    f"[{filename}] {nested_key}.'{field}' 타입 불일치: "
                    f"기대={_type_name(expected_type)}, 실제={type(nested_data[field]).__name__}"
                )
    return warnings


def _validate_item(filename, idx, item, item_fields) -> list:
    """개별 아이템 필드 검증 — 누락/None/타입 불일치 경고 반환"""
    warnings = []
    for field, expected_type in item_fields.items():
        if field not in item:
            warnings.append(f"[{filename}] 항목[{idx}] 필수 필드 '{field}' 누락")
        elif item[field] is None:
            warnings.append(
                f"[{filename}] 항목[{idx}] 필드 '{field}'이 None "
                f"(기대 타입: {_type_name(expected_type)})"
            )
        elif not _check_type(item[field], expected_type):
            warnings.append(
                f"[{filename}] 항목[{idx}] 필드 '{field}' 타입 불일치: "
                f"기대={_type_name(expected_type)}, 실제={type(item[field]).__name__}"
            )
    return warnings


def _validate_items(filename, data, schema) -> list:
    """항목(아이템) 컬렉션 검증 — 리스트 또는 딕셔너리 구조 모두 지원"""
    warnings = []
    items_key = schema.get("items_key")
    if not items_key or items_key not in data:
        return warnings

    items_data = data[items_key]
    items_type = schema.get("items_type", "list")

    if items_type == "dict" and isinstance(items_data, dict):
        # price_analysis.json 같은 딕셔너리 구조
        items = list(items_data.items())
    elif isinstance(items_data, list):
        items = list(enumerate(items_data))
    else:
        return warnings

    item_fields = schema.get("item_fields", {})
    for idx, item in items:
        if not isinstance(item, dict):
            continue
        # error 필드가 있는 항목은 스킵 (graceful degradation)
        if item.get("error"):
            continue
        warnings.extend(_validate_item(filename, idx, item, item_fields))

    return warnings


def validate_json(filename, data):
    """
    JSON 데이터를 스키마에 따라 검증.

    Args:
        filename: 스키마 이름 (예: "prices.json")
        data: 검증할 딕셔너리

    Returns:
        list[str]: 경고 메시지 목록 (빈 리스트 = 정상)
    """
    if filename not in SCHEMAS:
        return []

    schema = SCHEMAS[filename]
    warnings = []
    warnings.extend(_validate_top_level(filename, data, schema))
    warnings.extend(_validate_nested(filename, data, schema))
    warnings.extend(_validate_items(filename, data, schema))
    return warnings


def validate_all_outputs(output_dir=None):
    """
    output/intel/ 디렉토리의 모든 JSON 파일을 검증.

    Args:
        output_dir: 검증할 디렉토리 경로 (기본: config.OUTPUT_DIR)

    Returns:
        dict[str, list[str]]: 파일별 경고 목록
    """
    if output_dir is None:
        from config import OUTPUT_DIR

        output_dir = OUTPUT_DIR

    output_dir = Path(output_dir)
    all_warnings = {}

    for filename in SCHEMAS:
        filepath = output_dir / filename
        if not filepath.exists():
            continue

        try:
            with filepath.open(encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            all_warnings[filename] = [f"[{filename}] JSON 파싱 실패: {e}"]
            continue

        warnings = validate_json(filename, data)
        all_warnings[filename] = warnings

        if warnings:
            for w in warnings:
                logger.warning(w)
        else:
            logger.info(f"[{filename}] 스키마 검증 통과")

    return all_warnings

#!/usr/bin/env python3
"""
원자적 JSON 쓰기 유틸리티.
tempfile + os.replace() 패턴으로 쓰다 중단돼도 기존 파일이 손상되지 않는다.
"""

import json
import os
import tempfile
from pathlib import Path


def write_json_atomic(path: Path, data: dict | list, indent: int = 2) -> None:
    """JSON을 임시 파일에 쓴 뒤 os.replace()로 원자적으로 교체."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=path.parent,
        suffix=".tmp",
        delete=False,
        encoding="utf-8",
    ) as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
        tmp_path = f.name
    os.replace(tmp_path, path)

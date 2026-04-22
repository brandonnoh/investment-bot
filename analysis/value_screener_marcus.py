#!/usr/bin/env python3
"""Marcus discovery_keywords.json → 섹터 매핑 헬퍼."""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DISCOVERY_KEYWORDS_PATH = PROJECT_ROOT / "output" / "intel" / "discovery_keywords.json"

# Marcus 키워드 텍스트 → 섹터 힌트 매핑
KEYWORD_SECTOR_HINTS: dict[str, str] = {
    "방산": "방산", "defense": "방산", "aerospace": "방산",
    "반도체": "반도체", "semiconductor": "반도체", "AI칩": "반도체",
    "AI": "AI/소프트웨어", "인공지능": "AI/소프트웨어", "클라우드": "AI/소프트웨어",
    "에너지": "에너지", "oil": "에너지", "원유": "에너지",
    "금융": "금융", "bank": "금융", "금리": "금융",
    "바이오": "바이오/헬스케어", "헬스케어": "바이오/헬스케어", "pharma": "바이오/헬스케어",
    "2차전지": "2차전지", "배터리": "2차전지", "리튬": "2차전지",
    "자동차": "자동차", "전기차": "자동차", "EV": "자동차",
    "원자재": "원자재/화학", "철강": "원자재/화학", "화학": "원자재/화학",
    "소비재": "소비재/리테일", "유통": "소비재/리테일",
}


def load_marcus_sectors() -> set[str]:
    """discovery_keywords.json 키워드를 섹터로 매핑해 set 반환.

    파일 없거나 매핑 실패 시 빈 set 반환 → 전체 허용.
    """
    if not DISCOVERY_KEYWORDS_PATH.exists():
        return set()
    try:
        data = json.loads(DISCOVERY_KEYWORDS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()

    sectors: set[str] = set()
    for item in data.get("keywords", []):
        text = item.get("keyword", "")
        for hint, sector in KEYWORD_SECTOR_HINTS.items():
            if hint in text:
                sectors.add(sector)
    return sectors

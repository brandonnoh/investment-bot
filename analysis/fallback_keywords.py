#!/usr/bin/env python3
"""
Discovery Keywords Fallback — Marcus 크론 실패 시 자동 키워드 생성
regime.json + macro.json 기반으로 시장 국면에 맞는 키워드 생성
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
STALE_HOURS = 25

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output" / "intel"
MACRO_PATH = OUTPUT_DIR / "macro.json"
REGIME_PATH = OUTPUT_DIR / "regime.json"

_REGIME_KEYWORDS = {
    "RISK_ON": [
        {"keyword": "성장주 기술주 반도체 수혜", "category": "sector", "priority": 1},
        {"keyword": "코스피 강세 외국인 순매수", "category": "macro", "priority": 2},
        {"keyword": "AI 전력 인프라 데이터센터", "category": "theme", "priority": 3},
    ],
    "RISK_OFF": [
        {"keyword": "방산 수주 방어주 안전자산", "category": "sector", "priority": 1},
        {"keyword": "금 달러 강세 헤지", "category": "macro", "priority": 2},
        {"keyword": "배당주 고배당 저변동성", "category": "sector", "priority": 3},
    ],
    "INFLATIONARY": [
        {"keyword": "에너지 원유 정유 수혜주", "category": "sector", "priority": 1},
        {"keyword": "소재 원자재 인플레이션 수혜", "category": "sector", "priority": 2},
        {"keyword": "수출주 달러강세 수혜", "category": "fx", "priority": 3},
    ],
    "STAGFLATION": [
        {"keyword": "금 방산 배당주 스태그플레이션", "category": "sector", "priority": 1},
        {"keyword": "현금비중 방어포트폴리오", "category": "macro", "priority": 2},
        {"keyword": "내수 방어주 경기침체 수혜", "category": "sector", "priority": 3},
    ],
}


def is_keywords_fresh(keywords_path: Path) -> bool:
    if not keywords_path.exists():
        return False
    try:
        data = json.loads(keywords_path.read_text())
        ts_str = data.get("generated_at", "")
        if not ts_str:
            return False
        ts = datetime.fromisoformat(ts_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=KST)
        age_hours = (datetime.now(KST) - ts).total_seconds() / 3600
        return age_hours < STALE_HOURS
    except Exception:
        return False


def generate_fallback_keywords(macro_path: Path, regime_path: Path) -> list:
    regime = "RISK_OFF"
    try:
        regime_data = json.loads(regime_path.read_text())
        regime = regime_data.get("regime", "RISK_OFF")
    except Exception:
        pass

    keywords = list(_REGIME_KEYWORDS.get(regime, _REGIME_KEYWORDS["RISK_OFF"]))

    try:
        macro_data = json.loads(macro_path.read_text())
        for ind in macro_data.get("indicators", []):
            name = ind.get("indicator", "")
            value = ind.get("value") or 0
            if name == "VIX" and value > 25:
                keywords.append(
                    {"keyword": "저변동성 방어주 배당", "category": "volatility", "priority": 4}
                )
            if name == "원/달러" and value > 1450:
                keywords.append(
                    {"keyword": "수출 선도기업 환율 수혜", "category": "fx", "priority": 4}
                )
    except Exception:
        pass

    seen = set()
    result = []
    for kw in sorted(keywords, key=lambda k: k["priority"]):
        if kw["keyword"] not in seen:
            seen.add(kw["keyword"])
            result.append(kw)
        if len(result) >= 5:
            break

    logger.info(f"Fallback 키워드 생성: {len(result)}건 (regime={regime})")
    return result


def save_fallback_keywords(keywords: list, output_path: Path) -> None:
    data = {
        "generated_at": datetime.now(KST).isoformat(),
        "source": "fallback",
        "keywords": keywords,
    }
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    logger.info(f"Fallback 키워드 저장: {output_path}")


def ensure_fresh_keywords(keywords_path: Path, output_dir: Path | None = None) -> bool:
    """키워드 파일이 stale이면 fallback으로 갱신. True=fresh, False=fallback 사용."""
    if is_keywords_fresh(keywords_path):
        return True

    out_dir = output_dir or OUTPUT_DIR
    macro_path = Path(out_dir) / "macro.json" if output_dir else MACRO_PATH
    regime_path = Path(out_dir) / "regime.json" if output_dir else REGIME_PATH

    keywords = generate_fallback_keywords(macro_path, regime_path)
    if keywords:
        save_fallback_keywords(keywords, keywords_path)
        logger.warning(f"Discovery keywords stale/missing — fallback 사용 ({len(keywords)}건)")
    return False

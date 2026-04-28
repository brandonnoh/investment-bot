#!/usr/bin/env python3
"""
자기 교정 시스템 — 성과 분석 결과를 교정 노트로 변환
performance_report.json → correction_notes.json
Marcus가 다음 분석 시 이 파일을 읽어 판단 보정에 활용
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
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output" / "intel"

# avg_score_hit 기준 임계값 (performance.py의 avg_score_hit은 0~1 범위 점수)
WEAK_THRESHOLD = 0.40
STRONG_THRESHOLD = 0.60


def generate_correction_notes(performance_data: dict) -> dict:
    """성과 보고서에서 교정 노트 생성.

    Args:
        performance_data: performance_report.json 전체 데이터

    Returns:
        교정 노트 dict (weak_factors, strong_factors, weight_adjustment, summary 포함)
    """
    monthly = performance_data.get("monthly_report", {})
    factor_analysis = monthly.get("factor_analysis", {})

    # weight_suggestion은 최상위 또는 monthly_report 안에 있을 수 있음
    weight_section = performance_data.get("weight_suggestion", {})
    weight_suggestion = weight_section.get("suggested_weights", weight_section)

    hit_rate = monthly.get("hit_rate_1w", monthly.get("hit_rate", 0))
    avg_return = monthly.get("avg_return_1w", monthly.get("avg_return", 0))

    # 팩터 강약 분류: avg_score_hit 기준
    weak_factors = [
        f
        for f, data in factor_analysis.items()
        if data.get("avg_score_hit", data.get("hit_rate", 0.5)) < WEAK_THRESHOLD
    ]
    strong_factors = [
        f
        for f, data in factor_analysis.items()
        if data.get("avg_score_hit", data.get("hit_rate", 0.5)) > STRONG_THRESHOLD
    ]

    # 성과 판정
    # Normalize: if >1 assume 0-100 scale
    normalized_rate = hit_rate / 100 if hit_rate > 1 else hit_rate
    if normalized_rate >= 0.6:
        performance_verdict = "양호"
    elif normalized_rate >= 0.4:
        performance_verdict = "보통"
    else:
        performance_verdict = "부진"

    # hit_rate가 0~100 범위인지 0~1 범위인지 판단
    if hit_rate > 1:
        hit_rate_display = f"{hit_rate:.1f}%"
    else:
        hit_rate_display = f"{hit_rate:.0%}"

    if avg_return > 1 or avg_return < -1:
        avg_return_display = f"{avg_return:.2f}%"
    else:
        avg_return_display = f"{avg_return:.1%}"

    summary_parts = [
        f"지난 달 적중률 {hit_rate_display} ({performance_verdict}), "
        f"평균 수익률 {avg_return_display}."
    ]
    if weak_factors:
        summary_parts.append(f"약한 팩터: {', '.join(weak_factors)} — 해당 종목 추천 시 신중히.")
    if strong_factors:
        summary_parts.append(f"강한 팩터: {', '.join(strong_factors)} — 해당 신호 신뢰도 높음.")
    if weight_suggestion:
        summary_parts.append("가중치 조정 적용됨.")

    period = monthly.get("period", "unknown")

    return {
        "period": period,
        "weak_factors": weak_factors,
        "strong_factors": strong_factors,
        "weight_adjustment": weight_suggestion,
        "summary": " ".join(summary_parts),
    }


def save_correction_notes(notes: dict, output_path: Path) -> None:
    """교정 노트를 JSON 파일로 저장.

    Args:
        notes: 교정 노트 dict
        output_path: 저장 경로
    """
    data = {**notes, "generated_at": datetime.now(KST).isoformat()}
    output_path = Path(output_path)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    logger.info(f"교정 노트 저장: {output_path}")
    return data


def run(
    performance_path: Path | None = None,
    output_dir: Path | None = None,
) -> dict | None:
    """파이프라인 진입점.

    Args:
        performance_path: performance_report.json 경로
        output_dir: correction_notes.json 출력 디렉토리

    Returns:
        교정 노트 dict, 또는 None (입력 없거나 오류 시)
    """
    perf_path = (
        Path(performance_path) if performance_path else OUTPUT_DIR / "performance_report.json"
    )
    out_dir = Path(output_dir) if output_dir else OUTPUT_DIR

    if not perf_path.exists():
        logger.info(f"성과 보고서 없음: {perf_path} — 교정 건너뜀")
        return None

    try:
        data = json.loads(perf_path.read_text())
    except Exception as e:
        logger.error(f"성과 보고서 읽기 실패: {e}")
        return None

    if "monthly_report" not in data:
        logger.info("월간 보고서 없음 — 교정 건너뜀")
        return None

    notes = generate_correction_notes(data)
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = save_correction_notes(notes, out_dir / "correction_notes.json")

    try:
        from db.connection import get_db_conn

        date = saved["generated_at"][:10]
        with get_db_conn() as conn:
            conn.execute(
                """INSERT INTO correction_notes_history
                       (date, period, weak_factors_json, strong_factors_json,
                        weight_adjustment_json, summary, generated_at)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(date) DO UPDATE SET
                       period=excluded.period,
                       weak_factors_json=excluded.weak_factors_json,
                       strong_factors_json=excluded.strong_factors_json,
                       weight_adjustment_json=excluded.weight_adjustment_json,
                       summary=excluded.summary,
                       generated_at=excluded.generated_at""",
                (
                    date,
                    saved.get("period"),
                    json.dumps(saved.get("weak_factors"), ensure_ascii=False),
                    json.dumps(saved.get("strong_factors"), ensure_ascii=False),
                    json.dumps(saved.get("weight_adjustment"), ensure_ascii=False),
                    saved.get("summary"),
                    saved["generated_at"],
                ),
            )
    except Exception as e:
        logger.error(f"[self_correction] DB 이력 저장 실패: {e}")
    return notes

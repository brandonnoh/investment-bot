"""성과 리포트 생성 레이어

- 월간 성적표 생성 (적중률, 평균 수익률, 팩터별 기여도)
- 마커스용 가중치 조정 제안
- output/intel/performance_report.json 저장
"""

import json
import logging
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

KST = timezone(timedelta(hours=9))
logger = logging.getLogger(__name__)


def _get_db_conn():
    """파일 DB 연결 반환"""
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def generate_monthly_report(conn=None, months=1):
    """월간 성적표 생성.

    Args:
        conn: DB 연결
        months: 조회 기간 (개월)

    Returns:
        dict: 월간 성적표
    """
    close_conn = False
    if conn is None:
        conn = _get_db_conn()
        close_conn = True

    now = datetime.now(KST)
    since = (now - timedelta(days=months * 30)).strftime("%Y-%m-%d")

    report = {
        "period": f"{since} ~ {now.strftime('%Y-%m-%d')}",
        "total_picks": 0,
        "hit_rate_1w": 0.0,
        "hit_rate_1m": 0.0,
        "avg_return_1w": 0.0,
        "avg_return_1m": 0.0,
        "factor_analysis": {},
        "top_picks": [],
        "bottom_picks": [],
    }

    try:
        rows = conn.execute(
            """
            SELECT ticker, name, discovered_at, composite_score,
                   score_value, score_quality, score_growth,
                   score_return, score_rsi, score_sentiment, score_macro,
                   price_at_discovery, outcome_1w, outcome_1m
            FROM opportunities
            WHERE discovered_at >= ?
              AND (outcome_1w IS NOT NULL OR outcome_1m IS NOT NULL)
            ORDER BY discovered_at DESC
        """,
            (since,),
        ).fetchall()

        if not rows:
            if close_conn:
                conn.close()
            return report

        report["total_picks"] = len(rows)

        # 적중률 + 평균 수익률
        hits_1w, returns_1w = 0, []
        hits_1m, returns_1m = 0, []

        for row in rows:
            if row["outcome_1w"] is not None:
                returns_1w.append(row["outcome_1w"])
                if row["outcome_1w"] > 0:
                    hits_1w += 1
            if row["outcome_1m"] is not None:
                returns_1m.append(row["outcome_1m"])
                if row["outcome_1m"] > 0:
                    hits_1m += 1

        if returns_1w:
            report["hit_rate_1w"] = round(hits_1w / len(returns_1w) * 100, 1)
            report["avg_return_1w"] = round(sum(returns_1w) / len(returns_1w), 2)
        if returns_1m:
            report["hit_rate_1m"] = round(hits_1m / len(returns_1m) * 100, 1)
            report["avg_return_1m"] = round(sum(returns_1m) / len(returns_1m), 2)

        # 팩터별 분석
        factors = ["value", "quality", "growth", "timing", "catalyst", "macro"]
        score_keys = {
            "value": "score_value",
            "quality": "score_quality",
            "growth": "score_growth",
            "timing": "score_return",  # timing ≈ return score
            "catalyst": "score_sentiment",
            "macro": "score_macro",
        }

        for factor in factors:
            key = score_keys[factor]
            hit_scores = []
            miss_scores = []

            for row in rows:
                score = row[key]
                outcome = row["outcome_1w"]
                if score is None or outcome is None:
                    continue
                if outcome > 0:
                    hit_scores.append(score)
                else:
                    miss_scores.append(score)

            report["factor_analysis"][factor] = {
                "avg_score_hit": round(sum(hit_scores) / len(hit_scores), 4)
                if hit_scores
                else 0.0,
                "avg_score_miss": round(sum(miss_scores) / len(miss_scores), 4)
                if miss_scores
                else 0.0,
                "hit_count": len(hit_scores),
                "miss_count": len(miss_scores),
            }

        # 최고/최저 성과
        with_1w = [r for r in rows if r["outcome_1w"] is not None]
        sorted_by_return = sorted(with_1w, key=lambda r: r["outcome_1w"], reverse=True)

        for row in sorted_by_return[:3]:
            report["top_picks"].append(
                {
                    "ticker": row["ticker"],
                    "name": row["name"],
                    "outcome_1w": row["outcome_1w"],
                    "outcome_1m": row["outcome_1m"],
                    "composite_score": row["composite_score"],
                }
            )

        for row in reversed(sorted_by_return[-3:]):
            report["bottom_picks"].append(
                {
                    "ticker": row["ticker"],
                    "name": row["name"],
                    "outcome_1w": row["outcome_1w"],
                    "outcome_1m": row["outcome_1m"],
                    "composite_score": row["composite_score"],
                }
            )

    except Exception as e:
        logger.error(f"월간 성적표 생성 실패: {e}")

    if close_conn:
        conn.close()

    return report


def generate_weight_suggestion(conn=None):
    """팩터 분석 기반 가중치 조정 제안.

    적중 그룹과 미적중 그룹의 팩터 점수 차이를 분석하여
    마커스가 가중치 조정을 검토할 수 있는 데이터 제공.

    Args:
        conn: DB 연결

    Returns:
        dict: 현재 가중치, 제안 가중치, 근거
    """
    current = config.OPPORTUNITY_CONFIG["composite_weights"].copy()

    suggestion = {
        "current_weights": current,
        "suggested_weights": current.copy(),
        "reasoning": [],
    }

    report = generate_monthly_report(conn=conn)
    fa = report.get("factor_analysis", {})

    if report["total_picks"] < 2:
        suggestion["reasoning"].append("데이터 부족 (최소 2건 필요) — 현재 가중치 유지")
        return suggestion

    # 적중/미적중 점수 차이가 큰 팩터 → 가중치 증가
    # 차이가 작거나 역전된 팩터 → 가중치 감소
    adjustments = {}
    for factor, data in fa.items():
        if data["hit_count"] == 0 or data["miss_count"] == 0:
            adjustments[factor] = 0.0
            continue
        diff = data["avg_score_hit"] - data["avg_score_miss"]
        adjustments[factor] = diff

    if not any(v != 0 for v in adjustments.values()):
        suggestion["reasoning"].append("팩터 차이 분석 불가 — 현재 가중치 유지")
        return suggestion

    # 조정 비율 계산 (차이 기반 상대 조정, 최대 ±0.05)
    new_weights = {}
    max_adjust = 0.05

    for factor in current:
        adj = adjustments.get(factor, 0.0)
        clamped = max(-max_adjust, min(max_adjust, adj * 0.1))
        new_weights[factor] = max(0.05, current[factor] + clamped)

    # 가중치 합 1.0으로 정규화
    total = sum(new_weights.values())
    if total > 0:
        new_weights = {k: round(v / total, 4) for k, v in new_weights.items()}

    # 합이 정확히 1.0이 되도록 보정
    remainder = round(1.0 - sum(new_weights.values()), 4)
    if remainder != 0:
        first_key = list(new_weights.keys())[0]
        new_weights[first_key] = round(new_weights[first_key] + remainder, 4)

    suggestion["suggested_weights"] = new_weights

    for factor, adj in adjustments.items():
        if adj > 0.1:
            suggestion["reasoning"].append(
                f"{factor}: 적중 그룹 점수가 높음 (+{adj:.3f}) → 가중치 증가 권장"
            )
        elif adj < -0.1:
            suggestion["reasoning"].append(
                f"{factor}: 미적중 그룹 점수가 오히려 높음 ({adj:.3f}) → 가중치 감소 권장"
            )

    if not suggestion["reasoning"]:
        suggestion["reasoning"].append("팩터 간 유의미한 차이 없음 — 미세 조정만 적용")

    return suggestion


def save_performance_report(conn=None, output_dir=None):
    """성과 리포트 JSON 저장.

    Args:
        conn: DB 연결
        output_dir: 출력 디렉토리 (기본: config.OUTPUT_DIR)
    """
    if output_dir is None:
        output_dir = config.OUTPUT_DIR

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(KST)

    # outcome 업데이트 결과 (순환 임포트 방지를 위해 lazy import)
    from analysis.performance import update_outcomes  # noqa: PLC0415

    outcome_result = update_outcomes(conn=conn)
    monthly = generate_monthly_report(conn=conn)
    weights = generate_weight_suggestion(conn=conn)

    report = {
        "updated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "outcome_summary": outcome_result,
        "monthly_report": monthly,
        "weight_suggestion": weights,
    }

    filepath = output_dir / "performance_report.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"성과 리포트 저장: {filepath}")
    return report

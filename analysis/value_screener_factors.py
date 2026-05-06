#!/usr/bin/env python3
"""5-팩터 가중 복합 점수 계산 — value_screener v2

팩터 가중치:
  수익성(Quality)  30%  — ROE + 영업이익률 + 부채비율
  가치(Value)      25%  — PBR + PER + 52주 저점 위치
  수급(Flow)       20%  — 외국인순매수 + 기관순매수
  모멘텀           15%  — RSI 역발상 (과매도 = 매력)
  성장(Growth)     10%  — 매출성장률 + EPS
"""

WEIGHTS: dict[str, float] = {
    "quality": 0.30,
    "value": 0.25,
    "flow": 0.20,
    "momentum": 0.15,
    "growth": 0.10,
}

# flow 데이터 없는 종목(미국 등)용 4팩터 재가중
WEIGHTS_NO_FLOW: dict[str, float] = {
    "quality": 0.35,
    "value": 0.30,
    "momentum": 0.20,
    "growth": 0.15,
}

_GRADE_CUTOFFS = [
    (0.90, "A+"),
    (0.80, "A"),
    (0.70, "B+"),
    (0.60, "B"),
    (0.50, "C"),
]

SCREEN_THRESHOLD = 0.60


def grade_from_score(score: float) -> str:
    for cutoff, label in _GRADE_CUTOFFS:
        if score >= cutoff:
            return label
    return "D"


# ── 개별 팩터 ──


def _factor_quality(m: dict) -> float:
    """수익성: ROE + 영업이익률 + 부채비율(역산)"""
    scores: list[float] = []
    roe = m.get("roe")
    if roe is not None:
        scores.append(min(1.0, max(0.0, roe / 25)))
    opm = m.get("operating_margin")
    if opm is not None:
        scores.append(min(1.0, max(0.0, opm / 25)))
    debt = m.get("debt_ratio")
    if debt is not None:
        scores.append(min(1.0, max(0.0, 1 - debt / 200)))
    return sum(scores) / len(scores) if scores else 0.5


def _factor_value(m: dict) -> float:
    """가치: PBR + PER + 52주 저점 위치"""
    scores: list[float] = []
    pbr = m.get("pbr")
    if pbr is not None and pbr > 0:
        scores.append(min(1.0, max(0.0, 1.5 / (pbr + 0.5))))
    per = m.get("per")
    if per is not None:
        if per <= 0 or per >= 100:
            scores.append(0.0)  # 적자 또는 고평가 → 낙제점
        else:
            scores.append(min(1.0, max(0.0, 1 - (per - 5) / 40)))
    pos = m.get("pos_52w_pct")
    if pos is not None:
        scores.append(min(1.0, max(0.0, 1 - pos / 100)))
    return sum(scores) / len(scores) if scores else 0.5


def _factor_momentum(m: dict) -> float:
    """모멘텀: RSI 역발상 — 과매도 구간이 진입 기회"""
    rsi = m.get("rsi")
    if rsi is None:
        return 0.5
    if rsi <= 25:
        return 1.0
    if rsi <= 35:
        return 0.85
    if rsi <= 45:
        return 0.60
    if rsi <= 55:
        return 0.40
    if rsi <= 65:
        return 0.25
    return 0.10


def _factor_flow(m: dict) -> float:
    """수급: 외국인 + 기관 순매수 (데이터 없으면 중립 0.5)"""
    scores: list[float] = []
    for key in ("foreign_net", "inst_net"):
        val = m.get(key)
        if val is not None:
            scores.append(min(1.0, max(0.0, 0.5 + val / 1e9)))
    return sum(scores) / len(scores) if scores else 0.5


def _factor_growth(m: dict) -> float:
    """성장: 매출성장률(%) + EPS 양수 여부"""
    scores: list[float] = []
    rev = m.get("revenue_growth")
    if rev is not None:
        # revenue_growth는 % 단위 (예: 18.0 = 18%). 60% 성장 = 만점
        scores.append(min(1.0, max(0.0, 0.5 + rev / 60)))
    eps = m.get("eps")
    if eps is not None:
        scores.append(1.0 if eps > 0 else 0.2)
    return sum(scores) / len(scores) if scores else 0.5


# ── 자연어 이유 생성 ──


def _generate_reason(m: dict, factors: dict[str, float]) -> str:
    reasons: list[str] = []

    fn = m.get("foreign_net")
    if fn and fn > 0:
        reasons.append("외국인 순매수")
    inst = m.get("inst_net")
    if inst and inst > 0:
        reasons.append("기관 순매수")

    rsi = m.get("rsi")
    if rsi is not None and rsi < 35:
        reasons.append(f"RSI {rsi:.0f} 과매도")

    pos = m.get("pos_52w_pct")
    if pos is not None and pos < 20:
        reasons.append("52주 저점 근접")

    pbr = m.get("pbr")
    if pbr and pbr < 1.0 and factors["value"] > 0.65:
        reasons.append(f"PBR {pbr:.1f} 저평가")

    per = m.get("per")
    if per and 0 < per < 12 and factors["value"] > 0.65:
        reasons.append(f"PER {per:.0f} 저평가")

    roe = m.get("roe")
    if roe and roe > 15 and factors["quality"] > 0.65:
        reasons.append(f"ROE {roe:.0f}%")

    rev = m.get("revenue_growth")
    if rev and rev > 15 and factors["growth"] > 0.65:
        reasons.append(f"매출 {rev:.0f}% 성장")

    if not reasons:
        best = max(factors, key=factors.get)
        labels = {
            "quality": "우수한 수익성",
            "value": "저평가 구간",
            "flow": "스마트머니 유입",
            "momentum": "기술적 저점",
            "growth": "성장 지속",
        }
        reasons.append(labels[best])

    return " + ".join(reasons[:3])


# ── 메인 진입점 ──


def calc_composite(metrics: dict) -> dict:
    """5(또는 4)팩터 복합 점수 계산 → {score, grade, factors, reason}

    flow 데이터(foreign_net, inst_net)가 없는 종목은 4팩터 가중치를 사용한다.
    """
    has_flow = (
        metrics.get("foreign_net") is not None
        or metrics.get("inst_net") is not None
    )

    factor_results: dict[str, float] = {
        "quality": _factor_quality(metrics),
        "value": _factor_value(metrics),
        "momentum": _factor_momentum(metrics),
        "growth": _factor_growth(metrics),
    }
    if has_flow:
        factor_results["flow"] = _factor_flow(metrics)
        weights = WEIGHTS
    else:
        weights = WEIGHTS_NO_FLOW

    score = round(sum(weights[k] * v for k, v in factor_results.items()), 4)
    return {
        "score": score,
        "grade": grade_from_score(score),
        "factors": {k: round(v, 3) for k, v in factor_results.items()},
        "reason": _generate_reason(metrics, factor_results),
    }

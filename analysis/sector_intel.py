#!/usr/bin/env python3
"""
섹터 인텔리전스 모듈

매크로 지표, 레짐, 뉴스를 종합하여 섹터별 점수를 산출한다.
- 기본 5.0점 → 레짐 preferred/avoid ±2.0
- MACRO_SECTOR_RULES 트리거 시 ±1.5
- 뉴스 키워드 매칭: 최대 +2.0
- signal: score >= 6.5 favorable, < 4.0 unfavorable, 그 외 neutral
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.sector_map import MACRO_SECTOR_RULES, SECTOR_MAP

KST = timezone(timedelta(hours=9))
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "intel"


# ── 데이터 로드 ──


def _load_json(path: Path) -> dict:
    """JSON 파일을 딕셔너리로 로드. 없으면 빈 딕셔너리 반환."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _load_news(path: Path) -> list[dict]:
    """뉴스 JSON을 리스트로 로드. 없으면 빈 리스트 반환."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("news", [])


# ── 매크로 지표 → 룰 매칭 ──


_RULE_VALUE_MAP = {
    "vix_high": ("^VIX", "value"),
    "vix_low": ("^VIX", "value"),
    "oil_surge": ("CL=F", "change_pct"),
    "oil_crash": ("CL=F", "change_pct"),
    "krw_weak": ("KRW=X", "value"),
    "krw_strong": ("KRW=X", "value"),
    "gold_surge": ("GC=F", "change_pct"),
}


def _get_indicator_value(
    rule_name: str,
    indicators: dict[str, dict],
) -> float:
    """룰 이름에 대응하는 지표 값을 반환한다."""
    ticker, field = _RULE_VALUE_MAP.get(rule_name, ("", "value"))
    return indicators.get(ticker, {}).get(field, 0.0)


def _check_trigger(direction: str, value: float, threshold: float) -> bool:
    """방향과 임계값으로 트리거 여부를 판정한다."""
    if direction in ("above", "above_change"):
        return value > threshold
    if direction in ("below", "below_change"):
        return value < threshold
    return False


# ── 점수 계산 ──


def _apply_regime(scores: dict[str, float], regime_data: dict) -> None:
    """레짐 preferred/avoid 섹터에 ±2.0 반영 (in-place)."""
    strategy = regime_data.get("strategy", {})
    for s in strategy.get("preferred_sectors", []):
        if s in scores:
            scores[s] += 2.0
    for s in strategy.get("avoid_sectors", []):
        if s in scores:
            scores[s] -= 2.0


def _apply_macro_rules(
    scores: dict[str, float],
    triggered_rules: dict[str, list[str]],
    indicators: dict[str, dict],
) -> None:
    """MACRO_SECTOR_RULES 적용하여 점수와 트리거 룰 갱신 (in-place)."""
    for rule_name, rule in MACRO_SECTOR_RULES.items():
        value = _get_indicator_value(rule_name, indicators)
        if not _check_trigger(rule["direction"], value, rule["threshold"]):
            continue
        for s in rule.get("favorable", []):
            if s in scores:
                scores[s] += 1.5
                triggered_rules[s].append(rule_name)
        for s in rule.get("unfavorable", []):
            if s in scores:
                scores[s] -= 1.5
                triggered_rules[s].append(rule_name)


def _score_from_macro(
    macro_data: dict,
    regime_data: dict,
) -> tuple[dict[str, float], dict[str, list[str]]]:
    """매크로 지표 + 레짐 → 섹터별 점수와 트리거된 룰 반환."""
    scores: dict[str, float] = {s: 5.0 for s in SECTOR_MAP}
    triggered_rules: dict[str, list[str]] = {s: [] for s in SECTOR_MAP}

    _apply_regime(scores, regime_data)

    indicators = {ind["ticker"]: ind for ind in macro_data.get("indicators", [])}
    _apply_macro_rules(scores, triggered_rules, indicators)

    return scores, triggered_rules


def _score_from_news(news_data: list[dict]) -> tuple[dict[str, float], dict[str, int]]:
    """뉴스 제목/요약 → 섹터별 언급 빈도 점수 (최대 +2.0)."""
    counts: dict[str, int] = {s: 0 for s in SECTOR_MAP}
    for article in news_data[:50]:
        text = article.get("title", "") + " " + article.get("summary", "")
        for sector, info in SECTOR_MAP.items():
            for kw in info.get("keywords", []):
                if kw in text:
                    counts[sector] += 1
                    break

    max_count = max(counts.values()) if any(counts.values()) else 1
    news_scores = {s: min(2.0, (c / max(max_count, 1)) * 2.0) for s, c in counts.items()}
    return news_scores, counts


# ── reasoning 생성 ──


def _build_reasoning(
    sector: str,
    triggered: list[str],
    regime: str,
    news_count: int,
) -> str:
    """섹터별 1~2줄 요약 reasoning을 생성한다."""
    parts: list[str] = []
    if regime:
        parts.append(f"레짐 {regime}")
    if triggered:
        parts.append(f"매크로 룰: {', '.join(triggered)}")
    if news_count > 0:
        parts.append(f"뉴스 언급 {news_count}건")
    return "; ".join(parts) if parts else "특이 신호 없음"


# ── signal 판정 ──


def _determine_signal(score: float) -> str:
    """점수 → favorable / neutral / unfavorable 판정."""
    if score >= 6.5:
        return "favorable"
    if score < 4.0:
        return "unfavorable"
    return "neutral"


# ── 진입점 ──


def run() -> dict:
    """섹터 점수화 실행 → sector_scores.json 저장."""
    macro_data = _load_json(OUTPUT_DIR / "macro.json")
    regime_data = _load_json(OUTPUT_DIR / "regime.json")
    news_data = _load_news(OUTPUT_DIR / "news.json")

    regime = regime_data.get("regime", "UNKNOWN")

    macro_scores, triggered_rules = _score_from_macro(macro_data, regime_data)
    news_scores, news_counts = _score_from_news(news_data)

    # 합산
    final: dict[str, float] = {}
    for sector in SECTOR_MAP:
        final[sector] = round(
            macro_scores.get(sector, 5.0) + news_scores.get(sector, 0.0),
            2,
        )

    # 정렬 + 상세 정보 조립
    sorted_sectors = sorted(final.items(), key=lambda x: x[1], reverse=True)
    sectors_out: list[dict] = []
    for name, score in sorted_sectors:
        top_tickers = SECTOR_MAP[name]["kr"][:2] + SECTOR_MAP[name]["us"][:2]
        sectors_out.append(
            {
                "name": name,
                "score": score,
                "signal": _determine_signal(score),
                "reasoning": _build_reasoning(
                    name,
                    triggered_rules.get(name, []),
                    regime,
                    news_counts.get(name, 0),
                ),
                "top_tickers": top_tickers,
            }
        )

    result = {
        "updated_at": datetime.now(KST).isoformat(),
        "regime": regime,
        "sectors": sectors_out,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "sector_scores.json"
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    try:
        from db.connection import get_db_conn

        date = result["updated_at"][:10]
        with get_db_conn() as conn:
            conn.execute(
                """INSERT INTO sector_scores_history (date, regime, sectors_json, updated_at)
                   VALUES (?,?,?,?)
                   ON CONFLICT(date) DO UPDATE SET
                       regime=excluded.regime,
                       sectors_json=excluded.sectors_json,
                       updated_at=excluded.updated_at""",
                (
                    date,
                    result["regime"],
                    json.dumps(result["sectors"], ensure_ascii=False),
                    result["updated_at"],
                ),
            )
    except Exception as e:
        print(f"[sector_intel] DB 이력 저장 실패: {e}")

    top = sectors_out[0] if sectors_out else {"name": "N/A", "score": 0}
    print(f"  \u2705 섹터 점수화 완료: top={top['name']}({top['score']})")
    return result


if __name__ == "__main__":
    run()

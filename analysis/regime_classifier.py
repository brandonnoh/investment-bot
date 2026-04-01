#!/usr/bin/env python3
"""
시장 레짐 분류기 — 매크로 데이터 기반 현재 시장 환경 분류
4가지 레짐: RISK_ON, RISK_OFF, INFLATIONARY, STAGFLATION
출력: output/intel/regime.json
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import OUTPUT_DIR

KST = timezone(timedelta(hours=9))


class RegimeClassifier:
    """매크로 데이터를 분석하여 시장 레짐을 분류하는 클래스"""

    # 레짐별 전략 정의
    STRATEGIES = {
        "RISK_ON": {
            "stance": "공격적",
            "preferred_sectors": ["성장주", "기술주", "소비재"],
            "avoid_sectors": ["방산", "유틸리티"],
            "cash_ratio": 0.1,
        },
        "RISK_OFF": {
            "stance": "방어적",
            "preferred_sectors": ["방산", "유틸리티", "금"],
            "avoid_sectors": ["성장주", "소형주"],
            "cash_ratio": 0.4,
        },
        "INFLATIONARY": {
            "stance": "중립",
            "preferred_sectors": ["에너지", "소재", "원자재"],
            "avoid_sectors": ["성장주", "채권"],
            "cash_ratio": 0.2,
        },
        "STAGFLATION": {
            "stance": "방어적",
            "preferred_sectors": ["금", "방산"],
            "avoid_sectors": ["성장주", "소비재", "채권"],
            "cash_ratio": 0.3,
        },
    }

    def classify(self, macro_data: dict) -> str:
        """
        매크로 데이터를 분석하여 시장 레짐 분류.

        Args:
            macro_data: macro.json 데이터 (dict with "indicators" list)

        Returns:
            레짐 문자열: "RISK_ON" | "RISK_OFF" | "INFLATIONARY" | "STAGFLATION"
        """
        indicators = macro_data.get("indicators", [])

        # 지표값 추출
        vix = self._get_indicator_value(indicators, "VIX")
        fx_change = self._get_indicator_change(indicators, "원/달러")
        oil_change = self._get_indicator_change(indicators, "WTI 유가")
        oil_value = self._get_indicator_value(indicators, "WTI 유가")

        # 우선순위 순서로 레짐 분류
        # 1. STAGFLATION: VIX > 25 AND 유가 급등 > 5%
        if vix is not None and oil_change is not None:
            if vix > 25 and oil_change > 5:
                return "STAGFLATION"

        # 2. RISK_OFF: VIX > 25 OR 원/달러 급등 > 3%
        if (vix is not None and vix > 25) or (fx_change is not None and fx_change > 3):
            return "RISK_OFF"

        # 3. INFLATIONARY: 유가 급등 > 5% OR (유가 > 85 AND 원/달러 변동 > 1%)
        if oil_change is not None and oil_change > 5:
            return "INFLATIONARY"
        if oil_value is not None and fx_change is not None:
            if oil_value > 85 and fx_change > 1:
                return "INFLATIONARY"

        # 4. RISK_ON: VIX < 20 AND 원/달러 변동 < 2% AND 유가 변동 < 3%
        vix_ok = vix is not None and vix < 20
        fx_ok = fx_change is None or abs(fx_change) < 2
        oil_ok = oil_change is None or abs(oil_change) < 3
        if vix_ok and fx_ok and oil_ok:
            return "RISK_ON"

        # 5. 기본값: 보수적 RISK_OFF
        return "RISK_OFF"

    def get_strategy(self, regime: str) -> dict:
        """
        레짐별 권장 투자 전략 반환.

        Args:
            regime: 레짐 문자열 ("RISK_ON" | "RISK_OFF" | "INFLATIONARY" | "STAGFLATION")

        Returns:
            전략 딕셔너리: {stance, preferred_sectors, avoid_sectors, cash_ratio}
        """
        # 알 수 없는 레짐은 RISK_OFF 전략으로 폴백
        return self.STRATEGIES.get(regime, self.STRATEGIES["RISK_OFF"])

    def _get_indicator_value(self, indicators: list, name: str) -> float | None:
        """지표 리스트에서 특정 지표의 값 추출"""
        for item in indicators:
            if item.get("indicator") == name:
                val = item.get("value")
                if val is not None:
                    try:
                        return float(val)
                    except (TypeError, ValueError):
                        return None
        return None

    def _get_indicator_change(self, indicators: list, name: str) -> float | None:
        """지표 리스트에서 특정 지표의 변동률 추출"""
        for item in indicators:
            if item.get("indicator") == name:
                change = item.get("change_pct")
                if change is not None:
                    try:
                        return float(change)
                    except (TypeError, ValueError):
                        return None
        return None


def _load_macro_data() -> dict:
    """macro.json 파일에서 매크로 데이터 로드"""
    macro_path = OUTPUT_DIR / "macro.json"
    if not macro_path.exists():
        print("  ⚠️  macro.json 없음 — fetch_macro.py를 먼저 실행하세요")
        return {}
    with open(macro_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_previous_regime() -> str | None:
    """이전에 저장된 regime.json에서 레짐 값 로드"""
    regime_path = OUTPUT_DIR / "regime.json"
    if not regime_path.exists():
        return None
    try:
        with open(regime_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("regime")
    except (json.JSONDecodeError, IOError):
        return None


def run() -> dict:
    """
    레짐 분류 실행 — macro.json 읽기 → 분류 → regime.json 저장.

    Returns:
        분류 결과 딕셔너리
    """
    print("\n[레짐 분류기]")

    classifier = RegimeClassifier()

    # 매크로 데이터 로드
    macro_data = _load_macro_data()
    indicators = macro_data.get("indicators", [])

    # 지표값 추출 (저장용)
    vix = classifier._get_indicator_value(indicators, "VIX")
    fx_change = classifier._get_indicator_change(indicators, "원/달러")
    oil_change = classifier._get_indicator_change(indicators, "WTI 유가")

    # 레짐 분류
    regime = classifier.classify(macro_data)
    strategy = classifier.get_strategy(regime)

    # 이전 레짐과 비교하여 변경 감지
    previous_regime = _load_previous_regime()
    if previous_regime is not None and previous_regime != regime:
        print(f"📊 레짐 변경: {previous_regime} → {regime}")

    # regime.json 저장
    output = {
        "classified_at": datetime.now(KST).isoformat(),
        "regime": regime,
        "vix": vix,
        "fx_change": fx_change,
        "oil_change": oil_change,
        "strategy": strategy,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    regime_path = OUTPUT_DIR / "regime.json"
    with open(regime_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  레짐: {regime} | VIX={vix} | FX변동={fx_change}% | 유가변동={oil_change}%")
    print(f"  전략: {strategy['stance']} (현금비중 {strategy['cash_ratio']*100:.0f}%)")

    return output


if __name__ == "__main__":
    run()

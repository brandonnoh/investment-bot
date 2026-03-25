"""
F24 — 마커스 에이전트 설정 테스트
골드만삭스 15년차 펀드매니저 페르소나, 프롬프트, 출력 형식 검증
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE_DIR = Path(__file__).resolve().parent.parent


# ── 1. 프롬프트 파일 존재 테스트 ──


class TestMarcusFiles:
    """마커스 에이전트 설정 파일 존재 검증"""

    def test_soul_md_exists(self):
        """SOUL.md 페르소나 파일이 존재해야 한다"""
        soul_path = BASE_DIR / "docs" / "marcus" / "SOUL.md"
        assert soul_path.exists(), f"SOUL.md not found at {soul_path}"

    def test_prompt_md_exists(self):
        """마커스 전용 프롬프트 파일이 존재해야 한다"""
        prompt_path = BASE_DIR / "docs" / "marcus" / "prompt.md"
        assert prompt_path.exists(), f"prompt.md not found at {prompt_path}"

    def test_soul_md_has_persona(self):
        """SOUL.md에 페르소나 핵심 요소가 포함되어야 한다"""
        soul = (BASE_DIR / "docs" / "marcus" / "SOUL.md").read_text(encoding="utf-8")
        # 페르소나 핵심 키워드
        assert "마커스" in soul or "Marcus" in soul
        assert "펀드매니저" in soul or "fund manager" in soul.lower()
        assert "골드만삭스" in soul or "Goldman" in soul

    def test_soul_md_has_analysis_principles(self):
        """SOUL.md에 분석 원칙이 포함되어야 한다"""
        soul = (BASE_DIR / "docs" / "marcus" / "SOUL.md").read_text(encoding="utf-8")
        # 리스크 우선, 데이터 근거 필수 등
        assert "리스크" in soul or "risk" in soul.lower()
        assert "데이터" in soul or "data" in soul.lower()

    def test_prompt_md_has_pipeline_steps(self):
        """프롬프트에 분석 파이프라인 단계가 포함되어야 한다"""
        prompt = (BASE_DIR / "docs" / "marcus" / "prompt.md").read_text(
            encoding="utf-8"
        )
        # 데이터 읽기, 분석, 출력 단계
        assert "price_analysis.json" in prompt or "prices.json" in prompt
        assert "marcus-analysis.md" in prompt

    def test_prompt_md_has_data_sources(self):
        """프롬프트에 읽어야 할 데이터 소스가 명시되어야 한다"""
        prompt = (BASE_DIR / "docs" / "marcus" / "prompt.md").read_text(
            encoding="utf-8"
        )
        # 핵심 데이터 소스 참조
        assert "fundamentals.json" in prompt or "fundamentals" in prompt
        assert "opportunities.json" in prompt or "opportunities" in prompt

    def test_prompt_md_has_output_path(self):
        """프롬프트에 출력 파일 경로가 명시되어야 한다"""
        prompt = (BASE_DIR / "docs" / "marcus" / "prompt.md").read_text(
            encoding="utf-8"
        )
        assert "marcus-analysis.md" in prompt


# ── 2. 출력 형식 검증 모듈 테스트 ──


class TestMarcusAnalysisValidator:
    """marcus_analysis.py 출력 형식 검증 모듈 테스트"""

    def test_module_import(self):
        """scripts/marcus_analysis.py가 import 가능해야 한다"""
        from scripts.marcus_analysis import validate_marcus_output  # noqa: F401

    def test_valid_output_passes(self):
        """올바른 형식의 marcus-analysis.md는 검증 통과해야 한다"""
        from scripts.marcus_analysis import validate_marcus_output

        valid_md = """# 마커스 분석 — 2026년 03월 26일

**분석 시각:** 05:30 KST
**확신 레벨:** ★★★★☆ (4/5)

## RISK FIRST — 오늘의 리스크

| 리스크 | 수준 | 근거 |
|--------|------|------|
| 환율 리스크 | 🟡 중간 | 원/달러 1,450원 돌파 |

## MARKET REGIME

현재 시장: Risk-On (약세)
VIX: 18.5 | Fear & Greed: 45 (Fear)

## PORTFOLIO REVIEW

| 종목 | 현재가 | 기술적 위치 | 펀더멘탈 | 판단 |
|------|--------|------------|---------|------|
| 삼성전자 | 188,700 | MA20 하회 | PER 12.3 | HOLD |

## OPPORTUNITIES — 발굴 종목 TOP 3

### 1. 한화에어로스페이스 (012450.KS) — 복합점수 0.82
- **밸류:** PER 15.2 (업종 -20%)
- **타이밍:** RSI 35 과매도
- **촉매:** 방산 수주 확대 뉴스
- **리스크:** 단기 과열 후 조정 가능성

## TODAY'S CALL

> 리스크 관리 우선. 환율 방향 주시하며 방산주 관심 유지.

**면책:** 이 분석은 AI 에이전트의 데이터 기반 판단이며, 투자 조언이 아닙니다.
"""
        result = validate_marcus_output(valid_md)
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_missing_confidence_level(self):
        """확신 레벨이 없으면 에러"""
        from scripts.marcus_analysis import validate_marcus_output

        md = """# 마커스 분석 — 2026년 03월 26일

## RISK FIRST — 오늘의 리스크
내용

## MARKET REGIME
내용

## PORTFOLIO REVIEW
내용

## TODAY'S CALL
> 요약
"""
        result = validate_marcus_output(md)
        assert result["valid"] is False
        assert any(
            "확신 레벨" in e or "confidence" in e.lower() for e in result["errors"]
        )

    def test_missing_risk_section(self):
        """RISK FIRST 섹션이 없으면 에러"""
        from scripts.marcus_analysis import validate_marcus_output

        md = """# 마커스 분석 — 2026년 03월 26일

**확신 레벨:** ★★★☆☆ (3/5)

## MARKET REGIME
내용

## PORTFOLIO REVIEW
내용

## TODAY'S CALL
> 요약
"""
        result = validate_marcus_output(md)
        assert result["valid"] is False
        assert any("RISK FIRST" in e for e in result["errors"])

    def test_missing_todays_call(self):
        """TODAY'S CALL 섹션이 없으면 에러"""
        from scripts.marcus_analysis import validate_marcus_output

        md = """# 마커스 분석 — 2026년 03월 26일

**확신 레벨:** ★★★☆☆ (3/5)

## RISK FIRST — 오늘의 리스크
내용

## MARKET REGIME
내용

## PORTFOLIO REVIEW
내용
"""
        result = validate_marcus_output(md)
        assert result["valid"] is False
        assert any("TODAY'S CALL" in e for e in result["errors"])

    def test_missing_disclaimer(self):
        """면책 조항이 없으면 에러"""
        from scripts.marcus_analysis import validate_marcus_output

        md = """# 마커스 분석 — 2026년 03월 26일

**확신 레벨:** ★★★☆☆ (3/5)

## RISK FIRST — 오늘의 리스크
내용

## MARKET REGIME
내용

## PORTFOLIO REVIEW
내용

## TODAY'S CALL
> 요약
"""
        result = validate_marcus_output(md)
        assert result["valid"] is False
        assert any("면책" in e or "disclaimer" in e.lower() for e in result["errors"])

    def test_extract_confidence_level(self):
        """확신 레벨 숫자를 추출할 수 있어야 한다"""
        from scripts.marcus_analysis import extract_confidence_level

        assert extract_confidence_level("**확신 레벨:** ★★★★☆ (4/5)") == 4
        assert extract_confidence_level("**확신 레벨:** ★★☆☆☆ (2/5)") == 2
        assert extract_confidence_level("no confidence") is None

    def test_extract_sections(self):
        """마크다운에서 섹션을 추출할 수 있어야 한다"""
        from scripts.marcus_analysis import extract_sections

        md = """# 마커스 분석 — 2026년 03월 26일

## RISK FIRST — 오늘의 리스크
리스크 내용

## MARKET REGIME
시장 내용

## TODAY'S CALL
> 콜 내용
"""
        sections = extract_sections(md)
        assert "RISK FIRST" in sections
        assert "MARKET REGIME" in sections
        assert "TODAY'S CALL" in sections

    def test_empty_input(self):
        """빈 입력은 에러"""
        from scripts.marcus_analysis import validate_marcus_output

        result = validate_marcus_output("")
        assert result["valid"] is False

    def test_minimal_valid_output(self):
        """최소 필수 요소만 포함하면 통과"""
        from scripts.marcus_analysis import validate_marcus_output

        md = """# 마커스 분석 — 2026년 03월 26일

**확신 레벨:** ★★★☆☆ (3/5)

## RISK FIRST — 오늘의 리스크
환율 리스크 중간

## MARKET REGIME
Risk-Off

## PORTFOLIO REVIEW
삼성전자 HOLD

## TODAY'S CALL
> 관망

**면책:** 이 분석은 AI 에이전트의 데이터 기반 판단이며, 투자 조언이 아닙니다.
"""
        result = validate_marcus_output(md)
        assert result["valid"] is True


# ── 3. config.py 마커스 설정 테스트 ──


class TestMarcusConfig:
    """config.py 마커스 관련 설정 테스트"""

    def test_marcus_config_exists(self):
        """config.py에 MARCUS_CONFIG가 정의되어야 한다"""
        import config

        assert hasattr(config, "MARCUS_CONFIG")

    def test_marcus_config_output_path(self):
        """마커스 출력 경로가 설정되어야 한다"""
        import config

        assert "output_file" in config.MARCUS_CONFIG

    def test_marcus_config_required_sections(self):
        """마커스 필수 섹션 목록이 설정되어야 한다"""
        import config

        assert "required_sections" in config.MARCUS_CONFIG
        sections = config.MARCUS_CONFIG["required_sections"]
        assert "RISK FIRST" in sections
        assert "MARKET REGIME" in sections
        assert "PORTFOLIO REVIEW" in sections
        assert "TODAY'S CALL" in sections

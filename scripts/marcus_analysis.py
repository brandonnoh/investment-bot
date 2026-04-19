#!/usr/bin/env python3
"""
마커스 분석 출력 검증 모듈
marcus-analysis.md의 필수 섹션, 확신 레벨, 면책 조항 등을 검증한다.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config


def extract_sections(md_text: str) -> dict:
    """마크다운에서 ## 섹션을 추출한다"""
    sections = {}
    current_key = None
    current_lines = []

    for line in md_text.split("\n"):
        if line.startswith("## "):
            # 이전 섹션 저장
            if current_key:
                sections[current_key] = "\n".join(current_lines).strip()
            # 새 섹션 시작 — 섹션 제목에서 핵심 키워드 추출
            title = line[3:].strip()
            # "RISK FIRST — 오늘의 리스크" → "RISK FIRST"
            key = title.split("—")[0].split("—")[0].strip()
            # "OPPORTUNITIES — 발굴 종목 TOP 3" → "OPPORTUNITIES"
            key = key.split("—")[0].strip()
            current_key = key
            current_lines = []
        elif current_key is not None:
            current_lines.append(line)

    # 마지막 섹션 저장
    if current_key:
        sections[current_key] = "\n".join(current_lines).strip()

    return sections


def extract_confidence_level(text: str) -> int | None:
    """확신 레벨 숫자를 추출한다 (1~5)"""
    # "★★★★☆ (4/5)" 패턴
    match = re.search(r"\((\d)/5\)", text)
    if match:
        return int(match.group(1))
    # ★ 개수 세기
    stars = text.count("★")
    if stars > 0:
        return stars
    return None


def validate_marcus_output(md_text: str) -> dict:
    """
    marcus-analysis.md 출력 형식을 검증한다.

    Returns:
        {"valid": bool, "errors": list[str], "warnings": list[str]}
    """
    errors = []
    warnings = []

    # 빈 입력 체크
    if not md_text or not md_text.strip():
        return {"valid": False, "errors": ["빈 입력"], "warnings": []}

    # 1. 확신 레벨 체크
    confidence = extract_confidence_level(md_text)
    if confidence is None:
        errors.append("확신 레벨 누락 — '**확신 레벨:** ★★★☆☆ (3/5)' 형식 필요")

    # 2. 필수 섹션 체크
    sections = extract_sections(md_text)
    # 2. 필수 요소 체크 (섹션 헤더 대신 키 문구로 검증)
    if "오늘의 판단" not in md_text:
        errors.append("필수 요소 누락: 오늘의 판단 블록")
    if "포트폴리오" not in md_text:
        errors.append("필수 요소 누락: 포트폴리오 테이블")
    if "매크로" not in md_text:
        errors.append("필수 요소 누락: 매크로 지표")

    # 3. 면책 조항 체크
    if "면책" not in md_text and "투자 조언이 아닙니다" not in md_text:
        errors.append("면책 조항 누락 — '투자 조언이 아닙니다' 문구 필요")

    if confidence and confidence >= 4:
        # 높은 확신 레벨에는 구체적 근거가 더 필요
        if len(md_text) < 500:
            warnings.append("높은 확신 레벨(4+)이지만 분석 내용이 짧음")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "confidence_level": confidence,
        "sections": list(sections.keys()),
    }


def run():
    """marcus-analysis.md 파일을 읽어 검증한다 (파이프라인 호출용)"""
    output_path = config.OUTPUT_DIR / config.MARCUS_CONFIG.get("output_file", "marcus-analysis.md")

    if not output_path.exists():
        print("  ⚠️ marcus-analysis.md 없음 (마커스 미실행)")
        return None

    md_text = output_path.read_text(encoding="utf-8")
    result = validate_marcus_output(md_text)

    if result["valid"]:
        level = result.get("confidence_level", "?")
        print(f"  ✅ 마커스 분석 검증 통과 (확신 레벨: {level}/5)")
    else:
        print(f"  ⚠️ 마커스 분석 형식 오류: {result['errors']}")

    for warning in result.get("warnings", []):
        print(f"  💡 {warning}")

    return result


if __name__ == "__main__":
    result = run()
    if result and not result["valid"]:
        sys.exit(1)

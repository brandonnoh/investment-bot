#!/usr/bin/env python3
"""
종목 스크리너 — 오늘의 주목 섹터 + 신규 종목 발굴
Yahoo Finance API로 섹터별 주요 종목/ETF 분석
출력: output/intel/screener.md
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import OUTPUT_DIR  # noqa: E402
from analysis.screener_report import (  # noqa: E402
    generate_screener_report,
    pick_highlights,
    generate_universe_section,
)
from analysis.screener_ticker import fetch_yahoo_quote, analyze_ticker  # noqa: E402, F401
from analysis.screener_universe import (  # noqa: E402
    UNIVERSE_KOSPI200,
    UNIVERSE_SP100,
    SCREENING_TARGETS,
    screen_universe,
    merge_universe,
)

KST = timezone(timedelta(hours=9))


def screen_sectors() -> dict:
    """섹터별 주요 종목 분석"""
    sector_results = {}

    for sector_name, sector_info in SCREENING_TARGETS.items():
        print(f"\n  📊 {sector_name} 섹터 분석 중...")
        results = []
        for ticker_info in sector_info["tickers"]:
            result = analyze_ticker(ticker_info)
            if result:
                results.append(result)
                status = "🔺" if (result.get("month_return") or 0) > 0 else "🔻"
                month_str = (
                    f"{result['month_return']:+.2f}%"
                    if result["month_return"] is not None
                    else "N/A"
                )
                print(
                    f"    {status} {result['name']}: {result['price']:,.2f} (1M: {month_str})"
                )

        # 1개월 수익률 기준 정렬
        results.sort(key=lambda x: x.get("month_return") or -999, reverse=True)
        sector_results[sector_name] = {
            "description": sector_info["description"],
            "stocks": results,
        }

    return sector_results


def run():
    """스크리너 파이프라인 실행"""
    print(
        f"\n🔍 종목 스크리너 시작 — {datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}"
    )

    # 섹터별 분석
    sector_results = screen_sectors()

    # opportunities.json이 있으면 발굴 종목 통합
    opp_path = OUTPUT_DIR / "opportunities.json"
    if opp_path.exists():
        try:
            with open(opp_path, encoding="utf-8") as f:
                opp_data = json.load(f)
            opp_tickers = [
                {
                    "ticker": o["ticker"],
                    "name": o.get("name", ""),
                    "sector": "발굴",
                    "market": o.get("market", "KR"),
                    "discovered_via": o.get("discovered_via", ""),
                }
                for o in opp_data.get("opportunities", [])
            ]
            # 기존 섹터 종목 리스트 추출
            existing_tickers = []
            for data in sector_results.values():
                existing_tickers.extend(data.get("stocks", []))
            merged = merge_universe(existing_tickers, opp_tickers)
            # 발굴 종목 중 기존에 없던 것들을 별도 섹터로 추가
            new_opps = [t for t in merged if t.get("sector") == "발굴"]
            if new_opps:
                sector_results["발굴 종목"] = {
                    "description": "AI 발굴 신규 종목",
                    "stocks": new_opps,
                }
                print(f"  🆕 발굴 종목 {len(new_opps)}개 통합")
        except Exception as e:
            print(f"  ⚠️ opportunities.json 로드 실패: {e}")

    # 주목 종목 선별
    highlights = pick_highlights(sector_results)

    # 유니버스 스크리닝
    print(f"\n  🌏 코스피 200 유니버스 스크리닝 ({len(UNIVERSE_KOSPI200)}개)...")
    kospi_top = []
    try:
        kospi_top = screen_universe(UNIVERSE_KOSPI200)
        print(f"  ✅ 코스피 TOP {len(kospi_top)}개 추출 완료")
    except Exception as e:
        print(f"  ⚠️ 코스피 유니버스 스크리닝 실패: {e}")

    print(f"\n  🌏 S&P 100 유니버스 스크리닝 ({len(UNIVERSE_SP100)}개)...")
    sp_top = []
    try:
        sp_top = screen_universe(UNIVERSE_SP100)
        print(f"  ✅ S&P 100 TOP {len(sp_top)}개 추출 완료")
    except Exception as e:
        print(f"  ⚠️ S&P 100 유니버스 스크리닝 실패: {e}")

    # 리포트 생성
    report = generate_screener_report(sector_results, highlights)
    report += "\n" + generate_universe_section(
        kospi_top, sp_top, len(UNIVERSE_KOSPI200), len(UNIVERSE_SP100)
    )

    # screener_results.json 저장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUTPUT_DIR / "screener_results.json"
    results_data = {
        "generated_at": datetime.now(KST).isoformat(),
        "kospi200_top10": kospi_top,
        "sp100_top10": sp_top,
        "total_kospi_scanned": len(UNIVERSE_KOSPI200),
        "total_sp_scanned": len(UNIVERSE_SP100),
    }
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results_data, f, ensure_ascii=False, indent=2)
    print(f"  💾 유니버스 결과 저장: {results_path}")

    # screener.md 저장
    output_path = OUTPUT_DIR / "screener.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n  📄 스크리너 저장: {output_path}")
    print(f"  ⭐ 주목 종목: {len(highlights)}개")
    print()

    return report


if __name__ == "__main__":
    run()

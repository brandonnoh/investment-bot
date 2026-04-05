"""Phase 4 뉴스 수집 목적 분리 테스트 (F20)

fetch_news.py = 포트폴리오 모니터링 (종목 RSS + 매크로 뉴스)
fetch_opportunities.py = 종목 발굴 전담 (키워드 기반 검색)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_fetch_news_module_exists():
    """fetch_news 모듈이 정상 임포트되는지"""
    from data.fetch_news import run

    assert callable(run)


def test_fetch_opportunities_module_exists():
    """fetch_opportunities 모듈이 발굴 전담하는지"""
    from data.fetch_opportunities import run as opp_run

    assert callable(opp_run)


def test_news_and_opportunities_separate():
    """두 모듈이 독립적으로 존재하는지"""
    from data import fetch_news, fetch_opportunities

    # 서로 다른 모듈
    assert fetch_news.__file__ != fetch_opportunities.__file__


def test_fetch_news_no_opportunity_keywords():
    """fetch_news의 MACRO_KEYWORDS에 opportunity 카테고리가 없어야 함"""
    from data.fetch_news import MACRO_KEYWORDS

    assert "opportunity" not in MACRO_KEYWORDS, (
        "fetch_news는 opportunity 카테고리를 포함하지 않아야 함 — "
        "종목 발굴은 fetch_opportunities가 전담"
    )


def test_fetch_news_macro_keywords_methods():
    """fetch_news의 매크로 키워드는 모두 RSS 방식이어야 함"""
    from data.fetch_news import MACRO_KEYWORDS

    for category, info in MACRO_KEYWORDS.items():
        assert info["method"] == "rss", (
            f"fetch_news의 {category} 카테고리는 RSS만 사용해야 함 — "
            "Brave 검색은 fetch_opportunities가 전담"
        )


def test_fetch_news_has_monitoring_categories():
    """fetch_news에 모니터링용 카테고리가 존재하는지"""
    from data.fetch_news import MACRO_KEYWORDS

    # 지정학/매크로 카테고리는 유지
    assert "geopolitics" in MACRO_KEYWORDS
    assert "macro" in MACRO_KEYWORDS

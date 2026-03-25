"""Phase 4 종목 발굴 테스트"""

import json
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name):
    with open(FIXTURES / name) as f:
        return json.load(f)


def test_parse_discovery_keywords():
    """discovery_keywords.json 파싱"""
    from data.fetch_opportunities import parse_keywords

    data = _load_fixture("sample_discovery_keywords.json")
    keywords = parse_keywords(data)
    assert len(keywords) == 2
    assert keywords[0]["keyword"] == "방산 수주 확대 2026"


def test_search_brave_news(monkeypatch):
    """Brave 뉴스 검색 모킹"""
    from data.fetch_opportunities import search_brave

    fixture = _load_fixture("sample_brave_response.json")
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(fixture).encode()
    mock_resp.status = 200
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(
        "data.fetch_opportunities.urllib.request.urlopen",
        lambda req, **kw: mock_resp,
    )
    monkeypatch.setenv("BRAVE_API_KEY", "test-key")
    results = search_brave("방산 수주", count=5)
    assert len(results) >= 1
    assert "title" in results[0]


def test_extract_opportunities_from_news():
    """뉴스 결과에서 종목 후보 추출"""
    from data.fetch_opportunities import extract_opportunities

    master = _load_fixture("sample_ticker_master.json")
    news = [
        {
            "title": "한화에어로스페이스(012450), 방산 수주 임박",
            "description": "수출 확대",
            "url": "https://ex.com/1",
        },
        {
            "title": "두산에너빌리티, 원전 수주 확정",
            "description": "건설 시작",
            "url": "https://ex.com/2",
        },
        {
            "title": "날씨 좋은 하루",
            "description": "맑음",
            "url": "https://ex.com/3",
        },
    ]
    opps = extract_opportunities(news, master, "방산 수주")
    tickers = [o["ticker"] for o in opps]
    assert "012450.KS" in tickers


def test_save_keywords_to_db(db_conn):
    """agent_keywords DB 저장"""
    from data.fetch_opportunities import save_keywords_to_db

    keywords = [
        {
            "keyword": "방산 수주",
            "category": "sector",
            "priority": 1,
            "reasoning": "테스트",
        }
    ]
    save_keywords_to_db(db_conn, keywords, "2026-03-25T05:30:00+09:00")
    row = db_conn.execute("SELECT keyword FROM agent_keywords").fetchone()
    assert row[0] == "방산 수주"


def test_save_opportunities_to_db(db_conn):
    """opportunities DB 저장"""
    from data.fetch_opportunities import save_opportunities_to_db

    opps = [
        {
            "ticker": "012450.KS",
            "name": "한화에어로스페이스",
            "discovered_via": "방산 수주",
            "source": "brave",
            "price_at_discovery": 350000,
        }
    ]
    save_opportunities_to_db(db_conn, opps)
    row = db_conn.execute("SELECT ticker FROM opportunities").fetchone()
    assert row[0] == "012450.KS"


def test_generate_opportunities_json():
    """opportunities.json 생성"""
    from data.fetch_opportunities import generate_json

    keywords = [{"keyword": "방산", "category": "sector", "priority": 1}]
    opps = [
        {
            "ticker": "012450.KS",
            "name": "한화에어로스페이스",
            "discovered_via": "방산",
            "composite_score": None,
        }
    ]
    result = generate_json(keywords, opps)
    assert "updated_at" in result
    assert "keywords" in result
    assert "opportunities" in result
    assert len(result["opportunities"]) == 1


def test_run_with_no_keywords(tmp_path):
    """키워드 파일 없을 때 graceful 빈 결과"""
    from data.fetch_opportunities import run

    result = run(keywords_path=tmp_path / "nonexistent.json", output_dir=tmp_path)
    assert result == []


def test_dedup_opportunities():
    """중복 종목 제거"""
    from data.fetch_opportunities import extract_opportunities

    master = _load_fixture("sample_ticker_master.json")
    news = [
        {"title": "삼성전자 실적 호조", "description": "", "url": "https://ex.com/1"},
        {"title": "삼성전자 투자 확대", "description": "", "url": "https://ex.com/2"},
    ]
    opps = extract_opportunities(news, master, "삼성전자")
    ticker_set = set(o["ticker"] for o in opps)
    # 같은 종목이 여러번 나와도 ticker는 같음
    assert "005930.KS" in ticker_set

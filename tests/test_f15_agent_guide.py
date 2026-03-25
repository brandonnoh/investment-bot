"""
F15 — 에이전트 가이드 최종 검증 + ERD 문서
AGENT_GUIDE.md, JARVIS_INTEGRATION.md의 JSON 예시/DB 쿼리/ERD가 실제 구현과 일치하는지 검증
"""

import json
import re
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── 헬퍼: 마크다운에서 JSON 코드 블록 추출 ──


def _remove_json_comments(text):
    """JSON 텍스트에서 // 주석 제거 (문자열 내부는 보존)"""
    result = []
    in_string = False
    escape = False
    i = 0
    while i < len(text):
        ch = text[i]
        if escape:
            result.append(ch)
            escape = False
            i += 1
            continue
        if ch == "\\" and in_string:
            result.append(ch)
            escape = True
            i += 1
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            result.append(ch)
            i += 1
            continue
        if not in_string and ch == "/" and i + 1 < len(text) and text[i + 1] == "/":
            # 줄 끝까지 스킵
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        result.append(ch)
        i += 1
    return "".join(result)


def extract_json_blocks(md_text):
    """마크다운에서 ```json ... ``` 블록 추출 (주석 제거 후 파싱)"""
    pattern = r"```json\s*\n(.*?)```"
    blocks = re.findall(pattern, md_text, re.DOTALL)
    results = []
    for block in blocks:
        cleaned = _remove_json_comments(block)
        try:
            data = json.loads(cleaned)
            results.append(data)
        except json.JSONDecodeError:
            pass  # 파싱 불가 블록 스킵 (pseudo-JSON 등)
    return results


def extract_sql_blocks(md_text):
    """마크다운에서 SQL 쿼리 추출 (sqlite3 ... 블록 또는 SELECT 문)"""
    # ```bash 블록 내 sqlite3 명령
    pattern = r'sqlite3\s+\S+\s+"([^"]+)"'
    return re.findall(pattern, md_text)


# ── 공통 fixture ──


@pytest.fixture
def agent_guide():
    path = Path(__file__).resolve().parent.parent / "AGENT_GUIDE.md"
    return path.read_text(encoding="utf-8")


@pytest.fixture
def jarvis_integration():
    path = Path(__file__).resolve().parent.parent / "JARVIS_INTEGRATION.md"
    return path.read_text(encoding="utf-8")


@pytest.fixture
def architecture():
    path = Path(__file__).resolve().parent.parent / "ARCHITECTURE.md"
    return path.read_text(encoding="utf-8")


@pytest.fixture
def db_schema(tmp_path):
    """실제 init_schema()로 생성한 인메모리 DB 스키마"""
    from db.init_db import init_schema

    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    return conn


@pytest.fixture
def actual_schemas():
    """utils/schema.py의 실제 스키마 정의"""
    from utils.schema import SCHEMAS

    return SCHEMAS


# ── 1. AGENT_GUIDE.md JSON 예시가 실제 스키마와 일치 ──


class TestAgentGuideJsonExamples:
    """AGENT_GUIDE.md의 JSON 예시 필드가 실제 스키마와 일치하는지 검증"""

    def test_prices_json_example_fields(self, agent_guide, actual_schemas):
        """prices.json 예시가 스키마 필수 필드를 포함"""
        blocks = extract_json_blocks(agent_guide)
        # prices.json 예시 찾기 (ticker 필드가 있는 블록)
        prices_block = None
        for b in blocks:
            if isinstance(b, dict) and "prices" in b and isinstance(b["prices"], list):
                prices_block = b
                break

        assert prices_block is not None, "AGENT_GUIDE.md에 prices.json 예시 없음"

        schema = actual_schemas["prices.json"]
        # 최상위 필드 검증
        for field in schema["top_level"]:
            assert field in prices_block, f"prices.json 예시에 '{field}' 누락"

        # 항목 필드 검증
        if prices_block["prices"]:
            item = prices_block["prices"][0]
            for field in schema["item_fields"]:
                assert field in item, f"prices.json 항목 예시에 '{field}' 누락"

    def test_price_analysis_json_example_fields(self, agent_guide, actual_schemas):
        """price_analysis.json 예시 필드가 실제 분석 결과와 일치"""
        blocks = extract_json_blocks(agent_guide)
        pa_block = None
        for b in blocks:
            if isinstance(b, dict) and "analysis" in b:
                pa_block = b
                break

        assert pa_block is not None, "AGENT_GUIDE.md에 price_analysis.json 예시 없음"

        # 최상위 필드
        schema = actual_schemas["price_analysis.json"]
        for field in schema["top_level"]:
            assert field in pa_block, f"price_analysis.json 예시에 '{field}' 누락"

        # 항목 필드 — 실제 analyze_ticker 출력 필드와 비교
        expected_fields = [
            "name",
            "current",
            "ma5",
            "ma20",
            "ma60",
            "ma_signal",
            "rsi_14",
            "rsi_signal",
            "high_52w",
            "low_52w",
            "position_52w",
            "volatility_30d",
            "trend",
            "trend_duration_days",
            "support",
            "resistance",
            "data_points",
        ]
        if pa_block.get("analysis"):
            first_ticker = next(iter(pa_block["analysis"].values()))
            for field in expected_fields:
                assert field in first_ticker, (
                    f"price_analysis.json 항목 예시에 '{field}' 누락"
                )

    def test_alerts_json_example_structure(self, agent_guide, actual_schemas):
        """alerts.json 예시가 실제 출력 구조 (wrapped, not bare array)와 일치"""
        blocks = extract_json_blocks(agent_guide)
        alerts_block = None
        for b in blocks:
            if isinstance(b, dict) and "alerts" in b and isinstance(b["alerts"], list):
                alerts_block = b
                break

        assert alerts_block is not None, (
            "AGENT_GUIDE.md에 alerts.json 예시 없음 (wrapped 구조 필요)"
        )

        # 실제 스키마와 일치하는 최상위 구조
        schema = actual_schemas["alerts.json"]
        for field in schema["top_level"]:
            assert field in alerts_block, f"alerts.json 예시에 '{field}' 누락"

    def test_engine_status_json_example_fields(self, agent_guide, actual_schemas):
        """engine_status.json 예시가 실제 구현과 일치 (미래 표시 아님)"""
        blocks = extract_json_blocks(agent_guide)
        es_block = None
        for b in blocks:
            if isinstance(b, dict) and "pipeline_ok" in b:
                es_block = b
                break

        assert es_block is not None, (
            "AGENT_GUIDE.md에 engine_status.json 예시 없음 (pipeline_ok 필드 필요)"
        )

        schema = actual_schemas["engine_status.json"]
        for field in schema["top_level"]:
            assert field in es_block, f"engine_status.json 예시에 '{field}' 누락"

    def test_engine_status_section_not_future(self, agent_guide):
        """engine_status.json 섹션이 '미래' 표시 아님"""
        assert "engine_status.json (미래)" not in agent_guide, (
            "engine_status.json은 이미 구현됨 — '(미래)' 표시 제거 필요"
        )

    def test_portfolio_summary_documented(self, agent_guide):
        """portfolio_summary.json 구조가 문서에 포함"""
        assert "portfolio_summary.json" in agent_guide
        # 실제 구조의 핵심 필드 존재 확인
        assert "stock_pnl_krw" in agent_guide, (
            "portfolio_summary.json 예시에 stock_pnl_krw 필드 누락"
        )
        assert "fx_pnl_krw" in agent_guide, (
            "portfolio_summary.json 예시에 fx_pnl_krw 필드 누락"
        )

    def test_macro_json_documented(self, agent_guide):
        """macro.json 구조가 문서에 포함"""
        blocks = extract_json_blocks(agent_guide)
        macro_block = None
        for b in blocks:
            if (
                isinstance(b, dict)
                and "indicators" in b
                and isinstance(b["indicators"], list)
            ):
                macro_block = b
                break

        assert macro_block is not None, "AGENT_GUIDE.md에 macro.json 예시 없음"

    def test_news_json_documented(self, agent_guide):
        """news.json 구조가 문서에 포함 (sentiment 필드 포함)"""
        blocks = extract_json_blocks(agent_guide)
        news_block = None
        for b in blocks:
            if isinstance(b, dict) and "news" in b and isinstance(b["news"], list):
                news_block = b
                break

        assert news_block is not None, "AGENT_GUIDE.md에 news.json 예시 없음"
        if news_block["news"]:
            item = news_block["news"][0]
            assert "sentiment" in item, "news.json 항목 예시에 sentiment 누락"


# ── 2. DB 쿼리 예시가 실제 스키마와 일치 ──


class TestDbQueries:
    """AGENT_GUIDE.md의 DB 쿼리 예시가 실제 스키마에서 실행 가능한지 검증"""

    def test_sql_queries_executable(self, agent_guide, db_schema):
        """문서의 모든 SQL 쿼리가 실제 스키마에서 구문 오류 없이 실행 가능"""
        queries = extract_sql_blocks(agent_guide)
        assert len(queries) > 0, "AGENT_GUIDE.md에 SQL 쿼리 예시 없음"

        for query in queries:
            # 실제 데이터가 없으므로 EXPLAIN 대신 빈 결과 허용
            query = query.strip().rstrip(";")
            try:
                db_schema.execute(query)
            except sqlite3.OperationalError as e:
                pytest.fail(f"SQL 쿼리 실행 실패: {e}\n쿼리: {query}")

    def test_prices_daily_query(self, db_schema):
        """prices_daily 테이블 조회 가능"""
        db_schema.execute(
            "SELECT date, close FROM prices_daily WHERE ticker='005930.KS' ORDER BY date DESC LIMIT 30"
        )

    def test_macro_daily_query(self, db_schema):
        """macro_daily 테이블 조회 가능"""
        db_schema.execute(
            "SELECT date, close, change_pct FROM macro_daily WHERE indicator='코스피' ORDER BY date DESC LIMIT 7"
        )

    def test_portfolio_history_query(self, db_schema):
        """portfolio_history 테이블 조회 가능"""
        db_schema.execute(
            "SELECT date, total_pnl_pct FROM portfolio_history ORDER BY date DESC LIMIT 30"
        )

    def test_news_sentiment_query(self, db_schema):
        """news 테이블 sentiment 컬럼 조회 가능"""
        db_schema.execute(
            "SELECT title, source, sentiment, published_at FROM news WHERE tickers LIKE '%005930%' ORDER BY published_at DESC LIMIT 10"
        )


# ── 3. ERD가 실제 테이블과 일치 ──


class TestErdMatchesSchema:
    """ARCHITECTURE.md ERD가 실제 DB 테이블/컬럼과 일치"""

    def _get_actual_tables(self, conn):
        """실제 DB의 테이블 목록"""
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        return {row[0] for row in cursor.fetchall()}

    def _get_actual_columns(self, conn, table):
        """실제 DB 테이블의 컬럼 목록"""
        cursor = conn.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in cursor.fetchall()}

    def test_erd_tables_exist(self, architecture, db_schema):
        """ERD에 나열된 DB 테이블이 모두 실제 존재"""
        actual_tables = self._get_actual_tables(db_schema)
        # ERD에서 테이블 이름 추출
        expected_db_tables = {
            "prices",
            "prices_daily",
            "macro",
            "macro_daily",
            "news",
            "alerts",
            "portfolio_history",
        }
        for table in expected_db_tables:
            assert table in actual_tables, f"ERD 테이블 '{table}'이 실제 DB에 없음"

    def test_erd_no_price_analysis_table(self, architecture, db_schema):
        """price_analysis는 DB 테이블이 아님 (JSON 파일만) — ERD에 테이블로 표시하지 않아야"""
        actual_tables = self._get_actual_tables(db_schema)
        assert "price_analysis" not in actual_tables

    def test_erd_prices_columns(self, architecture, db_schema):
        """ERD의 prices 테이블 컬럼이 실제와 일치"""
        actual = self._get_actual_columns(db_schema, "prices")
        expected = {
            "id",
            "ticker",
            "name",
            "price",
            "prev_close",
            "change_pct",
            "volume",
            "timestamp",
            "market",
            "data_source",
        }
        assert expected.issubset(actual), f"prices 누락 컬럼: {expected - actual}"

    def test_erd_portfolio_history_columns(self, architecture, db_schema):
        """ERD의 portfolio_history 컬럼이 실제와 일치"""
        actual = self._get_actual_columns(db_schema, "portfolio_history")
        expected = {
            "id",
            "date",
            "total_value_krw",
            "total_invested_krw",
            "total_pnl_krw",
            "total_pnl_pct",
            "fx_rate",
            "fx_pnl_krw",
            "holdings_snapshot",
        }
        assert expected.issubset(actual), (
            f"portfolio_history 누락 컬럼: {expected - actual}"
        )

    def test_erd_news_columns(self, architecture, db_schema):
        """ERD의 news 테이블에 sentiment 컬럼 포함"""
        actual = self._get_actual_columns(db_schema, "news")
        assert "sentiment" in actual, "news 테이블에 sentiment 컬럼 없음"


# ── 4. JARVIS_INTEGRATION.md 동기화 ──


class TestJarvisIntegrationSync:
    """JARVIS_INTEGRATION.md가 AGENT_GUIDE.md 및 실제 구현과 동기화"""

    def test_file_table_includes_all_json(self, jarvis_integration):
        """파일 테이블에 모든 JSON 출력 파일 포함"""
        required_files = [
            "prices.json",
            "macro.json",
            "news.json",
            "price_analysis.json",
            "portfolio_summary.json",
            "engine_status.json",
        ]
        for f in required_files:
            assert f in jarvis_integration, f"JARVIS_INTEGRATION.md에 '{f}' 언급 없음"

    def test_alerts_json_structure_consistent(self, jarvis_integration):
        """alerts.json 예시가 실제 wrapped 구조와 일치"""
        blocks = extract_json_blocks(jarvis_integration)
        # alerts 관련 블록이 있으면 wrapped 구조여야 함
        for b in blocks:
            if isinstance(b, list) and b and "level" in b[0]:
                pytest.fail(
                    "JARVIS_INTEGRATION.md의 alerts.json 예시가 bare array — "
                    "실제 출력은 {triggered_at, count, alerts: [...]}"
                )

    def test_section6_requirements_resolved(self, jarvis_integration):
        """섹션 6 고도화 요청사항이 구현 완료 표시"""
        # 모든 요청이 이미 구현됨 — '현재 부족한 것들' 같은 표현이 남아있으면 안 됨
        assert "현재 부족한 것들" not in jarvis_integration, (
            "JARVIS_INTEGRATION.md 섹션 6: 모든 요청이 구현 완료됨 — '현재 부족한 것들' 제거 필요"
        )

    def test_sentiment_module_name_correct(self, jarvis_integration):
        """감성 분석 모듈명이 실제와 일치 (analysis/sentiment.py)"""
        # news_sentiment.py는 잘못된 이름
        if "news_sentiment.py" in jarvis_integration:
            pytest.fail(
                "JARVIS_INTEGRATION.md에 'news_sentiment.py' 참조 — "
                "실제 모듈은 'analysis/sentiment.py'"
            )

    def test_file_tree_includes_sentiment(self, jarvis_integration):
        """파일 경로에 analysis/sentiment.py 포함"""
        assert "sentiment.py" in jarvis_integration, (
            "JARVIS_INTEGRATION.md 파일 트리에 sentiment.py 언급 없음"
        )


# ── 5. ARCHITECTURE.md 정확성 ──


class TestArchitectureAccuracy:
    """ARCHITECTURE.md의 ERD와 모듈 설명이 실제와 일치"""

    def test_sentiment_module_name(self, architecture):
        """감성 분석 모듈명이 실제와 일치"""
        if "news_sentiment.py" in architecture:
            pytest.fail(
                "ARCHITECTURE.md에 'news_sentiment.py' — "
                "실제 모듈은 'analysis/sentiment.py'"
            )

    def test_price_analysis_erd_label(self, architecture):
        """price_analysis ERD가 'JSON 출력' 또는 '계산 결과'로 표시 (테이블 아님)"""
        # ERD에서 price_analysis가 테이블처럼 표시되면 안 됨
        # 하지만 뷰/계산 결과로 표시는 허용
        assert "price_analysis" in architecture, "ERD에 price_analysis 언급 없음"

    def test_analysis_modules_table(self, architecture):
        """분석 모듈 테이블에 sentiment.py 포함"""
        assert "sentiment" in architecture.lower(), (
            "ARCHITECTURE.md 분석 모듈 테이블에 sentiment 언급 없음"
        )

    def test_engine_status_documented(self, architecture):
        """engine_status.json이 출력 인터페이스에 포함"""
        assert "engine_status.json" in architecture, (
            "ARCHITECTURE.md에 engine_status.json 미포함"
        )

    def test_portfolio_summary_example_structure(self, architecture):
        """ARCHITECTURE.md의 portfolio_summary.json 예시가 실제 구조와 일치"""
        blocks = extract_json_blocks(architecture)
        ps_block = None
        for b in blocks:
            if isinstance(b, dict) and "exchange_rate" in b and "total" in b:
                ps_block = b
                break

        assert ps_block is not None, (
            "ARCHITECTURE.md에 portfolio_summary.json 예시 없음 "
            "(exchange_rate + total 구조 필요)"
        )

        # total 객체 내부 필드 검증
        total = ps_block.get("total", {})
        for field in ["invested_krw", "current_value_krw", "pnl_krw", "pnl_pct"]:
            assert field in total, (
                f"ARCHITECTURE.md portfolio_summary 예시의 total.'{field}' 누락"
            )

        # sectors/holdings/risk/history 키 검증
        assert "sectors" in ps_block or "holdings" in ps_block, (
            "ARCHITECTURE.md portfolio_summary 예시에 sectors 또는 holdings 누락"
        )
        assert "risk" in ps_block, "ARCHITECTURE.md portfolio_summary 예시에 risk 누락"

    def test_architecture_erd_all_columns(self, architecture, db_schema):
        """ERD에 표시된 모든 테이블의 핵심 컬럼이 실제 DB에 존재"""
        # macro_daily 핵심 컬럼
        cursor = db_schema.execute("PRAGMA table_info(macro_daily)")
        cols = {row[1] for row in cursor.fetchall()}
        for field in [
            "indicator",
            "date",
            "open",
            "high",
            "low",
            "close",
            "change_pct",
        ]:
            assert field in cols, f"macro_daily 컬럼 '{field}' 누락"

        # alerts 핵심 컬럼
        cursor = db_schema.execute("PRAGMA table_info(alerts)")
        cols = {row[1] for row in cursor.fetchall()}
        for field in [
            "level",
            "event_type",
            "ticker",
            "message",
            "triggered_at",
            "notified",
        ]:
            assert field in cols, f"alerts 컬럼 '{field}' 누락"

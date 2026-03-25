"""
F11 — JSON 출력 스키마 검증 테스트
output/intel/ JSON 파일의 필수 필드 + 타입 검증
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.schema import SCHEMAS, validate_json, validate_all_outputs


# ── 스키마 정의 테스트 ──


class TestSchemaDefinitions:
    """스키마 딕셔너리가 올바르게 정의되어 있는지 확인"""

    def test_all_json_files_have_schema(self):
        """모든 output/intel/ JSON 파일에 대한 스키마가 정의되어 있어야 함"""
        expected = {
            "prices.json",
            "macro.json",
            "news.json",
            "portfolio_summary.json",
            "alerts.json",
            "price_analysis.json",
            "opportunities.json",
            "engine_status.json",
        }
        assert expected == set(SCHEMAS.keys())

    def test_schema_has_required_keys(self):
        """각 스키마에 top_level 필수, item_fields는 항목 구조가 있는 경우만"""
        for name, schema in SCHEMAS.items():
            assert "top_level" in schema, f"{name}: top_level 누락"
            # item_fields는 항목 배열/딕셔너리가 있는 스키마만 필요
            if schema.get("items_key"):
                assert "item_fields" in schema, f"{name}: item_fields 누락"

    def test_schema_fields_have_types(self):
        """모든 필드에 타입이 지정되어 있어야 함"""
        valid_types = {str, int, float, bool, list, dict, "number"}
        for name, schema in SCHEMAS.items():
            for field, ftype in schema["top_level"].items():
                assert ftype in valid_types, (
                    f"{name}.top_level.{field}: 유효하지 않은 타입 {ftype}"
                )
            for field, ftype in schema.get("item_fields", {}).items():
                assert ftype in valid_types, (
                    f"{name}.item_fields.{field}: 유효하지 않은 타입 {ftype}"
                )


# ── 유효한 JSON 검증 테스트 ──


class TestValidJson:
    """올바른 JSON이 검증을 통과하는지 확인"""

    def test_valid_prices_json(self):
        """유효한 prices.json은 경고 없이 통과"""
        data = {
            "updated_at": "2026-03-25T10:00:00+09:00",
            "count": 1,
            "prices": [
                {
                    "ticker": "005930.KS",
                    "name": "삼성전자",
                    "price": 55000,
                    "prev_close": 54000,
                    "change_pct": 1.85,
                    "volume": 1000000,
                    "currency": "KRW",
                    "market": "KR",
                    "timestamp": "2026-03-25T10:00:00+09:00",
                    "data_source": "yahoo",
                }
            ],
        }
        warnings = validate_json("prices.json", data)
        assert warnings == []

    def test_valid_macro_json(self):
        """유효한 macro.json은 경고 없이 통과"""
        data = {
            "updated_at": "2026-03-25T10:00:00+09:00",
            "count": 1,
            "indicators": [
                {
                    "indicator": "코스피",
                    "ticker": "KOSPI",
                    "value": 2500.0,
                    "prev_close": 2490.0,
                    "change_pct": 0.4,
                    "category": "INDEX",
                    "timestamp": "2026-03-25T10:00:00+09:00",
                }
            ],
        }
        warnings = validate_json("macro.json", data)
        assert warnings == []

    def test_valid_news_json(self):
        """유효한 news.json은 경고 없이 통과"""
        data = {
            "updated_at": "2026-03-25T10:00:00+09:00",
            "count": 1,
            "news": [
                {
                    "title": "테스트 뉴스",
                    "source": "연합뉴스",
                    "url": "https://example.com/news/1",
                    "published_at": "2026-03-25",
                    "relevance_score": 0.8,
                    "sentiment": 0.5,
                    "category": "stock",
                    "tickers": ["005930.KS"],
                    "timestamp": "2026-03-25T10:00:00+09:00",
                }
            ],
        }
        warnings = validate_json("news.json", data)
        assert warnings == []

    def test_valid_portfolio_summary_json(self):
        """유효한 portfolio_summary.json은 경고 없이 통과"""
        data = {
            "updated_at": "2026-03-25T10:00:00+09:00",
            "exchange_rate": 1350.0,
            "total": {
                "invested_krw": 10000000,
                "current_value_krw": 11000000,
                "pnl_krw": 1000000,
                "pnl_pct": 10.0,
            },
            "holdings": [
                {
                    "ticker": "005930.KS",
                    "name": "삼성전자",
                    "currency": "KRW",
                    "price": 55000,
                    "avg_cost": 50000,
                    "qty": 10,
                    "current_value_krw": 550000,
                    "invested_krw": 500000,
                    "pnl_krw": 50000,
                    "pnl_pct": 10.0,
                }
            ],
            "sectors": [],
            "risk": {},
        }
        warnings = validate_json("portfolio_summary.json", data)
        assert warnings == []

    def test_valid_alerts_json(self):
        """유효한 alerts.json은 경고 없이 통과"""
        data = {
            "triggered_at": "2026-03-25T10:00:00+09:00",
            "count": 1,
            "alerts": [
                {
                    "level": "RED",
                    "event_type": "stock_drop",
                    "message": "삼성전자 -5% 급락",
                    "value": -5.0,
                    "threshold": -3.0,
                }
            ],
        }
        warnings = validate_json("alerts.json", data)
        assert warnings == []

    def test_valid_price_analysis_json(self):
        """유효한 price_analysis.json은 경고 없이 통과"""
        data = {
            "updated_at": "2026-03-25T10:00:00+09:00",
            "analysis": {
                "005930.KS": {
                    "name": "삼성전자",
                    "current": 55000,
                    "rsi_14": 55.0,
                    "trend": "uptrend",
                }
            },
        }
        warnings = validate_json("price_analysis.json", data)
        assert warnings == []


# ── 무효한 JSON 검증 테스트 ──


class TestInvalidJson:
    """잘못된 JSON이 적절한 경고를 반환하는지 확인"""

    def test_missing_top_level_field(self):
        """필수 최상위 필드 누락 시 경고"""
        data = {"count": 1, "prices": []}  # updated_at 누락
        warnings = validate_json("prices.json", data)
        assert any("updated_at" in w for w in warnings)

    def test_wrong_top_level_type(self):
        """최상위 필드 타입이 틀리면 경고"""
        data = {
            "updated_at": "2026-03-25T10:00:00+09:00",
            "count": "not_a_number",  # int여야 함
            "prices": [],
        }
        warnings = validate_json("prices.json", data)
        assert any("count" in w and "타입" in w for w in warnings)

    def test_missing_item_field(self):
        """배열 항목에 필수 필드 누락 시 경고"""
        data = {
            "updated_at": "2026-03-25T10:00:00+09:00",
            "count": 1,
            "prices": [
                {
                    "ticker": "005930.KS",
                    # name 누락
                    "price": 55000,
                    "prev_close": 54000,
                    "change_pct": 1.85,
                    "volume": 1000000,
                    "currency": "KRW",
                    "market": "KR",
                    "timestamp": "2026-03-25T10:00:00+09:00",
                    "data_source": "yahoo",
                }
            ],
        }
        warnings = validate_json("prices.json", data)
        assert any("name" in w for w in warnings)

    def test_wrong_item_field_type(self):
        """배열 항목 필드 타입이 틀리면 경고"""
        data = {
            "updated_at": "2026-03-25T10:00:00+09:00",
            "count": 1,
            "prices": [
                {
                    "ticker": "005930.KS",
                    "name": "삼성전자",
                    "price": "오만원",  # number여야 함
                    "prev_close": 54000,
                    "change_pct": 1.85,
                    "volume": 1000000,
                    "currency": "KRW",
                    "market": "KR",
                    "timestamp": "2026-03-25T10:00:00+09:00",
                    "data_source": "yahoo",
                }
            ],
        }
        warnings = validate_json("prices.json", data)
        assert any("price" in w and "타입" in w for w in warnings)

    def test_none_where_string_expected(self):
        """문자열이 와야 할 곳에 None이 오면 경고"""
        data = {
            "updated_at": "2026-03-25T10:00:00+09:00",
            "count": 1,
            "prices": [
                {
                    "ticker": "005930.KS",
                    "name": None,  # str이어야 함
                    "price": 55000,
                    "prev_close": 54000,
                    "change_pct": 1.85,
                    "volume": 1000000,
                    "currency": "KRW",
                    "market": "KR",
                    "timestamp": "2026-03-25T10:00:00+09:00",
                    "data_source": "yahoo",
                }
            ],
        }
        warnings = validate_json("prices.json", data)
        assert any("name" in w and "None" in w for w in warnings)

    def test_multiple_items_validates_all(self):
        """여러 항목이 있을 때 모든 항목을 검증"""
        data = {
            "updated_at": "2026-03-25T10:00:00+09:00",
            "count": 2,
            "indicators": [
                {
                    "indicator": "코스피",
                    "ticker": "KOSPI",
                    "value": 2500.0,
                    "prev_close": 2490.0,
                    "change_pct": 0.4,
                    "category": "INDEX",
                    "timestamp": "2026-03-25T10:00:00+09:00",
                },
                {
                    # indicator 누락
                    "ticker": "KOSDAQ",
                    "value": 800.0,
                    "prev_close": 790.0,
                    "change_pct": 1.27,
                    "category": "INDEX",
                    "timestamp": "2026-03-25T10:00:00+09:00",
                },
            ],
        }
        warnings = validate_json("macro.json", data)
        assert any("indicator" in w and "[1]" in w for w in warnings)

    def test_empty_data_no_crash(self):
        """빈 데이터도 에러 없이 경고 반환"""
        warnings = validate_json("prices.json", {})
        assert len(warnings) > 0

    def test_unknown_schema_ignored(self):
        """스키마가 정의되지 않은 파일명은 빈 경고 반환"""
        warnings = validate_json("unknown_file.json", {"foo": "bar"})
        assert warnings == []


# ── 에러 항목 스킵 테스트 ──


class TestErrorItemSkip:
    """error 필드가 있는 항목은 필수 필드 검증을 스킵"""

    def test_error_item_skips_validation(self):
        """에러 레코드는 필수 필드 누락이어도 경고 없음"""
        data = {
            "updated_at": "2026-03-25T10:00:00+09:00",
            "count": 0,
            "prices": [
                {
                    "ticker": "005930.KS",
                    "name": "삼성전자",
                    "error": "API 타임아웃",
                }
            ],
        }
        warnings = validate_json("prices.json", data)
        assert warnings == []


# ── number 타입 검증 (int 또는 float) ──


class TestNumberType:
    """'number' 타입은 int와 float 모두 허용"""

    def test_int_accepted_as_number(self):
        """int 값이 number 필드에 허용"""
        data = {
            "updated_at": "2026-03-25T10:00:00+09:00",
            "count": 1,
            "prices": [
                {
                    "ticker": "005930.KS",
                    "name": "삼성전자",
                    "price": 55000,  # int
                    "prev_close": 54000,
                    "change_pct": 1.85,
                    "volume": 1000000,
                    "currency": "KRW",
                    "market": "KR",
                    "timestamp": "2026-03-25T10:00:00+09:00",
                    "data_source": "yahoo",
                }
            ],
        }
        warnings = validate_json("prices.json", data)
        assert warnings == []

    def test_float_accepted_as_number(self):
        """float 값이 number 필드에 허용"""
        data = {
            "updated_at": "2026-03-25T10:00:00+09:00",
            "count": 1,
            "prices": [
                {
                    "ticker": "005930.KS",
                    "name": "삼성전자",
                    "price": 55000.5,  # float
                    "prev_close": 54000.0,
                    "change_pct": 1.85,
                    "volume": 1000000,
                    "currency": "KRW",
                    "market": "KR",
                    "timestamp": "2026-03-25T10:00:00+09:00",
                    "data_source": "yahoo",
                }
            ],
        }
        warnings = validate_json("prices.json", data)
        assert warnings == []


# ── validate_all_outputs 통합 테스트 ──


class TestValidateAllOutputs:
    """파일 시스템에서 JSON을 읽어 검증하는 통합 함수"""

    def test_validates_existing_files(self, tmp_path):
        """존재하는 JSON 파일을 읽어서 검증"""
        prices = {
            "updated_at": "2026-03-25T10:00:00+09:00",
            "count": 0,
            "prices": [],
        }
        (tmp_path / "prices.json").write_text(json.dumps(prices), encoding="utf-8")
        all_warnings = validate_all_outputs(tmp_path)
        assert "prices.json" in all_warnings
        assert all_warnings["prices.json"] == []

    def test_skips_missing_files(self, tmp_path):
        """존재하지 않는 파일은 스킵"""
        all_warnings = validate_all_outputs(tmp_path)
        # 파일이 없으면 결과에 포함되지 않음
        assert len(all_warnings) == 0

    def test_reports_invalid_file(self, tmp_path):
        """무효한 JSON 파일의 경고를 반환"""
        bad_prices = {"prices": [{"ticker": "X"}]}  # updated_at, count 누락
        (tmp_path / "prices.json").write_text(json.dumps(bad_prices), encoding="utf-8")
        all_warnings = validate_all_outputs(tmp_path)
        assert len(all_warnings["prices.json"]) > 0

    def test_handles_malformed_json(self, tmp_path):
        """깨진 JSON 파일도 에러 없이 경고 반환"""
        (tmp_path / "prices.json").write_text("{invalid json}", encoding="utf-8")
        all_warnings = validate_all_outputs(tmp_path)
        assert any(
            "파싱" in w or "JSON" in w for w in all_warnings.get("prices.json", [])
        )


# ── price_analysis.json 특수 구조 테스트 ──


class TestPriceAnalysisSchema:
    """price_analysis.json은 배열이 아닌 딕셔너리 구조"""

    def test_analysis_dict_items_validated(self):
        """analysis 딕셔너리의 각 값이 item_fields로 검증됨"""
        data = {
            "updated_at": "2026-03-25T10:00:00+09:00",
            "analysis": {
                "005930.KS": {
                    # name 누락
                    "current": 55000,
                    "rsi_14": 55.0,
                    "trend": "uptrend",
                },
            },
        }
        warnings = validate_json("price_analysis.json", data)
        assert any("name" in w for w in warnings)

    def test_portfolio_total_nested_validation(self):
        """portfolio_summary.json의 total 딕셔너리 필드 검증"""
        data = {
            "updated_at": "2026-03-25T10:00:00+09:00",
            "exchange_rate": 1350.0,
            "total": {
                "invested_krw": 10000000,
                # current_value_krw 누락
                "pnl_krw": 1000000,
                "pnl_pct": 10.0,
            },
            "holdings": [],
            "sectors": [],
            "risk": {},
        }
        warnings = validate_json("portfolio_summary.json", data)
        assert any("current_value_krw" in w for w in warnings)

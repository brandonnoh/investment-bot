#!/usr/bin/env python3
"""F23 테스트 — 수급 데이터 수집 (KRX 외국인/기관 순매수 + Fear & Greed Index)"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── KRX 수급 데이터 수집 테스트 ──


class TestFetchKrxSupply:
    """KRX 외국인/기관 순매수 수집"""

    def test_parse_krx_response_success(self):
        """KRX API 응답 파싱 — 정상"""
        from data.fetch_supply import parse_krx_response

        # KRX 투자자별 매매동향 API 응답 형식
        raw = {
            "OutBlock_1": [
                {
                    "ISU_CD": "005930",
                    "ISU_NM": "삼성전자",
                    "FRGN_NET_BUY_QTY": "1500000",
                    "INST_NET_BUY_QTY": "-800000",
                },
                {
                    "ISU_CD": "000660",
                    "ISU_NM": "SK하이닉스",
                    "FRGN_NET_BUY_QTY": "-200000",
                    "INST_NET_BUY_QTY": "500000",
                },
            ]
        }
        result = parse_krx_response(raw)
        assert len(result) == 2
        assert result["005930"]["foreign_net"] == 1500000
        assert result["005930"]["inst_net"] == -800000
        assert result["000660"]["foreign_net"] == -200000
        assert result["000660"]["inst_net"] == 500000

    def test_parse_krx_response_empty(self):
        """KRX 응답 비어있음"""
        from data.fetch_supply import parse_krx_response

        assert parse_krx_response({}) == {}
        assert parse_krx_response({"OutBlock_1": []}) == {}

    def test_parse_krx_response_comma_numbers(self):
        """콤마가 포함된 숫자 처리"""
        from data.fetch_supply import parse_krx_response

        raw = {
            "OutBlock_1": [
                {
                    "ISU_CD": "005930",
                    "ISU_NM": "삼성전자",
                    "FRGN_NET_BUY_QTY": "1,500,000",
                    "INST_NET_BUY_QTY": "-800,000",
                },
            ]
        }
        result = parse_krx_response(raw)
        assert result["005930"]["foreign_net"] == 1500000
        assert result["005930"]["inst_net"] == -800000

    @patch("data.fetch_supply.urllib.request.urlopen")
    def test_fetch_krx_supply_success(self, mock_urlopen):
        """KRX API 호출 성공"""
        from data.fetch_supply import fetch_krx_supply

        response_data = {
            "OutBlock_1": [
                {
                    "ISU_CD": "005930",
                    "ISU_NM": "삼성전자",
                    "FRGN_NET_BUY_QTY": "1000000",
                    "INST_NET_BUY_QTY": "500000",
                },
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(response_data).encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = fetch_krx_supply()
        assert "005930" in result
        assert result["005930"]["foreign_net"] == 1000000

    @patch("data.fetch_supply.urllib.request.urlopen")
    def test_fetch_krx_supply_failure_graceful(self, mock_urlopen):
        """KRX API 실패 시 빈 딕셔너리 반환 (graceful degradation)"""
        from data.fetch_supply import fetch_krx_supply

        mock_urlopen.side_effect = Exception("Connection refused")
        result = fetch_krx_supply()
        assert result == {}


# ── Fear & Greed Index 수집 테스트 ──


class TestFetchFearGreed:
    """CNN Fear & Greed Index 수집"""

    @patch("data.fetch_supply.urllib.request.urlopen")
    def test_fetch_fear_greed_success(self, mock_urlopen):
        """Fear & Greed Index 수집 성공"""
        from data.fetch_supply import fetch_fear_greed

        response_data = {
            "fear_and_greed": {
                "score": 35.0,
                "rating": "fear",
                "previous_close": 38.0,
            }
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(response_data).encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = fetch_fear_greed()
        assert result is not None
        assert result["score"] == 35.0
        assert result["rating"] == "fear"

    @patch("data.fetch_supply.urllib.request.urlopen")
    def test_fetch_fear_greed_failure_graceful(self, mock_urlopen):
        """Fear & Greed 수집 실패 시 None 반환"""
        from data.fetch_supply import fetch_fear_greed

        mock_urlopen.side_effect = Exception("Timeout")
        result = fetch_fear_greed()
        assert result is None

    def test_fear_greed_to_macro_score(self):
        """Fear & Greed → 매크로 방향 점수 변환"""
        from data.fetch_supply import fear_greed_to_score

        # 극도의 공포 (0) → -1.0
        assert fear_greed_to_score(0) == -1.0
        # 중립 (50) → 0.0
        assert fear_greed_to_score(50) == 0.0
        # 극도의 탐욕 (100) → 1.0
        assert fear_greed_to_score(100) == 1.0
        # 공포 (25) → -0.5
        assert fear_greed_to_score(25) == -0.5
        # 탐욕 (75) → 0.5
        assert fear_greed_to_score(75) == 0.5

    def test_fear_greed_to_macro_score_none(self):
        """Fear & Greed None일 때 중립 0.0"""
        from data.fetch_supply import fear_greed_to_score

        assert fear_greed_to_score(None) == 0.0


# ── DB 저장 테스트 ──


class TestSupplyDB:
    """수급 데이터 DB 저장"""

    def test_save_supply_to_db(self, db_conn):
        """fundamentals 테이블에 foreign_net/inst_net 저장"""
        from data.fetch_supply import save_supply_to_db

        # 기존 fundamentals 레코드 삽입
        db_conn.execute(
            """INSERT INTO fundamentals (ticker, name, market, per, updated_at)
               VALUES ('005930.KS', '삼성전자', 'KR', 10.5, '2026-03-26')"""
        )
        db_conn.commit()

        supply_data = {
            "005930": {"foreign_net": 1500000, "inst_net": -800000},
        }
        save_supply_to_db(db_conn, supply_data)

        row = db_conn.execute(
            "SELECT foreign_net, inst_net FROM fundamentals WHERE ticker='005930.KS'"
        ).fetchone()
        assert row is not None
        assert row[0] == 1500000
        assert row[1] == -800000

    def test_save_supply_no_matching_ticker(self, db_conn):
        """매칭되는 종목이 없을 때 에러 없이 건너뜀"""
        from data.fetch_supply import save_supply_to_db

        supply_data = {
            "999999": {"foreign_net": 100, "inst_net": 200},
        }
        # 에러 없이 실행되어야 함
        save_supply_to_db(db_conn, supply_data)

    def test_fundamentals_table_has_supply_columns(self, db_conn):
        """fundamentals 테이블에 foreign_net/inst_net 컬럼 존재"""
        cursor = db_conn.execute("PRAGMA table_info(fundamentals)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "foreign_net" in columns
        assert "inst_net" in columns


# ── 매크로 방향 통합 테스트 ──


class TestMacroDirectionWithFearGreed:
    """Fear & Greed를 매크로 방향에 반영"""

    def test_macro_direction_with_fear_greed(self):
        """Fear & Greed가 매크로 방향 계산에 포함"""
        from analysis.composite_score import calculate_macro_direction

        macro = {
            "KOSPI": {"change_pct": 1.0},
            "KRW=X": {"change_pct": -0.5},
            "CL=F": {"change_pct": 2.0},
            "^VIX": {"change_pct": -3.0},
        }
        # Fear & Greed 없이 (기준값)
        calculate_macro_direction(macro)

        # Fear & Greed 포함 (극도의 공포)
        macro_with_fg = {**macro, "fear_greed": {"score": 10, "rating": "extreme fear"}}
        score_with_fear = calculate_macro_direction(macro_with_fg)

        # Fear & Greed 포함 (탐욕)
        macro_with_greed = {**macro, "fear_greed": {"score": 80, "rating": "greed"}}
        score_with_greed = calculate_macro_direction(macro_with_greed)

        # 공포 시 매크로 방향이 더 부정적
        assert score_with_fear < score_with_greed

    def test_macro_direction_fear_greed_absent(self):
        """Fear & Greed 없으면 기존 4팩터만 사용"""
        from analysis.composite_score import calculate_macro_direction

        macro = {
            "KOSPI": {"change_pct": 0},
            "KRW=X": {"change_pct": 0},
            "CL=F": {"change_pct": 0},
            "^VIX": {"change_pct": 0},
        }
        score = calculate_macro_direction(macro)
        assert score == 0.0


# ── run() 통합 테스트 ──


class TestSupplyRun:
    """run() 통합 테스트"""

    @patch("data.fetch_supply.fetch_fear_greed")
    @patch("data.fetch_supply.fetch_krx_supply")
    def test_run_success(self, mock_krx, mock_fg, db_conn, tmp_output_dir):
        """run() 정상 실행 — KRX + Fear & Greed 수집"""
        from data.fetch_supply import run

        # 펀더멘탈 레코드 준비
        db_conn.execute(
            """INSERT INTO fundamentals (ticker, name, market, per, updated_at)
               VALUES ('005930.KS', '삼성전자', 'KR', 10.5, '2026-03-26')"""
        )
        db_conn.commit()

        mock_krx.return_value = {
            "005930": {"foreign_net": 1000000, "inst_net": 500000},
        }
        mock_fg.return_value = {
            "score": 42.0,
            "rating": "fear",
            "previous_close": 45.0,
        }

        result = run(conn=db_conn, output_dir=str(tmp_output_dir))

        # 반환값 확인
        assert "krx_supply" in result
        assert "fear_greed" in result
        assert result["fear_greed"]["score"] == 42.0

        # DB 업데이트 확인
        row = db_conn.execute(
            "SELECT foreign_net, inst_net FROM fundamentals WHERE ticker='005930.KS'"
        ).fetchone()
        assert row[0] == 1000000

        # JSON 파일 생성 확인
        json_path = tmp_output_dir / "supply_data.json"
        assert json_path.exists()
        data = json.loads(json_path.read_text())
        assert "fear_greed" in data
        assert "krx_supply" in data

    @patch("data.fetch_supply.fetch_fear_greed")
    @patch("data.fetch_supply.fetch_krx_supply")
    def test_run_all_fail_graceful(self, mock_krx, mock_fg, db_conn, tmp_output_dir):
        """KRX + Fear & Greed 모두 실패해도 에러 없이 완료"""
        from data.fetch_supply import run

        mock_krx.return_value = {}
        mock_fg.return_value = None

        result = run(conn=db_conn, output_dir=str(tmp_output_dir))

        assert result["krx_supply"] == {}
        assert result["fear_greed"] is None

    @patch("data.fetch_supply.fetch_fear_greed")
    @patch("data.fetch_supply.fetch_krx_supply")
    def test_run_partial_success(self, mock_krx, mock_fg, db_conn, tmp_output_dir):
        """KRX 실패 + Fear & Greed 성공"""
        from data.fetch_supply import run

        mock_krx.return_value = {}
        mock_fg.return_value = {
            "score": 55.0,
            "rating": "neutral",
            "previous_close": 52.0,
        }

        result = run(conn=db_conn, output_dir=str(tmp_output_dir))
        assert result["krx_supply"] == {}
        assert result["fear_greed"]["score"] == 55.0


# ── JSON 스키마 테스트 ──


class TestSupplyJsonSchema:
    """supply_data.json 스키마 검증"""

    @patch("data.fetch_supply.fetch_fear_greed")
    @patch("data.fetch_supply.fetch_krx_supply")
    def test_json_schema(self, mock_krx, mock_fg, db_conn, tmp_output_dir):
        """supply_data.json 필수 필드 확인"""
        from data.fetch_supply import run

        mock_krx.return_value = {}
        mock_fg.return_value = {
            "score": 50.0,
            "rating": "neutral",
            "previous_close": 48.0,
        }

        run(conn=db_conn, output_dir=str(tmp_output_dir))

        json_path = tmp_output_dir / "supply_data.json"
        data = json.loads(json_path.read_text())

        assert "updated_at" in data
        assert "fear_greed" in data
        assert "krx_supply" in data

"""
F10 — 에러 복구 강화 테스트
HTTP 재시도 + 지수 백오프 + 서킷 브레이커 + 이상값 감지
"""

import json
import sys
import time
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── retry_request 테스트 ──


class TestRetryRequest:
    """지수 백오프 재시도 테스트"""

    def test_성공_시_즉시_반환(self):
        """첫 시도에서 성공하면 바로 결과 반환"""
        from utils.http import retry_request

        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"result": "ok"}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            result = retry_request("http://example.com", timeout=5)
            assert result == b'{"result": "ok"}'
            assert mock_open.call_count == 1

    def test_일시_실패_후_재시도_성공(self):
        """1회 실패 후 2회차에서 성공"""
        from utils.http import retry_request

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"ok"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        effects = [urllib.error.URLError("timeout"), mock_resp]

        with patch("urllib.request.urlopen", side_effect=effects) as mock_open:
            with patch("time.sleep") as mock_sleep:
                result = retry_request("http://example.com", timeout=5)
                assert result == b"ok"
                assert mock_open.call_count == 2
                # 첫 재시도 대기: 1초
                mock_sleep.assert_called_once_with(1)

    def test_최대_재시도_후_예외(self):
        """3회 모두 실패하면 마지막 예외 발생"""
        from utils.http import retry_request

        error = urllib.error.URLError("server down")
        with patch("urllib.request.urlopen", side_effect=error), patch("time.sleep"):
            with pytest.raises(urllib.error.URLError):
                retry_request("http://example.com", max_retries=3, timeout=5)

    def test_지수_백오프_대기시간(self):
        """재시도 대기: 1초 → 2초 → 4초"""
        from utils.http import retry_request

        error = urllib.error.URLError("fail")
        with patch("urllib.request.urlopen", side_effect=error):
            with patch("time.sleep") as mock_sleep:
                with pytest.raises(urllib.error.URLError):
                    retry_request("http://example.com", max_retries=3, timeout=5)
                # 3회 시도 → 2회 재시도 대기 (마지막 시도 후에는 대기 없음)
                assert mock_sleep.call_args_list == [call(1), call(2)]

    def test_헤더_전달(self):
        """커스텀 헤더가 Request에 전달됨"""
        from utils.http import retry_request

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"ok"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        headers = {"User-Agent": "TestBot", "X-Custom": "value"}
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            retry_request("http://example.com", headers=headers, timeout=5)
            req = mock_open.call_args[0][0]
            assert req.get_header("User-agent") == "TestBot"
            assert req.get_header("X-custom") == "value"

    def test_HTTP_4xx_재시도_안함(self):
        """클라이언트 오류(4xx)는 재시도하지 않음"""
        from utils.http import retry_request

        error = urllib.error.HTTPError("http://example.com", 404, "Not Found", {}, None)
        with patch("urllib.request.urlopen", side_effect=error):
            with patch("time.sleep") as mock_sleep:
                with pytest.raises(urllib.error.HTTPError):
                    retry_request("http://example.com", timeout=5)
                mock_sleep.assert_not_called()

    def test_HTTP_429_재시도함(self):
        """Rate limit(429)은 재시도 대상"""
        from utils.http import retry_request

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"ok"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        error_429 = urllib.error.HTTPError(
            "http://example.com", 429, "Too Many Requests", {}, None
        )
        effects = [error_429, mock_resp]
        with patch("urllib.request.urlopen", side_effect=effects), patch("time.sleep"):
            result = retry_request("http://example.com", timeout=5)
            assert result == b"ok"

    def test_HTTP_5xx_재시도함(self):
        """서버 오류(5xx)는 재시도 대상"""
        from utils.http import retry_request

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"ok"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        error_500 = urllib.error.HTTPError(
            "http://example.com", 500, "Internal Server Error", {}, None
        )
        effects = [error_500, mock_resp]
        with patch("urllib.request.urlopen", side_effect=effects), patch("time.sleep"):
            result = retry_request("http://example.com", timeout=5)
            assert result == b"ok"


# ── CircuitBreaker 테스트 ──


class TestCircuitBreaker:
    """서킷 브레이커 테스트"""

    def test_초기_상태_닫힘(self):
        """초기 상태는 CLOSED (정상 동작)"""
        from utils.http import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        assert cb.is_available("yahoo") is True

    def test_실패_누적_후_차단(self):
        """연속 N회 실패 시 해당 소스 차단"""
        from utils.http import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        cb.record_failure("yahoo")
        cb.record_failure("yahoo")
        assert cb.is_available("yahoo") is True  # 2회 — 아직 열림
        cb.record_failure("yahoo")
        assert cb.is_available("yahoo") is False  # 3회 — 차단

    def test_성공_시_카운터_리셋(self):
        """성공하면 실패 카운터 초기화"""
        from utils.http import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        cb.record_failure("yahoo")
        cb.record_failure("yahoo")
        cb.record_success("yahoo")
        cb.record_failure("yahoo")
        assert cb.is_available("yahoo") is True  # 리셋 후 1회 — 정상

    def test_복구_시간_후_재시도_허용(self):
        """recovery_timeout 경과 후 다시 시도 가능"""
        from utils.http import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        cb.record_failure("naver")
        cb.record_failure("naver")
        assert cb.is_available("naver") is False

        # 시간 경과 시뮬레이션
        cb._sources["naver"]["opened_at"] = time.time() - 2
        assert cb.is_available("naver") is True

    def test_소스별_독립_관리(self):
        """소스마다 독립적으로 서킷 관리"""
        from utils.http import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60)
        cb.record_failure("yahoo")
        cb.record_failure("yahoo")
        assert cb.is_available("yahoo") is False
        assert cb.is_available("naver") is True

    def test_반개방_후_성공_시_닫힘(self):
        """반개방(half-open) 상태에서 성공하면 CLOSED로 복구"""
        from utils.http import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        cb.record_failure("yahoo")
        cb.record_failure("yahoo")
        assert cb.is_available("yahoo") is False

        # 복구 시간 경과 → half-open
        cb._sources["yahoo"]["opened_at"] = time.time() - 2
        assert cb.is_available("yahoo") is True

        # 성공 → closed
        cb.record_success("yahoo")
        assert cb.is_available("yahoo") is True
        assert cb._sources["yahoo"]["failures"] == 0

    def test_반개방_후_실패_시_다시_열림(self):
        """반개방 상태에서 또 실패하면 다시 OPEN"""
        from utils.http import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        cb.record_failure("yahoo")
        cb.record_failure("yahoo")

        # 복구 시간 경과 → half-open
        cb._sources["yahoo"]["opened_at"] = time.time() - 2
        assert cb.is_available("yahoo") is True  # half-open 허용

        # 또 실패 → open
        cb.record_failure("yahoo")
        assert cb.is_available("yahoo") is False

    def test_get_status_반환(self):
        """서킷 상태 조회"""
        from utils.http import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        status = cb.get_status("yahoo")
        assert status["state"] == "closed"
        assert status["failures"] == 0

        cb.record_failure("yahoo")
        cb.record_failure("yahoo")
        cb.record_failure("yahoo")
        status = cb.get_status("yahoo")
        assert status["state"] == "open"
        assert status["failures"] == 3


# ── 이상값 감지 테스트 ──


class TestDataValidation:
    """수집 데이터 이상값 감지 테스트"""

    def test_정상_가격_통과(self):
        """정상 가격은 경고 없음"""
        from utils.http import validate_price_data

        warnings = validate_price_data(50000, 49000, "005930.KS")
        assert warnings == []

    def test_가격_0_경고(self):
        """가격이 0이면 경고"""
        from utils.http import validate_price_data

        warnings = validate_price_data(0, 50000, "005930.KS")
        assert len(warnings) == 1
        assert "0" in warnings[0]

    def test_가격_음수_경고(self):
        """가격이 음수면 경고"""
        from utils.http import validate_price_data

        warnings = validate_price_data(-100, 50000, "005930.KS")
        assert len(warnings) == 1
        assert "음수" in warnings[0] or "0" in warnings[0]

    def test_가격_None_경고(self):
        """가격이 None이면 경고"""
        from utils.http import validate_price_data

        warnings = validate_price_data(None, 50000, "005930.KS")
        assert len(warnings) >= 1

    def test_전일비_50퍼센트_초과_경고(self):
        """전일 대비 ±50% 초과 변동 시 경고"""
        from utils.http import validate_price_data

        # +60% 상승
        warnings = validate_price_data(80000, 50000, "005930.KS")
        assert len(warnings) == 1
        assert "50%" in warnings[0]

    def test_전일비_50퍼센트_미만_하락_경고(self):
        """-50% 초과 하락 시 경고"""
        from utils.http import validate_price_data

        # -60% 하락
        warnings = validate_price_data(20000, 50000, "005930.KS")
        assert len(warnings) == 1
        assert "50%" in warnings[0]

    def test_전일비_30퍼센트_정상(self):
        """±30% 변동은 경고 없음 (극단적이지만 합법적)"""
        from utils.http import validate_price_data

        warnings = validate_price_data(65000, 50000, "005930.KS")
        assert warnings == []

    def test_prev_close_없으면_검증_스킵(self):
        """prev_close가 없으면 변동률 검증 스킵"""
        from utils.http import validate_price_data

        warnings = validate_price_data(50000, None, "005930.KS")
        assert warnings == []

    def test_prev_close_0_검증_스킵(self):
        """prev_close가 0이면 변동률 검증 스킵 (나누기 방지)"""
        from utils.http import validate_price_data

        warnings = validate_price_data(50000, 0, "005930.KS")
        assert warnings == []


# ── config 통합 테스트 ──


class TestConfigIntegration:
    """config.py에 HTTP 재시도 설정이 있는지 확인"""

    def test_HTTP_RETRY_CONFIG_존재(self):
        """config.py에 HTTP_RETRY_CONFIG 설정 존재"""
        from config import HTTP_RETRY_CONFIG

        assert "max_retries" in HTTP_RETRY_CONFIG
        assert "base_delay" in HTTP_RETRY_CONFIG
        assert HTTP_RETRY_CONFIG["max_retries"] == 3
        assert HTTP_RETRY_CONFIG["base_delay"] == 1

    def test_CIRCUIT_BREAKER_CONFIG_존재(self):
        """config.py에 CIRCUIT_BREAKER_CONFIG 설정 존재"""
        from config import CIRCUIT_BREAKER_CONFIG

        assert "failure_threshold" in CIRCUIT_BREAKER_CONFIG
        assert "recovery_timeout" in CIRCUIT_BREAKER_CONFIG


# ── fetch 모듈 통합 테스트 ──


class TestFetchIntegration:
    """수집 모듈에서 재시도/서킷 브레이커 동작 확인"""

    @patch("utils.http.urllib.request.urlopen")
    def test_prices_yahoo_재시도(self, mock_urlopen):
        """fetch_prices의 Yahoo 호출이 재시도됨"""
        from data.fetch_prices import fetch_yahoo_quote

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {
                "chart": {
                    "result": [
                        {
                            "meta": {
                                "regularMarketPrice": 100.0,
                                "chartPreviousClose": 99.0,
                            }
                        }
                    ]
                }
            }
        ).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        # 1회 실패 후 성공
        mock_urlopen.side_effect = [
            urllib.error.URLError("timeout"),
            mock_resp,
        ]
        with patch("utils.http.time.sleep"):
            result = fetch_yahoo_quote("TSLA")
        assert result["regularMarketPrice"] == 100.0
        assert mock_urlopen.call_count == 2

    @patch("utils.http.urllib.request.urlopen")
    def test_macro_yahoo_재시도(self, mock_urlopen):
        """fetch_macro의 Yahoo 호출이 재시도됨"""
        from data.fetch_macro import fetch_yahoo_quote

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {
                "chart": {
                    "result": [
                        {
                            "meta": {
                                "regularMarketPrice": 1400.5,
                                "chartPreviousClose": 1395.0,
                            }
                        }
                    ]
                }
            }
        ).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [
            urllib.error.URLError("timeout"),
            mock_resp,
        ]
        with patch("utils.http.time.sleep"):
            result = fetch_yahoo_quote("KRW=X")
        assert result["regularMarketPrice"] == 1400.5
        assert mock_urlopen.call_count == 2

    @patch("utils.http.urllib.request.urlopen")
    def test_prices_naver_재시도(self, mock_urlopen):
        """fetch_prices의 네이버 호출이 재시도됨"""
        from data.fetch_prices import fetch_naver_price

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {
                "datas": [
                    {
                        "closePrice": "55,000",
                        "compareToPreviousClosePrice": "1,000",
                        "fluctuationsRatio": "1.85",
                        "accumulatedTradingVolume": "10,000,000",
                        "highPrice": "56,000",
                        "lowPrice": "54,000",
                    }
                ]
            }
        ).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [
            urllib.error.URLError("timeout"),
            mock_resp,
        ]
        with patch("utils.http.time.sleep"):
            result = fetch_naver_price("005930")
        assert result["price"] == 55000
        assert mock_urlopen.call_count == 2


# ── 로그 기록 테스트 ──


class TestLogging:
    """재시도/스킵 로그 기록 테스트"""

    def test_재시도_로그_출력(self, capsys):
        """재시도 시 로그 메시지 출력"""
        from utils.http import retry_request

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"ok"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        error = urllib.error.URLError("timeout")
        with patch("urllib.request.urlopen", side_effect=[error, mock_resp]):
            with patch("time.sleep"):
                retry_request("http://example.com", timeout=5)

        captured = capsys.readouterr()
        assert "재시도" in captured.out or "retry" in captured.out.lower()

    def test_서킷_차단_로그_출력(self, capsys):
        """서킷 차단 시 로그 메시지 출력"""
        from utils.http import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60)
        cb.record_failure("yahoo")
        cb.record_failure("yahoo")

        captured = capsys.readouterr()
        assert "서킷" in captured.out or "circuit" in captured.out.lower()

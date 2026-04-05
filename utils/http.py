"""
공통 HTTP 헬퍼 모듈 — 재시도 + 서킷 브레이커 + 이상값 감지
모든 수집 모듈(fetch_prices, fetch_macro, fetch_news)에서 공통 사용
"""

import time
import urllib.error
import urllib.request

# ── 지수 백오프 재시도 ──


def retry_request(url, headers=None, timeout=10, max_retries=3, base_delay=1):
    """
    HTTP 요청 + 지수 백오프 재시도.
    - 5xx, 429, URLError → 재시도
    - 4xx (429 제외) → 즉시 예외
    - 최대 max_retries회 시도 후 마지막 예외 발생

    Returns:
        bytes: 응답 본문
    """
    req = urllib.request.Request(url, headers=headers or {})
    last_error = None

    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            last_error = e
            # 4xx (429 제외)는 재시도 무의미
            if 400 <= e.code < 500 and e.code != 429:
                raise
            # 5xx, 429 → 재시도
            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt)
                print(
                    f"    🔄 HTTP {e.code} 재시도 ({attempt + 1}/{max_retries}), {delay}초 대기"
                )
                time.sleep(delay)
        except urllib.error.URLError as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt)
                print(
                    f"    🔄 네트워크 오류 재시도 ({attempt + 1}/{max_retries}), {delay}초 대기: {e}"
                )
                time.sleep(delay)

    raise last_error


# ── 서킷 브레이커 ──


class CircuitBreaker:
    """
    소스별 서킷 브레이커.
    - CLOSED: 정상. 실패 카운트 누적
    - OPEN: failure_threshold 도달 시 차단. recovery_timeout 후 HALF-OPEN
    - HALF-OPEN: 1회 시도 허용. 성공 → CLOSED, 실패 → OPEN
    """

    def __init__(self, failure_threshold=5, recovery_timeout=300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._sources = {}  # {source: {failures, state, opened_at}}

    def _ensure_source(self, source):
        """소스 엔트리 초기화"""
        if source not in self._sources:
            self._sources[source] = {
                "failures": 0,
                "state": "closed",
                "opened_at": None,
            }

    def is_available(self, source):
        """해당 소스가 요청 가능한지 확인"""
        self._ensure_source(source)
        info = self._sources[source]

        if info["state"] == "closed":
            return True

        if info["state"] == "open":
            # recovery_timeout 경과 → half-open
            if time.time() - info["opened_at"] >= self.recovery_timeout:
                info["state"] = "half_open"
                return True
            return False

        # half_open → 1회 허용
        return True

    def record_failure(self, source):
        """실패 기록"""
        self._ensure_source(source)
        info = self._sources[source]
        info["failures"] += 1

        if info["failures"] >= self.failure_threshold:
            info["state"] = "open"
            info["opened_at"] = time.time()
            print(
                f"    ⚡ 서킷 OPEN: {source} (연속 {info['failures']}회 실패, {self.recovery_timeout}초 차단)"
            )

    def record_success(self, source):
        """성공 기록 — 카운터 리셋"""
        self._ensure_source(source)
        self._sources[source] = {
            "failures": 0,
            "state": "closed",
            "opened_at": None,
        }

    def get_status(self, source):
        """소스의 서킷 상태 반환"""
        self._ensure_source(source)
        info = self._sources[source]

        # 실제 상태 반영 (open이지만 timeout 경과 시)
        state = info["state"]
        if state == "open" and info["opened_at"]:
            if time.time() - info["opened_at"] >= self.recovery_timeout:
                state = "half_open"

        return {
            "state": state,
            "failures": info["failures"],
            "opened_at": info["opened_at"],
        }


# ── 이상값 감지 ──


def validate_price_data(price, prev_close, ticker, threshold_pct=50):
    """
    수집 데이터 이상값 검증.
    - 가격 0 또는 음수 → 경고
    - 가격 None → 경고
    - 전일비 ±threshold_pct% 초과 → 경고

    Returns:
        list[str]: 경고 메시지 목록 (빈 리스트 = 정상)
    """
    warnings = []

    if price is None:
        warnings.append(f"[{ticker}] 가격이 None — 데이터 누락")
        return warnings

    if price <= 0:
        warnings.append(f"[{ticker}] 가격이 0 이하: {price}")
        return warnings

    # 전일비 변동률 검증
    if prev_close and prev_close > 0:
        change_pct = abs((price - prev_close) / prev_close * 100)
        if change_pct > threshold_pct:
            warnings.append(
                f"[{ticker}] 전일비 {change_pct:.1f}% 변동 — 50% 초과 이상값 의심 "
                f"(현재: {price}, 전일: {prev_close})"
            )

    return warnings

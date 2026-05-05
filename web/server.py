#!/usr/bin/env python3
"""
미션컨트롤 HTTP 서버 (포트 8421)
ThreadingHTTPServer + SSE 실시간 업데이트
"""

import contextlib
import json
import os
import queue
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
import analysis.value_screener_strategies as screener  # noqa: E402
import db.ssot_wealth as ssot  # noqa: E402
import web.api as api  # noqa: E402
import web.api_advisor as api_advisor  # noqa: E402
import web.api_company as api_company  # noqa: E402
import web.api_history as api_history  # noqa: E402
import web.investment_advisor as investment_advisor  # noqa: E402
from db.init_db import init_db  # noqa: E402

init_db()

PORT = 8421
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")
_API_KEY = os.environ.get("INTERNAL_API_KEY", "")

_ALLOWED_LOG_NAMES = {"marcus", "pipeline", "jarvis", "alerts_watch", "refresh_prices"}
_CONTENT_TYPES: dict[str, str] = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".txt": "text/plain; charset=utf-8",
    ".webp": "image/webp",
    ".map": "application/json",
}
_NEXT_OUT = Path(__file__).parent.parent / "web-next" / "out"
WEB_DIR = _NEXT_OUT

_sse_clients: list[queue.Queue] = []
_sse_lock = threading.Lock()


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """다중 연결을 지원하는 ThreadingHTTPServer."""

    daemon_threads = True


class MissionControlHandler(BaseHTTPRequestHandler):
    """미션컨트롤 요청 핸들러."""

    def _check_auth(self) -> bool:
        """X-API-Key 헤더 검증. INTERNAL_API_KEY 미설정 시 항상 True."""
        if not _API_KEY:
            return True
        return self.headers.get("X-API-Key", "") == _API_KEY

    def log_message(self, format, *args):
        """보안 관련 요청(비정상 상태코드, 변경 메서드)만 기록."""
        if args and len(args) >= 2:
            status = str(args[1]) if len(args) > 1 else ""
            method = str(args[0]).split()[0] if args[0] else ""
            if status.startswith(("4", "5")) or method in ("POST", "PUT", "DELETE"):
                print(f"[server] {self.address_string()} {format % args}")

    def send_json(self, data: dict, status: int = 200):
        """JSON 응답 전송."""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, filepath: Path, content_type: str):
        """파일 내용 전송."""
        try:
            content = filepath.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_response(404)
            self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
            self.end_headers()

    def do_OPTIONS(self):
        """CORS preflight 처리."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key")
        self.end_headers()

    def _handle_api_data(self):
        """인텔 데이터 JSON 응답"""
        data = api.load_intel_data()
        self.send_json(data)

    def _handle_api_file(self, params: dict):
        """파일 다운로드 요청 처리 (MD/JSON)"""
        name = params.get("name", [""])[0]
        if not name or "/" in name or "\\" in name:
            self.send_json({"error": "잘못된 파일명"}, 400)
            return
        if name.endswith(".md"):
            if name not in api.MD_FILES:
                self.send_json({"error": "허용되지 않은 파일"}, 403)
                return
            content = api.load_md_file(name)
            body = content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/markdown; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif name.endswith(".json"):
            if name not in api.INTEL_FILES:
                self.send_json({"error": "허용되지 않은 파일"}, 403)
                return
            self.send_file(api.INTEL_DIR / name, "application/json; charset=utf-8")
        else:
            self.send_json({"error": "지원하지 않는 파일 형식"}, 400)

    def _serve_static(self, path: str):
        """정적 파일 서빙 + SPA 폴백."""
        safe = Path(path.lstrip("/"))
        if ".." in safe.parts:
            self.send_response(403)
            self.end_headers()
            return
        file_path = WEB_DIR / "index.html" if path == "/" else WEB_DIR / safe
        if file_path.is_file():
            ext = file_path.suffix.lower()
            ct = _CONTENT_TYPES.get(ext, "application/octet-stream")
            self.send_file(file_path, ct)
        else:
            index = WEB_DIR / "index.html"
            if index.is_file():
                self.send_file(index, "text/html; charset=utf-8")
            else:
                self.send_response(404)
                self.end_headers()

    def _parse_int_param(self, params: dict, key: str, default: int, lo: int, hi: int) -> int:
        """쿼리 파라미터를 정수로 파싱. 범위 초과 시 클램핑."""
        try:
            return max(lo, min(hi, int(params.get(key, [str(default)])[0])))
        except (ValueError, TypeError):
            return default

    def do_GET(self):
        """GET 요청 라우팅."""
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # 헬스체크 경로는 인증 불필요
        if path != "/api/status" and not self._check_auth():
            self.send_json({"error": "인증 실패"}, 401)
            return

        # API 라우트 우선 처리
        if path == "/api/data":
            self._handle_api_data()
        elif path == "/api/file":
            self._handle_api_file(params)
        elif path == "/api/status":
            self.send_json(api.get_process_status())
        elif path == "/api/events":
            self._handle_sse()
        elif path == "/api/analysis-history":
            date = params.get("date", [None])[0]
            if date:
                result = api.load_analysis_detail(date)
                self.send_json(result if result else {})
            else:
                self.send_json(api.load_analysis_history())
        elif path == "/api/wealth":
            days = self._parse_int_param(params, "days", 60, 1, 365)
            self.send_json(api.load_wealth_data(days))
        elif path == "/api/logs":
            name = params.get("name", ["marcus"])[0]
            if name not in _ALLOWED_LOG_NAMES:
                self.send_json({"error": "허용되지 않은 로그 이름"}, 400)
                return
            lines = self._parse_int_param(params, "lines", 80, 1, 1000)
            log_path = api.PID_DIR / f"{name}.log"
            self.send_json(api.load_log_tail(log_path, lines))
        elif path == "/api/opportunities":
            strategy = params.get("strategy", ["composite"])[0]
            if strategy not in screener.STRATEGY_META:
                self.send_json({"error": "알 수 없는 전략"}, 400)
                return
            opps = screener.get_opportunities_cached(strategy)
            self.send_json(
                {
                    "strategy": strategy,
                    "meta": screener.STRATEGY_META[strategy],
                    "opportunities": opps,
                    "total_count": len(opps),
                }
            )
        elif path == "/api/solar":
            limit = self._parse_int_param(params, "limit", 100, 1, 1000)
            listings = api.load_solar_listings(limit)
            self.send_json({"listings": listings, "count": len(listings)})
        elif path == "/api/strategies":
            self.send_json({"strategies": list(screener.STRATEGY_META.values())})
        elif path == "/api/investment-assets":
            self.send_json(api.load_investment_assets())
        elif path == "/api/advisor-strategies":
            limit = self._parse_int_param(params, "limit", 20, 1, 100)
            self.send_json(api_advisor.load_advisor_strategies(limit))
        elif path == "/api/regime-history":
            days = self._parse_int_param(params, "days", 90, 1, 365)
            self.send_json(api_history.load_regime_history(days))
        elif path == "/api/sector-scores-history":
            days = self._parse_int_param(params, "days", 90, 1, 365)
            self.send_json(api_history.load_sector_scores_history(days))
        elif path == "/api/correction-notes-history":
            limit = self._parse_int_param(params, "limit", 30, 1, 200)
            self.send_json(api_history.load_correction_notes_history(limit))
        elif path == "/api/performance-report-history":
            days = self._parse_int_param(params, "days", 90, 1, 365)
            self.send_json(api_history.load_performance_report_history(days))
        elif path == "/api/company":
            ticker = params.get("ticker", [""])[0]
            self.send_json(api_company.load_company_profile(ticker))
        elif path == "/api/health":
            self.send_json(api.load_health_status())
        elif path == "/api/price-history":
            ticker = params.get("ticker", [""])[0]
            days = self._parse_int_param(params, "days", 30, 5, 180)
            self.send_json(api.load_price_history(ticker, days))
        elif path == "/api/macro-history":
            series_id = params.get("series_id", [""])[0]
            days = self._parse_int_param(params, "days", 30, 5, 365)
            self.send_json(api.load_macro_history(series_id, days))
        else:
            self._serve_static(path)

    def do_POST(self):
        """POST 요청 라우팅."""
        if not self._check_auth():
            self.send_json({"error": "인증 실패"}, 401)
            return
        path = urlparse(self.path).path

        if path == "/api/run-pipeline":
            result = api.run_background(
                "pipeline",
                ["python3", str(PROJECT_ROOT / "run_pipeline.py")],
            )
            self.send_json(result)

        elif path == "/api/run-marcus":
            result = api.run_background(
                "marcus",
                ["python3", str(PROJECT_ROOT / "scripts" / "run_marcus.py")],
            )
            self.send_json(result)

        elif path == "/api/refresh-prices":
            result = api.run_background(
                "refresh_prices",
                [
                    "python3",
                    str(PROJECT_ROOT / "scripts" / "refresh_prices.py"),
                ],
            )
            self.send_json(result)

        elif path == "/api/health/run":
            # health_check.py 동기 실행 — 완료 후 최신 결과 반환
            result = api.run_health_check_sync()
            self.send_json(result)

        elif path == "/api/wealth/assets":
            body = self._read_json_body()
            try:
                asset_id = ssot.create_extra_asset(
                    name=body["name"],
                    asset_type=body["asset_type"],
                    current_value_krw=float(body["current_value_krw"]),
                    monthly_deposit_krw=float(body.get("monthly_deposit_krw", 0)),
                    is_fixed=bool(body.get("is_fixed", False)),
                    maturity_date=body.get("maturity_date"),
                    note=body.get("note"),
                )
                self.send_json({"ok": True, "id": asset_id}, 201)
            except (KeyError, ValueError) as e:
                self.send_json({"error": str(e)}, 400)

        elif path == "/api/investment-advice":
            body = self._read_json_body()
            result = investment_advisor.get_investment_advice(body)
            self.send_json(result)

        elif path == "/api/investment-advice-stream":
            body = self._read_json_body()
            self.close_connection = True  # 스트리밍 완료 후 반드시 연결 종료 (keep-alive 금지)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
            self.end_headers()
            try:
                for event in investment_advisor.stream_investment_advice(body):
                    payload = json.dumps(event, ensure_ascii=False)
                    self.wfile.write(f"data: {payload}\n\n".encode())
                    self.wfile.flush()
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

        elif path == "/api/advisor-strategies":
            body = self._read_json_body()
            try:
                loans = body.get("loans", [])
                if not isinstance(loans, list):
                    loans = []
                strategy_id = api_advisor.save_advisor_strategy(
                    capital=int(body["capital"]),
                    leverage_amt=int(body.get("leverage_amt", 0)),
                    risk_level=int(body.get("risk_level", 3)),
                    recommendation=body["recommendation"],
                    loans=loans,
                    monthly_savings=int(body.get("monthly_savings", 0)),
                )
                self.send_json({"ok": True, "id": strategy_id}, 201)
            except (KeyError, ValueError) as e:
                self.send_json({"error": str(e)}, 400)

        else:
            self.send_response(404)
            self.end_headers()

    def _read_json_body(self) -> dict:
        """요청 바디를 JSON으로 파싱 (최대 10MB)."""
        length = int(self.headers.get("Content-Length", 0))
        if length > 10 * 1024 * 1024:
            raise ValueError("요청 바디가 너무 큽니다 (최대 10MB)")
        return json.loads(self.rfile.read(length)) if length else {}

    def do_PUT(self):
        """PUT 요청 라우팅 (자산 수정)."""
        if not self._check_auth():
            self.send_json({"error": "인증 실패"}, 401)
            return
        path = urlparse(self.path).path
        if path.startswith("/api/wealth/assets/"):
            try:
                asset_id = int(path.rsplit("/", 1)[-1])
                body = self._read_json_body()
                ok = ssot.update_extra_asset_by_id(
                    asset_id=asset_id,
                    name=body["name"],
                    asset_type=body["asset_type"],
                    current_value_krw=float(body["current_value_krw"]),
                    monthly_deposit_krw=float(body.get("monthly_deposit_krw", 0)),
                    is_fixed=bool(body.get("is_fixed", False)),
                    maturity_date=body.get("maturity_date"),
                    note=body.get("note"),
                )
                self.send_json({"ok": ok}, 200 if ok else 404)
            except (KeyError, ValueError) as e:
                self.send_json({"error": str(e)}, 400)
        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self):
        """DELETE 요청 라우팅."""
        if not self._check_auth():
            self.send_json({"error": "인증 실패"}, 401)
            return
        path = urlparse(self.path).path
        if path.startswith("/api/wealth/assets/"):
            try:
                asset_id = int(path.rsplit("/", 1)[-1])
                ok = ssot.delete_extra_asset_by_id(asset_id)
                self.send_json({"ok": ok}, 200 if ok else 404)
            except ValueError:
                self.send_json({"error": "잘못된 id"}, 400)
        elif path.startswith("/api/advisor-strategies/"):
            try:
                strategy_id = int(path.rsplit("/", 1)[-1])
                ok = api_advisor.delete_advisor_strategy(strategy_id)
                self.send_json({"ok": ok}, 200 if ok else 404)
            except ValueError:
                self.send_json({"error": "잘못된 id"}, 400)
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_sse(self):
        """SSE 스트림 처리 - 클라이언트 연결 유지."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.end_headers()

        client_queue: queue.Queue = queue.Queue(maxsize=100)
        with _sse_lock:
            _sse_clients.append(client_queue)
        try:
            self.wfile.write(b"data: connected\n\n")
            self.wfile.flush()
            last_ping = time.time()
            while True:
                try:
                    event = client_queue.get(timeout=1.0)
                    self.wfile.write(f"data: {event}\n\n".encode())
                    self.wfile.flush()
                except queue.Empty:
                    now = time.time()
                    if now - last_ping >= 30:
                        self.wfile.write(b"data: ping\n\n")
                        self.wfile.flush()
                        last_ping = now
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with _sse_lock, contextlib.suppress(ValueError):
                _sse_clients.remove(client_queue)


def _broadcast_sse(event: str):
    """모든 SSE 클라이언트에 이벤트 브로드캐스트."""
    with _sse_lock:
        dead_clients = []
        for client_queue in _sse_clients:
            try:
                client_queue.put_nowait(event)
            except queue.Full:
                dead_clients.append(client_queue)
        for dead in dead_clients:
            _sse_clients.remove(dead)


def _watch_intel_dir():
    """output/intel/ 디렉토리 변경 감지 (5초 폴링)."""
    last_mtime = 0.0
    while True:
        try:
            if api.INTEL_DIR.exists():
                mtimes = [f.stat().st_mtime for f in api.INTEL_DIR.iterdir() if f.is_file()]
                if mtimes:
                    current_mtime = max(mtimes)
                    if current_mtime > last_mtime:
                        if last_mtime > 0:
                            _broadcast_sse("update")
                        last_mtime = current_mtime
        except Exception as e:
            print(f"[watcher] 오류: {e}")
        time.sleep(5)


def main():
    """서버 시작."""
    watcher = threading.Thread(target=_watch_intel_dir, daemon=True, name="intel-watcher")
    watcher.start()
    print("[watcher] output/intel/ 감시 시작 (5초 간격)")

    server = ThreadingHTTPServer(("", PORT), MissionControlHandler)
    print(f"[server] 미션컨트롤 대시보드: http://localhost:{PORT}")
    print("[server] 종료: Ctrl+C")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] 서버 종료")
        server.server_close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
미션컨트롤 HTTP 서버 (포트 8421)
ThreadingHTTPServer + SSE 실시간 업데이트
"""

import contextlib
import json
import queue
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from urllib.parse import parse_qs, urlparse

# 프로젝트 루트를 모듈 경로에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from web.api import (
    INTEL_DIR,
    get_process_status,
    load_intel_data,
    load_md_file,
    run_background,
)

PORT = 8421
WEB_DIR = Path(__file__).parent

# SSE 클라이언트 큐 관리
_sse_clients: list[queue.Queue] = []
_sse_lock = threading.Lock()


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """다중 연결을 지원하는 ThreadingHTTPServer."""

    daemon_threads = True


class MissionControlHandler(BaseHTTPRequestHandler):
    """미션컨트롤 요청 핸들러."""

    def log_message(self, format, *args):
        """기본 로그는 억제 (오류만 출력)."""
        pass

    def log_error(self, format, *args):
        print(f"[server] 오류: {format % args}")

    def send_json(self, data: dict, status: int = 200):
        """JSON 응답 전송."""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, filepath: Path, content_type: str):
        """파일 내용 전송."""
        try:
            content = filepath.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        """CORS preflight 처리."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _handle_api_data(self):
        """인텔 데이터 JSON 응답"""
        data = load_intel_data()
        self.send_json(data)

    def _handle_api_file(self, params: dict):
        """파일 다운로드 요청 처리 (MD/JSON)"""
        name = params.get("name", [""])[0]
        if not name or "/" in name or "\\" in name:
            self.send_json({"error": "잘못된 파일명"}, 400)
            return
        if name.endswith(".md"):
            content = load_md_file(name)
            body = content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/markdown; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif name.endswith(".json"):
            self.send_file(INTEL_DIR / name, "application/json; charset=utf-8")
        else:
            self.send_json({"error": "지원하지 않는 파일 형식"}, 400)

    def do_GET(self):
        """GET 요청 라우팅."""
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/":
            self.send_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
        elif path == "/static/app.js":
            self.send_file(WEB_DIR / "static" / "app.js", "application/javascript; charset=utf-8")
        elif path == "/static/style.css":
            self.send_file(WEB_DIR / "static" / "style.css", "text/css; charset=utf-8")
        elif path == "/api/data":
            self._handle_api_data()
        elif path == "/api/file":
            self._handle_api_file(params)
        elif path == "/api/status":
            self.send_json(get_process_status())
        elif path == "/api/events":
            self._handle_sse()
        elif path == "/api/analysis-history":
            date = params.get("date", [None])[0]
            if date:
                result = load_analysis_detail(date)
                self.send_json(result if result else {})
            else:
                self.send_json(load_analysis_history())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        """POST 요청 라우팅."""
        path = urlparse(self.path).path

        if path == "/api/run-pipeline":
            result = run_background(
                "pipeline",
                ["python3", str(PROJECT_ROOT / "run_pipeline.py")],
            )
            self.send_json(result)

        elif path == "/api/run-marcus":
            result = run_background(
                "marcus",
                ["python3", str(PROJECT_ROOT / "scripts" / "run_marcus.py")],
            )
            self.send_json(result)

        else:
            self.send_response(404)
            self.end_headers()

    def _handle_sse(self):
        """SSE 스트림 처리 - 클라이언트 연결 유지."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        # 클라이언트 큐 등록
        client_queue: queue.Queue = queue.Queue()
        with _sse_lock:
            _sse_clients.append(client_queue)

        try:
            # 초기 연결 확인 메시지
            self.wfile.write(b"data: connected\n\n")
            self.wfile.flush()

            last_ping = time.time()
            while True:
                try:
                    # 큐에서 이벤트 대기 (1초 타임아웃)
                    event = client_queue.get(timeout=1.0)
                    msg = f"data: {event}\n\n".encode()
                    self.wfile.write(msg)
                    self.wfile.flush()
                except queue.Empty:
                    # 30초마다 ping 전송
                    now = time.time()
                    if now - last_ping >= 30:
                        self.wfile.write(b"data: ping\n\n")
                        self.wfile.flush()
                        last_ping = now
        except (BrokenPipeError, ConnectionResetError):
            # 클라이언트 연결 끊김
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
            if INTEL_DIR.exists():
                # 디렉토리 내 모든 파일의 최신 mtime 계산
                mtimes = [f.stat().st_mtime for f in INTEL_DIR.iterdir() if f.is_file()]
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
    # 파일 감시 데몬 스레드 시작
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

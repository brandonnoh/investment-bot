# 인증/인가 보안 감사 보고서

**감사 대상:** `/Users/jarvis/Projects/investment-bot`
**감사 범위:** `web/server.py`, `web/api.py`, `web/api_company.py`, `web/api_advisor.py`, `web-next/src/app/api/[...path]/route.ts`, `web-next/src/hooks/useSSE.ts`, `web-next/src/lib/api.ts`
**감사 기준:** OWASP Top 10 (A01 Broken Access Control, A07 Identification and Authentication Failures)
**감사일:** 2026-05-02

---

## 요약

| 심각도 | 건수 |
|--------|------|
| CRITICAL | 2 |
| HIGH | 4 |
| MEDIUM | 3 |
| LOW | 3 |
| **합계** | **12** |

---

## 발견 사항

---

### SEC-A-001: 전체 API 인증 완전 부재

- **파일:라인** — `web/server.py:167–243` (do_GET), `web/server.py:245–338` (do_POST), `web/server.py:347–390` (do_PUT, do_DELETE)
- **심각도:** CRITICAL
- **OWASP:** A01 Broken Access Control, A07 Identification and Authentication Failures
- **증거:**
  ```python
  # server.py:167
  def do_GET(self):
      """GET 요청 라우팅."""
      parsed = urlparse(self.path)
      path = parsed.path
      params = parse_qs(parsed.query)
      if path == "/api/data":
          self._handle_api_data()
      # ... 어떤 요청자 검증도 없음
  ```
  모든 핸들러(`do_GET`, `do_POST`, `do_PUT`, `do_DELETE`)에서 요청자 신원 확인 로직이 단 한 줄도 없다. 토큰, API Key, 세션, IP 화이트리스트 중 어느 것도 적용되지 않았다.
- **영향:** Flask API(포트 8421)에 네트워크 접근 가능한 모든 주체(내부 네트워크, VPN 연결자, 동일 Docker 네트워크의 다른 컨테이너)가 아무런 검증 없이 모든 엔드포인트를 호출할 수 있다.

---

### SEC-A-002: `/api/run-pipeline`, `/api/run-marcus`, `/api/refresh-prices` — 임의 파이프라인 실행 노출

- **파일:라인** — `web/server.py:249–272`, `web/api.py:134–163`
- **심각도:** CRITICAL
- **OWASP:** A01 Broken Access Control
- **증거:**
  ```python
  # server.py:249
  if path == "/api/run-pipeline":
      result = api.run_background(
          "pipeline",
          ["python3", str(PROJECT_ROOT / "run_pipeline.py")],
      )
  # api.py:149
  proc = subprocess.Popen(
      cmd,
      cwd=str(PROJECT_ROOT),
      stdout=log_f,
      stderr=log_f,
      start_new_session=True,
  )
  ```
  인증 없이 HTTP POST 한 번으로 호스트에서 `python3 run_pipeline.py` 프로세스가 생성된다. cmd 리스트는 하드코딩되어 있어 명령 주입은 불가능하나, 인증 없는 `subprocess.Popen` 트리거 자체가 문제다.
- **완화 요소:** 중복 실행 방지 로직(`get_running_pid`)은 있다. 명령 자체는 고정값이다.
- **영향:** 네트워크 접근 가능한 누구든 파이프라인을 무한 반복 실행하여 CPU/메모리 자원을 소진하거나, 외부 API(Yahoo Finance, DART, Brave)에 과도한 요청을 유발할 수 있다. 중복 실행 방지가 있더라도 이전 프로세스 종료 직후 즉시 재실행 요청이 가능하다.

---

### SEC-A-003: CORS `Access-Control-Allow-Origin: *` — 기본값이 와일드카드

- **파일:라인** — `web/server.py:37`, `web/server.py:88`, `web/server.py:111`, `web-next/src/app/api/[...path]/route.ts:12`
- **심각도:** HIGH
- **OWASP:** A01 Broken Access Control
- **증거:**
  ```python
  # server.py:37
  ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")
  # server.py:88
  self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
  ```
  ```typescript
  // route.ts:12
  const SSE_HEADERS = {
    'Access-Control-Allow-Origin': '*',   // 하드코딩, 환경변수조차 없음
    ...
  }
  ```
  Flask 쪽은 환경변수 `ALLOWED_ORIGIN`이 설정되지 않을 경우 `*`로 폴백한다. `docker-compose.yml`에서 해당 환경변수가 설정된 흔적이 없으므로 프로덕션에서도 `*`가 적용 중이다. Next.js proxy의 SSE 응답 헤더는 환경변수도 없이 `*`로 하드코딩되어 있다.
- **영향:** 인증이 없으므로 현재는 CORS 와일드카드의 직접 피해가 제한적이나, 인증 레이어(쿠키 기반)가 추가될 경우 즉시 CSRF/credential 누출 경로가 된다. 또한 악의적인 웹 페이지가 사용자 브라우저를 통해 내부 API를 간접 호출하는 경로가 열려 있다.

---

### SEC-A-004: `/api/logs` — 로그 파일 내용 무인증 노출

- **파일:라인** — `web/server.py:192–199`, `web/api.py:166–175`
- **심각도:** HIGH
- **OWASP:** A01 Broken Access Control
- **증거:**
  ```python
  # server.py:192
  elif path == "/api/logs":
      name = params.get("name", ["marcus"])[0]
      if name not in _ALLOWED_LOG_NAMES:
          self.send_json({"error": "허용되지 않은 로그 이름"}, 400)
          return
      lines = self._parse_int_param(params, "lines", 80, 1, 1000)
      log_path = api.PID_DIR / f"{name}.log"
      self.send_json(api.load_log_tail(log_path, lines))
  ```
  로그 이름 화이트리스트(`marcus`, `pipeline`, `jarvis`, `alerts_watch`, `refresh_prices`)가 구현되어 path traversal은 방지된다. 그러나 인증이 없으므로 이 로그 파일들의 내용을 누구나 읽을 수 있다. 파이프라인 로그(`pipeline.log`)에는 API 키, 에러 메시지에 포함된 URL, 재무 데이터 처리 결과 등 민감 정보가 포함될 수 있다.
- **완화 요소:** 파일명 화이트리스트로 path traversal은 차단됨.
- **영향:** 로그에 포함된 환경변수 값, API 응답 내용, 내부 경로 정보가 외부에 노출될 수 있다.

---

### SEC-A-005: SSE 스트림 `/api/events` — 무인증 실시간 데이터 노출 + 무제한 연결

- **파일:라인** — `web/server.py:392–431`, `web-next/src/hooks/useSSE.ts:14`
- **심각도:** HIGH
- **OWASP:** A01 Broken Access Control
- **증거:**
  ```python
  # server.py:392
  def _handle_sse(self):
      self.send_response(200)
      self.send_header("Content-Type", "text/event-stream")
      # ...인증 검증 없음
      client_queue: queue.Queue = queue.Queue(maxsize=100)
      with _sse_lock:
          _sse_clients.append(client_queue)  # 연결 수 제한 없음
  ```
  ```typescript
  // useSSE.ts:14
  const es = new EventSource(`${BASE}/api/events`)
  // Authorization 헤더 없음 (EventSource API 특성상 헤더 추가 불가)
  ```
  SSE 연결 수에 대한 상한이 없다(`_sse_clients` 리스트 무제한 성장). 인증 없이 누구든 연결하면 `intel-data` 갱신 이벤트를 실시간으로 수신한다.
- **영향:** 1) 누구나 데이터 갱신 타이밍을 실시간 모니터링 가능. 2) 다수의 클라이언트가 SSE에 연결하면 스레드 풀과 메모리가 고갈되어 DoS가 발생할 수 있다(`ThreadingMixIn`은 요청당 스레드를 생성하며 연결이 유지되는 동안 스레드가 살아있다).

---

### SEC-A-006: Next.js 프록시 — 모든 경로/메서드 무조건 통과

- **파일:라인** — `web-next/src/app/api/[...path]/route.ts:14–70`
- **심각도:** HIGH
- **OWASP:** A01 Broken Access Control
- **증거:**
  ```typescript
  // route.ts:14
  async function proxy(req: NextRequest, path: string[]) {
    const pathStr = path.join('/')
    const url = `${API_BASE}/api/${pathStr}${req.nextUrl.search}`
    // ...추가 검증 없이 fetch(url, { method: req.method, body: bodyText })
  }
  export async function GET(req, { params }) { return proxy(req, path) }
  export async function POST(req, { params }) { return proxy(req, path) }
  export async function PUT(req, { params }) { return proxy(req, path) }
  export async function DELETE(req, { params }) { return proxy(req, path) }
  ```
  Next.js 프록시는 경로, 메서드, 파라미터에 대해 어떤 허용 목록 검증도 없이 Flask로 그대로 전달한다. PUT/DELETE 포함 모든 HTTP 메서드가 프록시된다.
- **영향:** Next.js를 통해 Flask의 모든 엔드포인트에 접근 가능하다. 또한 `path.join('/')` 결과가 `../secret` 형태가 될 경우 `fetch`가 URL을 정규화하면서 `/api/` 프리픽스를 우회할 수 있다 (예: `GET /api/../health` → fetch가 `http://flask/health`로 요청). Flask 라우터에 `/health` 같은 별도 핸들러가 없으므로 현재는 영향이 제한적이나, 잠재적 우회 경로다.

---

### SEC-A-007: PUT/DELETE 자산 수정·삭제 — 인증 없이 재무 데이터 변조 가능

- **파일:라인** — `web/server.py:347–390`
- **심각도:** HIGH
- **OWASP:** A01 Broken Access Control
- **증거:**
  ```python
  # server.py:371
  def do_DELETE(self):
      path = urlparse(self.path).path
      if path.startswith("/api/wealth/assets/"):
          try:
              asset_id = int(path.rsplit("/", 1)[-1])
              ok = ssot.delete_extra_asset_by_id(asset_id)
              self.send_json({"ok": ok}, 200 if ok else 404)
  ```
  인증 없이 자산 ID 정수 값만 알면 `DELETE /api/wealth/assets/{id}` 호출로 비금융 자산 레코드를 영구 삭제할 수 있다. `PUT /api/wealth/assets/{id}`로 자산 가치 임의 변조도 가능하다. 같은 방식으로 `DELETE /api/advisor-strategies/{id}`도 노출된다.
- **영향:** 재무 기록(`extra_assets` 테이블)의 무단 삭제 및 변조. ID는 자동증가 정수로 순열 추정이 쉽다.

---

### SEC-A-008: `/api/file` — INTEL_DIR 내 비허가 JSON 파일 접근

- **파일:라인** — `web/server.py:121–138`
- **심각도:** MEDIUM
- **OWASP:** A01 Broken Access Control
- **증거:**
  ```python
  # server.py:135
  elif name.endswith(".json"):
      self.send_file(api.INTEL_DIR / name, "application/json; charset=utf-8")
  ```
  `name`이 `INTEL_FILES` 목록에 있는지 검증하지 않는다. `/` 및 `\` 포함 여부만 확인한다. `output/intel/` 디렉토리에는 `discovery_keywords.json`, `search_keywords.json`, `universe_cache.json` 등 `INTEL_FILES` 목록에 없는 파일들도 존재한다. 이 파일들의 이름만 알면 API를 통해 읽을 수 있다.
- **영향:** 의도적으로 공개하지 않은 내부 분석 데이터(검색 키워드, 유니버스 캐시 등) 노출. 파일이 추가되는 시점에 접근 범위가 자동으로 확대된다.

---

### SEC-A-009: `send_file` / SSE / 스트리밍 응답 — 보안 헤더 누락

- **파일:라인** — `web/server.py:94–106` (send_file), `web/server.py:392–431` (_handle_sse), `web/server.py:299–316` (investment-advice-stream)
- **심각도:** MEDIUM
- **OWASP:** A05 Security Misconfiguration
- **증거:**
  ```python
  # server.py:94 — send_file: X-Frame-Options, X-Content-Type-Options 없음
  def send_file(self, filepath: Path, content_type: str):
      content = filepath.read_bytes()
      self.send_response(200)
      self.send_header("Content-Type", content_type)
      self.send_header("Content-Length", str(len(content)))
      self.send_header("Cache-Control", "no-store")
      self.end_headers()  # 보안 헤더 없음
  ```
  `send_json`에만 `X-Content-Type-Options: nosniff`와 `X-Frame-Options: DENY`가 설정된다. `send_file`이 사용되는 정적 파일, 마크다운 응답, SSE 스트림, AI 어드바이저 스트리밍 응답에는 이 헤더들이 없다. `Content-Security-Policy`는 어디에도 없다.
- **영향:** MIME 스니핑 공격, 클릭재킹 공격에 대한 부분적 노출. CSP 부재로 XSS 발생 시 영향 범위 제한 불가.

---

### SEC-A-010: `_read_json_body` — Content-Length 신뢰 기반 읽기

- **파일:라인** — `web/server.py:340–345`
- **심각도:** MEDIUM
- **OWASP:** A03 Injection
- **증거:**
  ```python
  # server.py:340
  def _read_json_body(self) -> dict:
      length = int(self.headers.get("Content-Length", 0))
      if length > 10 * 1024 * 1024:
          raise ValueError("요청 바디가 너무 큽니다 (최대 10MB)")
      return json.loads(self.rfile.read(length)) if length else {}
  ```
  10MB 상한 체크는 있으나 `Content-Length: 0`을 보내고 실제 바디를 포함시키는 HTTP 요청 스머글링(smuggling) 시나리오에서 바디가 무시된다. 또한 `Content-Length`를 실제 바디보다 크게 지정하면 `rfile.read(length)` 호출이 블로킹되어 스레드가 묶인다(Slowloris 변형).
- **영향:** 대량의 동시 요청으로 스레드 풀 소진 가능. 단일 요청으로 스레드를 장기 점유 가능.

---

### SEC-A-011: `/api/company` — ticker 파라미터 길이 제한 없음

- **파일:라인** — `web/server.py:237–239`, `web/api_company.py:74–87`
- **심각도:** LOW
- **OWASP:** A03 Injection
- **증거:**
  ```python
  # server.py:237
  ticker = params.get("ticker", [""])[0]
  self.send_json(api_company.load_company_profile(ticker))
  # api_company.py:77
  code = ticker.split(".")[0]
  pat = f"%{code}%"
  rows = conn.execute(
      "...WHERE title LIKE ? OR summary LIKE ?", (pat, pat)
  )
  ```
  ticker에 길이 제한이 없다. LIKE 패턴에 사용되므로 매우 긴 ticker 값이 들어오면 SQLite LIKE 연산의 CPU 비용이 증가한다. SQL 인젝션은 파라미터화된 쿼리로 방지되어 있다.
- **영향:** 매우 긴 ticker로 LIKE 쿼리 부하를 유발할 수 있으나, SQLite 특성상 실질적 피해는 제한적.

---

### SEC-A-012: Flask 서버 바인딩 주소 — 모든 인터페이스 노출

- **파일:라인** — `web/server.py:473`, `docker-compose.yml:8`
- **심각도:** LOW
- **OWASP:** A05 Security Misconfiguration
- **증거:**
  ```python
  # server.py:473
  server = ThreadingHTTPServer(("", PORT), MissionControlHandler)
  ```
  ```yaml
  # docker-compose.yml:8
  ports:
    - "8421:8421"
  ```
  Flask 서버가 `""` (모든 인터페이스)에 바인딩되고, docker-compose가 호스트의 모든 인터페이스에 8421 포트를 바인딩한다. Tailscale VPN을 통해 접근하는 설계이나, 호스트의 LAN 인터페이스에도 동일하게 노출된다. `127.0.0.1:8421`로 바인딩하거나 docker-compose에서 `127.0.0.1:8421:8421`로 제한했다면 Docker 네트워크 내부에서만 접근 가능했을 것이다.
- **완화 요소:** 프로젝트 문서에 "Tailscale VPN 전용"으로 명시됨. 실제 위협 면적은 네트워크 환경에 의존.
- **영향:** 같은 LAN의 다른 호스트에서 8421 포트에 직접 접근 가능. Next.js(:3000)을 거치지 않고 Flask API를 직접 호출할 수 있다.

---

## 위험 매트릭스 요약

| ID | 엔드포인트 | 현재 통제 | 주요 위험 | 심각도 |
|----|-----------|----------|----------|--------|
| SEC-A-001 | 전체 | 없음 | 무인증 전체 노출 | CRITICAL |
| SEC-A-002 | `/api/run-pipeline` 등 | 중복 실행 방지 | 무인증 프로세스 실행 | CRITICAL |
| SEC-A-003 | 전체 | ALLOWED_ORIGIN env (미설정) | CORS 와일드카드 | HIGH |
| SEC-A-004 | `/api/logs` | 파일명 화이트리스트 | 로그 내용 노출 | HIGH |
| SEC-A-005 | `/api/events` | 없음 | 무인증 SSE + 무제한 연결 | HIGH |
| SEC-A-006 | 전체 (Next.js 프록시) | 없음 | 무검증 프록시 통과 | HIGH |
| SEC-A-007 | PUT/DELETE `/api/wealth/assets` 등 | 없음 | 무인증 데이터 변조/삭제 | HIGH |
| SEC-A-008 | `/api/file` | 확장자 체크, `/` 차단 | 비허가 JSON 접근 | MEDIUM |
| SEC-A-009 | send_file, SSE, 스트리밍 | 없음 | 보안 헤더 누락 | MEDIUM |
| SEC-A-010 | POST 전체 | 10MB 상한 | Slowloris 변형 DoS | MEDIUM |
| SEC-A-011 | `/api/company` | 파라미터화 쿼리 | LIKE 부하 | LOW |
| SEC-A-012 | 서버 바인딩 | VPN 네트워크 분리 | LAN 직접 노출 | LOW |

---

## 완화 우선순위 권고 (수정 금지 — 참고용)

1. **즉시 (CRITICAL):** API Key 또는 공유 시크릿 헤더(`X-API-Key`) 기반 미들웨어를 `do_GET`/`do_POST`/`do_PUT`/`do_DELETE` 진입부에 단일 지점으로 추가. 특히 `/api/run-pipeline`, `/api/run-marcus` 등 실행 트리거 엔드포인트 우선.
2. **단기 (HIGH):** `ALLOWED_ORIGIN` 환경변수를 docker-compose에서 명시적으로 `http://100.90.201.87:3000`으로 설정. Next.js proxy의 SSE 헤더도 동일하게 제한.
3. **단기 (HIGH):** SSE 연결 수 상한 설정 (예: 동시 연결 10개 초과 시 503 반환).
4. **중기 (MEDIUM):** `send_file` 및 스트리밍 응답에도 `X-Content-Type-Options`, `X-Frame-Options` 추가. `/api/file` 엔드포인트에 `INTEL_FILES` 화이트리스트 적용.
5. **장기 (LOW):** Flask 서버를 `127.0.0.1`에만 바인딩하고 docker-compose에서 `127.0.0.1:8421:8421`로 변경.

---

*이 보고서는 코드 수정 없이 정적 분석만으로 작성되었습니다. 실제 익스플로잇 가능성은 네트워크 환경(Tailscale VPN 격리 수준)에 따라 달라질 수 있습니다.*

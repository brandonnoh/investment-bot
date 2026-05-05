# API 보안 감사 보고서

**감사 대상:** `/Users/jarvis/Projects/investment-bot`
**감사 일자:** 2026-05-02
**감사 범위:** `web/server.py`, `web/api.py`, `web/api_company.py`, `web/api_history.py`, `web/api_advisor.py`, `web-next/src/app/api/[...path]/route.ts`
**기준:** OWASP A04 (Insecure Design), A05 (Security Misconfiguration)

---

## 요약

| 심각도 | 건수 |
|--------|------|
| HIGH   | 3    |
| MEDIUM | 5    |
| LOW    | 4    |
| INFO   | 2    |
| **합계** | **14** |

---

## 취약점 목록

---

### SEC-P-01: `web/server.py:37` — CORS 와일드카드 기본값
**심각도:** HIGH
**OWASP:** A05 (Security Misconfiguration)
**증거:**
```python
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")
# 환경변수 미설정 시 모든 출처 허용
self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
```
**영향:** `ALLOWED_ORIGIN` 환경변수가 설정되지 않으면 `Access-Control-Allow-Origin: *`가 전송된다. 모든 외부 도메인이 브라우저를 통해 API에 CORS 요청을 보낼 수 있다. 내부 투자 포트폴리오 데이터(`/api/data`), 전재산 데이터(`/api/wealth`), 기업 분석 데이터가 악성 사이트 방문만으로 탈취 가능하다.

---

### SEC-P-02: `web/server.py:249-271` — 파이프라인/Marcus 실행 API에 Rate Limit 없음
**심각도:** HIGH
**OWASP:** A04 (Insecure Design)
**증거:**
```python
if path == "/api/run-pipeline":
    result = api.run_background(
        "pipeline",
        ["python3", str(PROJECT_ROOT / "run_pipeline.py")],
    )
    self.send_json(result)
```
**영향:** `run_background()`의 PID 파일 기반 중복 방지(`get_running_pid`)는 동시 실행을 막지만, 파이프라인이 완료된 직후 반복 호출을 막지 못한다. 인증 없이 누구나 반복 호출하여 CPU/IO/Yahoo Finance API를 고갈시킬 수 있다. `/api/health/run`(동기 실행, 30초 타임아웃)도 동일하다. 네트워크 접근 가능한 공격자가 DoS 달성 가능.

---

### SEC-P-03: `web/server.py:121-138` — `/api/file` 파일명 화이트리스트 미검사
**심각도:** HIGH
**OWASP:** A04 (Insecure Design)
**증거:**
```python
def _handle_api_file(self, params: dict):
    name = params.get("name", [""])[0]
    if not name or "/" in name or "\\" in name:  # 슬래시만 검사
        self.send_json({"error": "잘못된 파일명"}, 400)
        return
    if name.endswith(".md"):
        content = api.load_md_file(name)   # INTEL_DIR / name — 화이트리스트 없음
    elif name.endswith(".json"):
        self.send_file(api.INTEL_DIR / name, ...)   # 동일
```
**영향:** 슬래시(`/`, `\`) 차단만으로는 INTEL_DIR 내의 모든 `.md`/`.json` 파일이 접근 가능하다. `INTEL_FILES`/`MD_FILES`에 없는 파일(예: `discovery_keywords.json` 등 파이프라인 임시 산출물)이 노출된다. 향후 INTEL_DIR에 민감 파일이 추가될 경우 즉시 유출된다. 화이트리스트 검사가 없다.

---

### SEC-P-04: `web/server.py:340-345` — `_read_json_body()` Content-Type 미검증 + JSONDecodeError 미처리
**심각도:** MEDIUM
**OWASP:** A04 (Insecure Design)
**증거:**
```python
def _read_json_body(self) -> dict:
    """요청 바디를 JSON으로 파싱 (최대 10MB)."""
    length = int(self.headers.get("Content-Length", 0))
    if length > 10 * 1024 * 1024:
        raise ValueError("요청 바디가 너무 큽니다 (최대 10MB)")
    return json.loads(self.rfile.read(length)) if length else {}
    # Content-Type 검사 없음, JSONDecodeError를 잡지 않음
```
**영향:** 1) `Content-Type: text/plain`으로 전송된 바이너리/폼 데이터도 JSON 파싱을 시도한다. 2) `json.loads()`가 `json.JSONDecodeError`(ValueError 서브클래스)를 발생시킬 때, 호출 측(`do_POST`)이 이를 잡지 않으면 HTTP 500이 반환되고 스택 트레이스가 서버 로그에 기록된다. 특히 `/api/investment-advice`(라인 294-297)와 `/api/investment-advice-stream`(라인 299-316)은 `_read_json_body()`를 `try/except` 블록 밖에서 호출하므로 500 에러가 그대로 반환된다.

---

### SEC-P-05: `web/server.py:291-292, 333-334, 365-366` — `str(e)` 내부 에러 메시지 노출
**심각도:** MEDIUM
**OWASP:** A05 (Security Misconfiguration)
**증거:**
```python
except (KeyError, ValueError) as e:
    self.send_json({"error": str(e)}, 400)
```
**영향:** `KeyError`는 `"'capital'"` 형태로 필드명을 노출한다. `ValueError`는 `float()` 변환 실패 시 `"could not convert string to float: 'abc'"` 형태의 메시지를 반환한다. 이를 통해 공격자는 내부 파라미터 명세 및 타입 구조를 열거할 수 있다. `web/api.py:163`의 `run_background()` 실패 시에도 `str(e)`를 반환한다.

---

### SEC-P-06: `web/api_company.py:77-85` — ticker LIKE 와일드카드 인젝션 (성능 DoS)
**심각도:** MEDIUM
**OWASP:** A04 (Insecure Design)
**증거:**
```python
code = ticker.split(".")[0]
pat = f"%{code}%"
rows = conn.execute(
    "... WHERE title LIKE ? OR summary LIKE ?",
    (pat, pat),
).fetchall()
```
**영향:** ticker에 `%`나 `_`가 포함되면 LIKE 패턴이 비정상적으로 확장된다. 예: `ticker="%"` → `pat="%%%"` — 뉴스 테이블 전체 스캔. `ticker="__%"` → `pat="%__%"` — 매우 넓은 패턴. SQL 인젝션은 파라미터화 쿼리로 방지되나, 와일드카드가 포함된 LIKE는 인덱스를 무력화하여 테이블 풀 스캔을 유발할 수 있다. 뉴스 테이블이 크면 DB 과부하 가능.

---

### SEC-P-07: `web/server.py:37, web-next/src/app/api/[...path]/route.ts:12` — 인증 계층 전무
**심각도:** MEDIUM
**OWASP:** A05 (Security Misconfiguration)
**증거:**
```python
# server.py: 인증 헤더 검사 없음
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")
# 모든 API 엔드포인트가 인증 없이 접근 가능
```
```typescript
// route.ts: 요청자 인증 없이 모든 경로를 프록시
async function proxy(req: NextRequest, path: string[]) {
  const url = `${API_BASE}/api/${pathStr}${req.nextUrl.search}`
  // 인증 검사 없음
```
**영향:** Tailscale VPN 접근을 전제로 하지만, 서버 레이어에 인증이 없으므로 VPN 내부의 모든 기기가 무제한 API 호출 가능하다. VPN 키 유출 또는 내부자 위협 시 포트폴리오 조회/수정(`/api/wealth/assets` DELETE), 파이프라인 실행이 제어 불가능해진다. 특히 `POST /api/run-pipeline`은 시스템 프로세스를 실행한다.

---

### SEC-P-08: `web/server.py:94-106` — `send_file()` CORS 헤더 누락
**심각도:** MEDIUM
**OWASP:** A05 (Security Misconfiguration)
**증거:**
```python
def send_file(self, filepath: Path, content_type: str):
    try:
        content = filepath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        # Access-Control-Allow-Origin 헤더 없음
        # X-Content-Type-Options 헤더 없음
```
**영향:** `send_json()`에는 `Access-Control-Allow-Origin`과 `X-Content-Type-Options: nosniff`가 포함되지만 `send_file()`에는 없다. `/api/file?name=*.json` 경로(라인 136)와 정적 파일 서빙 경로(라인 151)에서 보안 헤더가 누락된다. 정책 불일치.

---

### SEC-P-09: `web/server.py:342` — Content-Length 없는 POST 요청 시 빈 dict 반환
**심각도:** LOW
**OWASP:** A04 (Insecure Design)
**증거:**
```python
length = int(self.headers.get("Content-Length", 0))
# ...
return json.loads(self.rfile.read(length)) if length else {}
```
**영향:** `Content-Length` 헤더가 없는 POST 요청은 빈 dict `{}`로 처리된다. `/api/wealth/assets`에서는 `body["name"]` KeyError로 400이 반환되어 영향이 제한적이나, `/api/investment-advice`에서는 빈 body를 기본값으로 처리하여 불필요한 Claude API 호출이 발생할 수 있다. chunked transfer encoding 요청도 동일하게 빈 dict가 된다.

---

### SEC-P-10: `web/api_advisor.py:18-36` — `recommendation` 필드 크기 검증 없음
**심각도:** LOW
**OWASP:** A04 (Insecure Design)
**증거:**
```python
def save_advisor_strategy(
    capital: int,
    leverage_amt: int,
    risk_level: int,
    recommendation: str,   # 크기 검증 없음
    ...
) -> int:
    ...
    cur = conn.execute(
        "INSERT INTO advisor_strategies ... VALUES (?, ?, ?, ?, ?, ?, ?)",
        (capital, leverage_amt, risk_level, recommendation, ...),
    )
```
**영향:** `recommendation` 필드는 Claude AI가 생성한 Markdown 텍스트를 저장한다. `_read_json_body()`의 10MB 바디 제한 내에서 수MB 크기의 문자열이 DB에 저장될 수 있다. SQLite는 TEXT 크기 제한이 없으므로, 악성 클라이언트가 대량 데이터를 DB에 주입하여 디스크를 고갈시킬 수 있다.

---

### SEC-P-11: `web/server.py:62` — SSE 클라이언트 수 제한 없음
**심각도:** LOW
**OWASP:** A04 (Insecure Design)
**증거:**
```python
_sse_clients: list[queue.Queue] = []
# ...
with _sse_lock:
    _sse_clients.append(client_queue)
# 연결 수 상한 없음
```
**영향:** 개별 큐는 `maxsize=100`으로 제한되지만 연결 자체의 수는 제한이 없다. 다수의 연결을 열어 각각 1개의 스레드(ThreadingMixIn)를 점유하면 스레드 풀 고갈이 가능하다. VPN 내부에서도 브라우저 탭 다수 열기로 발생할 수 있다.

---

### SEC-P-12: `web/api.py:250` — `load_wealth_data()` 에러 시 `str(e)` 노출
**심각도:** LOW
**OWASP:** A05 (Security Misconfiguration)
**증거:**
```python
except Exception as e:
    print(f"[api] wealth 데이터 로드 실패: {e}")
    return {"error": str(e)}   # 내부 예외 메시지를 HTTP 응답에 포함
```
**영향:** DB 연결 실패, 파일 경로 오류, Import 에러 등 내부 예외의 전체 메시지가 `/api/wealth` 응답 body에 포함된다. 시스템 경로, 모듈 구조 등이 노출될 수 있다.

---

### SEC-P-13 (INFO): `web-next/src/app/api/[...path]/route.ts:5` — `PYTHON_API_URL` 기본값이 `localhost`
**심각도:** INFO
**증거:**
```typescript
const API_BASE = process.env.PYTHON_API_URL ?? 'http://localhost:8421'
```
**영향:** 프로덕션에서 `PYTHON_API_URL`이 미설정된 경우 `localhost:8421`에 연결을 시도한다. 컨테이너 환경에서는 동작하지 않아 502 반환. 보안 취약점이 아닌 설정 위험. 환경변수 설정 여부 런타임 검증이 없다.

---

### SEC-P-14 (INFO): `web/server.py:167-243` — GET 엔드포인트에 POST 요청 시 동작
**심각도:** INFO
**증거:**
```python
def do_GET(self): ...
def do_POST(self): ...
# do_GET과 do_POST가 독립적으로 라우팅 — 메서드 혼용 체크 없음
```
**영향:** `POST /api/data`는 `do_POST`에서 `404`를 반환한다 (else 분기). `GET /api/run-pipeline`은 `do_GET`에서 정적 파일 서빙 폴백으로 넘어간다. 메서드 매칭 자체는 Python의 `do_GET/do_POST` 분리로 격리되어 있다. 405 Method Not Allowed가 아닌 404/정적 폴백이 반환되는 것은 의도와 다른 동작.

---

## 우선순위 수정 권고

| 순위 | ID | 조치 |
|------|----|------|
| 1 | SEC-P-01 | `ALLOWED_ORIGIN` 기본값을 `*`에서 실제 도메인으로 변경. 최소 환경변수 미설정 시 서버 시작 거부 |
| 2 | SEC-P-03 | `_handle_api_file()`에서 `name in (INTEL_FILES + MD_FILES)` 화이트리스트 검사 추가 |
| 3 | SEC-P-04 | `_read_json_body()`에서 `json.JSONDecodeError` 명시 처리 → 400 반환. `Content-Type: application/json` 검증 추가 |
| 4 | SEC-P-02 | `/api/run-pipeline`, `/api/run-marcus`, `/api/health/run`에 IP별 호출 간격 제한(예: 60초) 추가 |
| 5 | SEC-P-06 | `_load_recent_news()`에서 ticker 입력을 `[A-Z0-9.]{1,20}` 정규식으로 검증 후 LIKE 사용 |
| 6 | SEC-P-05 | 에러 응답에서 `str(e)` 대신 고정 메시지 반환. 상세 에러는 서버 로그에만 기록 |
| 7 | SEC-P-08 | `send_file()`에 `Access-Control-Allow-Origin`과 `X-Content-Type-Options` 헤더 추가 |
| 8 | SEC-P-10 | `recommendation` 저장 전 `len(recommendation) <= 100_000` 검증 추가 |

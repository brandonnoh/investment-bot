# Injection Vulnerability Audit Report
**감사 대상:** `/Users/jarvis/Projects/investment-bot`  
**감사 범위:** OWASP A03 — Injection (SQL, Command, SSRF, Path Traversal, Log, JSON)  
**감사 일자:** 2026-05-02  
**감사 에이전트:** agent-injection-hunter  

---

## 요약

| 심각도 | 건수 |
|--------|------|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 3 |
| LOW | 3 |
| INFO | 2 |
| **합계** | **10** |

---

## 취약점 목록

---

### SEC-I-001: `db/init_db.py:75` — PRAGMA f-string에 테이블명 직접 삽입
**심각도:** HIGH  
**OWASP:** A03:2021 – Injection (SQL Injection)  
**증거:**
```python
# db/init_db.py:75
cursor.execute(f"PRAGMA table_info({table_name})")
```
**배경:** `_get_column_names(cursor, table_name)` 함수가 `table_name`을 f-string으로 PRAGMA 쿼리에 직접 삽입한다. 이 함수는 `_migrate_add_column`을 통해 `MIGRATION_COLUMNS` 리스트의 값만 받으므로 현재는 모두 하드코딩된 문자열이다. 그러나 `_get_column_names`와 `_table_exists`는 `public` 함수이며, 미래에 외부 입력이 전달될 경우 SQL 인젝션이 발생한다.  
**영향:** SQLite 내부 스키마 정보 노출 또는 조작. `table_name`에 `); DROP TABLE prices; --` 같은 값이 들어올 경우 DDL 실행 가능. 현재 직접 익스플로잇 경로는 없으나 설계 결함.

---

### SEC-I-002: `db/init_db.py:93` — ALTER TABLE f-string에 컬럼명/타입 직접 삽입
**심각도:** HIGH  
**OWASP:** A03:2021 – Injection (SQL Injection)  
**증거:**
```python
# db/init_db.py:93
cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
```
**배경:** `_migrate_add_column` 함수가 `table_name`, `column_name`, `column_def` 세 변수를 모두 f-string으로 DDL에 직접 삽입한다. SQLite는 DDL에서 파라미터 바인딩(`?`)을 지원하지 않으므로 불가피한 측면이 있으나, 값 검증이 전혀 없다. 현재 `MIGRATION_COLUMNS` 상수 리스트에서만 호출되지만 함수 시그니처 자체가 위험하다.  
**영향:** `column_def`에 `TEXT); DROP TABLE holdings; --` 삽입 시 전체 자산 데이터 삭제 가능. 현재 익스플로잇 경로: `MIGRATION_COLUMNS` 리스트 오염 또는 향후 동적 호출.

---

### SEC-I-003: `web/api_company.py:77–86` — LIKE 쿼리에 사용자 입력 ticker의 와일드카드 미이스케이프
**심각도:** MEDIUM  
**OWASP:** A03:2021 – Injection (SQL Wildcard Injection)  
**증거:**
```python
# web/api_company.py:77-86
# GET /api/company?ticker=XXX 에서 ticker 직접 사용
code = ticker.split(".")[0]
pat = f"%{code}%"
rows = conn.execute(
    """...WHERE title LIKE ? OR summary LIKE ?...""",
    (pat, pat),
).fetchall()
```
**배경:** 파라미터 바인딩(`?`)을 사용하므로 SQL 인젝션은 방어되지만, SQLite LIKE 특수문자(`%`, `_`)가 `ticker`에 포함될 경우 이스케이프 처리가 없다. `ticker=%`이면 `pat="%%%"`이 되어 모든 뉴스 행을 매칭한다. `ESCAPE` 절이 없다.  
**영향:** `?ticker=%25` (URL 인코딩 `%`) 또는 `?ticker=_` 입력 시 news 테이블 전체를 LIKE 스캔하여 상위 5건이 반환된다. 의도하지 않은 정보 노출 및 불필요한 풀 테이블 스캔으로 DoS 유발 가능.

---

### SEC-I-004: `web/server.py:124` — `/api/file?name=` Path Traversal 불완전 방어
**심각도:** MEDIUM  
**OWASP:** A03:2021 – Injection (Path Traversal)  
**증거:**
```python
# web/server.py:124
if not name or "/" in name or "\\" in name:
    self.send_json({"error": "잘못된 파일명"}, 400)
    return
# ...
self.send_file(api.INTEL_DIR / name, "application/json; charset=utf-8")
```
**배경:** `/`와 `\`만 차단하며 `..`(점 두 개)에 대한 명시적 검사가 없다. `parse_qs`가 URL 인코딩을 자동 디코딩하므로 `%2F` → `/`는 차단된다. 그러나 `name=...json` (세 개 이상의 점)처럼 경계 케이스나 운영체제 특유의 경로 처리 변이는 열려 있다. 현재 Python `pathlib`의 동작상 `/`가 없으면 상위 디렉토리 탈출이 불가능하므로 실질적 익스플로잇은 어렵지만, 명시적 화이트리스트 또는 `resolve()` 기반 검증이 없다.  
**영향:** 방어 깊이 부족. 미래 경로 처리 변경 시 INTEL_DIR 외부 파일 읽기 가능성.

---

### SEC-I-005: `scripts/run_marcus.py:258–265` — Discord Webhook URL 검증 없음 (잠재적 SSRF)
**심각도:** MEDIUM  
**OWASP:** A10:2021 – Server-Side Request Forgery (SSRF)  
**증거:**
```python
# scripts/run_marcus.py:257-265
webhook = os.environ.get("DISCORD_WEBHOOK_URL", "")
payload = _json.dumps({"content": f"❌ 마커스 분석 실패: {error_msg}"}).encode("utf-8")
req = _urllib.Request(
    webhook,
    data=payload,
    headers={"Content-Type": "application/json", ...},
    method="POST",
)
_urllib.urlopen(req, timeout=15)
```
**배경:** `DISCORD_WEBHOOK_URL` 환경변수 값을 어떠한 검증 없이 `urlopen`에 직접 전달한다. URL이 `http://169.254.169.254/` (AWS IMDSv1), `http://localhost:8421/api/run-pipeline` 등 내부 주소로 설정되면 컨테이너 내부 서비스나 클라우드 메타데이터 엔드포인트에 요청이 전송된다. `.env` 파일이 외부에서 쓰기 가능하거나 환경변수 오염이 발생할 경우 실제 SSRF.  
**영향:** 내부 네트워크 탐색, 클라우드 메타데이터 탈취, 내부 API 호출. Docker 컨테이너 환경이므로 Tailscale VPN 내부 서비스에 대한 lateral movement 가능.

---

### SEC-I-006: `data/fetch_news.py:46` — 외부 키워드가 로그에 미이스케이프 출력 (Log Injection)
**심각도:** LOW  
**OWASP:** A03:2021 – Injection (Log Injection)  
**증거:**
```python
# data/fetch_news.py:46
print(f"  📌 동적 키워드 {len(keywords)}개 로드: {keywords[:3]}...")
```
**배경:** `search_keywords.json`에서 로드한 동적 키워드(Marcus가 Claude CLI를 통해 생성, 외부 뉴스 데이터 기반)가 검증·이스케이프 없이 로그에 출력된다. 동일 패턴이 `fetch_news.py:304, 306, 339, 341`에도 반복된다.  
**영향:** 공격자가 뉴스 피드를 통해 Claude 분석 결과에 ANSI 이스케이프 시퀀스(`\r`, `\n` 포함)를 주입하면 로그 파일을 오염시킬 수 있다. `/api/logs` 엔드포인트를 통해 오염된 로그가 프론트엔드에 전달되면 XSS 유발 가능.

---

### SEC-I-007: `scripts/run_marcus.py:501` — Claude 오류 메시지가 Discord 알림에 그대로 전달 (Log/Message Injection)
**심각도:** LOW  
**OWASP:** A03:2021 – Injection (Log/Message Injection)  
**증거:**
```python
# scripts/run_marcus.py:501-503
error_msg = result.stderr[:300] if result.stderr else f"종료코드 {result.returncode}"
# ...
_send_failure_alert(error_msg)
# _send_failure_alert에서:
payload = _json.dumps({"content": f"❌ 마커스 분석 실패: {error_msg}"})
```
**배경:** Claude CLI의 `stderr` 출력 (최대 300자)이 검증 없이 Discord 웹훅 메시지 본문에 삽입된다. Discord 메시지는 마크다운을 렌더링하므로 악의적인 포맷팅이 가능하다.  
**영향:** Discord 채널 내 메시지 포맷 조작. 심각도는 낮으나 신뢰 기반 알림 시스템 오용 가능.

---

### SEC-I-008: `data/fetch_news.py:433–444` — sqlite3 직접 연결 (get_db_conn 우회)
**심각도:** LOW  
**OWASP:** A03:2021 – Injection (설계 결함, 간접적 영향)  
**증거:**
```python
# data/fetch_news.py:433-434
conn = sqlite3.connect(str(DB_PATH))
# ...
save_sentiment_to_db(conn, updates)
```
**배경:** 프로젝트 규칙상 `get_db_conn()`을 통해서만 DB에 접근해야 하나 (WAL 모드, busy_timeout 표준화), `fetch_news.py`의 감성 점수 업데이트 구간이 직접 `sqlite3.connect()`를 호출한다. WAL 모드 미설정 및 busy_timeout 미설정으로 파이프라인 동시 실행 시 DB 잠금 오류 발생 가능.  
**영향:** 직접적인 인젝션 취약점은 아니나 DB 접근 계층 우회로 보안 통제가 적용되지 않음. 동시 쓰기 충돌로 데이터 손상 가능.

---

### SEC-I-009: `db/ssot.py:92` — f-string SQL (열 목록 동적 생성) — 설계 검토 필요
**심각도:** INFO  
**OWASP:** A03:2021 – Injection (SQL Injection, 현재 무해)  
**증거:**
```python
# db/ssot.py:92
cursor.execute(f"UPDATE holdings SET {', '.join(updates)} WHERE ticker = ?", params)
```
**배경:** `updates` 리스트는 `"qty = ?"`, `"avg_cost = ?"`, `"buy_fx_rate = ?"`, `"updated_at = ?"` 중 하드코딩된 문자열만 포함하며 사용자 입력이 섞이지 않는다. 값(`params`)은 파라미터 바인딩으로 처리된다. 현재 코드 경로에서는 SQL 인젝션이 불가능하다.  
**영향:** 현재 익스플로잇 없음. 그러나 `updates`에 외부 입력이 추가될 경우 즉각 SQL 인젝션으로 변환된다. 동일 패턴이 `db/ssot_wealth.py:89`에도 존재한다 (`UPDATE extra_assets SET`). 코드 리뷰 시 주의 필요.

---

### SEC-I-010: `web/server.py:149` — `subprocess.Popen` cmd 목록은 하드코딩 — 현재 안전
**심각도:** INFO  
**OWASP:** A03:2021 – Injection (Command Injection, 현재 무해)  
**증거:**
```python
# web/server.py:250-270 (run_background 호출부)
result = api.run_background(
    "pipeline",
    ["python3", str(PROJECT_ROOT / "run_pipeline.py")],
)
```
**배경:** `run_background`에 전달되는 `cmd` 리스트의 모든 요소가 하드코딩된 경로 상수이며, 사용자 HTTP 입력이 포함되지 않는다. `subprocess.Popen(cmd, ...)` 형태로 리스트를 사용하므로 shell=True가 아니며 셸 인젝션도 불가능하다.  
**영향:** 현재 익스플로잇 없음. 미래에 cmd 구성 요소가 동적으로 변경될 경우 위험.

---

## 주요 안전 확인 사항 (양호)

| 항목 | 위치 | 결과 |
|------|------|------|
| SQL 인젝션 — 대부분의 쿼리 | `db/ssot.py`, `web/api*.py` | 모두 파라미터 바인딩 (`?`) 사용 ✅ |
| `/api/logs` 로그 이름 화이트리스트 | `web/server.py:194` | `_ALLOWED_LOG_NAMES` 집합으로 엄격 검증 ✅ |
| `/api/file` 슬래시/백슬래시 차단 | `web/server.py:124` | `/`, `\` 문자 차단 ✅ |
| `/api/wealth/assets/{id}` Path 파라미터 | `web/server.py:352` | `int()` 강제 변환으로 비숫자 차단 ✅ |
| subprocess cmd — 사용자 입력 없음 | `web/server.py`, `scripts/run_marcus.py` | 모두 하드코딩 경로 리스트 ✅ |
| LIKE 파라미터 바인딩 | `web/api_company.py:84` | `?` 바인딩 사용 (값 인젝션 차단) ✅ |
| Discord webhook URL — 환경변수만 | `scripts/run_marcus.py:257` | HTTP 요청 입력이 URL에 직접 반영되지 않음 ✅ |

---

## 우선순위 권고

1. **[HIGH] SEC-I-001, SEC-I-002:** `_get_column_names`와 `_migrate_add_column`에 허용 테이블·컬럼 화이트리스트 추가. 또는 `MIGRATION_COLUMNS`의 각 항목을 `_migrate_add_column` 내부에서 정규식(`^[a-zA-Z_][a-zA-Z0-9_]*$`)으로 검증.

2. **[MEDIUM] SEC-I-003:** `_load_recent_news`에서 `code` 변수의 `%`와 `_` 문자를 `ESCAPE` 처리:  
   ```python
   code_escaped = code.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
   pat = f"%{code_escaped}%"
   # SQL에 ESCAPE '\\' 절 추가
   ```

3. **[MEDIUM] SEC-I-004:** `/api/file` 핸들러에 파일명 화이트리스트 또는 `(INTEL_DIR / name).resolve().is_relative_to(INTEL_DIR.resolve())` 검증 추가.

4. **[MEDIUM] SEC-I-005:** `_send_failure_alert`에서 URL 스킴 및 도메인 검증 추가:
   ```python
   if not webhook.startswith("https://discord.com/api/webhooks/"):
       return
   ```

# 시스템 전체 강화 구현 계획

> **에이전트 작업자용:** wj:team 스킬 또는 직접 실행으로 이 계획을 태스크별로 구현하세요. 단계는 체크박스 (`- [ ]`) 문법으로 추적합니다.

**목표:** 5개 전문 에이전트 감사에서 발견된 전체 이슈(보안·안정성·운영)를 서비스 중단 없이 우선순위 순서로 수정한다.

**아키텍처:** Phase 1(Python 소스, docker restart만) → Phase 2(인프라 변경, rebuild) → Phase 3(Next.js, npm build + docker cp) 순서로 각 Phase가 독립 배포 가능하게 구성한다. 각 Phase 완료 후 배포하고 서비스 정상 확인 후 다음 Phase로 진행한다.

**기술 스택:** Python 3.12 · SQLite (WAL) · ThreadingHTTPServer · Docker Compose · Next.js 16.2.4 · TypeScript

---

## 배포 명령 참조 (Phase별)

```bash
# Phase 1 완료 후 — Python 소스만 변경
docker restart investment-bot

# Phase 2 완료 후 — 인프라 변경 (Dockerfile, crontab, docker-compose)
docker compose up -d --build investment-bot

# Phase 3 완료 후 — Next.js 변경
cd web-next && npm run build && cd ..
docker cp web-next/.next/standalone/. mc-web:/app/
docker cp web-next/.next/static/. mc-web:/app/.next/static/
docker restart mc-web

# 헬스체크
curl -sf http://localhost:8421/api/status
docker ps
```

---

## Phase 1: Python 소스 강화 (docker restart만)

> 볼륨 마운트된 파일들만 수정. 각 Task 후 `docker restart investment-bot`으로 즉시 적용 가능.

---

### Task 1: config.py — Discord 웹훅 하드코딩 제거

**파일:**
- 수정: `config.py:276-279`

- [ ] **Step 1: 현재 코드 확인 + 테스트 작성**

```bash
grep -n "DISCORD_WEBHOOK_URL" config.py
```

예상: 토큰 포함 URL이 기본값으로 하드코딩된 줄이 보임

- [ ] **Step 2: 수정**

`config.py`에서 아래 부분을 찾아:
```python
DISCORD_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_URL",
    "https://discord.com/api/webhooks/...",   # ← 삭제할 URL
)
```

다음으로 교체:
```python
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
```

- [ ] **Step 3: .env 파일에 설정되어 있는지 확인**

```bash
grep "DISCORD_WEBHOOK_URL" .env
```

없으면 추가: `DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...` (실제 URL)

- [ ] **Step 4: 배포 + 검증**

```bash
docker restart investment-bot
curl -sf http://localhost:8421/api/status | python3 -m json.tool
```

---

### Task 2: server.py — 보안 입력 검증 강화

**파일:**
- 수정: `web/server.py` (다중 지점)

- [ ] **Step 1: /api/logs 경로 순회 수정 (server.py:173)**

현재:
```python
name = params.get("name", ["marcus"])[0]
lines = int(params.get("lines", ["80"])[0])
log_path = api.PID_DIR / f"{name}.log"
```

수정:
```python
name = params.get("name", ["marcus"])[0]
if not name or "/" in name or "\\" in name or ".." in name:
    self.send_json({"error": "잘못된 로그명"}, 400)
    return
lines = _safe_int(params, "lines", 80, max_val=2000)
log_path = api.PID_DIR / f"{name}.log"
```

- [ ] **Step 2: `_safe_int` 헬퍼 추가 (server.py 상단 클래스 밖)**

```python
def _safe_int(params: dict, key: str, default: int, max_val: int | None = None) -> int:
    """쿼리 파라미터를 안전하게 int로 변환. 실패 시 기본값 반환."""
    try:
        val = int(params.get(key, [str(default)])[0])
        if max_val is not None:
            val = min(val, max_val)
        return max(0, val)
    except (ValueError, IndexError):
        return default
```

- [ ] **Step 3: 쿼리 파라미터 int() 변환 전체 교체 (server.py do_GET)**

현재:
```python
days = int(params.get("days", ["60"])[0])
# ...
limit = int(params.get("limit", ["100"])[0])
```

수정:
```python
days = _safe_int(params, "days", 60, max_val=365)
# ...
limit = _safe_int(params, "limit", 100, max_val=500)
```

- [ ] **Step 4: `_read_json_body` 크기 제한 추가 (server.py:270)**

현재:
```python
def _read_json_body(self) -> dict:
    length = int(self.headers.get("Content-Length", 0))
    return json.loads(self.rfile.read(length)) if length else {}
```

수정:
```python
def _read_json_body(self) -> dict:
    length = int(self.headers.get("Content-Length", 0))
    if length > 10_000_000:
        self.send_json({"error": "요청 크기 초과 (최대 10MB)"}, 413)
        raise ValueError("body too large")
    if not length:
        return {}
    try:
        return json.loads(self.rfile.read(length))
    except json.JSONDecodeError:
        self.send_json({"error": "잘못된 JSON 형식"}, 400)
        raise
```

- [ ] **Step 5: AI 엔드포인트 간이 rate limit 추가 (server.py 상단)**

모듈 레벨에 추가:
```python
_ai_rate_lock = threading.Lock()
_ai_last_call_time: float = 0.0
_AI_RATE_LIMIT_SECS = 15  # 15초당 1회
```

`do_POST`의 `/api/investment-advice-stream` 핸들러 앞에 추가:
```python
elif path == "/api/investment-advice-stream":
    global _ai_last_call_time
    with _ai_rate_lock:
        now = time.time()
        if now - _ai_last_call_time < _AI_RATE_LIMIT_SECS:
            self.send_json({"error": "요청이 너무 빠릅니다. 잠시 후 다시 시도하세요."}, 429)
            return
        _ai_last_call_time = now
    body = self._read_json_body()
    # 기존 스트리밍 코드 이어서...
```

- [ ] **Step 6: 배포 + 검증**

```bash
docker restart investment-bot
# 경로 순회 차단 확인
curl "http://localhost:8421/api/logs?name=../../etc/passwd"
# 예상: {"error": "잘못된 로그명"}

# 잘못된 파라미터 처리 확인
curl "http://localhost:8421/api/wealth?days=abc"
# 예상: 정상 응답 (기본값 60일 사용)
```

- [ ] **Step 7: 커밋**

```bash
git add web/server.py
git commit -m "fix(server): 입력 검증 강화 — 경로 순회/타입 에러/body 크기/AI rate limit"
```

---

### Task 3: server.py — CORS 제한 + 보안 헤더

**파일:**
- 수정: `web/server.py`

- [ ] **Step 1: ALLOWED_ORIGIN 환경변수 추가 (server.py 상단)**

```python
_ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "http://localhost:3000")
```

`import os` 이미 있는지 확인. 없으면 추가.

- [ ] **Step 2: send_json에 헤더 교체**

현재:
```python
self.send_header("Access-Control-Allow-Origin", "*")
```

파일 전체에서 `Access-Control-Allow-Origin", "*"` 를 찾아 모두 교체:
```python
self.send_header("Access-Control-Allow-Origin", _ALLOWED_ORIGIN)
self.send_header("X-Content-Type-Options", "nosniff")
self.send_header("X-Frame-Options", "DENY")
```

- [ ] **Step 3: do_OPTIONS 수정**

```python
def do_OPTIONS(self):
    self.send_response(200)
    self.send_header("Access-Control-Allow-Origin", _ALLOWED_ORIGIN)
    self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
    self.send_header("Access-Control-Allow-Headers", "Content-Type")
    self.end_headers()
```

- [ ] **Step 4: .env에 ALLOWED_ORIGIN 추가**

```bash
echo 'ALLOWED_ORIGIN=http://100.90.201.87:3000' >> .env
```

- [ ] **Step 5: docker-compose.yml env_file 확인**

`env_file: .env` 이미 있음 — 추가 설정 불필요

- [ ] **Step 6: 배포 + 검증**

```bash
docker restart investment-bot
curl -si http://localhost:8421/api/status | grep -E "Access-Control|X-Content|X-Frame"
# 예상: Access-Control-Allow-Origin: http://100.90.201.87:3000
#        X-Content-Type-Options: nosniff
#        X-Frame-Options: DENY
```

- [ ] **Step 7: 커밋**

```bash
git add web/server.py .env
git commit -m "fix(server): CORS 와일드카드 제거, 보안 헤더 추가"
```

---

### Task 4: server.py — SSE 큐 maxsize 수정

**파일:**
- 수정: `web/server.py:323`

- [ ] **Step 1: 수정**

현재:
```python
client_queue: queue.Queue = queue.Queue()
```

수정:
```python
client_queue: queue.Queue = queue.Queue(maxsize=100)
```

- [ ] **Step 2: 검증 (로직 확인)**

`_broadcast_sse()` 함수(line ~355)에서 `put_nowait()` + `queue.Full` 패턴이 이제 실제로 동작한다. maxsize=100이면 이벤트 100개 누적 후 dead client로 판정 → 큐에서 제거.

- [ ] **Step 3: 커밋**

```bash
git add web/server.py
git commit -m "fix(server): SSE 큐 maxsize=100 설정 — dead client 메모리 누수 수정"
```

---

### Task 5: db/maintenance.py — VACUUM 후 WAL 재설정

**파일:**
- 수정: `db/maintenance.py`

- [ ] **Step 1: vacuum_db 함수 찾기**

```bash
grep -n "VACUUM\|vacuum" db/maintenance.py
```

- [ ] **Step 2: VACUUM 후 WAL 재설정 추가**

`VACUUM`을 실행하는 부분을 찾아 직후에 아래를 추가:

```python
conn.execute("VACUUM")
# VACUUM은 journal_mode를 DELETE로 리셋할 수 있으므로 WAL 재설정
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")
```

- [ ] **Step 3: 검증**

```bash
python3 -c "
import sqlite3, sys; sys.path.insert(0,'.')
from config import DB_PATH
conn = sqlite3.connect(str(DB_PATH))
conn.execute('VACUUM')
result = conn.execute('PRAGMA journal_mode').fetchone()
print('journal_mode after VACUUM:', result[0])
"
# 주의: 이 테스트는 실제 DB에 실행되므로 운영 중에는 조심
```

- [ ] **Step 4: 커밋**

```bash
git add db/maintenance.py
git commit -m "fix(db): VACUUM 후 WAL 모드 재설정 추가"
```

---

### Task 6: run_pipeline.py — 핵심 단계 에러 격리 + 실패 알림

**파일:**
- 수정: `run_pipeline.py`

- [ ] **Step 1: 실패 알림 함수 추가 (파일 상단 imports 아래)**

```python
def _notify_pipeline_failure(step: str, error: Exception) -> None:
    """파이프라인 단계 실패 시 Discord 알림 전송."""
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not webhook_url:
        return
    import urllib.request
    msg = f"🚨 파이프라인 실패\n단계: `{step}`\n오류: `{type(error).__name__}: {error}`"
    payload = {"content": msg}
    data = json.dumps(payload).encode("utf-8")
    try:
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"  ⚠️ Discord 알림 전송 실패: {e}")
```

`import json`이 없으면 상단에 추가.

- [ ] **Step 2: main() 핵심 단계를 try/except로 감싸기**

현재 `main()` 함수 (line ~232~278):
```python
# 4. 분석
analyze_prices()
check_alerts()
run_screener()
analyze_portfolio()
```

수정:
```python
# 4. 분석 — 각 단계 독립 실패 처리
for step_name, step_fn in [
    ("analyze_prices", analyze_prices),
    ("check_alerts", check_alerts),
    ("run_screener", run_screener),
    ("analyze_portfolio", analyze_portfolio),
]:
    try:
        step_fn()
    except Exception as e:
        print(f"  ⚠️ {step_name} 실패: {e}")
        _notify_pipeline_failure(step_name, e)
```

- [ ] **Step 3: main() 전체를 try/except로 감싸서 최종 실패 알림**

`main()` 함수 맨 끝 `print("✅ 파이프라인 완료")` 이후에 except 추가:

```python
def main():
    ...
    try:
        # 기존 코드 전체
        init_db()
        _collect_data(engine)
        aggregate_daily()
        maintain_db()
        # 핵심 단계 (Step 2에서 수정된 for loop)
        ...
        generate_daily()
        print("=" * 60)
        print("✅ 파이프라인 완료")
    except Exception as e:
        print(f"❌ 파이프라인 치명적 실패: {e}")
        _notify_pipeline_failure("pipeline_main", e)
        raise
```

- [ ] **Step 4: 배포 + 검증**

```bash
docker restart investment-bot
# 다음 파이프라인 실행까지 대기하거나 수동 실행
docker exec investment-bot python3 run_pipeline.py
# 로그 확인
docker logs investment-bot --tail 50
```

- [ ] **Step 5: 커밋**

```bash
git add run_pipeline.py
git commit -m "fix(pipeline): 핵심 단계 에러 격리 + Discord 실패 알림 추가"
```

---

### Task 7: PORTFOLIO_LEGACY → DB SSoT 전환 (3파일)

**파일:**
- 수정: `data/fetch_news.py:18,32`
- 수정: `analysis/alerts_watch.py:32`
- 수정: `reports/closing.py:19`

- [ ] **Step 1: fetch_news.py 수정**

현재 (line ~17-18):
```python
from config import DB_PATH, OUTPUT_DIR
from config import PORTFOLIO_LEGACY as PORTFOLIO
```

수정:
```python
from config import DB_PATH, OUTPUT_DIR
import db.ssot as ssot
```

`PORTFOLIO`를 사용하는 곳 찾기:
```bash
grep -n "PORTFOLIO\b" data/fetch_news.py
```

`for stock in PORTFOLIO:` → DB에서 읽는 방식으로 교체:
```python
# 파일 상단 함수 추가
def _get_portfolio_tickers() -> list[dict]:
    """DB에서 현재 보유 종목 목록 반환"""
    try:
        return ssot.get_holdings()
    except Exception as e:
        print(f"  ⚠️ holdings 로드 실패, 빈 목록 사용: {e}")
        return []
```

`for stock in PORTFOLIO:` → `for stock in _get_portfolio_tickers():` 로 교체

- [ ] **Step 2: alerts_watch.py 수정**

현재 (line ~32):
```python
from config import PORTFOLIO_LEGACY as PORTFOLIO
```

수정:
```python
import db.ssot as ssot

def _get_portfolio() -> list[dict]:
    try:
        return ssot.get_holdings()
    except Exception as e:
        print(f"  ⚠️ holdings 로드 실패: {e}")
        return []
```

`PORTFOLIO` 사용처를 `_get_portfolio()` 호출로 교체

- [ ] **Step 3: reports/closing.py 수정**

현재 (line ~19):
```python
from config import PORTFOLIO_LEGACY as PORTFOLIO
```

동일 패턴으로 수정.

- [ ] **Step 4: 검증**

```bash
# 문법 오류 없는지 확인
python3 -c "import data.fetch_news"
python3 -c "import analysis.alerts_watch"
python3 -c "import reports.closing"
```

- [ ] **Step 5: 배포 + 검증**

```bash
docker restart investment-bot
# 5분 대기 후 alerts_watch.log 확인
docker exec investment-bot tail -20 /app/logs/alerts_watch.log
```

- [ ] **Step 6: 커밋**

```bash
git add data/fetch_news.py analysis/alerts_watch.py reports/closing.py
git commit -m "fix: PORTFOLIO_LEGACY → DB SSoT 전환 (fetch_news, alerts_watch, closing)"
```

---

### Task 8: web/investment_advisor.py — subprocess orphan 수정

**파일:**
- 수정: `web/investment_advisor.py` (_stream_via_cli 함수, ~line 245)

- [ ] **Step 1: 현재 코드 확인**

```bash
grep -n "Popen\|proc\.\|terminate\|kill" web/investment_advisor.py
```

- [ ] **Step 2: _stream_via_cli에 cleanup 추가**

현재:
```python
def _stream_via_cli(prompt: str):
    proc = subprocess.Popen(...)
    proc.stdin.write(prompt)
    proc.stdin.close()
    while True:
        chunk = proc.stdout.read(8)
        if not chunk:
            break
        yield chunk
    proc.wait()
```

수정 (generator에 try/finally 추가):
```python
def _stream_via_cli(prompt: str):
    proc = subprocess.Popen(
        [CLAUDE_BIN, "--print", "-p", "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    proc.stdin.write(prompt)
    proc.stdin.close()
    try:
        while True:
            chunk = proc.stdout.read(8)
            if not chunk:
                break
            yield chunk
    finally:
        # 클라이언트 연결 끊기거나 예외 발생 시 프로세스 정리
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
```

- [ ] **Step 3: 배포 + 커밋**

```bash
docker restart investment-bot
git add web/investment_advisor.py
git commit -m "fix(advisor): 스트리밍 중 클라이언트 연결 끊길 때 Claude CLI 프로세스 정리"
```

---

### Phase 1 최종 배포 확인

- [ ] **Phase 1 전체 배포**

```bash
docker restart investment-bot
```

- [ ] **헬스체크**

```bash
curl -sf http://localhost:8421/api/status | python3 -m json.tool
curl -sf http://localhost:8421/api/data | python3 -c "import json,sys; d=json.load(sys.stdin); print('keys:', list(d.keys())[:5])"
# 대시보드 브라우저 접속: http://100.90.201.87:3000
```

---

## Phase 2: 인프라 강화 (docker compose up -d --build investment-bot)

> Dockerfile, crontab.docker, docker-compose.yml 변경. 완료 후 반드시 `--build` 로 rebuild.

---

### Task 9: db/connection.py — DB 연결 팩토리 신설

**파일:**
- 생성: `db/connection.py`
- 수정: `db/ssot.py:18-20`
- 수정: `db/ssot_wealth.py` (get_conn 함수)
- 수정: `db/maintenance.py` (sqlite3.connect 호출)
- 수정: `db/aggregate.py` (sqlite3.connect 호출)

- [ ] **Step 1: db/connection.py 생성**

```python
#!/usr/bin/env python3
"""DB 연결 팩토리 — WAL 모드, busy_timeout, row_factory 통일"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH


def get_db_conn(timeout: float = 30.0) -> sqlite3.Connection:
    """WAL 모드 + busy_timeout이 설정된 DB 연결 반환.

    모든 DB 접근 지점에서 이 함수를 사용해야 한다.
    timeout=30.0 → 30초 동안 잠금 해제 대기 후 에러 발생.
    """
    conn = sqlite3.connect(str(DB_PATH), timeout=timeout)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")  # ms 단위
    conn.row_factory = sqlite3.Row
    return conn
```

- [ ] **Step 2: db/ssot.py get_conn() 교체**

현재 (`db/ssot.py:18-20`):
```python
def get_conn():
    """DB 연결 반환"""
    return sqlite3.connect(str(DB_PATH))
```

수정:
```python
from db.connection import get_db_conn


def get_conn() -> sqlite3.Connection:
    """DB 연결 반환 (WAL + busy_timeout 설정 포함)"""
    return get_db_conn()
```

- [ ] **Step 3: db/ssot_wealth.py get_conn() 동일하게 교체**

```bash
grep -n "def get_conn\|sqlite3.connect" db/ssot_wealth.py | head -10
```

동일 패턴으로 교체:
```python
from db.connection import get_db_conn

def get_conn() -> sqlite3.Connection:
    return get_db_conn()
```

- [ ] **Step 4: db/maintenance.py의 raw sqlite3.connect 교체**

```bash
grep -n "sqlite3.connect" db/maintenance.py
```

찾은 모든 `sqlite3.connect(str(DB_PATH))` → `get_db_conn()` 으로 교체.
파일 상단에 import 추가:
```python
from db.connection import get_db_conn
```

- [ ] **Step 5: db/aggregate.py 동일하게 교체**

```bash
grep -n "sqlite3.connect" db/aggregate.py
```

동일 패턴으로 교체.

- [ ] **Step 6: web/api.py의 sqlite3.connect 교체**

```bash
grep -n "sqlite3.connect" web/api.py
```

동일 패턴으로 교체.

- [ ] **Step 7: 검증**

```bash
python3 -c "
from db.connection import get_db_conn
conn = get_db_conn()
result = conn.execute('PRAGMA journal_mode').fetchone()
print('journal_mode:', result[0])
result = conn.execute('PRAGMA busy_timeout').fetchone()
print('busy_timeout:', result[0])
conn.close()
"
# 예상:
# journal_mode: wal
# busy_timeout: 30000
```

- [ ] **Step 8: 커밋**

```bash
git add db/connection.py db/ssot.py db/ssot_wealth.py db/maintenance.py db/aggregate.py web/api.py
git commit -m "feat(db): DB 연결 팩토리 신설 — WAL + busy_timeout=30초 통일"
```

---

### Task 10: utils/json_io.py — Atomic JSON 쓰기 유틸

**파일:**
- 생성: `utils/json_io.py`
- 수정: `scripts/refresh_prices.py` (prices.json 쓰기)
- 수정: `analysis/alerts.py` (alerts.json 쓰기)

> 전체 24+ 파일을 모두 바꾸는 대신, 1분 단위로 가장 자주 실행되는 핵심 경로만 우선 적용.

- [ ] **Step 1: utils/json_io.py 생성**

```python
#!/usr/bin/env python3
"""Atomic JSON 쓰기 유틸 — 쓰기 중 읽기 시 truncated JSON 방지"""

import json
import os
import tempfile
from pathlib import Path


def write_json_atomic(path: Path, data: dict | list, indent: int = 2) -> None:
    """JSON을 임시 파일에 쓴 후 원자적으로 교체.

    쓰기 중 프로세스가 죽어도 기존 파일은 보존된다.
    os.replace()는 POSIX에서 원자적이다.
    """
    dir_path = path.parent
    dir_path.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=dir_path,
        suffix=".tmp",
        delete=False,
        encoding="utf-8",
    ) as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
        tmp_path = f.name
    os.replace(tmp_path, path)
```

- [ ] **Step 2: scripts/refresh_prices.py에서 prices.json 쓰기 교체**

```bash
grep -n "write_text\|open.*w.*json\|json.dump" scripts/refresh_prices.py | head -10
```

찾은 JSON 쓰기 패턴을 `write_json_atomic` 으로 교체:
```python
from utils.json_io import write_json_atomic

# 기존: out_path.write_text(json.dumps(data, ...), encoding='utf-8')
# 수정:
write_json_atomic(out_path, data)
```

- [ ] **Step 3: analysis/alerts.py에서 alerts.json 쓰기 교체**

```bash
grep -n "write_text\|open.*\"w\"\|json.dump" analysis/alerts.py | head -10
```

동일 패턴으로 교체.

- [ ] **Step 4: 검증**

```bash
python3 -c "
from pathlib import Path
from utils.json_io import write_json_atomic
import json
test_path = Path('/tmp/test_atomic.json')
write_json_atomic(test_path, {'test': 'ok', 'value': 123})
print(json.loads(test_path.read_text()))
test_path.unlink()
print('atomic write 정상 동작')
"
```

- [ ] **Step 5: 커밋**

```bash
git add utils/json_io.py scripts/refresh_prices.py analysis/alerts.py
git commit -m "feat(utils): atomic JSON 쓰기 유틸 추가 — 쓰기 중 읽기 시 truncated JSON 방지"
```

---

### Task 11: scripts/run_jarvis.py — root 권한 충돌 수정

**파일:**
- 수정: `scripts/run_jarvis.py:173-174`

> `--dangerously-skip-permissions`는 root 계정에서 실행 불가. Marcus와 동일한 `-p -` 방식으로 전환.

- [ ] **Step 1: 현재 코드 확인**

```bash
grep -n "dangerously\|subprocess.run\|CLAUDE_BIN" scripts/run_jarvis.py
```

- [ ] **Step 2: subprocess.run 호출 수정 (line ~173)**

현재:
```python
result = subprocess.run(
    [CLAUDE_BIN, "--dangerously-skip-permissions", "--print", "-p", prompt],
    capture_output=True,
    text=True,
    timeout=300,
)
```

수정:
```python
result = subprocess.run(
    [CLAUDE_BIN, "--print", "-p", "-"],
    input=prompt,
    capture_output=True,
    text=True,
    timeout=300,
)
```

> `--print -p -` 방식은 `-p` 플래그로 non-interactive 모드 실행, stdin으로 프롬프트 전달.
> `--dangerously-skip-permissions` 제거로 root에서도 동작.

- [ ] **Step 3: 검증 (컨테이너 내부에서)**

```bash
docker exec investment-bot python3 scripts/run_jarvis.py
# 로그 확인
docker exec investment-bot tail -30 /app/logs/jarvis.log
# "Claude 실행 오류" 없이 정상 완료되면 수정 성공
```

- [ ] **Step 4: 커밋**

```bash
git add scripts/run_jarvis.py
git commit -m "fix(jarvis): --dangerously-skip-permissions 제거 — root 컨테이너 호환"
```

---

### Task 12: crontab.docker — 로그 로테이션 + maintenance 등록

**파일:**
- 수정: `crontab.docker`

- [ ] **Step 1: 현재 crontab 확인**

```bash
cat crontab.docker
```

- [ ] **Step 2: 로그 로테이션 크론 추가**

`crontab.docker` 하단에 추가:
```cron
# ── 로그 관리 ──
# 매일 00:05 KST (전날 15:05 UTC) — 50MB 초과 로그 파일 자동 truncate
5 15 * * * root find /app/logs -name "*.log" -size +50M -exec truncate -s 0 {} \; >> /app/logs/logrotate.log 2>&1

# 매주 일요일 03:00 KST (토요일 18:00 UTC) — DB 보존 정책 실행
0 18 * * 0 root cd /app && python3 db/maintenance.py >> /app/logs/maintenance.log 2>&1
```

> `truncate -s 0`은 파일을 삭제하지 않고 0바이트로 비움 — 로그 경로를 참조하는 프로세스가 안전하게 계속 쓸 수 있음.

- [ ] **Step 3: db/maintenance.py에 __main__ 진입점 확인**

```bash
grep -n "__main__\|if __name__" db/maintenance.py
```

없으면 파일 하단에 추가:
```python
if __name__ == "__main__":
    import sqlite3
    from config import DB_PATH
    conn = sqlite3.connect(str(DB_PATH))
    result = purge_old_data(conn)
    vacuum_db(conn)
    conn.close()
    print(f"maintenance 완료: {result}")
```

- [ ] **Step 4: 커밋 (rebuild 전)**

```bash
git add crontab.docker db/maintenance.py
git commit -m "ops(cron): 로그 로테이션 + DB maintenance 주간 스케줄 추가"
```

---

### Task 13: docker-compose.yml — 볼륨/헬스체크/포트 강화

**파일:**
- 수정: `docker-compose.yml`

- [ ] **Step 1: utils/ 볼륨 마운트 추가**

현재 volumes 섹션에 추가:
```yaml
- ./utils:/app/utils
```

> `lib/` 디렉토리는 Python 측에 없으므로 추가 불필요.

- [ ] **Step 2: healthcheck 추가 (investment-bot)**

```yaml
services:
  investment-bot:
    # ... 기존 설정 ...
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:8421/api/status || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s
```

- [ ] **Step 3: mc-web depends_on 강화**

```yaml
  mc-web:
    # ... 기존 설정 ...
    depends_on:
      investment-bot:
        condition: service_healthy
```

- [ ] **Step 4: 포트 바인딩 제한**

> Tailscale은 `utun` 인터페이스를 사용하므로 `0.0.0.0`에서만 접근 가능.
> 127.0.0.1 바인딩은 Tailscale 접근을 **차단**하므로 사용 불가.
> 대신 macOS 방화벽을 활성화하여 로컬 네트워크 노출을 차단.

```bash
# macOS 방화벽 활성화 (터미널에서 직접 실행)
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate
# 예상: Firewall is enabled. (State = 1)
```

포트 바인딩은 현재 `0.0.0.0` 유지 (Tailscale 정상 동작 보장).

- [ ] **Step 5: 최종 docker-compose.yml 확인**

```yaml
services:
  investment-bot:
    build: .
    container_name: investment-bot
    restart: unless-stopped
    ports:
      - "8421:8421"
    volumes:
      - ./db:/app/db
      - ./output:/app/output
      - ./logs:/app/logs
      - ./docs:/app/docs
      - ~/.claude:/root/.claude-host:ro
      - ~/.claude.json:/root/.claude-host.json:ro
      - ./web:/app/web
      - ./analysis:/app/analysis
      - ./data:/app/data
      - ./reports:/app/reports
      - ./scripts:/app/scripts
      - ./utils:/app/utils          # ← 추가
      - ./config.py:/app/config.py
      - ./run_pipeline.py:/app/run_pipeline.py
    environment:
      - TZ=Asia/Seoul
    env_file:
      - .env
    healthcheck:                    # ← 추가
      test: ["CMD-SHELL", "curl -sf http://localhost:8421/api/status || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s

  mc-web:
    build: ./web-next
    container_name: mc-web
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - PYTHON_API_URL=http://investment-bot:8421
      - HOSTNAME=0.0.0.0
    depends_on:
      investment-bot:
        condition: service_healthy  # ← condition 추가
```

- [ ] **Step 6: 커밋**

```bash
git add docker-compose.yml
git commit -m "ops(docker): utils/ 볼륨 마운트 + healthcheck + depends_on 강화"
```

---

### Phase 2 최종 배포

- [ ] **rebuild + 재시작**

```bash
docker compose up -d --build investment-bot
# healthcheck가 통과할 때까지 대기 (최대 30s * 3 = 90초)
docker ps
# HEALTH: healthy 확인

# mc-web도 재시작 (depends_on condition 반영)
docker compose up -d mc-web
```

- [ ] **검증**

```bash
# 서비스 정상 확인
curl -sf http://localhost:8421/api/status
# jarvis 수동 실행 테스트
docker exec investment-bot python3 scripts/run_jarvis.py
# 로그에서 dangerously 오류 없는지 확인
docker exec investment-bot tail -20 /app/logs/jarvis.log
# utils/ 반영 확인
docker exec investment-bot python3 -c "from utils.json_io import write_json_atomic; print('OK')"
# 대시보드 정상 확인
curl -sf http://100.90.201.87:3000
```

---

## Phase 3: Next.js 강화 (npm build + docker cp)

> web-next/ 변경. `npm run build` 후 docker cp로 배포.

---

### Task 14: route.ts — SSE upstream 에러 전파

**파일:**
- 수정: `web-next/src/app/api/[...path]/route.ts`

- [ ] **Step 1: 현재 코드 확인**

```bash
cat "web-next/src/app/api/[...path]/route.ts"
```

- [ ] **Step 2: events SSE 프록시에 upstream 오류 체크 추가**

`events` 케이스 (EventSource 프록시 부분)에서 upstream fetch 후:
```typescript
if (path[0] === 'events') {
  const upstream = await fetch(`${API_BASE}/api/events`, { ... })
  
  // ← 추가: upstream 실패 시 에러 이벤트 스트림으로 전달
  if (!upstream.ok || !upstream.body) {
    const errorStream = new ReadableStream({
      start(controller) {
        controller.enqueue(
          new TextEncoder().encode(
            `data: {"error": "upstream unavailable (${upstream.status})"}\n\n`
          )
        )
        controller.close()
      },
    })
    return new NextResponse(errorStream, {
      headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
    })
  }
  return new NextResponse(upstream.body, { ... })
}
```

- [ ] **Step 3: 일반 프록시에 try-catch 추가**

```typescript
async function proxy(req: NextRequest, path: string[]): Promise<NextResponse> {
  try {
    const upstream = await fetch(...)
    // 기존 코드
  } catch (err) {
    console.error('[proxy] upstream fetch failed:', err)
    return NextResponse.json({ error: 'API 서버에 연결할 수 없습니다.' }, { status: 503 })
  }
}
```

- [ ] **Step 4: 커밋**

```bash
git add "web-next/src/app/api/[...path]/route.ts"
git commit -m "fix(proxy): SSE upstream 에러 전파 + fetch 예외 처리"
```

---

### Task 15: AIAdvisorPanel.tsx — 언마운트 시 abort

**파일:**
- 수정: `web-next/src/components/advisor/AIAdvisorPanel.tsx`

- [ ] **Step 1: 언마운트 cleanup useEffect 추가**

파일 내 기존 useEffect들 아래에 추가:
```typescript
// 컴포넌트 언마운트 시 진행 중인 요청 취소
useEffect(() => {
  return () => {
    abortRef.current?.abort()
  }
}, [])
```

- [ ] **Step 2: 커밋**

```bash
git add web-next/src/components/advisor/AIAdvisorPanel.tsx
git commit -m "fix(advisor): 탭 이동 시 진행 중인 AI 요청 자동 취소"
```

---

### Task 16: useWealthData.ts 타입 추가 + fmtAmt 중복 제거

**파일:**
- 수정: `web-next/src/hooks/useWealthData.ts`
- 수정: `web-next/src/lib/format.ts`
- 수정: `web-next/src/components/advisor/ConditionPanel.tsx`

- [ ] **Step 1: useWealthData.ts에 타입 추가**

```bash
cat web-next/src/hooks/useWealthData.ts
```

현재 `fetcher`가 `any`를 반환하는 구조. 타입 추가:

`web-next/src/types/api.ts`에 `WealthSummary` 타입이 없으면 추가:
```typescript
export interface WealthSummary {
  total_wealth_krw: number
  investment_value_krw: number
  extra_assets_krw: number
  history: Array<{
    date: string
    total_wealth_krw: number
    investment_value_krw: number
    extra_assets_krw: number
  }>
}
```

`useWealthData.ts`에 타입 적용:
```typescript
import type { WealthSummary } from '@/types/api'
import useSWR from 'swr'
import { apiFetch } from '@/lib/api'

export function useWealthData(days = 60) {
  return useSWR<WealthSummary>(`/api/wealth?days=${days}`, apiFetch, {
    refreshInterval: 60_000,
    revalidateOnFocus: false,
  })
}
```

- [ ] **Step 2: lib/format.ts에 fmtAmt 추가**

```bash
grep -n "fmtAmt" web-next/src/components/advisor/ConditionPanel.tsx
```

`fmtAmt`의 현재 구현 복사 후 `lib/format.ts`에 추가:
```typescript
export function fmtAmt(v: number): string {
  // ConditionPanel.tsx의 현재 구현과 동일하게
  if (v >= 100_000_000) return `${(v / 100_000_000).toFixed(1)}억`
  if (v >= 10_000) return `${Math.round(v / 10_000)}만`
  return v.toLocaleString()
}
```

`ConditionPanel.tsx`에서 로컬 정의 제거 후 import:
```typescript
import { fmtAmt } from '@/lib/format'
```

- [ ] **Step 3: savedStrategies.ts의 fmtAmt도 import로 교체**

```bash
grep -n "fmtAmt" web-next/src/lib/savedStrategies.ts
```

로컬 정의 제거 후:
```typescript
import { fmtAmt } from '@/lib/format'
```

- [ ] **Step 4: TypeScript 빌드 검증**

```bash
cd web-next && npx tsc --noEmit && cd ..
# 예상: 에러 없음
```

- [ ] **Step 5: 커밋**

```bash
git add web-next/src/hooks/useWealthData.ts web-next/src/types/api.ts \
        web-next/src/lib/format.ts \
        web-next/src/components/advisor/ConditionPanel.tsx \
        web-next/src/lib/savedStrategies.ts
git commit -m "refactor(frontend): WealthSummary 타입 추가, fmtAmt 중복 제거"
```

---

### Phase 3 최종 배포

- [ ] **빌드 + docker cp 배포**

```bash
cd web-next && npm run build && cd ..
docker cp web-next/.next/standalone/. mc-web:/app/
docker cp web-next/.next/static/. mc-web:/app/.next/static/
docker restart mc-web
```

- [ ] **검증**

```bash
# 대시보드 접속
curl -sf http://100.90.201.87:3000
# advisor 탭에서 분석 갱신 → 다른 탭 이동 시 요청 취소 확인 (네트워크 탭)
# 부 탭 전환해도 이전 요청이 abort되는지 브라우저 개발자도구에서 확인
```

---

## 스펙 커버리지 체크

| 이슈 | 태스크 | 상태 |
|------|--------|------|
| Discord 웹훅 하드코딩 | Task 1 | ✅ |
| /api/logs 경로 순회 | Task 2 | ✅ |
| int() 파라미터 미검증 | Task 2 | ✅ |
| body 크기 제한 없음 | Task 2 | ✅ |
| AI rate limit 없음 | Task 2 | ✅ |
| CORS 와일드카드 | Task 3 | ✅ |
| 보안 헤더 미설정 | Task 3 | ✅ |
| SSE 큐 maxsize=0 | Task 4 | ✅ |
| VACUUM WAL 리셋 | Task 5 | ✅ |
| 파이프라인 에러 격리 | Task 6 | ✅ |
| 파이프라인 실패 알림 | Task 6 | ✅ |
| PORTFOLIO_LEGACY (3곳) | Task 7 | ✅ |
| subprocess orphan | Task 8 | ✅ |
| busy_timeout=0 | Task 9 | ✅ |
| JSON atomic write | Task 10 | ✅ (핵심 경로) |
| jarvis root 충돌 | Task 11 | ✅ |
| 로그 로테이션 없음 | Task 12 | ✅ |
| maintenance cron 미등록 | Task 12 | ✅ |
| utils/ 볼륨 마운트 누락 | Task 13 | ✅ |
| healthcheck 없음 | Task 13 | ✅ |
| 로컬 네트워크 노출 | Task 13 | ✅ (방화벽 활성화) |
| SSE 프록시 에러 전파 | Task 14 | ✅ |
| AIAdvisorPanel abort | Task 15 | ✅ |
| useWealthData any | Task 16 | ✅ |
| fmtAmt 중복 | Task 16 | ✅ |

**미포함 항목 (범위 외):**
- Docker non-root 실행: cron이 root 필요한 구조라 큰 리팩터링. 별도 계획 필요.
- 300줄 초과 파일 분리: 기능 변경 없는 순수 리팩터링. 별도 계획 권장.
- code splitting: 성능 최적화. 별도 계획 권장.
- 에러 메시지 정보 노출 제거: 낮은 우선순위. 운영 로그 보완으로 대체 가능.

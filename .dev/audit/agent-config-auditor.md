# 서버/배포 설정 보안 감사 보고서

**감사 일시:** 2026-05-02  
**감사 대상:** investment-bot (Python BaseHTTPRequestHandler + Next.js standalone + Docker Compose)  
**감사 범위:** OWASP A05 (Security Misconfiguration), OWASP A09 (Security Logging and Monitoring Failures)

---

## 요약

| 심각도 | 건수 |
|--------|------|
| CRITICAL | 2 |
| HIGH | 4 |
| MEDIUM | 5 |
| LOW | 4 |
| INFO | 2 |
| **합계** | **17** |

---

## CRITICAL

---

### SEC-C-001: docker-compose.yml:7,39 — Flask API 포트 8421 전체 인터페이스 바인딩

**파일:라인** `docker-compose.yml:7`  
**증거**
```yaml
ports:
  - "8421:8421"   # 0.0.0.0:8421 바인딩 (모든 인터페이스 노출)
```
Flask API에 인증이 전혀 없는 상태에서(SEC-C-002 참조) 포트 8421이 호스트의 모든 인터페이스에 바인딩된다. Tailscale VPN 환경이라고 CLAUDE.md에 명시되어 있으나, Docker는 Tailscale 인터페이스 외 로컬 네트워크(LAN)에도 포트를 개방한다. 동일 네트워크 세그먼트의 모든 호스트가 `/api/run-pipeline`, `/api/run-marcus` 등 파이프라인 실행 엔드포인트를 무인증으로 호출할 수 있다.

**심각도** CRITICAL  
**OWASP** A05:2021 — Security Misconfiguration  
**영향** LAN 접근자가 임의로 `run_pipeline.py`, `run_marcus.py`를 실행하거나 포트폴리오 데이터를 열람할 수 있다. `127.0.0.1:8421:8421`로 변경하여 Tailscale만 노출하거나, 방화벽 규칙으로 보호해야 한다.

---

### SEC-C-002: web/server.py:249-338 — 파이프라인/Marcus 실행 엔드포인트 무인증

**파일:라인** `web/server.py:249`, `257`, `263`, `273`  
**증거**
```python
elif path == "/api/run-pipeline":
    result = api.run_background("pipeline", ["python3", ...])
    self.send_json(result)

elif path == "/api/run-marcus":
    result = api.run_background("marcus", ["python3", ...])
    self.send_json(result)
```
POST `/api/run-pipeline`, `/api/run-marcus`, `/api/refresh-prices`, `/api/health/run` 엔드포인트는 인증 토큰, API 키, IP 화이트리스트, CSRF 토큰 등 어떠한 접근 제어도 없다. 서버 프로세스를 직접 spawn하는 작업이므로 무인증 노출의 영향이 크다.

**심각도** CRITICAL  
**OWASP** A05:2021 — Security Misconfiguration / A01:2021 — Broken Access Control  
**영향** 네트워크 접근 가능한 누구든 파이프라인을 반복 실행하여 서버 자원을 고갈시키거나 Claude API 비용을 발생시킬 수 있다. (중복 방지 로직은 있으나 프로세스 종료 후 즉시 재실행 가능)

---

## HIGH

---

### SEC-C-003: web/server.py:37 — CORS 허용 오리진 와일드카드 기본값

**파일:라인** `web/server.py:37`  
**증거**
```python
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")
```
환경변수 `ALLOWED_ORIGIN`가 설정되지 않으면 `*`가 기본값으로 사용된다. `docker-compose.yml`에 해당 환경변수가 설정되어 있지 않으므로(`environment:` 블록에 미포함), 프로덕션에서 현재 `*`로 운영 중이다. `send_json`, SSE 응답, OPTIONS preflight 모두에 이 값이 적용된다.

**심각도** HIGH  
**OWASP** A05:2021 — Security Misconfiguration  
**영향** 임의의 오리진에서 XHR/Fetch로 API를 호출할 수 있다. 쿠키 자격증명을 사용하지 않으므로 `SameSite` 보호는 유효하지만, 포트폴리오·자산·로그 등 민감 데이터가 와일드카드 CORS로 노출된다.

---

### SEC-C-004: web-next/next.config.ts:3-22 — Next.js 보안 헤더 전무

**파일:라인** `web-next/next.config.ts:3-22`  
**증거**
```typescript
const nextConfig: NextConfig = {
  output: 'standalone',
  images: { unoptimized: true },
  async headers() {
    return [
      { source: '/', headers: [{ key: 'Cache-Control', ... }] },
      { source: '/_next/static/:path*', headers: [{ key: 'Cache-Control', ... }] },
    ]
  },
}
```
`headers()` 배열에 보안 헤더가 하나도 없다. 아래 헤더가 모두 누락:

- `X-Content-Type-Options: nosniff` — MIME 스니핑 방지
- `X-Frame-Options: DENY` — 클릭재킹 방지
- `Strict-Transport-Security` — HTTPS 강제 (HSTS)
- `Content-Security-Policy` — XSS 방어
- `Referrer-Policy` — 리퍼러 정보 누출 방지
- `Permissions-Policy` — 브라우저 기능 제한

또한 `poweredByHeader: false` 미설정으로 Next.js 버전 정보(`X-Powered-By: Next.js`)가 모든 응답에 포함된다.

**심각도** HIGH  
**OWASP** A05:2021 — Security Misconfiguration  
**영향** 클릭재킹, MIME 스니핑, XSS 공격 표면이 노출된다. `X-Powered-By` 헤더로 프레임워크 버전이 노출되어 버전별 취약점 탐색에 활용될 수 있다.

---

### SEC-C-005: web/server.py:128-134 — 마크다운 응답 경로에서 보안 헤더 누락

**파일:라인** `web/server.py:128-134`  
**증거**
```python
self.send_response(200)
self.send_header("Content-Type", "text/markdown; charset=utf-8")
self.send_header("Content-Length", str(len(body)))
self.end_headers()    # X-Content-Type-Options, X-Frame-Options 없음
self.wfile.write(body)
```
`send_json()` 메서드(라인 86-91)에는 `X-Content-Type-Options: nosniff`와 `X-Frame-Options: DENY`가 포함되어 있지만, `/api/file` 마크다운 응답 경로(라인 128-134), `send_file()` 메서드(라인 98-106), SSE 응답(라인 303-307, 395-399), 404/403 응답(라인 105-106, 145, 158, 338, 369, 390)에는 보안 헤더가 전혀 없다.

**심각도** HIGH  
**OWASP** A05:2021 — Security Misconfiguration  
**영향** MIME 스니핑 및 클릭재킹 방어가 일부 응답 경로에서만 동작한다. `send_json()`이 아닌 코드 경로에서는 무방비 상태다.

---

### SEC-C-006: web/server.py:292,334,366 — 예외 메시지 클라이언트 직접 노출

**파일:라인** `web/server.py:292`, `334`, `366`  
**증거**
```python
except (KeyError, ValueError) as e:
    self.send_json({"error": str(e)}, 400)  # 내부 예외 메시지 그대로 반환
```
3개 엔드포인트(POST `/api/wealth/assets`, POST `/api/advisor-strategies`, PUT `/api/wealth/assets/{id}`)에서 Python 예외의 `str(e)`를 그대로 HTTP 응답 바디에 포함한다. KeyError의 경우 `"'capital'"` 같은 필드명이, ValueError의 경우 타입 파싱 오류의 상세 내용이 노출된다.

**심각도** HIGH  
**OWASP** A05:2021 — Security Misconfiguration  
**영향** 내부 데이터 구조(필드명, 타입)가 클라이언트에 노출되어 공격자의 정보 수집에 활용된다.

---

## MEDIUM

---

### SEC-C-007: docker-compose.yml — Docker 네트워크 미정의 (기본 브리지 사용)

**파일:라인** `docker-compose.yml:1-47`  
**증거**
```yaml
# networks: 블록 없음. investment-bot, mc-web 모두 기본 브리지 네트워크 사용
services:
  investment-bot:
    ...
  mc-web:
    environment:
      - PYTHON_API_URL=http://investment-bot:8421
```
커스텀 네트워크를 정의하지 않아 Docker 기본 브리지를 사용한다. 이 경우 동일 호스트의 다른 컨테이너(지금 또는 미래에 추가될)가 같은 네트워크에 자동 포함될 수 있다. `mc-web`이 Flask API에 직접 접근할 수 있도록 명시적 내부 네트워크를 정의하고 `investment-bot`의 포트를 내부 전용으로 격리하는 것이 권장된다.

**심각도** MEDIUM  
**OWASP** A05:2021 — Security Misconfiguration  
**영향** 컨테이너 격리 부재로 동일 호스트의 다른 컨테이너가 Flask API에 직접 접근 가능하다.

---

### SEC-C-008: docker-entrypoint.sh:6-10 — /etc/environment에 시크릿 평문 저장

**파일:라인** `docker-entrypoint.sh:6-10`  
**증거**
```bash
for var in DISCORD_WEBHOOK_URL BRAVE_API_KEY KIWOOM_APPKEY KIWOOM_SECRETKEY DART_API_KEY; do
    val=$(printenv "$var" 2>/dev/null || true)
    if [ -n "$val" ]; then
        echo "$var=$val" >> /etc/environment
    fi
done
```
cron에 환경변수를 전달하기 위해 시크릿 값을 `/etc/environment` 파일에 평문으로 기록한다. 컨테이너 내부에서 루트 권한을 가진 모든 프로세스(cron job 포함)가 이 파일을 읽을 수 있다. `docker exec`로 컨테이너에 진입하면 바로 확인 가능하다.

**심각도** MEDIUM  
**OWASP** A05:2021 — Security Misconfiguration  
**영향** 컨테이너 침해 시 API 키 전체가 단일 파일로 노출된다.

---

### SEC-C-009: docker-entrypoint.sh:6 — cron 환경에 GOOGLE_GEMINI_API_KEY, R2_SECRET_ACCESS_KEY 등 누락

**파일:라인** `docker-entrypoint.sh:6`, `crontab.docker:17-18`  
**증거**
```bash
# docker-entrypoint.sh — /etc/environment로 전달되는 변수
for var in DISCORD_WEBHOOK_URL BRAVE_API_KEY KIWOOM_APPKEY KIWOOM_SECRETKEY DART_API_KEY; do

# crontab.docker — GOOGLE_GEMINI_API_KEY, SANITY_API_WRITE_TOKEN, R2_SECRET_ACCESS_KEY를 요구하는 잡
50 7 * * 1-5 root ... python3 scripts/sync_to_r2.py    # R2_SECRET_ACCESS_KEY 필요
55 7 * * 1-5 root ... python3 scripts/publish_blog.py  # GOOGLE_GEMINI_API_KEY, SANITY_API_WRITE_TOKEN 필요
```
`sync_to_r2.py`는 `os.environ["CLOUDFLARE_ACCOUNT_ID"]`, `os.environ["R2_SECRET_ACCESS_KEY"]`를 직접 참조하고, `publish_blog.py`는 `os.environ["SANITY_API_WRITE_TOKEN"]`, `os.environ["GOOGLE_GEMINI_API_KEY"]`를 직접 참조한다. 그러나 이 변수들은 cron 환경 전달 목록에 없다. 이는 기능 오류이기도 하지만, 누락된 시크릿이 어떤 우회 경로로 cron에 전달되고 있는지 확인이 필요하다.

**심각도** MEDIUM  
**OWASP** A09:2021 — Security Logging and Monitoring Failures (설정 감사 누락)  
**영향** 잡이 KeyError로 조용히 실패하거나, 별도 경로로 시크릿이 주입되고 있다면 그 경로가 감사에서 누락된 것이다.

---

### SEC-C-010: Dockerfile:15 — `COPY . .`로 .env 외 민감 파일 빌드 이미지 포함 가능성

**파일:라인** `Dockerfile:15`  
**증거**
```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .    # .dockerignore 통과한 모든 파일 복사
```
`.dockerignore`에 `.env`가 명시적으로 제외되어 있다. 그러나 `.kiwoom_token.json`, `.claude/`, `.claude-logs/`는 `.dockerignore`에 있지만, 실수로 삭제하거나 새 시크릿 파일이 추가될 경우 빌드 이미지에 포함된다. `COPY . .` 패턴은 화이트리스트 방식보다 안전하지 않다.

**심각도** MEDIUM  
**OWASP** A05:2021 — Security Misconfiguration  
**영향** `.dockerignore` 누락 또는 업데이트 실수 시 시크릿이 이미지 레이어에 포함되어 `docker history` 또는 이미지 추출로 노출된다.

---

### SEC-C-011: docker-compose.yml:13-14 — Claude 인증 정보 컨테이너 마운트

**파일:라인** `docker-compose.yml:13-14`  
**증거**
```yaml
volumes:
  - ~/.claude:/root/.claude-host:ro
  - ~/.claude.json:/root/.claude-host.json:ro
```
호스트의 Claude 인증 파일(`~/.claude.json`, `~/.claude/`)을 컨테이너에 마운트하고, `docker-entrypoint.sh:18-20`에서 writable 위치에 복사(`cp -r /root/.claude-host/. /root/.claude/`)한다. 컨테이너 침해 시 Claude 계정 자격증명이 탈취된다. 또한 crontab에서 1분마다 credentials를 동기화(`cp /root/.claude-host/.credentials.json /root/.claude/.credentials.json`)하여 항상 최신 토큰이 유지된다.

**심각도** MEDIUM  
**OWASP** A05:2021 — Security Misconfiguration  
**영향** 컨테이너 침해 시 Claude 계정 탈취. 현재 아키텍처상 불가피하나 위험으로 명시해야 한다.

---

## LOW

---

### SEC-C-012: web-next/src/app/api/[...path]/route.ts:11 — Next.js 프록시 SSE에서도 CORS 와일드카드

**파일:라인** `web-next/src/app/api/[...path]/route.ts:11`  
**증거**
```typescript
const SSE_HEADERS = {
  'Content-Type': 'text/event-stream',
  'Cache-Control': 'no-cache',
  Connection: 'keep-alive',
  'Access-Control-Allow-Origin': '*',   // 하드코딩된 와일드카드
}
```
Flask 측 `ALLOWED_ORIGIN`와 별도로 Next.js 프록시 레이어에서도 SSE 및 AI 어드바이저 스트리밍 응답에 `Access-Control-Allow-Origin: *`가 하드코딩되어 있다. 환경변수화가 되어 있지 않으며, Flask의 `ALLOWED_ORIGIN` 설정을 개선해도 이 레이어는 별도로 수정해야 한다.

**심각도** LOW  
**OWASP** A05:2021 — Security Misconfiguration  
**영향** SSE 스트림을 통해 투자 이벤트 알림이 임의 오리진에 노출될 수 있다.

---

### SEC-C-013: web/server.py:75-77 — HTTP 액세스 로그 전면 억제

**파일:라인** `web/server.py:75-77`  
**증거**
```python
def log_message(self, format, *args):
    """기본 로그는 억제 (오류만 출력)."""
    pass
```
모든 HTTP 요청 로그가 `pass`로 억제된다. 비정상 접근, 반복 호출, 보안 관련 이벤트(`/api/run-pipeline` 호출 등)에 대한 감사 추적이 불가능하다.

**심각도** LOW  
**OWASP** A09:2021 — Security Logging and Monitoring Failures  
**영향** 침해 사고 발생 시 타임라인 재구성, 공격자 IP 추적이 불가능하다.

---

### SEC-C-014: Dockerfile:5 — Node.js + npm을 Python 서비스 이미지에 포함

**파일:라인** `Dockerfile:5`  
**증거**
```dockerfile
RUN apt-get update && apt-get install -y nodejs npm cron --no-install-recommends \
    && npm install -g @anthropic-ai/claude-code
```
Flask API 컨테이너에 Node.js, npm, `@anthropic-ai/claude-code` CLI가 설치된다. 공격 표면을 최소화하는 원칙(최소 권한)에 어긋난다. Claude CLI 호출은 `subprocess.run`으로 이루어지는데, Node.js 런타임 취약점이 Flask 컨테이너에도 영향을 미친다.

**심각도** LOW  
**OWASP** A05:2021 — Security Misconfiguration  
**영향** Node.js/npm 취약점이 Python API 서비스에도 영향을 미친다. 공격 표면 확대.

---

### SEC-C-015: Dockerfile, web-next/Dockerfile — 컨테이너 루트 사용자 실행

**파일:라인** `Dockerfile:26`, `web-next/Dockerfile:15`  
**증거**
```dockerfile
# 두 Dockerfile 모두 USER 지시어 없음
CMD ["/entrypoint.sh"]          # investment-bot: root 실행
CMD ["node", "server.js"]       # mc-web: root 실행
```
두 컨테이너 모두 `USER` 지시어가 없어 root(uid=0)로 프로세스가 실행된다. Flask 서버 침해 시 컨테이너 내 모든 파일(`/etc/environment`의 API 키, 마운트된 DB, 로그 등)에 대한 완전한 접근 권한이 주어진다.

**심각도** LOW  
**OWASP** A05:2021 — Security Misconfiguration  
**영향** 컨테이너 탈출 취약점 또는 애플리케이션 레벨 RCE 발생 시 피해 범위가 root 수준으로 확대된다.

---

## INFO

---

### SEC-C-016: web/server.py:37 — ALLOWED_ORIGIN 환경변수 존재하나 기본값 `*`

**파일:라인** `web/server.py:37`  
**증거**
```python
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")
```
CORS 오리진 제한 메커니즘은 구현되어 있다. `docker-compose.yml`의 `environment:` 블록에 `ALLOWED_ORIGIN=http://100.90.201.87:3000`을 추가하면 즉시 효과를 발휘한다. SEC-C-003과 연계하여 조치 권고.

**심각도** INFO  
**OWASP** A05:2021  
**영향** 환경변수 1줄 추가로 해결 가능.

---

### SEC-C-017: web/server.py:40 — 로그 이름 화이트리스트로 경로 순회 방지 구현

**파일:라인** `web/server.py:40`, `193-196`  
**증거**
```python
_ALLOWED_LOG_NAMES = {"marcus", "pipeline", "jarvis", "alerts_watch", "refresh_prices"}
if name not in _ALLOWED_LOG_NAMES:
    self.send_json({"error": "허용되지 않은 로그 이름"}, 400)
    return
```
`/api/logs` 엔드포인트에서 파일명 파라미터를 화이트리스트로 검증하여 경로 순회(Path Traversal)를 방어하고 있다. 긍정적인 보안 구현이다.

**심각도** INFO  
**OWASP** A05:2021  
**영향** 양호. 이 패턴을 다른 파일 접근 경로에도 일관 적용 권고.

---

## 조치 우선순위

| 우선순위 | 항목 | 조치 |
|---------|------|------|
| 1 | SEC-C-001 | `docker-compose.yml` 포트를 `127.0.0.1:8421:8421`로 변경 |
| 2 | SEC-C-002 | `/api/run-pipeline`, `/api/run-marcus` 등에 간단한 공유 시크릿 토큰 인증 추가 |
| 3 | SEC-C-003 | `docker-compose.yml` `environment:`에 `ALLOWED_ORIGIN=http://100.90.201.87:3000` 추가 |
| 4 | SEC-C-004 | `next.config.ts`에 `poweredByHeader: false` + 보안 헤더 추가 |
| 5 | SEC-C-005 | `server.py`의 모든 응답 코드 경로에 `X-Content-Type-Options`, `X-Frame-Options` 헤더 적용 |
| 6 | SEC-C-006 | `str(e)` 대신 제네릭 오류 메시지 반환 (`"잘못된 요청 형식"`) |
| 7 | SEC-C-007 | `docker-compose.yml`에 커스텀 네트워크 정의, `investment-bot` 포트 내부망 전용 격리 |
| 8 | SEC-C-013 | `log_message` 억제 해제 또는 보안 이벤트(POST 실행 엔드포인트)만 선택 로깅 |

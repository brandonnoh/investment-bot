# 암호화/시크릿 관리 보안 감사 보고서

**감사 일시:** 2026-05-02  
**감사 대상:** `/Users/jarvis/Projects/investment-bot`  
**감사 기준:** OWASP A02 (Cryptographic Failures), A07 (Identification and Authentication Failures)  
**감사 범위:** Python 백엔드, Next.js 프론트엔드, Docker 인프라, 시크릿 관리 전반

---

## 요약

| 심각도 | 건수 |
|--------|------|
| CRITICAL | 2 |
| HIGH | 4 |
| MEDIUM | 3 |
| LOW | 2 |
| INFO | 2 |

---

## 취약점 목록

---

### SEC-K-001: API 키 평문 하드코딩 — Claude 에이전트 메모리 파일

**위치:** `/Users/jarvis/.claude/projects/.../memory/reference_dart_api.md:7-11`

**증거:**
```
DART OpenAPI 인증키: `311eca264f4eddceb0e620e2974a5d4540c94d39`
- `.env`에 `DART_API_KEY=311eca264f4eddceb0e620e2974a5d4540c94d39` 로 저장
```
또한 `MEMORY.md:7`에 키 앞뒤를 마스킹(`311eca...c94d39`)한 상태로 참조.

**설명:** DART OpenAPI 인증키 전체 값이 Claude 에이전트 메모리 파일(로컬 파일시스템 평문 JSON)에 하드코딩되어 있다. 이 디렉토리는 `.gitignore`에 없으며, 향후 이 메모리가 다른 컨텍스트로 전달되면 키가 외부에 노출될 수 있다.

**심각도:** CRITICAL  
**OWASP:** A02 — Cryptographic Failures  
**영향:** DART API 키 탈취 시 공시 정보 무단 조회, API 쿼터 소진, 계정 정지 위험

---

### SEC-K-002: Gemini API 키가 HTTP 요청 URL 쿼리 파라미터에 노출

**위치:** `scripts/publish_blog.py:43`, `scripts/publish_blog.py:62`

**증거:**
```python
url = f"{GEMINI_BASE}/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
url = f"{GEMINI_BASE}/models/imagen-4.0-generate-001:predict?key={GEMINI_API_KEY}"
```
또한 실패 시 `resp.text[:200]`를 `print`로 출력(라인 85)하며, 이 내용이 `/app/logs/publish_blog.log`에 저장된다. Google API 오류 응답 본문에 요청 URL(키 포함)이 echo되는 경우가 있다.

**설명:** Google Gemini REST API 키를 URL 쿼리스트링에 포함시키는 방식은 HTTP 서버 액세스 로그, 프록시 로그, 브라우저 히스토리, Referrer 헤더 등에 키가 평문으로 기록된다. Google 공식 가이드는 API 키를 `x-goog-api-key` 헤더로 전달할 것을 권장한다.

**심각도:** CRITICAL  
**OWASP:** A02 — Cryptographic Failures  
**영향:** 서버 로그 열람 권한을 가진 누구든 Gemini API 키를 획득 가능. `/api/logs` 엔드포인트가 `publish_blog` 로그 이름을 허용한다면 더욱 심각 (현재는 허용 목록에 없음).

---

### SEC-K-003: Flask API 전 엔드포인트에 인증 없음 — 개인 금융 데이터 및 실행 권한 노출

**위치:** `web/server.py:37`, `docker-compose.yml:7-8`

**증거:**
```python
# server.py:37
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "")  # .env에 미설정 → 기본값 "*"

# docker-compose.yml
ports:
  - "8421:8421"  # 0.0.0.0:8421 바인딩 — 모든 인터페이스 노출
```
`.env`에 `ALLOWED_ORIGIN`이 설정되어 있지 않아 기본값 `"*"`(와일드카드)가 사용됨.

**설명:** Flask API(포트 8421)는 인증/인가 없이 다음 민감한 기능을 노출한다:
- `GET /api/wealth` — 전재산 이력(투자+비금융 자산) 반환
- `GET /api/data` — 포트폴리오 요약, 보유 종목 전체 노출
- `POST /api/run-pipeline` — 파이프라인(외부 API 호출 포함) 임의 실행 가능
- `POST /api/run-marcus` — Claude CLI 프로세스 임의 실행 가능
- `POST /api/investment-advice` — Claude API 키를 소비하는 호출 임의 실행 가능

포트 8421이 `0.0.0.0`에 바인딩되어, Tailscale 네트워크 내 모든 호스트가 인증 없이 접근 가능하다.

**심각도:** HIGH  
**OWASP:** A07 — Identification and Authentication Failures  
**영향:** Tailscale 네트워크 내 임의 클라이언트가 개인 금융 정보 열람, AI API 비용 강제 소비, 파이프라인 강제 실행 가능

---

### SEC-K-004: ANTHROPIC_API_KEY가 .env에 없음 — 폴백 메커니즘으로 Claude OAuth 토큰 컨테이너 내 노출

**위치:** `web/claude_caller.py:70-72`, `docker-entrypoint.sh:13-19`, `docker-compose.yml:13-14`

**증거:**
```python
# claude_caller.py:70
api_key = os.environ.get("ANTHROPIC_API_KEY", "")
if not api_key:
    raise RuntimeError("ANTHROPIC_API_KEY 없음")
# → API 키 없으면 Claude CLI + OAuth 폴백으로 진입
```
```yaml
# docker-compose.yml:13-14
volumes:
  - ~/.claude:/root/.claude-host:ro   # 호스트 OAuth 토큰 마운트
  - ~/.claude.json:/root/.claude-host.json:ro
```
```bash
# docker-entrypoint.sh:16-19
cp -r /root/.claude-host/. /root/.claude/  # writable 위치로 복사
```

**설명:** `.env`에 `ANTHROPIC_API_KEY`가 없다. 결과적으로 `claude_caller.py`는 항상 OAuth 토큰 폴백 경로를 사용한다. 호스트의 `~/.claude/` 디렉토리(OAuth `credentials.json` 포함)가 컨테이너에 마운트되고, 엔트리포인트에서 `/root/.claude/`로 복사되어 컨테이너 루트 유저가 OAuth 토큰에 접근 가능하다. 또한 cron 잡이 매 1분마다 토큰을 동기화(`cp /root/.claude-host/.credentials.json /root/.claude/.credentials.json`)하여 토큰이 지속적으로 컨테이너 내부에 존재한다.

**심각도:** HIGH  
**OWASP:** A02 — Cryptographic Failures, A07 — Identification and Authentication Failures  
**영향:** 컨테이너 탈출 또는 컨테이너 내 코드 실행 권한 획득 시 Claude OAuth 토큰 탈취 가능. 볼륨 마운트 경로(`ro`)가 컨테이너 내에서 writable 복사본을 만들므로 읽기 전용 제한이 실질적으로 우회됨.

---

### SEC-K-005: Docker entrypoint에서 일부 시크릿만 /etc/environment 전파 — cron 잡 시크릿 불일치

**위치:** `docker-entrypoint.sh:5-11`

**증거:**
```bash
for var in DISCORD_WEBHOOK_URL BRAVE_API_KEY KIWOOM_APPKEY KIWOOM_SECRETKEY DART_API_KEY; do
    val=$(printenv "$var" 2>/dev/null || true)
    if [ -n "$val" ]; then
        echo "$var=$val" >> /etc/environment
    fi
done
```
`/etc/environment`에 기록되지 않는 시크릿: `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `CLOUDFLARE_ACCOUNT_ID`, `SANITY_API_WRITE_TOKEN`, `GOOGLE_GEMINI_API_KEY`, `SANITY_PROJECT_ID`, `SANITY_DATASET`

**설명:** `sync_to_r2.py`(07:50 cron)와 `publish_blog.py`(07:55 cron)는 `os.environ["R2_ACCESS_KEY_ID"]` 등을 `[]` 접근으로 읽는다(KeyError 발생). Docker `env_file` 지시어는 Flask 프로세스 환경에만 주입되며 cron 데몬은 `/etc/environment`를 읽는다. 이 시크릿들이 `/etc/environment`에 없으면 cron 잡이 `KeyError`로 크래시한다.

**심각도:** HIGH (운영 가용성 + 시크릿 관리 일관성)  
**OWASP:** A02 — Cryptographic Failures (시크릿 관리 누락)  
**영향:** R2 업로드 및 블로그 발행 cron 잡 전체 실패. 오류 메시지에 환경변수명이 노출될 수 있음.

---

### SEC-K-006: Flask CORS — ALLOWED_ORIGIN 미설정으로 와일드카드 적용

**위치:** `web/server.py:37`

**증거:**
```python
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "")
# .env 확인 결과: ALLOWED_ORIGIN 항목 없음 → 런타임 값은 "*"
```
CORS 헤더: `Access-Control-Allow-Origin: *` (모든 오리진 허용)

**설명:** Flask API는 CORS 헤더로 `*`를 전송하여 모든 오리진에서의 cross-origin 요청을 허용한다. 인증이 없는 API와 결합되면, 임의 웹페이지가 방문자의 브라우저를 통해 Flask API를 호출하여 금융 데이터를 탈취하거나 파이프라인을 실행시킬 수 있다 (CSRF 유사 공격).

**심각도:** HIGH  
**OWASP:** A07 — Identification and Authentication Failures  
**영향:** 악의적 웹페이지가 방문자 브라우저를 경유해 Flask API의 쓰기 엔드포인트(run-pipeline, wealth/assets) 호출 가능

---

### SEC-K-007: Next.js SSE 프록시 응답에 Access-Control-Allow-Origin: * 설정

**위치:** `web-next/src/app/api/[...path]/route.ts:7-11`

**증거:**
```typescript
const SSE_HEADERS = {
  'Content-Type': 'text/event-stream',
  'Cache-Control': 'no-cache',
  Connection: 'keep-alive',
  'Access-Control-Allow-Origin': '*',
}
```
이 헤더는 SSE(`/api/events`)와 AI 어드바이저 스트리밍(`/api/investment-advice-stream`) 응답에 모두 적용됨.

**설명:** SSE 스트리밍 응답에 `*` CORS 헤더를 설정하면, 임의 오리진의 JavaScript가 실시간 시장 데이터 스트림과 AI 어드바이저 응답을 수신할 수 있다. SSE 연결은 쿠키 기반 세션이 없어도 유지된다.

**심각도:** MEDIUM  
**OWASP:** A07 — Identification and Authentication Failures  
**영향:** 크로스 오리진 사이트에서 EventSource를 통해 실시간 데이터 스트림 구독 가능

---

### SEC-K-008: Python 로그 파일이 볼륨 마운트로 호스트에 영구 저장 — 시크릿 간접 노출 위험

**위치:** `docker-compose.yml:11`, `crontab.docker` (모든 cron 잡의 `>> /app/logs/*.log`)

**증거:**
```yaml
volumes:
  - ./logs:/app/logs  # 호스트에 영구 마운트
```
```bash
# crontab.docker
python3 scripts/publish_blog.py >> /app/logs/publish_blog.log 2>&1
```
`publish_blog.py:85`: `print(f"[WARN] 이미지 생성 실패: {resp.status_code} {resp.text[:200]}")`

**설명:** Gemini API 오류 응답 본문이 최대 200자까지 로그에 기록된다. Google API 오류 응답 일부는 요청 URL(API 키 포함)을 반환한다. 이 로그는 호스트 `./logs/` 경로에 영구 저장되며, `/api/logs` 엔드포인트로 일부 로그가 노출된다(현재 `publish_blog`는 허용 목록 외). 또한 로그 로테이션 설정(매일 00:05)이 10MB 초과 시에만 압축하므로 장기간 평문 보존 가능.

**심각도:** MEDIUM  
**OWASP:** A02 — Cryptographic Failures  
**영향:** 로그 파일 접근 권한이 있는 공격자가 Gemini API 오류를 통해 키를 간접 획득 가능

---

### SEC-K-009: sync_to_r2.py 및 publish_blog.py — 시크릿 미설정 시 KeyError 크래시 (방어 코드 없음)

**위치:** `scripts/sync_to_r2.py:11-12,33-34`, `scripts/publish_blog.py:13,15-16`

**증거:**
```python
# sync_to_r2.py (모듈 최상위 레벨 — import 시 즉시 실행)
BUCKET = os.environ["R2_BUCKET_NAME"]        # 라인 11
ACCOUNT_ID = os.environ["CLOUDFLARE_ACCOUNT_ID"]  # 라인 12
```
```python
# publish_blog.py (모듈 최상위 레벨)
SANITY_PROJECT_ID = os.environ["SANITY_PROJECT_ID"]  # 라인 13
SANITY_TOKEN = os.environ["SANITY_API_WRITE_TOKEN"]  # 라인 15
GEMINI_API_KEY = os.environ["GOOGLE_GEMINI_API_KEY"] # 라인 16
```

**설명:** `os.environ["KEY"]` 패턴은 키 미설정 시 `KeyError`를 발생시켜 모듈 임포트 자체가 실패한다. 또한 이 변수들은 모듈 최상위 레벨에서 평가되므로, 스크립트 로드 시 즉시 환경 의존성이 생긴다. `os.environ.get()` + 명시적 빈값 검사 패턴을 사용하는 다른 모듈(`fetch_gold_krx.py` 등)과 일관성이 없다.

**심각도:** MEDIUM  
**OWASP:** A02 — Cryptographic Failures (시크릿 관리 패턴 불일치)  
**영향:** 환경변수 미설정 또는 SEC-K-005 문제 발생 시 cron 잡 전체 크래시, 오류 메시지에서 환경변수명 노출

---

### SEC-K-010: Flask API 포트 8421 — 0.0.0.0 바인딩으로 컨테이너 네트워크 전체 노출

**위치:** `docker-compose.yml:7`, `web/server.py` (ThreadingHTTPServer `""` 바인딩)

**증거:**
```yaml
ports:
  - "8421:8421"  # 호스트의 모든 인터페이스에 노출
```
```python
server = ThreadingHTTPServer(("", PORT), MissionControlHandler)  # "" = 0.0.0.0
```

**설명:** Flask API가 컨테이너 내부에서 `0.0.0.0:8421`로 리슨하고, docker-compose에서 `8421:8421`로 매핑되어 호스트의 모든 네트워크 인터페이스에 노출된다. Tailscale 외 다른 네트워크 인터페이스(로컬 네트워크 등)를 통해서도 접근 가능할 수 있다. SEC-K-003(인증 없음)과 결합되면 공격 표면이 넓다. `127.0.0.1:8421`로 바인딩하고 Next.js 컨테이너가 내부 네트워크로 접근하는 방식이 안전하다.

**심각도:** LOW  
**OWASP:** A07 — Identification and Authentication Failures  
**영향:** 로컬 네트워크 내 다른 기기에서 Flask API에 무단 접근 가능

---

### SEC-K-011: .kiwoom_token.json — .gitignore 등록 확인 완료, 그러나 Docker 빌드 컨텍스트 제외 필요

**위치:** `.gitignore:10`, `.dockerignore:14`

**증거:**
```
# .gitignore:10
.kiwoom_token.json

# .dockerignore:14  
.kiwoom_token.json
```
`git ls-files .kiwoom_token.json` 결과: 추적 없음 (올바름).  
파일 내용: `{"access_token": "<값>", "expires_at": "2026-05-05T05:30:05..."}`

**설명:** `.kiwoom_token.json`은 git과 Docker 빌드 컨텍스트 모두에서 올바르게 제외됨. 그러나 파일이 호스트 프로젝트 루트에 존재하며, 이 디렉토리가 Docker 볼륨으로 마운트되지 않아 컨테이너 접근 불가. 현재 관리 방식은 적절함.

**심각도:** LOW (현재 적절히 관리됨, 주의 유지 필요)  
**OWASP:** A02 — Cryptographic Failures  
**영향:** 현재 위험 낮음. 향후 `./` 디렉토리를 볼륨으로 마운트하면 컨테이너에서 접근 가능해짐.

---

### SEC-K-012: NEXT_PUBLIC_API_BASE — 비시크릿 설정값, 클라이언트 노출 적절

**위치:** `web-next/src/lib/api.ts:12-13`, 다수 컴포넌트

**증거:**
```typescript
const BASE = typeof window !== 'undefined' && process.env.NEXT_PUBLIC_API_BASE
  ? process.env.NEXT_PUBLIC_API_BASE
  : ''
```

**설명:** `NEXT_PUBLIC_` 접두사로 노출되는 환경변수는 `NEXT_PUBLIC_API_BASE`(Flask API URL) 하나뿐이다. 이 값은 개발 모드 전용으로 사용되며 API 키나 시크릿이 아니다. 프로덕션에서는 빈값(`''`)으로 상대 경로를 사용한다. API 키를 `NEXT_PUBLIC_` 접두사로 노출하는 사례는 없음.

**심각도:** INFO (취약점 없음, 확인 완료)  
**OWASP:** A02 — 해당 없음  
**영향:** 없음

---

## 추가 관찰 사항

### 양호한 보안 관행 (확인 완료)

1. **`.env` git 비추적:** `.gitignore:11`에 `.env` 등록, `git ls-files .env` 결과 빈값 — 시크릿이 git 이력에 없음.
2. **`.env` Docker 빌드 컨텍스트 제외:** `.dockerignore:13`에 `.env` 등록 — `COPY . .` 시 이미지에 포함 안 됨.
3. **Docker `env_file` 사용:** 시크릿을 `docker-compose.yml`에 하드코딩하지 않고 `env_file: - .env`로 주입.
4. **DART API 키 소스 코드 비포함:** `data/fetch_dart_corp_codes.py`, `data/fetch_fundamentals_sources.py` 모두 `os.environ.get()` 사용.
5. **Kiwoom 토큰 git 비추적:** `.gitignore`와 `.dockerignore` 모두에 `.kiwoom_token.json` 등록.
6. **Claude 자격증명 읽기 전용 마운트:** `docker-compose.yml:13`에서 `~/.claude:/root/.claude-host:ro` — 호스트 원본은 컨테이너에서 수정 불가.
7. **로그 엔드포인트 화이트리스트:** `server.py:40`에서 `_ALLOWED_LOG_NAMES` 집합으로 허용 로그만 노출.
8. **Anthropic API 헤더 전송:** `claude_caller.py`에서 API 키를 `x-api-key` 헤더로 전송(URL 제외).

---

## 우선순위별 조치 권고

| 우선순위 | 항목 | 조치 |
|----------|------|------|
| 즉시 | SEC-K-001 | Claude 메모리 파일의 DART API 키 삭제. 키 노출로 판단하여 DART에서 재발급 고려 |
| 즉시 | SEC-K-002 | `publish_blog.py`에서 Gemini API 키를 URL 쿼리 파라미터 대신 `x-goog-api-key` 헤더로 전환 |
| 단기 | SEC-K-005 | `docker-entrypoint.sh`의 `/etc/environment` 전파 목록에 R2/Sanity/Gemini/Cloudflare 키 추가 |
| 단기 | SEC-K-003 | Flask API에 간단한 Bearer 토큰 인증 추가 (최소: 내부 네트워크 전용 시크릿 헤더) |
| 단기 | SEC-K-006 | `.env`에 `ALLOWED_ORIGIN=http://100.90.201.87:3000` 설정 |
| 중기 | SEC-K-004 | `.env`에 `ANTHROPIC_API_KEY` 추가하여 OAuth 토큰 컨테이너 마운트 의존성 제거 |
| 중기 | SEC-K-010 | `docker-compose.yml`에서 Flask 포트를 `127.0.0.1:8421:8421`로 변경하여 루프백 전용 바인딩 |
| 중기 | SEC-K-009 | `sync_to_r2.py`, `publish_blog.py`에서 `os.environ["KEY"]` → `os.environ.get("KEY")` + 명시적 검사로 전환 |

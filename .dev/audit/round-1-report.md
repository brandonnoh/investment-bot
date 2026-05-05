# Round 1 보안 감사 리포트

**프로젝트:** investment-bot  
**감사 일시:** 2026-05-04  
**감사 범위:** Python 백엔드 (Flask), Next.js 프론트엔드, Docker 인프라, 의존성, 시크릿 관리  
**스캔 방법:** 8개 전문 에이전트 병렬 정적 분석  
**소스 에이전트:** auth-auditor, injection-hunter, crypto-auditor, api-security-auditor, supply-chain-auditor, config-auditor, data-integrity-auditor, client-security-auditor

---

## 감사 범위 요약

| 항목 | 내용 |
|------|------|
| 기술 스택 | Python 3.12 (BaseHTTPServer), Next.js 16.2.4, SQLite, Docker Compose |
| 인증 방식 | **없음** |
| API 서버 노출 | 0.0.0.0:8421 (Tailscale VPN 설계 의존) |
| 외부 API 의존 | DART, Yahoo Finance, Brave, Anthropic Claude, Gemini, Sanity, R2 |
| 총 감사 파일 수 | ~60개 이상 |
| 총 이슈 발견 | **67건** (중복 제거 후 45건) |

---

## 도메인별 요약

| 도메인 | CRITICAL | HIGH | MEDIUM | LOW | INFO |
|--------|----------|------|--------|-----|------|
| 인증/인가 | 1 | 5 | 1 | 1 | 0 |
| 암호화/시크릿 | 2 | 4 | 3 | 2 | 1 |
| 설정/배포 | 0 | 4 | 3 | 2 | 1 |
| 주입/경로 | 0 | 2 | 4 | 2 | 1 |
| 데이터/로그 | 1 | 2 | 3 | 1 | 1 |
| 공급망/의존성 | 0 | 1 | 3 | 1 | 1 |
| **합계** | **4** | **18** | **17** | **9** | **5** |

---

## CRITICAL 이슈

---

### SEC-C-001: `web/server.py` 전체 — Flask API 인증 완전 부재

- **에이전트:** auth-auditor, api-security-auditor, config-auditor, crypto-auditor, data-integrity-auditor (5개 에이전트 동시 발견)
- **OWASP:** A01 Broken Access Control, A07 Identification and Authentication Failures
- **파일:라인** `web/server.py:167–390` (do_GET, do_POST, do_PUT, do_DELETE 전체)
- **증거:**
  ```python
  def do_GET(self):
      # Authorization 헤더, API 키, 세션 검증 코드 없음
      if path == "/api/data":
          self._handle_api_data()
      # ...포트폴리오, 전재산, 분석 이력 모두 무인증 노출
  
  elif path == "/api/run-pipeline":
      result = api.run_background("pipeline", ["python3", "run_pipeline.py"])
      # subprocess.Popen 무인증 트리거
  ```
- **영향:** VPN 내 모든 주체가 개인 금융 데이터(평균단가, 수익률, 전재산) 열람, 파이프라인 강제 실행, Claude API 비용 강제 소비, 자산 데이터 변조/삭제 가능. 포트 8421이 0.0.0.0에 바인딩되어 LAN 전체에 동일 위험.
- **현재 완화 요소:** Tailscale VPN 네트워크 격리 (네트워크 레이어 의존)

---

### SEC-C-002: `scripts/publish_blog.py:43,62` — Gemini API 키 URL 쿼리 파라미터 노출

- **에이전트:** crypto-auditor
- **OWASP:** A02 Cryptographic Failures
- **파일:라인** `scripts/publish_blog.py:43`, `:62`
- **증거:**
  ```python
  url = f"{GEMINI_BASE}/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
  # API 오류 응답 바디 로그 기록 (라인 85)
  print(f"[WARN] 이미지 생성 실패: {resp.status_code} {resp.text[:200]}")
  ```
- **영향:** HTTP 서버 액세스 로그, 프록시 로그에 키 평문 기록. Google API 오류 응답이 요청 URL(키 포함)을 echo할 경우 `publish_blog.log`에 키 저장. 로그 파일 권한이 644이므로 읽기 가능.
- **수정 방향:** `x-goog-api-key` 헤더로 이동

---

### SEC-C-003: `db/history.db` — SQLite DB 평문 저장 + world-readable (644)

- **에이전트:** data-integrity-auditor
- **OWASP:** A02 Cryptographic Failures
- **파일:라인** `db/history.db`, `db/history_rebuilt.db`
- **증거:**
  ```
  -rw-r--r--@ 1 jarvis staff  2703360 history.db
  -rw-r--r--  1 jarvis staff 38400000 history_rebuilt.db
  ```
  `holdings`(종목·수량·평균단가·계좌), `transactions`(매매 내역), `total_wealth_history`, `portfolio_history`(holdings_snapshot), `analysis_history`(Claude 분석 전문), `advisor_strategies`(자본금·대출·전략) 전부 평문 저장.
- **영향:** 동일 OS 사용자, 동일 그룹 프로세스, 컨테이너 탈출 시 전체 금융 이력 일괄 추출. `history_rebuilt.db` 38MB가 방치 중.
- **수정 방향:** `chmod 600 db/*.db`, `history_rebuilt.db` 삭제

---

### SEC-C-004: Claude 메모리 파일 — DART API 키 평문 하드코딩

- **에이전트:** crypto-auditor
- **OWASP:** A02 Cryptographic Failures
- **파일:라인** `/Users/jarvis/.claude/projects/.../memory/reference_dart_api.md:7-11`
- **증거:**
  ```
  DART OpenAPI 인증키: `311eca264f4eddceb0e620e2974a5d4540c94d39`
  ```
  `MEMORY.md:7`에도 일부 마스킹 형태로 참조(`311eca...c94d39`).
- **영향:** 메모리 파일이 다른 컨텍스트로 전달되거나 git에 커밋될 경우 키 노출. DART 키 탈취 시 기업 공시 무단 조회, API 쿼터 소진, 계정 정지.
- **수정 방향:** 메모리 파일에서 키 값 삭제, DART에서 키 재발급 고려

---

## HIGH 이슈

---

### SEC-H-001: `web/server.py:37`, `route.ts:11` — CORS 와일드카드 기본값 (전 응답 경로)

- **에이전트:** auth-auditor, api-security-auditor, config-auditor, crypto-auditor, client-security-auditor
- **OWASP:** A05 Security Misconfiguration
- **증거:**
  ```python
  ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")  # docker-compose에 미설정
  ```
  ```typescript
  'Access-Control-Allow-Origin': '*'  // route.ts SSE 헤더 하드코딩
  ```
- **영향:** 임의 악성 웹페이지가 방문자 브라우저를 통해 Flask API를 호출, 포트폴리오 데이터 탈취 가능. 인증 레이어(쿠키) 추가 시 즉시 CSRF 경로.
- **수정 방향:** `.env`에 `ALLOWED_ORIGIN=http://100.90.201.87:3000` 설정, `route.ts` SSE 헤더도 환경변수 기반으로 변경

---

### SEC-H-002: `web/server.py:392` — SSE 무인증 + 연결 수 무제한

- **에이전트:** auth-auditor, api-security-auditor
- **OWASP:** A01 Broken Access Control
- **파일:라인** `web/server.py:392–431`
- **증거:**
  ```python
  with _sse_lock:
      _sse_clients.append(client_queue)  # 연결 수 제한 없음
  ```
- **영향:** 무인증 실시간 이벤트 구독. 다수 연결로 `ThreadingMixIn` 스레드 풀 고갈 → DoS.
- **수정 방향:** 연결 수 상한 설정(10개), X-API-Key 헤더 인증

---

### SEC-H-003: `route.ts:14-16` — Next.js 프록시 경로 무검증 (경로 인젝션/SSRF)

- **에이전트:** auth-auditor, client-security-auditor, supply-chain-auditor
- **OWASP:** A01 Broken Access Control, A03 Injection
- **파일:라인** `web-next/src/app/api/[...path]/route.ts:14-16`
- **증거:**
  ```typescript
  const pathStr = path.join('/')
  const url = `${API_BASE}/api/${pathStr}${req.nextUrl.search}`
  // 경로 화이트리스트, .. 정규화, 메서드 제한 없음
  ```
- **영향:** `../` 시퀀스로 Flask 내부 엔드포인트 우회 가능. PUT/DELETE 포함 모든 메서드 무조건 통과.
- **수정 방향:** 허용 경로 화이트리스트 또는 정규화된 경로가 `/api/`로 시작하는지 검증

---

### SEC-H-004: `web/server.py:347–390` — PUT/DELETE 자산/전략 무인증 변조·삭제

- **에이전트:** auth-auditor
- **OWASP:** A01 Broken Access Control
- **파일:라인** `web/server.py:371`
- **증거:**
  ```python
  def do_DELETE(self):
      asset_id = int(path.rsplit("/", 1)[-1])
      ok = ssot.delete_extra_asset_by_id(asset_id)  # 인증 없음
  ```
- **영향:** ID가 자동증가 정수이므로 순열 추정으로 비금융 자산 레코드 영구 삭제 가능.

---

### SEC-H-005: `web/server.py:121–138` — `/api/file` INTEL_FILES 화이트리스트 미적용

- **에이전트:** auth-auditor, api-security-auditor, config-auditor
- **OWASP:** A01 Broken Access Control
- **파일:라인** `web/server.py:135`
- **증거:**
  ```python
  elif name.endswith(".json"):
      self.send_file(api.INTEL_DIR / name, ...)  # INTEL_FILES 목록 비교 없음
  ```
- **영향:** `discovery_keywords.json`, `search_keywords.json`, `universe_cache.json` 등 비공개 분석 파일 접근 가능.
- **수정 방향:** `.md`는 `MD_FILES`, `.json`은 `INTEL_FILES` 목록 대조 추가

---

### SEC-H-006: `next.config.ts` — Next.js 보안 헤더 전무

- **에이전트:** config-auditor, client-security-auditor
- **OWASP:** A05 Security Misconfiguration
- **파일:라인** `web-next/next.config.ts:3-22`
- **증거:** `headers()` 배열에 CSP, X-Content-Type-Options, X-Frame-Options, HSTS, Referrer-Policy 전무. `poweredByHeader: false` 미설정으로 Next.js 버전 노출.
- **영향:** 클릭재킹, MIME 스니핑, XSS 방어선 부재.
- **수정 방향:** `next.config.ts` headers에 보안 헤더 추가, `poweredByHeader: false` 설정

---

### SEC-H-007: `web/server.py` send_file/SSE/스트리밍 — 보안 헤더 누락

- **에이전트:** auth-auditor, api-security-auditor, config-auditor
- **OWASP:** A05 Security Misconfiguration
- **파일:라인** `web/server.py:94-106` (send_file), `:392-431` (SSE), `:299-316` (스트리밍)
- **증거:** `send_json()`에만 `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` 설정. `send_file`, SSE, 스트리밍, 404/403 응답에는 없음.
- **수정 방향:** `send_headers_common()` 헬퍼 함수로 모든 응답 경로에 적용

---

### SEC-H-008: `web/claude_caller.py`, `docker-compose.yml:13-14` — OAuth 토큰 컨테이너 writable 복사

- **에이전트:** crypto-auditor, supply-chain-auditor
- **OWASP:** A02 Cryptographic Failures
- **파일:라인** `docker-entrypoint.sh:16-19`, `docker-compose.yml:13-14`
- **증거:**
  ```yaml
  volumes:
    - ~/.claude:/root/.claude-host:ro   # 읽기 전용 마운트
  ```
  ```bash
  cp -r /root/.claude-host/. /root/.claude/  # writable 경로로 복사 → ro 제한 우회
  ```
- **영향:** 컨테이너 탈출 또는 내부 코드 실행 시 Claude OAuth 토큰 탈취. cron이 매 1분 토큰 동기화.
- **수정 방향:** `.env`에 `ANTHROPIC_API_KEY` 추가하여 OAuth 토큰 의존성 제거

---

### SEC-H-009: `docker-entrypoint.sh:5-11` — cron 시크릿 불일치 (R2/Sanity/Gemini 누락)

- **에이전트:** crypto-auditor, config-auditor, supply-chain-auditor
- **OWASP:** A02 Cryptographic Failures (운영 가용성)
- **파일:라인** `docker-entrypoint.sh:5-11`
- **증거:**
  ```bash
  # /etc/environment에 기록하는 목록
  for var in DISCORD_WEBHOOK_URL BRAVE_API_KEY KIWOOM_APPKEY KIWOOM_SECRETKEY DART_API_KEY; do
  # 누락: R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, GOOGLE_GEMINI_API_KEY,
  #       SANITY_API_WRITE_TOKEN, SANITY_PROJECT_ID 등
  ```
- **영향:** `sync_to_r2.py`(07:50), `publish_blog.py`(07:55) cron 잡이 `KeyError`로 크래시. 매일 조용히 실패 중.
- **수정 방향:** 누락된 5개 환경변수를 `/etc/environment` 전파 목록에 추가

---

### SEC-H-010: `db/init_db.py:75,93` — PRAGMA/ALTER TABLE f-string SQL injection

- **에이전트:** injection-hunter
- **OWASP:** A03 Injection
- **파일:라인** `db/init_db.py:75`, `:93`
- **증거:**
  ```python
  cursor.execute(f"PRAGMA table_info({table_name})")       # 라인 75
  cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")  # 라인 93
  ```
- **현재 상태:** `MIGRATION_COLUMNS` 하드코딩 상수에서만 호출 → 직접 익스플로잇 경로 없음. 그러나 함수 시그니처 자체가 위험.
- **영향:** 미래 동적 호출 시 DDL 인젝션 → 테이블 삭제 가능.
- **수정 방향:** 테이블/컬럼명 식별자 화이트리스트 검증 추가

---

### SEC-H-011: `Dockerfile` / `web-next/Dockerfile` — root 사용자 실행

- **에이전트:** supply-chain-auditor, config-auditor
- **OWASP:** A05 Security Misconfiguration
- **증거:** 두 Dockerfile 모두 `USER` 지시어 없음 → 모든 프로세스가 uid=0(root)로 실행.
- **영향:** 컨테이너 탈출 또는 취약점 익스플로잇 시 호스트 root 권한 획득.
- **수정 방향:** `RUN useradd -m appuser && USER appuser`

---

### SEC-H-012: `output/intel/cio-briefing.md` — 644 권한 + 포트폴리오 상세 포함

- **에이전트:** data-integrity-auditor
- **OWASP:** A02 Cryptographic Failures
- **파일:라인** `output/intel/cio-briefing.md`
- **증거:**
  ```
  -rw-r--r-- 1 jarvis staff 7376 cio-briefing.md
  # 내용: 보유 종목별 현재가·평균단가 대비 수익률·매매 액션 포함
  ```
- **수정 방향:** `run_jarvis.py`에서 파일 생성 후 `os.chmod(OUTPUT_FILE, 0o600)` 추가

---

### SEC-H-013: `logs/*.log` — 644 권한 + 파이프라인 실행 이력

- **에이전트:** data-integrity-auditor
- **OWASP:** A09 Security Logging and Monitoring Failures
- **증거:**
  ```
  -rw-r--r-- 1 jarvis staff 17266110 refresh_prices.log
  -rw-r--r-- 1 jarvis staff   370778 pipeline.log
  ```
- **수정 방향:** `run_background()` 함수에서 `os.umask(0o077)` 후 로그 파일 오픈, 또는 생성 후 `chmod 600`

---

### SEC-H-014: `fetch_fundamentals_sources.py:164`, `:415` — DART API 키 URL 쿼리 파라미터

- **에이전트:** data-integrity-auditor, crypto-auditor
- **OWASP:** A09 Security Logging and Monitoring Failures
- **파일:라인** `data/fetch_fundamentals_sources.py:164-166`, `:415`
- **증거:**
  ```python
  url = f"https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json?crtfc_key={api_key}&..."
  ```
- **영향:** 네트워크 오류 시 `{e}` 내부에 URL이 로그에 기록 → DART 키 간접 노출.
- **수정 방향:** `crtfc_key`를 Authorization 헤더로 이동 (DART API 지원 여부 확인 후)

---

### SEC-H-015: `scripts/run_marcus.py`, `web/claude_caller.py` — Claude AI에 포트폴리오 평균단가·손익 전송

- **에이전트:** data-integrity-auditor
- **OWASP:** A02 Cryptographic Failures
- **파일:라인** `scripts/run_marcus.py:441-477`, `web/advisor_data.py:100-143`
- **증거:** `portfolio_summary.json`의 `avg_cost`, `qty`, `pnl_krw` 필드가 Anthropic 서버로 전송되는 프롬프트에 직접 포함.
- **영향:** 개인 금융 정보가 제3자(Anthropic) 서버에 전송. 데이터 학습 활용 약관 위험.
- **수정 방향:** avg_cost → 범주형 표현(예: "수익 +10% 구간"), 절대값 대신 비중 비율 전달

---

## MEDIUM 이슈

---

### SEC-M-001: `web/server.py:340-345` — Content-Length 기반 Slowloris 변형 DoS

- **OWASP:** A03 Injection
- `Content-Length`를 실제 바디보다 크게 지정 시 `rfile.read(length)` 블로킹 → 스레드 점유.
- **수정 방향:** `read_timeout` 설정 또는 `Content-Length` 상한 + 소켓 타임아웃

---

### SEC-M-002: `web/api_company.py:77-86` — LIKE 와일드카드 미이스케이프

- **OWASP:** A03 Injection
- `ticker=%`로 호출 시 news 테이블 전체 스캔. SQL 인젝션은 아니나 DB DoS.
- **수정 방향:** `pat = f"%{code.replace('%','').replace('_','')}%"` 또는 ESCAPE 절 사용

---

### SEC-M-003: `web/server.py:124` — `/api/file` path traversal 방어 불완전

- **OWASP:** A03 Injection
- `/`, `\` 문자열 검사만 존재. `resolve().is_relative_to(INTEL_DIR)` 검증 없음.
- **수정 방향:** `resolved = (INTEL_DIR / name).resolve()` 후 `is_relative_to(INTEL_DIR)` 검증

---

### SEC-M-004: `scripts/run_marcus.py:258-265` — Discord Webhook URL SSRF 가능성

- **OWASP:** A10 Server-Side Request Forgery
- `DISCORD_WEBHOOK_URL` 환경변수를 스킴·도메인 검증 없이 `urlopen`에 직접 전달.
- **수정 방향:** URL이 `https://discord.com/` 또는 `https://discordapp.com/` 시작 여부 검증

---

### SEC-M-005: `data/fetch_news.py:46,304` — 외부 키워드 로그 출력 (Log Injection)

- **OWASP:** A03 Injection
- Claude가 뉴스 기반으로 생성한 키워드가 이스케이프 없이 stdout → `/api/logs` 경유 → 프론트엔드.
- **수정 방향:** 로그 출력 시 `\r\n` 제거 또는 키워드 길이/문자 제한

---

### SEC-M-006: `web/server.py:292,334,366` — `str(e)` HTTP 응답 노출

- **OWASP:** A09 Security Logging and Monitoring Failures
- `KeyError`, `ValueError`의 상세 내용이 HTTP 응답에 그대로 포함. 내부 필드명, 타입 구조 노출.
- **수정 방향:** 제너릭 메시지 반환 + 서버 측 로그에만 상세 기록

---

### SEC-M-007: `requirements.txt` — Python 의존성 버전 미고정 + lockfile 없음

- **OWASP:** A06 Vulnerable and Outdated Components
- `yfinance>=0.2`, `pytest>=7.0`, `ruff>=0.4.0` 범위 지정. Lockfile 없어 빌드 재현성 없음.
- **수정 방향:** `pip freeze > requirements-lock.txt` 또는 `uv lock`

---

### SEC-M-008: `Dockerfile:1`, `web-next/Dockerfile:1` — 이미지 digest 미고정

- **OWASP:** A06 Vulnerable and Outdated Components
- `python:3.12-slim`, `node:20-alpine` 태그만 사용. `npm install -g @anthropic-ai/claude-code` 버전 미지정.
- **수정 방향:** `python:3.12-slim@sha256:...` 또는 정확한 마이너 버전 고정

---

### SEC-M-009: `docker-entrypoint.sh:6-10` — 시크릿을 `/etc/environment` (0644) 평문 기록

- **OWASP:** A02 Cryptographic Failures
- 5개 API 키가 `/etc/environment` (world-readable)에 평문 기록.
- **수정 방향:** `chmod 600 /etc/environment`, 또는 envdir 패턴으로 대체

---

### SEC-M-010: `web-next/src/lib/format.ts`, `localStorage` — 재무 설정 localStorage 저장

- **OWASP:** A02 Cryptographic Failures
- `mc-advisor-settings` 키에 `capital`(자본금), 대출 금액, 금리가 평문으로 localStorage 저장.
- **수정 방향:** 민감 필드는 서버 세션에만 저장 또는 암호화

---

### SEC-M-011: `DrawerSections.tsx`, `DiscoveryTab.tsx` — news URL javascript: 스킴 미차단

- **OWASP:** A03 Injection (DOM XSS)
- `item.url`, `profile.website`를 `<a href>`에 검증 없이 삽입. `rel="noopener noreferrer"`는 있으나 `javascript:` 스킴 차단 없음.
- **수정 방향:** `url.startsWith('https://') || url.startsWith('http://')` 검증 후 렌더링

---

### SEC-M-012: `web-next/package.json` — npm ^ 범위 의존성 + postcss XSS 취약 번들

- **OWASP:** A06 Vulnerable and Outdated Components
- `next@16.2.4` 내부 번들 `postcss@8.4.31`이 GHSA-qx2v-qp2m-jg93 (XSS) 취약.
- **수정 방향:** next.js 최신 버전으로 업그레이드

---

### SEC-M-013: `docker-compose.yml:13-14` — 호스트 `~/.claude/` 자격증명 컨테이너 마운트

- **OWASP:** A02 Cryptographic Failures
- 호스트 OAuth 토큰이 컨테이너에 마운트 + writable 경로로 복사 (SEC-H-008과 관련).
- **수정 방향:** ANTHROPIC_API_KEY 환경변수 직접 사용으로 대체 시 마운트 불필요

---

### SEC-M-014: `output/intel/` — 파일 권한 혼재 (민감 파일이 644)

- **OWASP:** A02 Cryptographic Failures
- `cio-briefing.md`(포트폴리오 상세), `universe_cache.json`(672종목 재무) 등이 644.
- **수정 방향:** 파이프라인 실행 후 `chmod 600 output/intel/*.json output/intel/*.md`

---

### SEC-M-015: `web/server.py:340` — POST 바디 Content-Type 미검증

- **OWASP:** A04 Insecure Design
- Content-Type 검증 없이 JSON 파싱. 잘못된 JSON 입력 시 try/except 없는 경로에서 HTTP 500.
- **수정 방향:** `Content-Type: application/json` 확인 + `JSONDecodeError` 캐치

---

### SEC-M-016: `web/api_advisor.py:18-36` — advisor_strategies 데이터 보존 정책 없음

- **OWASP:** A02 Cryptographic Failures
- `total_wealth_history`, `portfolio_history`, `analysis_history`, `advisor_strategies` 무기한 누적.
- **수정 방향:** `maintenance.py`에 보존 기간 정책 추가 (wealth 2년, analysis 1년, advisor 6개월)

---

## LOW 이슈

---

### SEC-L-001: `docker-compose.yml:7,39` — Flask/Next.js 포트 0.0.0.0 바인딩

- **OWASP:** A05 (VPN 설계로 부분 완화)
- `127.0.0.1:8421:8421`로 변경 시 LAN 직접 접근 차단

---

### SEC-L-002: `requirements.txt` — boto3/requests 미선언 의존성

- **OWASP:** A06 — 실제 사용 중인 패키지가 requirements.txt에 없음

---

### SEC-L-003: `db/history.db.bak`, `db/history_rebuilt.db` — 복구 임시 파일 미정리

- 38MB 전체 금융 이력 DB 복사본 방치. `history_rebuilt.db`는 644 권한.

---

### SEC-L-004: `web/server.py:192-199` — `/api/logs` 로그 내용 무인증 노출

- 화이트리스트로 path traversal 차단되나, 로그 파일 내용 자체는 인증 없이 노출.

---

### SEC-L-005: `web/api_company.py:74-87` — ticker 파라미터 길이 제한 없음

- 매우 긴 ticker로 LIKE 쿼리 CPU 부하 유발 가능. 실질 피해 제한적.

---

### SEC-L-006: `scripts/sync_to_r2.py:11`, `publish_blog.py:13` — `os.environ["KEY"]` 패턴

- 키 미설정 시 모듈 import 자체 실패. `os.environ.get()` + 명시적 검사로 일관성 확보 필요.

---

### SEC-L-007: `web-next/Dockerfile` — `.dockerignore` 없음

- `node_modules` 등이 builder 레이어에 포함될 수 있음.

---

### SEC-L-008: `web/server.py:340` — Discord 알림에 내부 오류 메시지 포함

- Marcus 분석 실패 시 `error_msg`가 Discord(외부 서버)로 전송. 내부 경로 포함 가능.

---

### SEC-L-009: `web/server.py:473` — Flask 포트 `""` 바인딩 (SEC-L-001과 동일 근원)

---

## INFO

---

### SEC-I-001: `NEXT_PUBLIC_API_BASE` — 클라이언트 노출 적절 (취약점 없음)

API 키가 아닌 Flask URL만 포함. 프로덕션에서 빈값 사용. ✅

---

### SEC-I-002: `crontab.docker` — 시크릿 하드코딩 없음 (양호)

환경변수 참조 방식 사용. ✅

---

### SEC-I-003: `.env` git 비추적, `.dockerignore` 등록 (양호)

`git ls-files .env` 빈값 확인. ✅

---

### SEC-I-004: `/api/file` URL 인코딩 path traversal 방어 동작 중

`parse_qs`가 `%2F`를 `/`로 디코딩 → 현재 검사에서 차단됨. 단, `resolve()` 기반 검증 없음(SEC-M-003).

---

### SEC-I-005: `dangerouslySetInnerHTML` 미사용, `rehype-raw` 미포함 (양호)

react-markdown HTML 태그 렌더링 기본 차단됨. ✅

---

## 수정 작업 리스트 (/wj:loop plan 호환)

### Wave 1 — CRITICAL (즉시)

| ID | 파일 | 에이전트 | 작업 |
|----|------|---------|------|
| SEC-C-001 | `web/server.py` | backend-dev | X-API-Key 헤더 기반 인증 미들웨어 추가 |
| SEC-C-002 | `scripts/publish_blog.py` | backend-dev | Gemini API 키 → `x-goog-api-key` 헤더로 이동 |
| SEC-C-003 | `db/history.db` | backend-dev | `chmod 600 db/*.db`, `history_rebuilt.db` 삭제 |
| SEC-C-004 | memory 파일 | 직접 수정 | DART API 키 메모리 파일에서 삭제 |

### Wave 2 — HIGH 우선순위 (단기)

| ID | 파일 | 에이전트 | 작업 |
|----|------|---------|------|
| SEC-H-001 | `.env`, `route.ts` | backend-dev + frontend-dev | ALLOWED_ORIGIN 설정, SSE 헤더 환경변수화 |
| SEC-H-005 | `web/server.py` | backend-dev | `/api/file` INTEL_FILES 화이트리스트 적용 |
| SEC-H-006 | `next.config.ts` | frontend-dev | 보안 헤더 추가, poweredByHeader: false |
| SEC-H-007 | `web/server.py` | backend-dev | send_headers_common() 헬퍼로 모든 응답에 보안 헤더 |
| SEC-H-009 | `docker-entrypoint.sh` | 직접 수정 | R2/Sanity/Gemini 키 /etc/environment 전파 추가 |
| SEC-H-012 | `scripts/run_jarvis.py` | backend-dev | 출력 파일 chmod 600 |
| SEC-H-013 | `web/api.py` | backend-dev | 로그 파일 umask 0o077 또는 생성 후 chmod 600 |
| SEC-H-014 | `data/fetch_fundamentals_sources.py` | backend-dev | DART 키 URL → 로그 마스킹 또는 헤더 이동 |

### Wave 3 — HIGH 보완 + MEDIUM (중기)

| ID | 파일 | 에이전트 | 작업 |
|----|------|---------|------|
| SEC-H-002 | `web/server.py` | backend-dev | SSE 연결 수 상한, 인증 적용 |
| SEC-H-003 | `route.ts` | frontend-dev | 프록시 경로 화이트리스트 또는 정규화 검증 |
| SEC-H-008 | `.env`, `docker-entrypoint.sh` | backend-dev | ANTHROPIC_API_KEY 추가, OAuth 마운트 의존 제거 |
| SEC-H-010 | `db/init_db.py` | backend-dev | 테이블/컬럼명 화이트리스트 검증 |
| SEC-H-011 | `Dockerfile`, `web-next/Dockerfile` | 직접 수정 | USER 지시어 추가 |
| SEC-M-001 | `web/server.py` | backend-dev | Slowloris 대응 소켓 타임아웃 |
| SEC-M-002 | `web/api_company.py` | backend-dev | LIKE 와일드카드 이스케이프 |
| SEC-M-003 | `web/server.py` | backend-dev | resolve().is_relative_to() 검증 |
| SEC-M-006 | `web/server.py`, `api.py` | backend-dev | str(e) → 제너릭 에러 메시지 |
| SEC-M-011 | `DrawerSections.tsx` 등 | frontend-dev | URL 스킴 검증 |

---

*이 리포트는 정적 분석만으로 작성되었습니다. 실제 익스플로잇 가능성은 네트워크 환경(Tailscale VPN)에 따라 달라질 수 있습니다.*

# 보안 감사 최종 리포트

**프로젝트:** investment-bot  
**감사 완료:** 2026-05-04  
**감사 방식:** 8개 전문 에이전트 병렬 정적 분석 → 3개 검증 에이전트 (오탐 검증 + 연쇄 공격 + ASVS 컴플라이언스)  
**총 분석 파일:** ~60개 이상  

---

## 최종 이슈 집계

| 심각도 | 건수 | 비고 |
|--------|------|------|
| **CRITICAL** | **4** | 전체 확정 |
| **HIGH** | **18** | 2건 오탐 제거 + 2건 신규 추가 (순 동일) |
| **MEDIUM** | **16** | 1건 오탐 제거 |
| **LOW** | **9** | 전체 확정 |
| **INFO** | **5** | 전체 확정 |
| **합계** | **52** | 오탐 3건 제거됨 |

---

## 오탐 제거 목록 (수정 작업에서 제외)

| ID | 판정 근거 |
|----|-----------|
| **SEC-H-010** (PRAGMA f-string SQL injection) | `_migrate_add_column` 호출자가 `MIGRATION_COLUMNS` 하드코딩 상수뿐. 외부 입력 경로 전무. |
| **SEC-H-014** (DART API 키 URL 로그 노출) | `urllib.error.HTTPError.__str__()`은 URL을 포함하지 않음. `str(e)` 보간 시 `"HTTP Error 401: Unauthorized"` 형태만 출력. |
| **SEC-M-004** (Discord Webhook SSRF) | `DISCORD_WEBHOOK_URL`은 `.env`에서만 설정. API 엔드포인트를 통한 환경변수 변조 경로 없음. 사전 침해 없이 성립 불가. |

---

## Phase 3 신규 발견 (컴플라이언스 검증)

### SEC-ADD-001 (HIGH): `data/fetch_solar_base.py:37-39` — SSL 인증서 검증 완전 비활성화

- **OWASP:** A05 Security Misconfiguration / ASVS V9.1.2
- **증거:**
  ```python
  _SSL_UNVERIFIED = ssl.create_default_context()
  _SSL_UNVERIFIED.check_hostname = False
  _SSL_UNVERIFIED.verify_mode = ssl.CERT_NONE
  ```
  모든 태양광 크롤러(`fetch_solar_*.py` 8개 모듈)가 이 컨텍스트를 공유 사용.
- **영향:** MITM 공격 시 위조된 TLS 인증서를 수용. 크롤러가 공격자 서버의 응답을 신뢰 데이터로 처리. 태양광 매물 데이터 오염 가능.
- **수정:** `ssl.create_default_context()` (기본값) 사용. 인증서 오류 시 개별 사이트 예외 처리.

---

### SEC-ADD-002 (HIGH): `web/server.py:75-77` — HTTP 액세스 로그 전면 차단

- **OWASP:** A09 Security Logging and Monitoring Failures / ASVS V7.1.1
- **증거:**
  ```python
  def log_message(self, format, *args):
      pass  # 모든 HTTP 접근 로그를 의도적으로 차단
  ```
- **영향:** 비인가 API 접근, 파이프라인 강제 실행, 자산 삭제 등 모든 보안 이벤트가 로그에 기록되지 않음. 사고 발생 시 포렌식 불가.
- **수정:** 보안 관련 이벤트(4xx, 5xx, POST, PUT, DELETE)는 별도 로그로 기록.

---

## 연쇄 공격 시나리오 요약 (6건)

| 체인 | 진입점 | 연결 취약점 | 최종 영향 | 난이도 | 즉시 차단 링크 |
|------|--------|------------|-----------|--------|--------------|
| **Chain-001** | 악성 웹페이지 | CORS `*` + 무인증 | Claude API 비용 강제 소진 + 파이프라인 데이터 오염 | **낮음** | `.env` ALLOWED_ORIGIN 1줄 |
| **Chain-002** | `publish_blog.py` | Gemini 키 URL → 로그 → `/api/logs` | Gemini API 키 탈취 (현재 진행 중 가능성) | **낮음** | `x-goog-api-key` 헤더 2줄 |
| **Chain-003** | Next.js 프록시 | 경로 인젝션 → `/api/file` 무화이트리스트 | 비공개 분석 파일 유출 (672종목 재무 포함) | 중간 | INTEL_FILES 화이트리스트 3줄 |
| **Chain-004** | RSS/뉴스 오염 | 로그 인젝션 → `/api/logs` → 프론트엔드 렌더링 | DOM XSS → 포트폴리오 탈취 | 높음 | 로그 CRLF 이스케이프 |
| **Chain-005** | VPN 내부 기기 | 무인증 DELETE + 정수 ID 열거 | 비금융 자산 레코드 영구 삭제 | 낮음 | X-API-Key 인증 미들웨어 |
| **Chain-006** | 컨테이너 탈출 | root 실행 + OAuth 토큰 writable 복사 | Claude OAuth + 5개 API 키 전체 탈취 | 높음 | USER 지시어 + API 키 환경변수 전환 |

> **⚠️ Chain-002는 현재 활성 가능성:** `docker-entrypoint.sh`에 `GOOGLE_GEMINI_API_KEY` 누락(SEC-H-009)으로 `publish_blog.py` cron이 `KeyError` 크래시 중. 크래시 스택 트레이스 + API 오류 응답이 로그에 기록될 수 있음.

---

## OWASP ASVS L2 주요 미준수 항목

| ASVS | 요구사항 | 상태 | 관련 이슈 |
|------|---------|------|-----------|
| V2.1/V4.1 | 인증 및 접근 제어 | ❌ 전면 부재 | SEC-C-001 |
| V6.1.2/V8.3.1 | 전송 암호화 | ❌ HTTP 평문 | N/A (TLS 추가 필요) |
| V7.1.1 | 보안 이벤트 로깅 | ❌ 전면 차단 | SEC-ADD-002 |
| V9.1.1 | TLS 1.2+ 적용 | ❌ HTTP만 | N/A |
| V9.1.2 | 서버 인증서 검증 | ❌ CERT_NONE | SEC-ADD-001 |
| V13.1.3 | API 레이트 리미팅 | ❌ 미구현 | SEC-H-002 |
| V14.4.1/V14.4.6 | HTTP 보안 헤더 + CSP | ❌ 전무 | SEC-H-006, SEC-H-007 |

**N/A 확정 항목:** V3 Session Management (stateless), V12 File Upload (기능 없음), V11 Business Logic (자동 매매 없음)

---

## CRITICAL 이슈 (4건)

### SEC-C-001 — `web/server.py` 전체: Flask API 인증 완전 부재
- 5개 에이전트 동시 발견. `do_GET/POST/PUT/DELETE` 전체 경로 인증 코드 없음.
- 개인 금융 데이터 열람, 파이프라인 실행, 자산 변조/삭제 무제한 허용.
- **수정:** X-API-Key 헤더 기반 미들웨어 (do_GET 진입 시점 단일 검증)

### SEC-C-002 — `scripts/publish_blog.py:43,62`: Gemini API 키 URL 쿼리 파라미터 노출
- `?key={GEMINI_API_KEY}` URL에 직접 삽입. `publish_blog.log`(644) + Google 서버 액세스 로그에 평문 기록.
- **수정:** `x-goog-api-key: {GEMINI_API_KEY}` 헤더로 이동

### SEC-C-003 — `db/history.db` 644 권한 + `history_rebuilt.db` 38MB 방치
- 포트폴리오 이력, 매매 내역, 전재산 이력, Claude 분석 전문 전부 평문 world-readable.
- **수정:** `chmod 600 db/history.db` + `rm db/history_rebuilt.db`

### SEC-C-004 — Claude 메모리 파일 DART API 키 평문 하드코딩
- `reference_dart_api.md:7-11`에 `311eca264f4eddceb0e620e2974a5d4540c94d39` 평문 기록.
- **수정:** 파일에서 키 값 삭제 + DART 키 재발급 권고

---

## HIGH 이슈 (18건)

| ID | 파일 | 설명 |
|----|------|------|
| SEC-H-001 | `server.py:37`, `route.ts:11` | CORS `*` 기본값 — 외부 브라우저 접근 허용 |
| SEC-H-002 | `server.py:392` | SSE 무인증 + 연결 수 무제한 (ThreadingMixIn DoS) |
| SEC-H-003 | `route.ts:14-16` | Next.js 프록시 경로 무검증 (경로 인젝션/SSRF) |
| SEC-H-004 | `server.py:371` | PUT/DELETE 자산 무인증 변조·삭제 (정수 ID 열거 가능) |
| SEC-H-005 | `server.py:135` | `/api/file` INTEL_FILES 화이트리스트 미적용 |
| SEC-H-006 | `next.config.ts` | Next.js 보안 헤더 전무 (CSP, X-Frame-Options 등) |
| SEC-H-007 | `server.py` 응답 경로 전체 | send_file/SSE/스트리밍 응답 보안 헤더 누락 |
| SEC-H-008 | `docker-entrypoint.sh:16-19` | OAuth 토큰 ro 마운트 → writable 복사 |
| SEC-H-009 | `docker-entrypoint.sh:5-11` | cron 시크릿 불일치 — R2/Sanity/Gemini 키 5종 누락 (운영 장애 활성) |
| SEC-H-011 | `Dockerfile` 2개 | root 사용자 실행 — USER 지시어 없음 |
| SEC-H-012 | `output/intel/cio-briefing.md` | 포트폴리오 상세 포함 파일 644 권한 |
| SEC-H-013 | `logs/*.log` | 파이프라인 로그 644 권한 (17MB refresh_prices.log) |
| SEC-H-015 | `run_marcus.py:441-477` | 포트폴리오 avg_cost·qty·pnl_krw를 Anthropic 서버 전송 |
| SEC-ADD-001 | `fetch_solar_base.py:37-39` | SSL 인증서 검증 완전 비활성화 (CERT_NONE) |
| SEC-ADD-002 | `server.py:75-77` | HTTP 액세스 로그 전면 차단 — 보안 이벤트 기록 불가 |
| V2.2.1 gap | `/api/run-pipeline`, `/api/run-marcus` | 레이트 리미팅 없음 — Claude API 비용 강제 소진 가능 |
| V1.2.1 gap | `route.ts` | 프록시 신뢰 경계 정의 없음 — Flask에 모든 요청 무조건 전달 |
| V13.1.3 gap | `server.py` 전체 | API 레이트 리미팅 미구현 |

---

## MEDIUM 이슈 (16건)

| ID | 파일 | 설명 |
|----|------|------|
| SEC-M-001 | `server.py:340-345` | Slowloris 변형 DoS — 소켓 타임아웃 없음 |
| SEC-M-002 | `api_company.py:79` | LIKE 와일드카드 미이스케이프 → DB DoS |
| SEC-M-003 | `server.py:124` | `/api/file` path traversal 방어 불완전 (resolve 미검증) |
| SEC-M-005 | `fetch_news.py:46,304` | 외부 키워드 로그 CRLF 미이스케이프 |
| SEC-M-006 | `server.py` 다수 | `str(e)` HTTP 응답 노출 — 내부 필드명 노출 |
| SEC-M-007 | `requirements.txt` | Python 의존성 버전 미고정 + lockfile 없음 |
| SEC-M-008 | `Dockerfile` 2개 | 이미지 digest 미고정 |
| SEC-M-009 | `docker-entrypoint.sh` | `/etc/environment` 0644 — 5개 API 키 world-readable |
| SEC-M-010 | `localStorage` | 자본금·대출 금액 localStorage 평문 저장 |
| SEC-M-011 | `DrawerSections.tsx` | `profile.website`, `item.url` javascript: 스킴 미차단 |
| SEC-M-012 | `package.json` | `postcss@8.4.31` GHSA-qx2v-qp2m-jg93 XSS 취약 번들 |
| SEC-M-013 | `docker-compose.yml` | `~/.claude/` 자격증명 컨테이너 마운트 (SEC-H-008 동일 근원) |
| SEC-M-014 | `output/intel/` | 민감 파일 644 혼재 (`universe_cache.json`, `screener_results.json` 등) |
| SEC-M-015 | `server.py:340` | POST 바디 Content-Type 미검증 |
| SEC-M-016 | `api_advisor.py` | advisor_strategies 데이터 보존 정책 없음 |
| V8.1.1 gap | `send_json()` | 금융 API 응답 `Cache-Control: no-store` 없음 |

---

## LOW 이슈 (9건)

| ID | 설명 |
|----|------|
| SEC-L-001 | Flask 포트 0.0.0.0 바인딩 — `127.0.0.1` 변경 권고 |
| SEC-L-002 | `boto3`, `requests` requirements.txt 미선언 |
| SEC-L-003 | `db/history_rebuilt.db`(38MB), `db/history.db.bak` 방치 |
| SEC-L-004 | `/api/logs` 로그 내용 무인증 노출 |
| SEC-L-005 | ticker 파라미터 길이 제한 없음 |
| SEC-L-006 | `os.environ["KEY"]` 패턴 — 미설정 시 import 실패 |
| SEC-L-007 | `web-next/Dockerfile` .dockerignore 없음 |
| SEC-L-008 | Discord 알림에 내부 오류 메시지 포함 |
| SEC-L-009 | `ThreadingHTTPServer(("", PORT))` 빈 문자열 바인딩 |

---

## 수정 작업 리스트

### Wave 1 — CRITICAL (즉시, 오늘)

| ID | 파일 | 에이전트 | 작업 |
|----|------|---------|------|
| **SEC-C-001** | `web/server.py` | backend-dev | X-API-Key 헤더 기반 인증 미들웨어 (do_GET/POST/PUT/DELETE 진입점) |
| **SEC-C-002** | `scripts/publish_blog.py` | backend-dev | Gemini API 키 → `x-goog-api-key` 헤더로 이동 |
| **SEC-C-003** | `db/` | 직접 명령 | `chmod 600 db/history.db` + `rm db/history_rebuilt.db` |
| **SEC-C-004** | 메모리 파일 | 직접 수정 | `reference_dart_api.md`에서 키 값 삭제 |
| **SEC-H-009** | `docker-entrypoint.sh` | backend-dev | R2/Sanity/Gemini 키 5종 `/etc/environment` 전파 목록 추가 (운영 장애 해소) |

### Wave 2 — HIGH 우선순위 (이번 주)

| ID | 파일 | 에이전트 | 작업 |
|----|------|---------|------|
| SEC-H-001 | `.env`, `route.ts` | backend-dev + frontend-dev | `ALLOWED_ORIGIN=http://100.90.201.87:3000` 설정, SSE 헤더 환경변수화 |
| SEC-H-005 | `web/server.py` | backend-dev | `/api/file` INTEL_FILES + MD_FILES 화이트리스트 적용 |
| SEC-H-006 | `next.config.ts` | frontend-dev | 보안 헤더 추가, `poweredByHeader: false` |
| SEC-H-007 | `web/server.py` | backend-dev | `send_headers_common()` 헬퍼로 모든 응답 경로에 보안 헤더 통일 |
| SEC-H-012 | `scripts/run_jarvis.py` | backend-dev | 출력 파일 생성 후 `os.chmod(path, 0o600)` |
| SEC-H-013 | `web/api.py` run_background | backend-dev | 로그 파일 `os.umask(0o077)` 또는 생성 후 `chmod 600` |
| SEC-ADD-001 | `data/fetch_solar_base.py` | backend-dev | `ssl.create_default_context()` 기본값 사용, `CERT_NONE` 제거 |
| SEC-ADD-002 | `web/server.py:75-77` | backend-dev | 보안 이벤트(4xx/5xx/POST/PUT/DELETE) 선택적 로깅 |

### Wave 3 — HIGH 보완 + MEDIUM (다음 주)

| ID | 파일 | 에이전트 | 작업 |
|----|------|---------|------|
| SEC-H-002 | `web/server.py` | backend-dev | SSE 연결 수 상한(10개), 인증 적용 |
| SEC-H-003 | `route.ts` | frontend-dev | 프록시 경로 화이트리스트 또는 `is_relative_to` 정규화 검증 |
| SEC-H-008 | `.env`, `docker-entrypoint.sh` | backend-dev | `ANTHROPIC_API_KEY` 직접 사용, OAuth 마운트 의존 제거 |
| SEC-H-011 | `Dockerfile`, `web-next/Dockerfile` | 직접 수정 | `RUN useradd -m appuser && USER appuser` |
| SEC-M-001 | `web/server.py` | backend-dev | Slowloris 대응 소켓 타임아웃 |
| SEC-M-002 | `web/api_company.py` | backend-dev | LIKE 와일드카드 이스케이프 |
| SEC-M-003 | `web/server.py` | backend-dev | `resolve().is_relative_to(INTEL_DIR)` 검증 |
| SEC-M-006 | `web/server.py` | backend-dev | `str(e)` → 제너릭 에러 메시지, 상세는 서버 로그만 |
| SEC-M-009 | `docker-entrypoint.sh` | backend-dev | `chmod 600 /etc/environment` 추가 |
| SEC-M-011 | `DrawerSections.tsx`, `DiscoveryTab.tsx` | frontend-dev | URL `http://` / `https://` 스킴 검증 |

---

## 즉시 수행 가능한 노코드 수정 (명령어 수준)

```bash
# SEC-C-003: DB 파일 권한 수정 + 임시 파일 삭제
chmod 600 db/history.db
rm -f db/history_rebuilt.db

# SEC-H-001: CORS 범위 제한
echo 'ALLOWED_ORIGIN=http://100.90.201.87:3000' >> .env

# docker restart로 반영
docker restart investment-bot
```

```
# SEC-C-004: Claude 메모리에서 DART API 키 삭제
# 파일: /Users/jarvis/.claude/projects/.../memory/reference_dart_api.md
# 삭제 대상: "311eca264f4eddceb0e620e2974a5d4540c94d39" 문자열
```

---

*이 리포트는 정적 분석 기반이며, 실제 네트워크 환경(Tailscale VPN)에 따라 일부 이슈의 실질 위험도는 낮아질 수 있습니다. 단, VPN 신뢰 경계가 단일 방어선임을 감안하면 내부 레이어 방어(인증, 권한, 로깅) 강화가 필수입니다.*

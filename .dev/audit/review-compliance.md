# ASVS L2 컴플라이언스 검증 리포트

**프로젝트:** investment-bot  
**검증 일시:** 2026-05-04  
**기준:** OWASP ASVS v4.0 Level 2  
**검증 목적:** Round 1 감사 리포트 커버리지 확인 + 누락 항목 보완  

---

## Round 1에서 다룬 ASVS 항목 (커버리지 확인)

| 다룬 ASVS 영역 | Round 1 이슈 ID | 내용 |
|---------------|----------------|------|
| V2.1 Password (인증 부재) | SEC-C-001 | API 전체 인증 없음 |
| V2.2 General Auth | SEC-C-001, SEC-H-002 | 브루트포스 방어 미언급 |
| V4.1 Access Control | SEC-C-001, SEC-H-003~005 | 기능별 접근 제어 부재 |
| V4.2 Least Privilege | SEC-H-011 | Docker root 실행 |
| V5.3 Output Encoding | SEC-M-011 | URL javascript: 스킴 미차단 |
| V6.2 Algorithms | SEC-C-003, SEC-M-009 | DB 평문 저장, /etc/environment 노출 |
| V7.4 Error Handling | SEC-M-006 | str(e) HTTP 응답 노출 |
| V8.3 Sensitive Data | SEC-C-003, SEC-M-010, SEC-M-016 | 파일 권한, localStorage 재무 데이터, 보존 정책 |
| V9.1 Communication | SEC-H-006, SEC-H-007 | 보안 헤더 누락 |
| V10.3 Deployed | SEC-M-007, SEC-M-008, SEC-M-012 | 의존성 버전 고정 미흡, 취약 컴포넌트 |
| V12.1 File Upload | (해당 없음 명시 없음) | — |
| V13.1 API Security | SEC-H-002, SEC-H-003, SEC-H-005 | 경로 검증, 화이트리스트 미적용 |
| V14.2 Dependency | SEC-M-007, SEC-M-008, SEC-L-002 | 버전 미고정, lockfile 없음 |

---

## Round 1에서 누락된 ASVS L2 항목

| ASVS ID | 요구사항 | 현재 상태 | 위험도 |
|---------|---------|----------|--------|
| **V1.1.2** | 위협 모델링 문서화 — 아키텍처 위협 모델과 대응 방안을 문서화해야 한다 | 프로젝트 어디에도 위협 모델 문서 없음. CLAUDE.md는 기능 문서만 존재 | MEDIUM |
| **V1.2.1** | 신뢰 경계 정의 — 컴포넌트 간 통신에 인증/권한 제어를 정의해야 한다 | Flask ↔ Next.js 프록시 신뢰 경계 정의 없음. route.ts는 모든 요청을 무조건 Flask로 전달 | HIGH |
| **V2.2.1** | 브루트포스 대응 — 30초당 최대 100회 이하 시도 제한 또는 계정 잠금 | `run_background()` 무제한 호출 가능. POST /api/run-pipeline, /api/run-marcus 초당 무제한 요청 허용 → Claude API 비용 강제 소모 | HIGH |
| **V2.2.2** | 소프트 잠금 — 로그인 실패 등 연속 실패 시 지연(soft lock) 적용 | 현재 인증 자체 없으므로 잠금 구조 전무. 인증 추가(SEC-C-001) 후에도 잠금 없으면 브루트포스 노출 | HIGH |
| **V3.1.1** | 세션 없음 선언 — stateless 설계 시 세션 관련 항목은 N/A로 명시 필요 | 세션/쿠키 전혀 없음. Stateless 설계로 V3.2~V3.5 대부분 N/A이나 Round 1에서 이를 명시하지 않아 누락으로 오해 가능 | INFO |
| **V5.1.1** | 입력 검증 — 모든 HTTP 파라미터를 신뢰할 수 없는 입력으로 처리하고 화이트리스트 방식으로 검증 | ticker, strategy, name 등 쿼리 파라미터에 타입/형식 검증 없음. `ticker` 파라미터: 길이 무제한, 특수문자 미차단 (`api_company.py` L13). `strategy` 파라미터: STRATEGY_META 화이트리스트 존재하나 타입 검증 없음 | MEDIUM |
| **V5.1.3** | 구조화된 데이터 검증 — JSON body 스키마 검증 | POST /api/wealth/assets, /api/advisor-strategies 등에서 `body["name"]` 직접 인덱싱. 값 형식(길이, 문자셋) 검증 없음. 예: `name` 필드에 10,000자 문자열 허용 | MEDIUM |
| **V5.1.4** | URL 리다이렉트 화이트리스트 | 프로젝트에 리다이렉트 없으므로 N/A. 단 SSE/프록시 업스트림 URL 검증 미흡(SEC-M-004 관련) | INFO |
| **V5.2.1** | 출력 인코딩 — HTML 컨텍스트에 삽입 시 HTML 이스케이프 | `react-markdown`이 HTML 렌더링을 기본 차단하므로 대부분 N/A. 단 `DrawerSections.tsx`에서 `profile.website`, `item.url`이 `href`에 직접 삽입 — 검증 없음 (SEC-M-011과 동일 근원이나 ASVS 5.2.1로 미분류) | MEDIUM |
| **V6.1.1** | 민감 데이터 분류 — 데이터를 보호 수준별로 분류해야 한다 | 금융 데이터(평균단가, 수익률, 전재산), API 키, Claude OAuth 토큰에 대한 분류 정책 문서 없음 | MEDIUM |
| **V6.1.2** | 민감 데이터 전송 암호화 — 네트워크 전송 시 TLS 적용 | Flask → Next.js 구간: 컨테이너 내부 HTTP (암호화 없음). Next.js → 클라이언트: Tailscale VPN 구간이지만 HTTP (포트 3000, TLS 없음). 외부 API(Anthropic, DART, Brave)는 urllib.request로 HTTPS 사용하나 HSTS 부재 | HIGH |
| **V6.2.1** | 검증된 암호 알고리즘 — 승인된 알고리즘만 사용 | 암호화 구현 자체 없음. SQLite DB, 로그 파일, output/intel/*.json 전부 평문. 금융 데이터에 대한 저장 암호화 전무 | HIGH |
| **V6.2.3** | 난수 생성 — 보안 목적 난수는 CSPRNG 사용 | 현재 보안 목적 난수 생성 없음. 추후 세션/토큰 구현 시 `os.urandom` 또는 `secrets` 모듈 사용 강제 필요 | INFO |
| **V7.1.1** | 로그 기록 범위 — 보안 관련 이벤트(인증 실패, 접근 거부, 입력 검증 실패) 로깅 | `server.py` L75: `log_message` 가 suppress됨. 모든 HTTP 접근 로그, 인증 실패(현재 인증 없음), 오류 이벤트가 기록되지 않음. 유일한 로그: `log_error`(서버 오류만) | HIGH |
| **V7.1.2** | 로그 무결성 — 로그에 개인 금융 데이터, API 키 등 민감 정보 포함 금지 | `pipeline.log`, `marcus.log`에 포트폴리오 평균단가/수익률, 분석 내용 포함 가능. `fetch_fundamentals_sources.py`에서 DART URL(키 포함) 에러 로그 기록(SEC-H-014) | HIGH |
| **V7.2.1** | 에러 처리 — 예외 발생 시 스택 트레이스를 클라이언트에 노출하지 않음 | `server.py`에서 KeyError/ValueError의 `str(e)` 반환 (SEC-M-006). 그러나 `traceback.format_exc()`는 사용하지 않아 스택 트레이스 노출은 없음. 단, 내부 필드명/타입 정보는 노출됨 | MEDIUM |
| **V7.3.3** | 로그 인젝션 방어 — 외부 입력을 로그에 기록 시 CRLF 이스케이프 | `fetch_news.py`의 외부 키워드(SEC-M-005). `marcus.log`에 사용자 입력 경유 데이터 기록 가능 | MEDIUM |
| **V8.1.1** | 민감 데이터 캐싱 방지 — HTTP 응답 캐시 방지 헤더 | `/api/data`, `/api/wealth` 등 금융 데이터 응답에 `Cache-Control: no-store` 없음. `send_json()`에 없고, `send_file()`에만 `no-store` 적용. 브라우저/CDN 캐싱으로 민감 금융 데이터 노출 가능 | MEDIUM |
| **V8.1.2** | 임시 파일 삭제 — 처리 완료 후 임시 파일 삭제 | `db/history_rebuilt.db` (38MB), `db/history.db.bak` 방치 (SEC-L-003). Round 1에서 LOW로 분류했으나 ASVS 8.1.2 항목으로 명시적 미분류 | LOW |
| **V8.2.1** | 클라이언트 민감 데이터 — 브라우저 자동완성 민감 필드 비활성화 | `AdvisorTab`의 자본금/대출금 입력 필드에 `autocomplete="off"` 적용 여부 확인 필요. 브라우저가 금융 수치 캐싱 가능 | LOW |
| **V8.3.1** | 민감 데이터 서버 전송 암호화 — 클라이언트→서버 전송 중 TLS | 내부 통신이 HTTP임 (V6.1.2와 동일 근원). localStorage의 `mc-advisor-settings`(자본금, 대출 금액)이 HTTP로 전송됨 | HIGH |
| **V9.1.1** | TLS 사용 — 모든 연결에 TLS 1.2+ 적용 | Flask API: HTTP (평문). Next.js: HTTP (평문). Tailscale가 WireGuard로 암호화하지만 애플리케이션 레이어 TLS 없음. ASVS는 네트워크 레이어 의존 허용하지 않음 | HIGH |
| **V9.1.2** | TLS 검증 — 서버 인증서 유효성 검증 | `data/fetch_solar_base.py` L37-39: `_SSL_UNVERIFIED` 컨텍스트에서 `check_hostname=False`, `verify_mode=ssl.CERT_NONE`. 모든 태양광 크롤러 요청에 적용됨. MITM 공격 노출 | HIGH |
| **V9.1.3** | 최신 TLS 버전 — TLS 1.0/1.1 비활성화 | 서버가 HTTP만 사용하므로 TLS 버전 설정 자체 없음 (V9.1.1과 동일 근원) | HIGH |
| **V10.2.1** | 악의적 코드 검색 — 백도어, 하드코딩 자격증명, 숨겨진 기능 | `docker-entrypoint.sh`에서 `cp -r /root/.claude-host/. /root/.claude/` — OAuth 토큰을 writable 경로에 복사. cron이 매 1분 갱신. 설계상 의도된 것이나 매 1분 권한 상승 패턴은 지속적 위협면 | MEDIUM |
| **V10.3.1** | 애플리케이션 무결성 — 업데이트된 바이너리/라이브러리 무결성 검증 | `npm install -g @anthropic-ai/claude-code` 버전 미지정(Dockerfile L4). 매 빌드마다 다른 버전 설치 가능. `@anthropic-ai/claude-code`의 의존성 체인 무결성 검증 없음 (SEC-M-008과 관련, 단 ASVS 10.3.1 항목으로 미분류) | MEDIUM |
| **V12.1.1** | 파일 업로드 — 현재 파일 업로드 기능 없음 | `/api/file`은 읽기만 지원. 업로드 기능 없으므로 V12.3~V12.6 전체 N/A | N/A |
| **V13.1.3** | API 레이트 리미팅 — API 요청 수 제한 | Flask 서버에 레이트 리미팅 미구현. POST /api/run-marcus → Claude API 비용 발생. 무제한 호출 허용. Next.js 프록시에도 없음 | HIGH |
| **V13.1.4** | API 버전 관리 — URL 또는 헤더 기반 버전 명시 | 모든 엔드포인트가 `/api/xxx` 형식. 버전 없음(`/api/v1/xxx`). 버전 비호환 변경 시 클라이언트 영향 추적 불가 | LOW |
| **V13.2.1** | RESTful API — 허용 HTTP 메서드 화이트리스트 | `do_OPTIONS`에서 `Allow: GET, POST, PUT, DELETE, OPTIONS` 전체 허용. 엔드포인트별 허용 메서드 제한 없음. 예: `/api/data`에 POST/DELETE 요청 → 404이지만 에러 응답이 일관되지 않음 | LOW |
| **V13.2.2** | RESTful JSON 검증 — Content-Type 검증 | POST 바디 처리 시 `Content-Type: application/json` 미검증 (SEC-M-015). Round 1에서 ASVS 분류 없이 A04로만 분류 | MEDIUM |
| **V13.3.1** | GraphQL/WebSocket | 사용 없으므로 N/A | N/A |
| **V14.1.1** | 보안 빌드 파이프라인 — CI/CD 보안 게이트 | GitHub push가 코드 백업 전용. 자동 빌드/배포 없음. `pre-deploy-check.sh`가 수동 실행 기반. SAST/의존성 스캔 자동화 없음 | MEDIUM |
| **V14.2.1** | 의존성 최신화 — 지원 중단 또는 취약한 컴포넌트 제거 | `postcss@8.4.31` GHSA-qx2v-qp2m-jg93 (SEC-M-012). `node:20-alpine`, `python:3.12-slim` 최신 패치 버전 보장 없음. 자동 업데이트 정책 없음 | MEDIUM |
| **V14.4.1** | HTTP 보안 헤더 — 모든 응답에 적용 | `send_json()`에만 X-Content-Type-Options, X-Frame-Options 적용 (SEC-H-007). `Cache-Control: no-store`가 금융 API 응답에 없음. CSP 전무. HSTS 전무 | HIGH |
| **V14.4.6** | CSP 헤더 — Content-Security-Policy 적용 | Next.js(`next.config.ts`)와 Flask 양쪽에 CSP 전무 (SEC-H-006에서 HIGH로 다뤘으나 CSP 특정 항목으로 미분류) | HIGH |
| **V14.5.1** | HTTP 요청 스머글링 방어 — 요청 파싱 일관성 | Python `http.server.BaseHTTPRequestHandler` 사용. `Content-Length`와 `Transfer-Encoding` 동시 존재 시 처리 정의 불명확. SEC-M-001(Slowloris)에서 부분 다뤘으나 HTTP 스머글링 측면 미언급 | MEDIUM |

---

## 해당 없는 항목 (N/A 근거)

| ASVS 챕터 | 항목 | N/A 근거 |
|-----------|------|---------|
| **V3 Session Management** (V3.2~V3.7 전체) | 세션 토큰 관리, 로그아웃, 재인증 | 완전 Stateless 아키텍처. 서버 세션/쿠키 없음. 인증 추가(SEC-C-001) 시 세션 없는 JWT 또는 API 키 방식 채택 예정 |
| **V3.1.1** | 세션 쿠키 보안 속성 | 쿠키 미사용 |
| **V4.3.1** | 관리 인터페이스 분리 | 관리 인터페이스 별도 없음. 모든 API가 동일 포트로 노출 (이 자체가 위험이나 별도 N/A 근거) |
| **V6.4.1** | 비밀 관리 솔루션 (Vault 등) | 규모상 HashiCorp Vault 등 미채택. .env 파일 + Docker env_file 사용. 개인 프로젝트 범주에서 현실적 대안 없음 |
| **V11 Business Logic** | 금융 트랜잭션 무결성 | 실제 거래 미수행. 읽기 전용 대시보드 + 수동 거래 지원. 자동 주문 기능 없음 |
| **V12.1~V12.6** | 파일 업로드 | 파일 업로드 기능 없음. `/api/file`은 읽기 전용 |
| **V13.3** | GraphQL | 미사용 |
| **V15 (예약)** | — | ASVS v4에서 미정의 |

---

## 추가 발견 사항 (Round 1 미언급, ASVS 직접 매핑 아닌 보안 결함)

| ID | 파일 | 설명 | 위험도 |
|----|------|------|--------|
| **SEC-ADD-001** | `data/fetch_solar_base.py:37-39` | `ssl.CERT_NONE` + `check_hostname=False` — 태양광 크롤러 전체 HTTPS 인증서 미검증. 악성 웹서버에서 금융 사기 매물 데이터 주입 가능 | HIGH |
| **SEC-ADD-002** | `web/server.py:75-77` | `log_message` suppress — 모든 HTTP 요청 로그 억제. 침해 발생 시 포렌식 불가. ASVS V7.1.1 위반 | HIGH |
| **SEC-ADD-003** | `web/api.py:82-163` | `send_json()` 응답에 `Cache-Control: no-store` 없음 — `/api/data`, `/api/wealth` 등 금융 응답이 브라우저 캐시에 저장될 수 있음. ASVS V8.1.1 위반 | MEDIUM |
| **SEC-ADD-004** | `web/server.py:473` | Flask 서버가 모든 인터페이스(`""`)에 바인딩. `127.0.0.1` 제한 없음. ASVS V1.2.1 위반 | LOW (SEC-L-001과 중복, 단 ASVS 분류 추가) |
| **SEC-ADD-005** | `web/investment_advisor.py`, `web/advisor_data.py` | 포트폴리오 데이터(평균단가, 수익률, 수량)가 Claude API 프롬프트에 원문 포함. ASVS V8.3.4(민감 데이터 최소화) 위반. Round 1 SEC-H-015에서 다뤘으나 ASVS 분류 없음 | HIGH |
| **SEC-ADD-006** | `docker-compose.yml:7` | Flask 포트 `8421:8421` 바인딩 — 호스트의 모든 인터페이스에 노출. `127.0.0.1:8421:8421`로 변경 필요 | LOW |

---

## 커버리지 요약

| ASVS 챕터 | Round 1 커버 | 이번 보완 | 합계 누락 |
|-----------|------------|---------|---------|
| V1 Architecture | 부분 (설정/배포) | V1.1.2 위협 모델, V1.2.1 신뢰 경계 | 2 |
| V2 Authentication | 부분 (인증 부재) | V2.2.1 레이트 리미팅, V2.2.2 잠금 | 2 |
| V3 Session | 미언급 | N/A 명시 (stateless) | 0 |
| V4 Access Control | 다수 | — | 0 |
| V5 Validation | 부분 | V5.1.1 화이트리스트, V5.1.3 스키마 검증 | 2 |
| V6 Cryptography | 부분 | V6.1.1 분류 정책, V6.1.2/V6.2.1 TLS/암호화 | 3 |
| V7 Error/Logging | 부분 | V7.1.1 접근 로그, V7.1.2 민감 정보 로그 | 2 |
| V8 Data Protection | 부분 | V8.1.1 캐시 방지, V8.2.1 자동완성, V8.3.1 전송 암호화 | 3 |
| V9 Communication | 부분 (헤더) | V9.1.1 TLS 부재, V9.1.2 인증서 미검증 | 2 |
| V10 Malicious Code | 부분 (의존성) | V10.2.1 OAuth 복사 패턴, V10.3.1 무결성 | 2 |
| V12 Files | 미언급 | N/A 명시 | 0 |
| V13 API | 부분 | V13.1.3 레이트 리미팅, V13.1.4 버전 관리, V13.2.2 CT 검증 | 3 |
| V14 Configuration | 부분 | V14.1.1 CI/CD 자동화, V14.4.1 캐시 헤더, V14.4.6 CSP, V14.5.1 스머글링 | 4 |

---

*이 리포트는 Round 1 정적 분석 결과를 OWASP ASVS v4.0 L2 프레임워크에 매핑하고 누락 항목을 보완한 것입니다. V9.1.1~V9.1.3 (TLS 전면 부재)과 V7.1.1 (접근 로그 억제), V9.1.2 (SSL 인증서 미검증)는 Round 1에서 다루지 않은 HIGH 수준 항목으로 즉각적인 검토가 필요합니다.*

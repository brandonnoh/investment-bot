# 연쇄 공격 시나리오 리포트

**기반 감사:** Round 1 보안 감사 리포트 (2026-05-04)  
**분석 일시:** 2026-05-04  
**분석 방법:** 개별 취약점 간 인과 연결 및 공격자 관점 시나리오 합성  
**전제:** 두 가지 공격자 모델 — (A) Tailscale VPN 내부 신뢰된 기기 접근자, (B) 피해자 브라우저를 매개로 한 외부 공격자

---

## Chain-001: 악성 웹페이지 → 파이프라인 강제 실행 → Claude API 비용 소진 및 데이터 오염

**공격자 모델:** 외부 (B)  
**필요 조건:** 피해자가 Tailscale 네트워크에 연결된 브라우저로 악성 웹페이지 방문  
**난이도:** 낮음 (사전 지식 없이 시도 가능)

- **진입점:** 악성 웹페이지 또는 이메일 링크 (피해자 브라우저 경유)
- **공격 단계:**
  1. `SEC-H-001` — Flask `ALLOWED_ORIGIN=*`, `route.ts` SSE 헤더 하드코딩 `*`. 악성 페이지에서 `fetch('http://100.90.201.87:8421/api/run-pipeline', {method:'POST'})` 호출 시 CORS 차단 없음
  2. `SEC-C-001` — `/api/run-pipeline` 인증 완전 부재. `api.run_background("pipeline", ["python3", "run_pipeline.py"])` 즉시 실행
  3. `SEC-H-002` — PID 중복 방지 로직이 유일한 제동 장치. 그러나 이전 파이프라인이 완료된 직후 재호출 시 연속 실행 가능. 연속 트리거는 루프 스크립트로 자동화 용이
  4. `SEC-H-015` — 파이프라인 실행 시 `run_marcus.py`가 포트폴리오 평균단가·손익·수량을 Anthropic 서버로 송신. 공격자가 파이프라인을 반복 트리거할수록 Anthropic API 비용 누적
- **최종 영향:**
  - Claude API 사용 비용 강제 소진 (marcus 1회 실행당 API 비용 발생)
  - 파이프라인이 오염된 외부 데이터(Brave/Yahoo/DART)를 재수집하여 `output/intel/` 덮어쓰기 → 분석 결과 오염 가능
  - 피해자가 이상 징후를 인지하기 전까지 반복 실행 가능
- **수정 우선순위 (차단 비용 최소 링크):** `SEC-H-001` — `.env`에 `ALLOWED_ORIGIN=http://100.90.201.87:3000` 한 줄 추가만으로 외부 브라우저 경유 공격 전체 차단. 비용: 환경변수 1줄 + route.ts 헤더 수정.

---

## Chain-002: Gemini API 키 → 로그 파일 → /api/logs → 클라이언트 노출 → 키 탈취

**공격자 모델:** 외부 (B) 또는 내부 (A)  
**필요 조건:** 브라우저에서 SystemTab의 로그 뷰어 접근, 또는 `/api/logs` 직접 호출  
**난이도:** 낮음 (로그 뷰어 UI가 이미 제공됨)

- **진입점:** `scripts/publish_blog.py` — Gemini API 키를 URL 쿼리 파라미터로 사용
- **공격 단계:**
  1. `SEC-C-002` — `publish_blog.py` 라인 43, 62에서 `?key={GEMINI_API_KEY}` 형태로 HTTP 요청 전송. Gemini 이미지 생성 실패(`imagen-4.0-generate-001`) 시 라인 85의 `resp.text[:200]`가 로그에 기록됨. Google API 오류 응답 일부 구현이 요청 URL을 echo하므로 키가 `publish_blog.log`에 평문 저장 가능
  2. `SEC-H-009` — `docker-entrypoint.sh`가 `GOOGLE_GEMINI_API_KEY`를 `/etc/environment` 전파 목록에서 누락. cron 잡 `publish_blog`가 매일 07:55에 `KeyError`로 크래시하며 스택 트레이스가 로그에 기록됨 (스택 트레이스에 환경변수명 및 컨텍스트 포함)
  3. `SEC-L-004` — `/api/logs?name=pipeline` (또는 향후 `publish_blog` 이름 추가 시) 엔드포인트가 인증 없이 로그 내용 반환
  4. `SEC-H-001` — CORS `*`로 인해 외부 브라우저에서도 `/api/logs` 직접 호출 가능
  5. `SEC-H-013` — `publish_blog.log`가 644 권한으로 컨테이너 내 world-readable. 컨테이너 접근 권한이 있는 어떤 프로세스도 읽기 가능
- **최종 영향:**
  - Gemini API 키 탈취 → 공격자가 이미지 생성(Imagen) 및 텍스트 생성(Gemini) 무단 사용 → 요금 부과
  - 키 만료 전까지 공격자는 비용 소진 공격 지속 가능
- **수정 우선순위 (차단 비용 최소 링크):** `SEC-C-002` — `x-goog-api-key` 헤더로 이동 (코드 2줄 수정). 키가 URL에 포함되지 않으면 로그에 기록될 수 없어 체인 1단계에서 완전 차단.

---

## Chain-003: Next.js 프록시 경로 인젝션 → Flask 내부 엔드포인트 도달 → 임의 파일 읽기

**공격자 모델:** 외부 (B) 또는 내부 (A)  
**필요 조건:** Next.js 서버(포트 3000) 접근 — Tailscale VPN 외부에서도 접근 가능한 경우 위험 증가  
**난이도:** 중간 (Flask 내부 구조 사전 지식 필요)

- **진입점:** `GET /api/[...path]` — Next.js 프록시 라우트
- **공격 단계:**
  1. `SEC-H-003` — `route.ts` 14-16행: `path.join('/')` 후 화이트리스트 없이 `${API_BASE}/api/${pathStr}` 조합. Next.js `[...path]` 세그먼트는 URL 디코딩 후 전달되므로 `%2F` → `/` 정규화 발생
  2. 예시 요청: `GET /api/file?name=../../../etc/passwd` → `path = ["file"]`, `search = "?name=../../../etc/passwd"` → Flask `/api/file?name=../../../etc/passwd` 전달
  3. `SEC-M-003` — `/api/file` 핸들러(server.py:124)가 `"/" in name` 검사만 수행. URL-decoded 이전 `%2F` 또는 `..` 만 포함된 경로(예: `....//` 또는 URL 이중 인코딩)로 우회 가능성. `resolve().is_relative_to(INTEL_DIR)` 검증 없음
  4. `SEC-H-005` — `.json` 확장자 파일에 대해 `INTEL_FILES` 목록 비교 없이 `send_file(INTEL_DIR / name)` 직접 서빙. `universe_cache.json`(672 종목 재무), `discovery_keywords.json` 등 비공개 분석 파일 접근 가능
  5. `SEC-H-001` — CORS `*`로 응답이 외부 브라우저 JS에서 읽기 가능 (`fetch()` 응답 `.json()` 파싱 허용)
- **최종 영향:**
  - 비공개 분석 파일 전체 유출 (종목 발굴 전략, 스크리너 결과)
  - 경로 우회 성공 시 `holdings_proposal.json`, `portfolio_summary.json` 등 포트폴리오 전략 정보 유출
  - 공개 블로그 게시 전 독점 분석 정보 선취득 가능
- **수정 우선순위 (차단 비용 최소 링크):** `SEC-H-005` — `server.py` `/api/file` 핸들러에 `if name not in api.INTEL_FILES` 조건 추가(코드 3줄). 화이트리스트 밖의 모든 파일 차단. 경로 인젝션 성공 여부와 무관하게 읽기 가능 파일을 공개 목록으로 제한.

---

## Chain-004: 뉴스 로그 인젝션 → /api/logs → 프론트엔드 렌더링 → DOM XSS

**공격자 모델:** 외부 (B) — 뉴스 소스 오염 통해 간접 공격  
**필요 조건:** 공격자가 RSS 피드 또는 Brave Search 결과에 페이로드를 주입할 수 있는 위치에 있음 (뉴스 퍼블리셔 또는 SEO poisoning)  
**난이도:** 높음 (뉴스 소스 오염 단계가 필요)

- **진입점:** 외부 RSS 피드 또는 Brave Search API 응답 — 공격자가 제어하는 뉴스 소스
- **공격 단계:**
  1. `SEC-M-005` — `fetch_news.py:46,304`: Claude가 뉴스 기반으로 생성한 검색 키워드 및 뉴스 제목/요약이 `\r\n` 이스케이프 없이 stdout에 기록됨. 공격자가 뉴스 제목에 `\r\nX-Injected-Header: malicious` 또는 로그 파서 혼란 페이로드를 삽입
  2. `SEC-H-013` — 로그 파일(pipeline.log, marcus.log)이 644 권한. 컨테이너 내 다른 프로세스가 읽기 가능
  3. `SEC-L-004` — `/api/logs?name=marcus&lines=1000` 인증 없이 로그 내용 반환
  4. `SEC-H-001` — CORS `*`. 외부 스크립트에서 응답 읽기 가능
  5. `SEC-M-011` — `DrawerSections.tsx` NewsItem 컴포넌트: `item.url`을 `href`에 직접 삽입하며 `javascript:` 스킴 차단 없음. 뉴스 DB에 `javascript:alert(document.cookie)` URL이 저장된 경우 클릭 시 XSS 실행. `item.title`은 `{item.title}` JSX 텍스트 노드 렌더링이므로 HTML 인젝션은 차단되지만 href XSS는 유효
  6. `SEC-H-006` — `next.config.ts` CSP 헤더 없음. XSS 실행 시 `fetch()`, `XMLHttpRequest` 등 외부 요청 제한 없음
- **최종 영향:**
  - XSS 성공 시 세션 컨텍스트에서 `/api/data`(포트폴리오 전체) 자동 요청 후 공격자 서버로 전송
  - LocalStorage(`mc-advisor-settings`: 자본금, 대출 금액) 탈취
  - 피해자 브라우저에서 `/api/run-pipeline`, `/api/run-marcus` POST 자동 실행 가능 (CSRF 없음)
- **수정 우선순위 (차단 비용 최소 링크):** `SEC-M-011` — `DrawerSections.tsx` NewsItem과 profile.website에 `url.startsWith('https://') || url.startsWith('http://')` 검증 2줄 추가. `javascript:` XSS 경로 차단. 뉴스 소스 오염 없이도 DB에 악성 URL이 들어올 수 있는 모든 경로를 방어.

---

## Chain-005: 내부 공격자 → /api/wealth/assets DELETE → ID 열거 → 비금융 자산 전체 삭제

**공격자 모델:** 내부 (A) — Tailscale VPN에 연결된 신뢰된 기기 사용자  
**필요 조건:** Tailscale VPN 접속 (또는 Chain-001의 CORS 우회)  
**난이도:** 낮음 (도구: curl 또는 브라우저 개발자 도구)

- **진입점:** Flask API 직접 호출 또는 Next.js 프록시 경유
- **공격 단계:**
  1. `SEC-C-001` — 모든 HTTP 메서드 인증 없음
  2. `SEC-H-004` — `do_DELETE` 핸들러: `asset_id = int(path.rsplit("/", 1)[-1])`. ID는 SQLite auto-increment 정수. `DELETE /api/wealth/assets/1`부터 순차 시도
  3. ID 1~200 범위 열거 스크립트 (반복 DELETE 요청). 각 요청에 대해 `{"ok": true}` 또는 `{"ok": false}` 응답으로 존재 여부 파악 가능
  4. `SEC-H-001` — CORS `*`이므로 외부 브라우저에서도 동일 공격 가능 (Chain-001 진입점 활용)
  5. `SEC-C-003` — DB가 644 권한이므로 삭제된 레코드의 포렌식 복구를 위한 백업 파일(`history.db.bak`, `history_rebuilt.db`)도 644 — 공격자가 삭제 전 DB 복사본을 확보하여 원본 데이터 분석 가능
- **최종 영향:**
  - 비금융 자산(`extra_assets`) 레코드 영구 삭제 → 전재산 계산 오류
  - `advisor_strategies` 테이블의 저장된 AI 전략 전체 삭제 가능 (`DELETE /api/advisor-strategies/{id}`)
  - 데이터 복구 수단 없음 (별도 백업 미운영 — `.bak` 파일은 임시 복구 파일이며 최신 상태 아님)
- **수정 우선순위 (차단 비용 최소 링크):** `SEC-C-001` + `SEC-H-001` 중 어느 하나만 수정해도 외부 공격자 차단 가능. VPN 내부 공격자까지 차단하려면 `SEC-C-001` X-API-Key 인증 미들웨어 추가가 필수. 비용: server.py에 API 키 검증 데코레이터 추가 (~20줄).

---

## Chain-006: Claude OAuth 토큰 → 컨테이너 내 RCE 경유 → 호스트 Claude 세션 탈취

**공격자 모델:** 내부 (A) 또는 취약점 체이닝으로 컨테이너 코드 실행 권한 확보한 외부 공격자  
**필요 조건:** 컨테이너 내부 임의 코드 실행 (예: Slowloris로 스레드 소진 후 타이밍 공격, 또는 Chain-003으로 설정 파일 읽기 성공 후 내부 엔드포인트 발견)  
**난이도:** 높음 (컨테이너 내부 실행 권한이 전제)

- **진입점:** 컨테이너 내부 프로세스 실행 권한
- **공격 단계:**
  1. `SEC-H-008` — `docker-compose.yml:13-14`: `~/.claude:/root/.claude-host:ro` 읽기 전용 마운트. 그러나 `docker-entrypoint.sh:16-19`: `cp -r /root/.claude-host/. /root/.claude/` — writable 경로로 복사. 매 1분 cron이 최신 OAuth 토큰을 `/root/.claude/`에 덮어씀
  2. `SEC-H-011` — 두 컨테이너 모두 `USER` 지시어 없음 → uid=0(root)로 실행. 컨테이너 내 `/root/.claude/` 직접 읽기 가능
  3. `SEC-C-003` — DB 644 권한. 컨테이너 내에서 `sqlite3 /app/db/history.db .dump` 실행 → 전체 금융 이력 덤프
  4. `SEC-M-009` — `/etc/environment` (0644)에 5개 API 키 평문 저장. 컨테이너 내 `cat /etc/environment`로 BRAVE_API_KEY, DART_API_KEY, DISCORD_WEBHOOK_URL, KIWOOM_APPKEY, KIWOOM_SECRETKEY 일괄 획득
  5. 탈취한 Claude OAuth 토큰으로 호스트 claude CLI 세션 사칭 → Anthropic 계정에서 claude code 무단 실행
- **최종 영향:**
  - Anthropic 계정 접근 권한 탈취 → Claude API 무제한 사용
  - 5개 API 키 동시 획득 (Brave, DART, Discord, Kiwoom 2개)
  - 전체 금융 이력 DB 덤프 (매매 내역, 전재산 이력, Claude 분석 전문)
  - Kiwoom 증권 API 키로 잔고 조회 (쓰기 권한 여부에 따라 매매 명령 가능성)
- **수정 우선순위 (차단 비용 최소 링크):** `SEC-H-008` — `.env`에 `ANTHROPIC_API_KEY` 직접 추가, `docker-entrypoint.sh`의 `cp ~/.claude-host` 구문 제거, `docker-compose.yml` 볼륨 마운트 삭제. OAuth 토큰 컨테이너 접근 자체를 차단하면 체인 최상위 자산(Claude 세션)을 보호. 동시에 `SEC-M-009`: `chmod 600 /etc/environment` 추가로 나머지 API 키 노출도 차단 가능.

---

## 체인별 우선순위 매트릭스

| 체인 | 공격자 | 실현 난이도 | 최종 영향 | 차단 링크 | 수정 비용 |
|------|--------|------------|-----------|-----------|-----------|
| Chain-001 | 외부 | 낮음 | API 비용 소진 / 데이터 오염 | SEC-H-001 | 매우 낮음 (환경변수 1줄) |
| Chain-002 | 외부/내부 | 낮음 | Gemini 키 탈취 / 요금 부과 | SEC-C-002 | 낮음 (코드 2줄) |
| Chain-003 | 외부/내부 | 중간 | 비공개 분석 파일 유출 | SEC-H-005 | 낮음 (코드 3줄) |
| Chain-004 | 외부 | 높음 | XSS → 포트폴리오 탈취 | SEC-M-011 | 낮음 (코드 2줄) |
| Chain-005 | 내부/외부 | 낮음 | 자산 데이터 영구 삭제 | SEC-C-001 | 중간 (인증 미들웨어) |
| Chain-006 | 내부+RCE | 높음 | Claude 세션 + 전체 키 탈취 | SEC-H-008 | 낮음 (볼륨 마운트 제거) |

**즉시 조치 권장 순서 (수정 비용 대비 차단 효과):**
1. `.env` `ALLOWED_ORIGIN` 설정 (Chain-001, 004, 005 외부 경로 일괄 차단)
2. Gemini API 키 → 헤더 이동 (Chain-002 차단)
3. `/api/file` INTEL_FILES 화이트리스트 (Chain-003 차단)
4. `DrawerSections.tsx` URL 스킴 검증 (Chain-004 최종 단계 차단)
5. `ANTHROPIC_API_KEY` 환경변수화 + 볼륨 마운트 제거 (Chain-006 차단)

---

*이 보고서는 정적 코드 분석 기반 시나리오 합성이며 실제 익스플로잇을 시도하지 않았습니다.*

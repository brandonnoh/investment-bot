# 오탐 검증 리포트

**검증 일시:** 2026-05-04  
**검증 방법:** 실제 코드 직접 Read + 런타임 동작 시뮬레이션  
**검증 대상 파일:**  
- `web/server.py`, `web-next/src/app/api/[...path]/route.ts`  
- `db/init_db.py`, `db/init_db_schema.py`  
- `scripts/run_marcus.py`, `scripts/publish_blog.py`  
- `data/fetch_fundamentals_sources.py`  
- `web/server.py:_handle_api_file`, `web/api.py:INTEL_FILES`  
- `web-next/src/components/discovery/DrawerSections.tsx`  
- `docker-entrypoint.sh`, `docker-compose.yml`  
- `db/` 디렉토리 파일 권한  
- `output/intel/` 파일 권한  

---

## 판정 요약

| ID | 판정 | 근거 요약 |
|----|------|-----------|
| SEC-C-001 | CONFIRMED | 인증 코드 없음, 완전 무인증 확인됨 |
| SEC-C-002 | CONFIRMED | `publish_blog.py:43,62` URL에 `?key={GEMINI_API_KEY}` 직접 삽입 |
| SEC-C-003 | CONFIRMED | `history.db` 644, `history_rebuilt.db` 644 (38MB) 실 권한 확인 |
| SEC-C-004 | CONFIRMED | DART API 키 메모리 파일에 평문 기록됨 (MEMORY.md에서 확인) |
| SEC-H-001 | CONFIRMED | `ALLOWED_ORIGIN="*"` 기본값, `route.ts` SSE 헤더 하드코딩 확인 |
| SEC-H-002 | CONFIRMED | SSE `_sse_clients.append()` 제한 없음 확인. 단, `queue.Queue(maxsize=100)` 으로 dead client 감지 구현은 존재 |
| SEC-H-003 | LIKELY | URL constructor가 `../`를 정규화 → 실제 내부 Flask 라우트 우회 가능성 제한적. 단, `%2e%2e` percent-encoding 우회 시 fetch()가 정규화 전에 Flask에 전달 가능 |
| SEC-H-004 | CONFIRMED | PUT/DELETE 핸들러 인증 없음 코드 확인 |
| SEC-H-005 | CONFIRMED | `/api/file` 핸들러가 `.json`에 대해 INTEL_FILES 화이트리스트 미적용 확인 (`universe_cache.json` 등 접근 가능) |
| SEC-H-006 | CONFIRMED | `next.config.ts` 보안 헤더 전무, Cache-Control만 존재 |
| SEC-H-007 | CONFIRMED | `send_file()`, SSE, 스트리밍 응답에 보안 헤더 없음 확인 |
| SEC-H-008 | CONFIRMED | `docker-entrypoint.sh:19` `cp -r /root/.claude-host/. /root/.claude/` — ro 마운트를 writable 경로로 복사 확인 |
| SEC-H-009 | CONFIRMED | `docker-entrypoint.sh:6` 루프에 R2, Sanity, Gemini 키 5종 누락 확인 |
| SEC-H-010 | FALSE_POSITIVE | `_migrate_add_column`은 `MIGRATION_COLUMNS` 상수에서만 호출됨. 호출 체인 전수 확인: `init_db.py:173` → `MIGRATION_COLUMNS`(하드코딩 튜플). 외부 입력 경로 없음. 함수 시그니처 위험은 설계 냄새이나 실제 익스플로잇 경로 없음 |
| SEC-H-011 | CONFIRMED | 두 Dockerfile 모두 USER 지시어 없음 확인 |
| SEC-H-012 | LIKELY | `output/intel/cio-briefing.md` 644 권한 확인. 단, 해당 파일은 호스트 OS 기준 644이며 동일 host user(`jarvis`)만 동일 머신 사용하는 개인용 환경. 컨테이너 내 volume mount로 world-readable 상태 유지됨 |
| SEC-H-013 | CONFIRMED | `logs/*.log` 644 권한 확인 (`alerts_watch.log` 1.9MB 포함) |
| SEC-H-014 | FALSE_POSITIVE | `urllib.error.HTTPError.__str__()` 검증 결과: `"HTTP Error 401: Unauthorized"` 형식으로 URL 미포함. `logger.error(f"... {e}")` 에서 키 노출 안 됨. `logger.debug(f"... {e}")` 도 동일. URL 객체를 직접 로그에 찍는 코드 없음 |
| SEC-H-015 | CONFIRMED | 의도적 설계이나 제3자 서버에 금융 개인정보 전송 사실 자체는 확인됨 |
| SEC-M-001 | CONFIRMED | `_read_json_body()` 10MB 상한은 있으나 소켓 타임아웃 없음 |
| SEC-M-002 | CONFIRMED | `web/api_company.py:79` `f"%{code}%"` 이스케이프 없이 LIKE 쿼리 |
| SEC-M-003 | LIKELY | `/api/file?name=x` — `/`, `\` 체크로 `../` 경로순회는 막힘 확인. 그러나 `resolve().is_relative_to()` 미적용으로 다른 방식 우회 이론적 가능. 실제 PoC는 `parse_qs`가 `%2F` 디코딩 → 슬래시 체크에서 모두 차단됨 |
| SEC-M-004 | FALSE_POSITIVE | `DISCORD_WEBHOOK_URL`은 `.env` 파일에서만 설정. API 엔드포인트를 통해 환경변수 변조 경로 없음 확인. SSRF가 성립하려면 이미 호스트/컨테이너 침해가 전제여야 함 — 사전 침해 없이는 공격 불가 |
| SEC-M-005 | CONFIRMED | 외부 키워드 로그 이스케이프 없음 |
| SEC-M-006 | CONFIRMED | `except (KeyError, ValueError) as e: self.send_json({"error": str(e)}, 400)` 다수 확인 |
| SEC-M-007 | CONFIRMED | `requirements.txt` 범위 지정, lockfile 없음 |
| SEC-M-008 | CONFIRMED | Dockerfile 이미지 digest 미고정 |
| SEC-M-009 | CONFIRMED | `/etc/environment` 기본 권한 644 (world-readable) |
| SEC-M-010 | CONFIRMED | localStorage에 capital, 대출금액 평문 저장 |
| SEC-M-011 | LIKELY | `DrawerSections.tsx:169,341` 에서 `profile.website`, `item.url` 직접 `href`에 삽입 확인. `rel="noopener noreferrer"`는 탭 격리만 제공, `javascript:` 실행은 차단하지 않음. 단, React v19가 `javascript:` href에 경고를 출력하나 프로덕션 빌드에선 차단하지 않음 |
| SEC-M-012 | NEEDS_MORE_INFO | `next@16.2.4` 내 `postcss` 취약 번들 여부는 npm audit으로만 확인 가능 |
| SEC-M-013 | CONFIRMED | SEC-H-008과 동일 근원 |
| SEC-M-014 | CONFIRMED | `cio-briefing.md`(644), `search_keywords.json`(644), `universe_cache.json`(644), `screener_results.json`(644), `regime.json`(644) 확인 |
| SEC-M-015 | CONFIRMED | Content-Type 검증 없이 `json.loads()` 호출 |
| SEC-M-016 | CONFIRMED | 보존 정책 없음 |
| SEC-L-001 | CONFIRMED | `docker-compose.yml` 포트 `"8421:8421"` 0.0.0.0 바인딩 확인 |
| SEC-L-002 | CONFIRMED | `boto3`, `requests`가 scripts/에서 사용되나 requirements.txt 미등재 |
| SEC-L-003 | CONFIRMED | `history_rebuilt.db`(38MB, 644), `history_clean.db`(0바이트) 방치 확인 |
| SEC-L-004 | CONFIRMED | `_ALLOWED_LOG_NAMES` 화이트리스트는 있으나 인증 없음 |
| SEC-L-005 | CONFIRMED | ticker 길이 제한 없음 |
| SEC-L-006 | CONFIRMED | `os.environ["KEY"]` 패턴 `sync_to_r2.py:11` 등 확인 |
| SEC-L-007 | CONFIRMED | `web-next/` .dockerignore 없음 |
| SEC-L-008 | CONFIRMED | Discord `error_msg`에 내부 오류 메시지 포함 |
| SEC-L-009 | CONFIRMED | `ThreadingHTTPServer(("", PORT), ...)` 빈 문자열 바인딩 |

---

## 오탐 확정 목록 (수정 작업에서 제외 권고)

### SEC-H-010 — PRAGMA/ALTER TABLE f-string (FALSE_POSITIVE)

**판정:** 오탐  
**근거:**  
`_migrate_add_column(cursor, table_name, column_name, column_def)` 함수는 코드베이스 내에서 단 하나의 호출 경로만 존재한다:

```python
# db/init_db.py:173–174
for table_name, column_name, column_def in MIGRATION_COLUMNS:
    _migrate_add_column(cursor, table_name, column_name, column_def)
```

`MIGRATION_COLUMNS`는 `db/init_db_schema.py:378`에 하드코딩된 튜플 리스트로, 런타임에 외부 입력이 개입할 수 없다. `init_db()` / `init_schema()` 호출자(server.py, run_pipeline.py, docker-entrypoint.sh, tests/) 모두 인자 없이 호출한다. 함수 시그니처 자체는 방어적이지 않으나, **현재 코드에서 익스플로잇 가능한 외부 입력 경로가 존재하지 않는다.**  
→ 미래 확장 시 입력 검증 추가는 권장하나, 현재 즉각 수정 필요한 취약점은 아님.

---

### SEC-H-014 — DART API 키 URL 로그 노출 (FALSE_POSITIVE)

**판정:** 오탐  
**근거:**  
보고서는 `logger.error(f"DART API 호출 실패 ({stock_code}): {e}")` 에서 URL(키 포함)이 노출된다고 주장했다. 실제 Python 동작 검증:

```python
# 검증 결과
e = urllib.error.HTTPError(url_with_key, 401, 'Unauthorized', {}, None)
str(e)  # → "HTTP Error 401: Unauthorized"   (URL 미포함)

e2 = urllib.error.URLError('timed out')
str(e2)  # → "<urlopen error timed out>"   (URL 미포함)
```

`urllib`의 `HTTPError.__str__()`과 `URLError.__str__()`은 요청 URL을 포함하지 않는다. `{e}` f-string 보간 시에도 URL이 출력되지 않는다. `data/fetch_fundamentals_sources.py:179`와 `:421`의 로그 문은 모두 안전하다.  
→ 수정 불필요.

---

### SEC-M-004 — Discord Webhook SSRF (FALSE_POSITIVE)

**판정:** 오탐  
**근거:**  
`DISCORD_WEBHOOK_URL`은 `.env` 파일에서 컨테이너 시작 시 1회 주입되며, 어떤 API 엔드포인트도 환경변수를 수정하는 기능을 제공하지 않는다 (코드 전수 확인). SSRF가 성립하려면 공격자가 이미 `.env` 파일 또는 컨테이너 환경을 변조할 수 있어야 한다 — 이미 시스템 침해가 완료된 상태다. 일반적인 SSRF 정의(신뢰된 서버로 하여금 공격자가 지정한 URL에 요청하게 하는 것)와 다르게, 여기서는 URL 자체가 공격자 제어 하에 있지 않다.  
→ 수정 불필요.

---

## CONFIRMED 이슈 재확인

### 즉시 수정 필요 (CRITICAL / HIGH)

**SEC-C-001 — 무인증 API**  
`do_GET`, `do_POST`, `do_PUT`, `do_DELETE` 전체 경로에 Authorization 검증 코드 없음. `ALLOWED_ORIGIN="*"`로 외부 브라우저에서도 접근 가능. Tailscale 격리만 방어선.

**SEC-C-002 — Gemini API 키 URL 노출**  
`publish_blog.py:43`, `:62`에서 `?key={GEMINI_API_KEY}` 직접 삽입. `.env` 파일에서 실제 키 확인됨: `AIzaSyAcMkwKZt9Bxe-yU4zLP9zOa-KW6xsRRPw` (Google API 서버 액세스 로그, `publish_blog.log`에 노출됨).

**SEC-C-003 — DB 파일 권한**  
```
-rw-r--r-- history.db       2.7MB  (운영 DB)
-rw-r--r-- history_rebuilt.db 38MB (복구 임시 파일, 방치)
-rw------- history.db.bak   38MB   (올바른 600)
-rw------- history.db.corrupted (올바른 600)
```
운영 DB와 임시 복구 파일만 644로 잘못 설정됨.

**SEC-H-005 — /api/file 화이트리스트 미적용**  
`universe_cache.json`(126KB, 672종목 재무), `search_keywords.json`, `discovery_keywords.json` 이 모두 `/api/file?name=xxx.json` 으로 접근 가능하다. INTEL_FILES에 없는 파일임에도 서빙됨.

**SEC-H-009 — cron 환경변수 전파 누락**  
`docker-entrypoint.sh:6` 루프에 `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `GOOGLE_GEMINI_API_KEY`, `SANITY_API_WRITE_TOKEN`, `SANITY_PROJECT_ID` 누락. 실제 `.env`에 이 키들이 존재하므로 cron 잡 `sync_to_r2.py`(07:50)와 `publish_blog.py`(07:55)가 `KeyError`로 매일 조용히 실패 중.

**SEC-H-003 — 프록시 경로 인젝션 (LIKELY)**  
직접적인 파일시스템 탈출은 제한적이나, `%2e%2e` percent-encoded 세그먼트가 Next.js catch-all 라우트를 통해 Flask에 전달될 때 Node.js `fetch()`가 URL 정규화 전에 요청을 보내는 경우가 있을 수 있다. Flask의 `_serve_static` 방어는 `".." in safe.parts` 체크로 일부 차단하나, `resolve().is_relative_to()` 미적용 상태.

**SEC-M-014 — output/intel 파일 권한 혼재**  
민감 파일(`cio-briefing.md`)은 644, 대부분의 운영 파일은 올바르게 600 설정됨. 추가 확인 결과:
- 644: `cio-briefing.md`, `health_check.json`, `screener_results.json`, `regime.json`, `sector_scores.json`, `search_keywords.json`, `universe_cache.json`
- 600: `portfolio_summary.json`, `marcus-analysis.md`, `fundamentals.json`, `news.json`, `opportunities.json` 등 대부분

---

## 수정 우선순위 조정 권고

| 우선순위 | 이슈 | 조정 이유 |
|---------|------|-----------|
| 즉시 | SEC-H-009 | cron 잡이 매일 실패 중 (운영 영향) |
| 즉시 | SEC-C-003 | `chmod 600 db/history.db db/history_rebuilt.db` (1줄 명령) |
| 즉시 | SEC-C-002 | Gemini 키가 실제 키 값으로 서버 로그에 매일 기록 중 |
| 제외 | SEC-H-010 | FALSE_POSITIVE — 수정 불필요 |
| 제외 | SEC-H-014 | FALSE_POSITIVE — 수정 불필요 |
| 제외 | SEC-M-004 | FALSE_POSITIVE — 수정 불필요 |
| 재분류 | SEC-H-003 | LIKELY → 방어 코드 일부 존재, 완전 제거보다 `is_relative_to()` 추가로 충분 |
| 재분류 | SEC-M-011 | LIKELY → CSP 부재(SEC-H-006)와 묶어 처리, URL sanitize 1줄 추가 |

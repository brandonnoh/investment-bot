# 데이터 무결성 / 민감정보 보안 감사 보고서

**감사 에이전트:** data-integrity-auditor  
**감사 일시:** 2026-05-02  
**적용 기준:** OWASP A02 (암호화 실패), A09 (보안 로깅 및 모니터링 실패)  
**범위:** `db/ssot.py`, `db/ssot_wealth.py`, `web/api.py`, `web/api_advisor.py`, `scripts/run_marcus.py`, `scripts/run_jarvis.py`, `web/claude_caller.py`, `output/intel/` 권한, `logs/` 권한

---

## 요약 (Executive Summary)

| 심각도 | 건수 |
|--------|------|
| CRITICAL | 2 |
| HIGH | 5 |
| MEDIUM | 4 |
| LOW | 3 |
| INFO | 2 |
| **합계** | **16** |

핵심 위험: 인증 없는 금융 API 전체 공개 (CRITICAL), DB·백업 파일 전 세계 읽기 가능 (CRITICAL), Claude AI에 전체 포트폴리오 평균단가/손익 전송 (HIGH), 로그 파일 전 세계 읽기 가능 (HIGH), DART API 키 URL 포함 (HIGH).

---

## 발견 사항

### SEC-D-001
**파일:** `web/server.py:37` — `ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")`  
**심각도:** CRITICAL  
**OWASP:** A02 (암호화 실패) / A05 (보안 설정 오류)  
**설명:** Flask API(포트 8421)에 인증·인가 메커니즘이 전혀 없다. JWT, 세션 쿠키, API 키 등 어떠한 접근 제어도 없이 `GET /api/data`, `GET /api/wealth`, `GET /api/analysis-history`, `POST /api/investment-advice` 등 전체 금융 데이터 엔드포인트가 네트워크에 열려 있다.  
**증거:** `web/server.py` 전체 `do_GET`/`do_POST` 핸들러에 `Authorization` 헤더 또는 세션 확인 코드 없음. `ALLOWED_ORIGIN` 기본값이 `"*"` (와일드카드)이어서 CORS도 비제한.  
**영향:** Tailscale VPN(100.90.201.87) 접근 권한이 있는 모든 주체 또는 동일 네트워크 노출 시 `avg_cost`, `qty`, `pnl_krw`, 전체 자산 규모, 비금융 자산 상세 정보를 인증 없이 조회 가능. `POST /api/wealth/assets`로 비금융 자산 추가·수정·삭제도 무인증 허용.

---

### SEC-D-002
**파일:** `db/history.db:0`, `db/history_rebuilt.db:0`  
**심각도:** CRITICAL  
**OWASP:** A02 (암호화 실패)  
**설명:** SQLite DB 파일이 암호화 없이 평문 저장, 파일 권한이 `rw-r--r--` (644)로 소유자 이외 읽기 가능.  
**증거:**
```
-rw-r--r--@ 1 jarvis staff  2703360 history.db
-rw-r--r--  1 jarvis staff 38400000 history_rebuilt.db
```
`history.db`에는 `holdings`(종목·수량·평균단가·계좌), `transactions`(매매 내역), `total_wealth_history`(일별 전체 자산), `portfolio_history`(holdings_snapshot 포함), `analysis_history`(Claude 분석 전문 — 포트폴리오 상세 포함), `advisor_strategies`(자본금·대출 정보·AI 어드바이스 전문) 테이블이 저장된다.  
**영향:** 동일 OS 사용자나 동일 그룹의 다른 프로세스/사용자가 파일을 직접 읽어 모든 금융 데이터 추출 가능. Docker 컨테이너 탈출 시 즉시 전체 금융 이력 노출. `history_rebuilt.db`는 38MB로 복구 작업 중 생성된 파일이며 영구 잔존 중.

---

### SEC-D-003
**파일:** `output/intel/cio-briefing.md:0`  
**심각도:** HIGH  
**OWASP:** A02 (암호화 실패)  
**설명:** `cio-briefing.md`가 `rw-r--r--` (644) 권한으로 생성되며, 파일 내부에 개인 금융 정보가 포함된다.  
**증거:**
```
-rw-r--r-- 1 jarvis staff 7376 cio-briefing.md
```
파일 내용 샘플 (실제 파일에서 확인):
```
| 현대차 | 531,000원 | 🔴 -4.50% | 51.67 중립 | **관망** | ... 매입손익 +2.31% ...
| 삼성전자 | 220,500원 | 🔴 -2.43% | ... 평단 대비 +8.57% 수익 쿠션 유효
| TIGER 코리아AI전력기 | 27,245원 | ... +62% 수익 중 20~30% 분할 매도 고려
```
보유 종목별 현재가, 평균단가 대비 수익률, 보유 수량 기반 액션 판단이 평문 파일로 저장된다.  
**영향:** 동일 OS 사용자, 컨테이너 내부 프로세스, 파일 시스템 스캔 도구 등에 의해 개인 투자 포지션 상세 노출.

---

### SEC-D-004
**파일:** `scripts/run_marcus.py:440-482`, `scripts/run_jarvis.py:93-149`  
**심각도:** HIGH  
**OWASP:** A02 (암호화 실패)  
**설명:** Claude AI(Anthropic 외부 서버)로 전송되는 프롬프트에 전체 포트폴리오 요약(`portfolio_summary.json`)이 포함된다. `portfolio_summary.json`에는 `avg_cost`(평균단가), `qty`(수량), `pnl_krw`(손익 금액), `pnl_pct`(손익률), `current_value_krw`(현재 평가금액)이 담겨 있다.  
**증거:**
- `run_marcus.py:441`: `portfolio_summary = _load_json(INTEL_DIR / "portfolio_summary.json", "portfolio_summary")`
- `run_marcus.py:477`: `portfolio_summary=portfolio_summary` → `_assemble_prompt()`에 삽입 후 Claude CLI로 전송
- `web/advisor_data.py:100-143`: `_load_portfolio()` 함수가 종목별 `avg_cost`, `qty`, `pnl_pct`를 마크다운 테이블로 구성하여 `_build_user_message()`에 삽입, `call_claude()` 또는 `stream_via_api()`로 Anthropic API 전송
- `portfolio_summary.json` 실제 키 목록: `['ticker', 'name', 'avg_cost', 'qty', 'current_value_krw', 'invested_krw', 'pnl_krw', 'pnl_pct', ...]`  
**영향:** 개인 금융 정보(매수 단가, 보유 수량, 손익)가 제3자(Anthropic) 서버로 전송된다. Anthropic 약관 상 학습 데이터 활용 가능성 및 데이터 처리 위탁 문제가 발생한다.

---

### SEC-D-005
**파일:** `data/fetch_fundamentals_sources.py:164-179`, `data/fetch_fundamentals_sources.py:415`  
**심각도:** HIGH  
**OWASP:** A09 (보안 로깅 및 모니터링 실패)  
**설명:** DART API 키가 HTTP 요청 URL의 쿼리 파라미터(`crtfc_key=`)에 직접 포함된다. Python `urllib`의 `URLError` 예외 메시지가 URL을 포함하여 로그에 출력될 수 있다.  
**증거:**
```python
# fetch_fundamentals_sources.py:164-166
url = (
    f"https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
    f"?crtfc_key={api_key}"   # API 키가 URL에 포함
    ...
)
# fetch_fundamentals_sources.py:415
url = f"...?corp_code={corp_code}&crtfc_key={api_key}"
```
`logger.error(f"DART API 호출 실패 ({stock_code}): {e}")` — 네트워크 오류 시 `{e}` 내부에 URL이 포함될 수 있다.  
**영향:** 로그 파일이 `rw-r--r--`(644) 권한이므로 DART API 키가 로그를 통해 노출될 위험. 또한 서버 측 HTTP 로그(외부 프록시·방화벽)에 API 키가 기록될 수 있다. DART API는 금융감독원 Open API로, 키 노출 시 제3자가 기업 재무 정보를 무제한 수집 가능.

---

### SEC-D-006
**파일:** `logs/*.log:0`  
**심각도:** HIGH  
**OWASP:** A09 (보안 로깅 및 모니터링 실패)  
**설명:** `logs/` 디렉토리 내 거의 모든 로그 파일이 `rw-r--r--`(644) 권한으로 생성된다. `refresh_prices.log`는 17MB, `pipeline.log`는 362KB, `universe_cache.log`는 98KB에 달한다.  
**증거:**
```
-rw-r--r-- 1 jarvis staff  17266110 refresh_prices.log
-rw-r--r-- 1 jarvis staff    370778 pipeline.log
-rw-r--r-- 1 jarvis staff   1954186 alerts_watch.log
-rw-r--r-- 1 jarvis staff    532874 launchd_alerts.log
```
예외: `news_notify.log`만 `rw-------`(600).  
**영향:** pipeline.log에는 `get_holdings()` 반복 호출 결과(보유 종목 목록) 흔적이 포함될 수 있다. 시스템 접근 권한이 있는 모든 사용자 또는 컨테이너 내 다른 프로세스가 파이프라인 실행 이력, 종목 변동 이력을 읽을 수 있다.

---

### SEC-D-007
**파일:** `web/api.py:162-163`, `web/api.py:249-250`, `web/server.py:292`, `web/server.py:334`, `web/server.py:366`  
**심각도:** MEDIUM  
**OWASP:** A09 (보안 로깅 및 모니터링 실패)  
**설명:** 내부 예외 메시지가 `str(e)` 형태로 HTTP 응답 JSON에 포함되어 클라이언트에 반환된다.  
**증거:**
```python
# api.py:163
return {"ok": False, "error": str(e)}
# api.py:250
return {"error": str(e)}
# server.py:292, 334, 366
self.send_json({"error": str(e)}, 400)
```
**영향:** 예외 메시지에 파일 경로, DB 스키마 정보, 내부 상태가 포함될 수 있어 정보 노출(Information Disclosure) 위험. 인증이 없는 API이므로 외부에서 의도적으로 오류를 유발하여 내부 구조 파악에 이용 가능.

---

### SEC-D-008
**파일:** `output/intel/` 디렉토리  
**심각도:** MEDIUM  
**OWASP:** A02 (암호화 실패)  
**설명:** `output/intel/` 디렉토리 자체는 `drwx------`(700)이나, 내부 일부 파일이 `rw-r--r--`(644)로 혼재한다. 금융 정보를 포함한 파일들의 권한이 불일치한다.  
**증거:**
```
# 민감 파일 — 올바른 600
-rw-------  portfolio_summary.json  (avg_cost, qty, pnl_krw)
-rw-------  marcus-analysis.md
-rw-------  daily_report.md
# 비민감 파일이지만 644로 혼재
-rw-r--r--  cio-briefing.md         ← 포트폴리오 상세 포함! (SEC-D-003)
-rw-r--r--  regime.json
-rw-r--r--  screener_results.json
-rw-r--r--  sector_scores.json
-rw-r--r--  search_keywords.json
-rw-r--r--@ universe_cache.json      (672개 종목 재무 데이터)
```
**영향:** `cio-briefing.md`가 644인 것이 가장 위험. `universe_cache.json`(126KB, 672종목 PER/PBR/ROE 데이터)도 644로 불필요하게 공개.

---

### SEC-D-009
**파일:** `db/ssot_wealth.py:144-172`, `db/maintenance.py:28-117`  
**심각도:** MEDIUM  
**OWASP:** A02 (암호화 실패)  
**설명:** `total_wealth_history`, `portfolio_history`, `analysis_history`, `advisor_strategies` 테이블에 대한 데이터 보존 정책(삭제·만료)이 존재하지 않는다. `db/maintenance.py`의 `purge_old_data()`는 `prices`, `macro`, `news` 테이블만 정리하며 금융 개인정보 테이블은 무기한 보존된다.  
**증거:**
- `maintenance.py:111`: `DELETE FROM news WHERE ...` — 뉴스 정리
- `maintenance.py:79,105`: `prices`, `macro` 정리
- `total_wealth_history`, `portfolio_history`, `analysis_history`, `advisor_strategies`, `holdings`, `transactions`: 삭제 쿼리 없음  
**영향:** 일별 전체 자산 스냅샷이 서비스 시작일부터 영구 누적. 향후 DB 파일 노출 시 수년치 자산 변동 이력이 일괄 유출. `portfolio_history.holdings_snapshot`(JSON)에 매일의 보유 종목·수량·단가가 기록됨.

---

### SEC-D-010
**파일:** `scripts/discord_notify.py:47-100`, `scripts/run_marcus.py:250-267`  
**심각도:** MEDIUM  
**OWASP:** A09 (보안 로깅 및 모니터링 실패)  
**설명:** Discord Webhook으로 전송되는 메시지에 투자 판단(매수·매도·익절·추가매수 권고)과 종목별 액션이 포함된다. Discord는 제3자 서비스이며, 단일 Webhook URL로 모든 알림이 전송된다.  
**증거:**
```python
# discord_notify.py:90-98 (_extract_jarvis_summary)
for line in md_text.splitlines():
    if "|" in line and ("익절" in line or "추가" in line or "금지" in line or "매수" in line):
        # 종목명, 액션을 Discord로 전송
        actions.append(f"• {name}: {action}")
# run_marcus.py:258
payload = {"content": f"❌ 마커스 분석 실패: {error_msg}"}
```
Marcus 분석 실패 시 오류 메시지(`error_msg`)도 Discord로 전송되며, 이 메시지에 내부 파일 경로 등이 포함될 수 있다.  
**영향:** 개인 투자 액션 정보(어떤 종목을 언제 매수·매도하는지)가 Discord(미국 서버) 제3자에 저장. Webhook URL 노출 시 임의 메시지 전송 가능(Webhook 스팸/피싱).

---

### SEC-D-011
**파일:** `web/claude_caller.py:68-94`, `web/claude_caller.py:131-171`  
**심각도:** LOW  
**OWASP:** A02 (암호화 실패)  
**설명:** `ANTHROPIC_API_KEY`가 HTTP 요청 헤더(`x-api-key`)로 전송되며, 예외 처리 시 `print(f"[advisor] API 호출 실패, CLI 폴백: {e}")` 로그에 예외 내용이 포함된다. 현재는 API 키 값 자체가 로그에 출력되지는 않으나, `urllib.request.urlopen()` 예외가 요청 객체를 포함할 경우 간접 노출 가능성 있음.  
**증거:** `claude_caller.py:126`: `print(f"[advisor] API 호출 실패, CLI 폴백: {e}")`  
**영향:** API 호출 실패 로그가 `logs/pipeline.log` 또는 표준 출력으로 기록되며, 해당 로그가 644 권한인 경우 정보 노출 가능. 현재 이 로그 파일의 권한은 확인 범위 외이나 동일 패턴 적용 시 위험.

---

### SEC-D-012
**파일:** `db/history.db.bak:0`, `db/history.db.corrupted:0`  
**심각도:** LOW  
**OWASP:** A02 (암호화 실패)  
**설명:** DB 복구 작업 중 생성된 백업 파일 2개(`history.db.bak`, `history.db.corrupted`)가 `rw-------`(600) 권한으로 존재한다. 권한은 적절하나 38MB 파일이 장기간 방치되어 불필요한 데이터 복사본이 남아 있다.  
**증거:**
```
-rw-------@ 1 jarvis staff 38608896 history.db.bak
-rw-------@ 1 jarvis staff 38608896 history.db.corrupted
-rw-r--r--  1 jarvis staff 38400000 history_rebuilt.db   ← 644!
```
`history_rebuilt.db`는 `rw-r--r--`(644)로 38MB의 전체 금융 이력 DB가 공개 읽기 가능 상태.  
**영향:** 복구 임시 파일이 정리되지 않고 잔존. 특히 `history_rebuilt.db`는 SEC-D-002와 같은 위험.

---

### SEC-D-013
**파일:** `web/api_advisor.py:18-36`, `db/ssot_wealth.py:1-352`  
**심각도:** LOW  
**OWASP:** A02 (암호화 실패)  
**설명:** `advisor_strategies` 테이블에 저장되는 `recommendation` 필드는 Claude AI가 생성한 투자 전략 전문(수천 자)으로, 자본금(`capital`), 대출 정보(`loans_json`), 월 저축액(`monthly_savings`)과 함께 평문 DB에 무기한 저장된다.  
**증거:**
```python
# api_advisor.py:30-36
cur = conn.execute(
    """INSERT INTO advisor_strategies
       (capital, leverage_amt, risk_level, recommendation, saved_at, loans_json, monthly_savings)
       VALUES (?, ?, ?, ?, ?, ?, ?)""",
    (capital, leverage_amt, risk_level, recommendation, ...)
)
```
**영향:** 사용자가 "전략 저장"을 누를 때마다 자본금·대출·투자 전략 전문이 DB에 누적. 보존 정��� 없음(SEC-D-009).

---

### SEC-D-014
**파일:** `web/server.py:340-345`  
**심각도:** INFO  
**OWASP:** A02  
**설명:** POST 요청 바디 최대 크기가 10MB로 제한되어 있다. 이는 적절한 방어 조치이나, 응용 레이어 DoS(서비스 거부) 방지 측면에서 추가 요청 횟수 제한(rate limit)이 없다.  
**증거:**
```python
# server.py:343-344
if length > 10 * 1024 * 1024:
    raise ValueError("요청 바디가 너무 큽니다 (최대 10MB)")
```
**영향:** `POST /api/investment-advice`는 Claude API 호출을 유발하므로, 반복 호출 시 Anthropic API 비용이 발생. 인증 없이 무제한 호출 가능.

---

### SEC-D-015
**파일:** `web/server.py:121-138`  
**심각도:** INFO  
**OWASP:** A02  
**설명:** `/api/file` 엔드포인트의 경로 순회(path traversal) 방어가 `"/" in name` 및 `"\\" in name` 검사로 구현되어 있다. `parse_qs`가 URL 인코딩(`%2F`)을 디코딩하므로 현재는 실질적 우회 불가능하다. 방어 논리가 올바르게 동작함을 확인.  
**증거:**
```python
# 테스트 결과
parse_qs('name=..%2F.env')  → {'name': ['../.env']}
# "/" in name 검사로 차단됨
```
**영향:** 현재 취약점 없음. 단, `INTEL_DIR` 경계 검증(절대 경로 비교) 없이 문자열 검사에만 의존하므로 향후 코드 변경 시 주의 필요.

---

### SEC-D-016
**파일:** `output/intel/health_check.json:0`, `output/intel/regime.json:0`  
**심각도:** INFO  
**OWASP:** A02  
**설명:** `health_check.json`과 `regime.json`이 `rw-r--r--`(644)이나, 내부 데이터는 VIX, 시장 레짐 등 공개 시장 정보로 개인 금융 정보를 포함하지 않는다.  
**증거:**
```
regime.json keys: ['classified_at', 'regime', 'confidence', 'panic_signal', 'vix', 'fx_change', 'oil_change', 'strategy']
```
**영향:** 민감 정보 없음. 시스템 운영 상태 정보 최소 노출.

---

## 권고 조치 (우선순위 순)

### 즉시 조치 (P0)

1. **[SEC-D-002] DB 파일 권한 수정:**
   ```bash
   chmod 600 /Users/jarvis/Projects/investment-bot/db/history.db
   chmod 600 /Users/jarvis/Projects/investment-bot/db/history_rebuilt.db
   rm /Users/jarvis/Projects/investment-bot/db/history_rebuilt.db
   rm /Users/jarvis/Projects/investment-bot/db/history.db.bak
   rm /Users/jarvis/Projects/investment-bot/db/history.db.corrupted
   ```

2. **[SEC-D-003] cio-briefing.md 생성 권한 수정:**
   `run_jarvis.py`에서 파일 생성 시 `os.chmod(OUTPUT_FILE, 0o600)` 추가.

### 단기 조치 (P1)

3. **[SEC-D-001] API 서버 접근 제어 강화:**
   최소한 공유 시크릿 헤더(`X-API-Key`) 또는 IP 화이트리스트 미들웨어 추가. Tailscale 환경이므로 `TAILSCALE_CLIENT_ID` 기반 인증 고려.

4. **[SEC-D-006] 로그 파일 권한 수정:**
   모든 로그 파일 생성 시 `rw-------`(600)으로 설정. `run_background()` 함수의 `log_path.open("a")` 호출 전 `os.umask(0o077)` 적용.

5. **[SEC-D-005] DART API 키를 URL 쿼리에서 제거:**
   `crtfc_key`를 HTTP Authorization 헤더로 이동하거나, 로그 출력 시 URL에서 키 값을 마스킹:
   ```python
   safe_url = url.replace(api_key, "***")
   logger.error(f"DART API 호출 실패 ({stock_code}): {e} [url={safe_url}]")
   ```

### 중기 조치 (P2)

6. **[SEC-D-009] 금융 데이터 보존 정책 추가:**
   `maintenance.py`에 `total_wealth_history`(2년 초과 삭제), `analysis_history`(1년 초과 삭제), `advisor_strategies`(6개월 초과 삭제) 정책 추가.

7. **[SEC-D-004] Claude 전송 데이터 최소화:**
   `portfolio_summary.json` 전송 시 `avg_cost`를 제거하고 현재 평가 비중만 전달. `advisor_data.py`의 `_load_portfolio()`에서 `avg_cost` 컬럼 제외 또는 범주형 표현(예: "대형주 40%") 으로 대체.

8. **[SEC-D-007] 예외 메시지 일반화:**
   HTTP 응답의 `{"error": str(e)}`를 제너릭 메시지로 대체하고, 상세 오류는 서버 로그에만 기록.

9. **[SEC-D-010] Discord 전송 최소화:**
   Webhook으로 전송되는 종목별 액션(매수·매도)을 제거하거나 익명화. 실패 오류 메시지에서 내부 경로 마스킹.

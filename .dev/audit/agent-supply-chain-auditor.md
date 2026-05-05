# 공급망/의존성 보안 감사 보고서

**감사 일시:** 2026-05-02  
**감사 범위:** OWASP A06 (Vulnerable and Outdated Components) + 공급망 보안  
**감사 도구:** 직접 파일 Read + npm audit + docker inspect  
**감사 대상 파일:**
- `requirements.txt`
- `web-next/package.json` + `package-lock.json`
- `Dockerfile` (루트)
- `web-next/Dockerfile`
- `docker-compose.yml`
- `crontab.docker`
- `docker-entrypoint.sh`

---

## 발견 사항 요약

| ID | 파일 | 심각도 | 범주 |
|----|------|--------|------|
| SEC-S-001 | `requirements.txt:3` | HIGH | 버전 범위 — Python 의존성 고정 없음 |
| SEC-S-002 | `requirements.txt:3,7,8` | MEDIUM | Lockfile 없음 — Python 재현 불가 |
| SEC-S-003 | `requirements.txt` | MEDIUM | 미선언 의존성 — boto3/requests 사용 중이나 목록 없음 |
| SEC-S-004 | `web-next/package.json:11-27` | MEDIUM | 버전 범위 (`^`) — 대부분 의존성 미고정 |
| SEC-S-005 | `web-next/package-lock.json` | INFO | postcss 내부 번들 버전 취약 (GHSA-qx2v-qp2m-jg93) |
| SEC-S-006 | `Dockerfile:1` | MEDIUM | 이미지 태그 미고정 — `python:3.12-slim` digest 없음 |
| SEC-S-007 | `Dockerfile:5` | MEDIUM | 이미지 태그 미고정 — `@anthropic-ai/claude-code` 버전 없음 |
| SEC-S-008 | `Dockerfile:5` | LOW | apt 패키지 버전 미고정 (`nodejs npm cron`) |
| SEC-S-009 | `Dockerfile` / `web-next/Dockerfile` | HIGH | root 실행 — `USER` 지시어 없음 |
| SEC-S-010 | `web-next/Dockerfile:1,8` | MEDIUM | `node:20-alpine` digest 없음 |
| SEC-S-011 | `web-next/Dockerfile` | LOW | web-next `.dockerignore` 없음 — node_modules 등 과다 COPY 위험 |
| SEC-S-012 | `docker-compose.yml:13-14` | MEDIUM | 호스트 `.claude/` 자격증명 컨테이너 마운트 |
| SEC-S-013 | `docker-compose.yml:7,40` | MEDIUM | 포트 0.0.0.0 바인딩 — 모든 인터페이스 노출 |
| SEC-S-014 | `docker-entrypoint.sh:6-10` | MEDIUM | 시크릿을 `/etc/environment` (0644) 에 기록 |
| SEC-S-015 | `crontab.docker` | INFO | 시크릿 하드코딩 없음 — 환경 변수 참조 방식 (양호) |
| SEC-S-016 | `web-next/src/app/api/[...path]/route.ts:16` | MEDIUM | 프록시 경로 검증 없음 — SSRF/경로 트래버설 가능 |

---

## 상세 항목

---

### SEC-S-001
**파일:라인** `requirements.txt:3,7,8`  
**설명** Python 의존성 전체가 최소 버전(`>=`) 또는 범위 지정으로만 고정되어 있음. `yfinance>=0.2`, `pytest>=7.0`, `ruff>=0.4.0` — 빌드 시점마다 다른 버전이 설치될 수 있음.  
**심각도** HIGH  
**OWASP** A06:2021 — Vulnerable and Outdated Components  
**증거**
```
yfinance>=0.2
pytest>=7.0
ruff>=0.4.0
```
현재 컨테이너에 설치된 버전: `yfinance==1.2.0`, `pytest` 미확인. `>=0.2`는 0.2에서 최신 메이저 버전까지 모두 허용함.  
**영향** 상위 호환성 파괴(breaking change) 또는 취약한 신규 버전이 다음 `docker build` 시 조용히 설치될 수 있음. 공급망 공격자가 신뢰받는 패키지의 새 버전에 악성 코드를 삽입하면 탐지 없이 설치됨.

---

### SEC-S-002
**파일:라인** `requirements.txt` (전체), 프로젝트 루트  
**설명** Python용 lockfile(`pip.lock`, `Pipfile.lock`, `poetry.lock`)이 존재하지 않음. 빌드 재현성을 보장할 방법 없음.  
**심각도** MEDIUM  
**OWASP** A06:2021 — Vulnerable and Outdated Components  
**증거**
```bash
# 조사 결과
ls pip.lock Pipfile.lock poetry.lock → 모두 NOT FOUND
```
Node.js 측은 `package-lock.json` (lockfileVersion: 3) 이 존재하고 `npm ci`로 설치하여 재현성 확보됨. Python 측은 동일한 보호가 없음.  
**영향** 동일한 `requirements.txt`로 서로 다른 빌드 환경에서 다른 패키지 버전이 설치됨. 의존성 컨퓨전(dependency confusion) 공격 표면.

---

### SEC-S-003
**파일:라인** `requirements.txt` (전체), `scripts/sync_to_r2.py:5`, `scripts/publish_blog.py:8`  
**설명** 실제로 사용하는 `boto3`, `requests` 패키지가 `requirements.txt`에 선언되어 있지 않음. 컨테이너에는 설치되어 있으나(`boto3==1.43.2`, `requests==2.33.1`) 어떻게 설치된 것인지 추적 불가.  
**심각도** MEDIUM  
**OWASP** A06:2021 — Vulnerable and Outdated Components  
**증거**
```python
# scripts/sync_to_r2.py:5
import boto3

# scripts/publish_blog.py:8
import requests
```
```bash
# 컨테이너 확인
docker exec investment-bot pip3 show boto3 requests
→ boto3==1.43.2, requests==2.33.1
```
`requirements.txt`에는 두 패키지 모두 없음.  
**영향** 미선언 의존성은 버전 감사, 취약성 스캔, 재현 빌드에서 누락됨. `docker build` 시 어떤 버전이 설치될지 예측 불가 (yfinance의 전이 의존성으로 인해 설치되고 있을 가능성 있음).

---

### SEC-S-004
**파일:라인** `web-next/package.json:11-27`  
**설명** 14개 production 의존성 중 `next`, `react`, `react-dom` 3개만 정확한 버전(`16.2.4`, `19.2.4`)으로 고정됨. 나머지 11개는 `^`(캐럿) 범위 지정.  
**심각도** MEDIUM  
**OWASP** A06:2021 — Vulnerable and Outdated Components  
**증거**
```json
"@base-ui/react": "^1.4.0",
"lucide-react": "^1.8.0",
"react-markdown": "^10.1.0",
"recharts": "^3.8.1",
"swr": "^2.4.1",
"zustand": "^5.0.12"
```
devDependencies도 전부 `^4`, `^20`, `^19`, `^5` 등 메이저 고정.  
**영향** `^`는 마이너/패치 자동 업그레이드를 허용. `package-lock.json`이 있어 `npm ci` 사용 시 재현성은 확보되나, lockfile 갱신(`npm install`) 시 취약 버전이 유입될 수 있음. lockfile 없이 빌드하는 환경(예: 개발 중)에서는 더 위험.

---

### SEC-S-005
**파일:라인** `web-next/package-lock.json` (내부 번들)  
**설명** `next@16.2.4`가 내부적으로 번들하는 `postcss@8.4.31`이 알려진 XSS 취약점 대상 버전임. `npm audit`이 moderate 심각도로 탐지.  
**심각도** MEDIUM (moderate — npm audit 기준)  
**OWASP** A06:2021 — Vulnerable and Outdated Components  
**증거**
```
Advisory: GHSA-qx2v-qp2m-jg93
Title: PostCSS has XSS via Unescaped </style> in its CSS Stringify Output
Package: postcss
Vulnerable range: <8.5.10
Installed (via next): node_modules/next/node_modules/postcss@8.4.31
Fixed version: postcss@8.5.10 (top-level: 8.5.10 ✓, but next 내부 번들: 8.4.31 ✗)
```
최상위 `postcss`는 `8.5.10`으로 안전하지만, `next` 내부 번들은 `8.4.31`로 취약 버전 사용.  
**영향** CSS stringify 출력에서 `</style>` 미이스케이프로 XSS 발생 가능. `npm audit fix`는 major downgrade(`9.3.3`)를 제안 — next@16.x 업그레이드로 해결 필요.

---

### SEC-S-006
**파일:라인** `Dockerfile:1`  
**설명** 기반 이미지 `python:3.12-slim`에 정확한 패치 버전 또는 SHA256 digest가 없음.  
**심각도** MEDIUM  
**OWASP** A06:2021 — Vulnerable and Outdated Components  
**증거**
```dockerfile
FROM python:3.12-slim
```
권장 형식 예시: `FROM python:3.12.10-slim` 또는 `FROM python:3.12-slim@sha256:abc123...`  
**영향** Docker Hub에서 `python:3.12-slim`이 조용히 갱신되면 다음 빌드 시 다른 Python 패치 버전 또는 다른 기반 OS 패키지가 포함될 수 있음. Supply-chain poisoning 공격의 진입점.

---

### SEC-S-007
**파일:라인** `Dockerfile:5`  
**설명** `npm install -g @anthropic-ai/claude-code`에 버전 지정이 없어 빌드 시 항상 최신 버전을 설치.  
**심각도** MEDIUM  
**OWASP** A06:2021 — Vulnerable and Outdated Components  
**증거**
```dockerfile
RUN apt-get update && apt-get install -y nodejs npm cron --no-install-recommends \
    && npm install -g @anthropic-ai/claude-code \
```
현재 설치된 버전: `@anthropic-ai/claude-code@2.1.117` (컨테이너 확인).  
**영향** claude CLI는 컨테이너 내부에서 Claude API 토큰(자격증명)을 직접 다루는 핵심 컴포넌트. 버전 미고정 시 새 빌드마다 다른 버전 설치, 행동 변경 또는 악성 패키지 버전 유입 위험.

---

### SEC-S-008
**파일:라인** `Dockerfile:5`  
**설명** `apt-get install -y nodejs npm cron`에 패키지 버전이 명시되어 있지 않음.  
**심각도** LOW  
**OWASP** A06:2021 — Vulnerable and Outdated Components  
**증거**
```dockerfile
RUN apt-get update && apt-get install -y nodejs npm cron --no-install-recommends \
```
권장: `nodejs=20.x.x-1 npm=10.x.x-1 cron=3.0pl1-xxx` 등 버전 고정.  
**영향** apt mirror의 패키지가 업데이트될 때 빌드 재현성 손상. Debian 취약 패치 버전이 의도치 않게 고정될 수 있음. 심각도 낮지만 재현성 원칙 위반.

---

### SEC-S-009
**파일:라인** `Dockerfile` (전체), `web-next/Dockerfile` (전체)  
**설명** 두 Dockerfile 모두 `USER` 지시어가 없어 컨테이너 프로세스가 `root(uid=0)`로 실행됨.  
**심각도** HIGH  
**OWASP** A06:2021 + CWE-269 (Improper Privilege Management)  
**증거**
```bash
# 실행 중인 컨테이너 확인
docker exec investment-bot id
→ uid=0(root) gid=0(root) groups=0(root)
```
Flask 서버(PID 1), cron 데몬, Python 스크립트 전부 root로 실행.  
**영향** 컨테이너 내 RCE 취약점 악용 시 컨테이너 내부에서 root 권한 즉시 획득. 컨테이너 탈출(container escape) 시 호스트에 root 수준 접근. 최소 권한 원칙(PoLP) 위반. 볼륨 마운트된 DB, 로그, 스크립트를 root로 수정 가능.

---

### SEC-S-010
**파일:라인** `web-next/Dockerfile:1,8`  
**설명** `node:20-alpine`에 마이너/패치 버전 또는 SHA256 digest 없음.  
**심각도** MEDIUM  
**OWASP** A06:2021 — Vulnerable and Outdated Components  
**증거**
```dockerfile
FROM node:20-alpine AS builder
FROM node:20-alpine AS runner
```
권장: `node:20.19.1-alpine3.21` 또는 `node:20-alpine@sha256:...`  
**영향** SEC-S-006과 동일. Node.js 20.x 패치 릴리즈마다 이미지가 변경될 수 있으며, 취약 Node.js 버전이 조용히 사용될 수 있음.

---

### SEC-S-011
**파일:라인** `web-next/Dockerfile:5` (`COPY . .`)  
**설명** `web-next/` 디렉토리에 `.dockerignore` 파일이 없어 `COPY . .` 실행 시 `node_modules/`, `out/`, `.next/`, `CLAUDE.md` 등이 builder 이미지에 모두 복사됨.  
**심각도** LOW  
**OWASP** A06:2021 (공격 표면 확장)  
**증거**
```bash
ls web-next/ → node_modules, out, package-lock.json, CLAUDE.md, tsconfig.tsbuildinfo 포함
cat web-next/.dockerignore → NO web-next/.dockerignore
```
루트의 `.dockerignore`는 `web-next/node_modules`, `web-next/.next`를 제외하고 있으나, `web-next/Dockerfile`은 `web-next/` 내부에서 별도 `.dockerignore` 없이 `COPY . .` 수행.  
**영향** `node_modules`가 builder 레이어에 포함되면 이미지 크기 증가. 이미 `npm ci`로 재설치하므로 기능 영향은 없으나, 이전 `npm install`에서 사용된 다른 버전 패키지나 개발 도구가 이미지 레이어에 잔류.

---

### SEC-S-012
**파일:라인** `docker-compose.yml:13-14`  
**설명** 호스트의 `~/.claude/` 디렉토리(Claude CLI 자격증명 포함)와 `~/.claude.json`이 컨테이너에 마운트됨.  
**심각도** MEDIUM  
**OWASP** A02:2021 — Cryptographic Failures / Credential Exposure  
**증거**
```yaml
volumes:
  - ~/.claude:/root/.claude-host:ro
  - ~/.claude.json:/root/.claude-host.json:ro
```
`docker-entrypoint.sh`에서 이를 `/root/.claude/`로 복사:
```bash
cp -r /root/.claude-host/. /root/.claude/
```
**영향** 컨테이너 내 RCE 시 Anthropic API 자격증명(`credentials.json`) 탈취 가능. `ro` 마운트이지만 entrypoint에서 writable 위치로 복사되어 실질적으로 쓰기 가능 사본이 컨테이너 내에 존재. 호스트 자격증명과 동일한 토큰이므로 계정 전체 접근 위험.

---

### SEC-S-013
**파일:라인** `docker-compose.yml:7,40`  
**설명** 포트 `8421`(Flask API)과 `3000`(Next.js)이 모든 네트워크 인터페이스(`0.0.0.0`)에 바인딩됨.  
**심각도** MEDIUM  
**OWASP** A05:2021 — Security Misconfiguration  
**증거**
```yaml
ports:
  - "8421:8421"   # investment-bot
  - "3000:3000"   # mc-web
```
```bash
docker port investment-bot → 8421/tcp -> 0.0.0.0:8421
docker port mc-web → 3000/tcp -> 0.0.0.0:3000
```
**영향** 호스트가 Tailscale VPN(`100.90.201.87`) 외에 다른 네트워크 인터페이스에도 연결된 경우(예: LAN, Wi-Fi), Flask API가 인증 없이 직접 노출됨. Flask API(`/api/run-pipeline`, `/api/investment-advice`)는 인증 레이어가 없으므로 내부 네트워크의 모든 호스트에서 접근 가능. `127.0.0.1:8421:8421`로 제한하거나 Tailscale 인터페이스 IP로 제한 권장.

---

### SEC-S-014
**파일:라인** `docker-entrypoint.sh:6-10`  
**설명** API 키 및 웹훅 시크릿을 `/etc/environment` 파일(퍼미션 `0644`)에 평문 기록. 컨테이너 내 모든 사용자가 읽기 가능.  
**심각도** MEDIUM  
**OWASP** A02:2021 — Cryptographic Failures  
**증거**
```bash
# docker-entrypoint.sh:6-10
for var in DISCORD_WEBHOOK_URL BRAVE_API_KEY KIWOOM_APPKEY KIWOOM_SECRETKEY DART_API_KEY; do
    val=$(printenv "$var" 2>/dev/null || true)
    if [ -n "$val" ]; then
        echo "$var=$val" >> /etc/environment
    fi
done
```
```bash
# 컨테이너 내 파일 퍼미션
docker exec investment-bot ls -la /etc/environment
→ -rw-r--r-- 1 root root 3249 May  4 14:06 /etc/environment
```
**영향** `/etc/environment`는 `world-readable`(`0644`). 컨테이너 내 non-root 프로세스(예: 향후 추가된 서비스)나 취약점을 통해 쉘 접근한 공격자가 `/etc/environment`를 읽어 5개 API 키/웹훅 URL 전체를 즉시 획득. 현재는 모든 프로세스가 root로 실행되어 실질적 위험은 낮으나, root 실행 문제(SEC-S-009) 해결 후에도 이 파일은 여전히 world-readable로 남음.

---

### SEC-S-015
**파일:라인** `crontab.docker` (전체)  
**설명** crontab에 하드코딩된 시크릿 없음. 모든 스크립트는 환경 변수를 `os.environ.get()`으로 참조. 양호.  
**심각도** INFO (문제 없음)  
**OWASP** — 해당 없음  
**증거**
```
# grep 결과: KEY|TOKEN|SECRET|PASSWORD|API_KEY → 매칭 없음
*/1 * * * * root cp /root/.claude-host/.credentials.json /root/.claude/.credentials.json 2>/dev/null || true
```
단, cron 자격증명 동기화 명령(위 1분 주기)은 호스트 자격증명 파일을 컨테이너 내 writable 경로로 복사 — SEC-S-012 참조.  
**영향** 없음 (crontab 자체는 안전).

---

### SEC-S-016
**파일:라인** `web-next/src/app/api/[...path]/route.ts:14-16`  
**설명** Next.js 프록시 라우트가 클라이언트에서 전달된 경로(`path` 파라미터)를 검증 없이 Flask API URL에 직접 연결.  
**심각도** MEDIUM  
**OWASP** A10:2021 — Server-Side Request Forgery (SSRF) 관련  
**증거**
```typescript
async function proxy(req: NextRequest, path: string[]) {
  const pathStr = path.join('/')
  const url = `${API_BASE}/api/${pathStr}${req.nextUrl.search}`
  // pathStr 검증 없이 fetch(url, ...) 호출
```
`PYTHON_API_URL`은 환경 변수로 고정(`http://investment-bot:8421`)되어 있어 외부 호스트로의 SSRF는 불가. 그러나 `../` 경로 트래버설을 통해 Flask 서버의 다른 경로 접근 시도 가능 (예: `path.join('/')` 후 `../admin` 등).  
**영향** 현재 구성에서 외부 SSRF 위험은 낮음 (`API_BASE`가 고정된 내부 서비스 URL). 그러나 경로 정규화 없이 `..`이 포함된 요청이 통과될 수 있으며, Flask 라우팅에 따라 의도치 않은 엔드포인트에 접근 가능. `API_BASE`가 환경 변수이므로 컨테이너 환경 변수 주입 취약점 발생 시 SSRF로 확장.

---

## 종합 위험 매트릭스

| 심각도 | 건수 | 항목 |
|--------|------|------|
| HIGH | 2 | SEC-S-001 (버전 범위), SEC-S-009 (root 실행) |
| MEDIUM | 9 | SEC-S-002, SEC-S-003, SEC-S-004, SEC-S-005, SEC-S-006, SEC-S-007, SEC-S-010, SEC-S-012, SEC-S-013, SEC-S-014, SEC-S-016 |
| LOW | 2 | SEC-S-008, SEC-S-011 |
| INFO | 1 | SEC-S-015 |

---

## 우선 조치 권고 (수정 우선순위)

1. **[즉시] SEC-S-009** — 두 Dockerfile에 비root USER 추가 (`useradd -r appuser` + `USER appuser`). cron은 root 필요하나 Flask는 비root로 실행 가능.
2. **[즉시] SEC-S-001 + SEC-S-002** — Python 의존성을 정확한 버전으로 고정 (`yfinance==1.2.0`, `pytest==9.0.2`, `ruff==0.x.x`) + `pip freeze > requirements.lock` 또는 `pip-tools` 도입.
3. **[단기] SEC-S-003** — `boto3==1.43.2`, `requests==2.33.1`을 `requirements.txt`에 명시 추가.
4. **[단기] SEC-S-013** — Flask API 포트를 `127.0.0.1:8421:8421` 또는 Tailscale IP로 제한. Next.js는 컨테이너 내부에서만 접근하면 되므로 포트 노출 불필요.
5. **[단기] SEC-S-014** — `/etc/environment` 퍼미션을 `0640`으로 변경 (`chmod 640 /etc/environment`). 또는 systemd secret / Docker secrets 사용.
6. **[중기] SEC-S-006, SEC-S-007, SEC-S-010** — 이미지를 정확한 버전 + SHA256 digest로 고정.
7. **[중기] SEC-S-005** — `next` 패키지를 postcss `>=8.5.10`을 번들하는 버전으로 업그레이드.
8. **[중기] SEC-S-012** — Claude 자격증명 마운트를 Init Container 패턴이나 Docker secrets로 교체하거나, entrypoint 복사 후 원본 마운트 파일 권한을 `0600`으로 강화.

---

*감사 에이전트: claude-sonnet-4-6 | 감사 방법론: 직접 파일 분석 + npm audit + docker inspect*

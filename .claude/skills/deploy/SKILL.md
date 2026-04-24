---
name: deploy
description: >
  investment-bot 배포/반영/재시작. '배포', 'deploy', '반영', '적용', 'docker',
  '빌드', 'build', '재시작', 'restart', 'docker cp', 'docker compose' 키워드가
  나오면 자동 적용. Python 소스·Next.js·Dockerfile 변경은 배포 방식이 전혀 다르므로
  반드시 이 스킬을 먼저 확인하고 smart-deploy.sh를 실행할 것.
---

# investment-bot 배포 스킬

## 핵심 원칙

**볼륨 마운트로 Python 소스는 빌드 없이 반영된다.**
`docker-compose.yml`에 `web/`, `analysis/`, `data/`, `reports/`, `scripts/`,
`config.py`, `run_pipeline.py`가 모두 볼륨 마운트됨.
→ Python 소스 변경은 `docker restart`만으로 반영. 빌드 불필요.

**`docker compose build` 없이 하는 게 목표.**
Dockerfile/requirements.txt 변경이 아닌 이상 빌드하지 않는다.
빌드가 필요할 때도 `--no-pull` 플래그로 Keychain 없이 실행.

---

## 배포 스크립트 실행 (항상 이것부터)

```bash
bash .claude/skills/deploy/scripts/smart-deploy.sh auto
```

스크립트가 git diff를 분석해서 필요한 트랙만 자동 실행한다.
무엇을 변경했는지 알면 모드를 직접 지정하는 게 더 빠르다:

| 변경 내용 | 명령 |
|-----------|------|
| Python 소스만 (`web/`, `analysis/` 등) | `bash .claude/skills/deploy/scripts/smart-deploy.sh python` |
| Dockerfile 또는 requirements.txt | `bash .claude/skills/deploy/scripts/smart-deploy.sh build` |
| Next.js (`web-next/`) | `bash .claude/skills/deploy/scripts/smart-deploy.sh web` |
| 복합 변경 | `bash .claude/skills/deploy/scripts/smart-deploy.sh auto` |

드라이런으로 미리 확인:
```bash
bash .claude/skills/deploy/scripts/smart-deploy.sh auto --dry-run
```

---

## 트랙별 내부 동작

### Python 소스 변경 (가장 빠름, ~3초)
```bash
docker restart investment-bot
```
볼륨 마운트로 이미 파일이 공유됨. 재시작만 하면 새 코드 로드.

### Dockerfile/requirements.txt 변경
```bash
docker compose build --no-pull investment-bot
docker compose up -d --no-deps investment-bot
docker restart investment-bot
```
`--no-pull`: Docker Hub 인증 스킵 → Keychain 불필요.
`python:3.12-slim`이 로컬 캐시에 없으면 실패한다 (아래 참고).

### Next.js 변경
```bash
cd web-next && npm run build && cd ..
docker cp web-next/.next/standalone/. mc-web:/app/
docker cp web-next/.next/static/. mc-web:/app/.next/static/
docker restart mc-web
docker restart investment-bot   # 항상 마지막에
```
반드시 `/. ` 형태 — 단순 `/` 사용 시 `static/static/` 중첩 버그.

---

## Git Push (코드 백업)

배포 전 코드가 커밋됐는지 확인:
```bash
git status
```
미커밋이 있으면 `/commit` 스킬로 커밋 후 `git push`.

---

## python:3.12-slim 캐시 없을 때

`--no-pull` 빌드가 실패하면 이미지가 없는 것. 인터랙티브 터미널에서:
```
! security -v unlock-keychain ~/Library/Keychains/login.keychain-db
! docker pull python:3.12-slim
```
이후 다시 `smart-deploy.sh build`.
한 번 당겨두면 이후엔 영구 캐시됨.

---

## 컨테이너 구조

| 컨테이너 | 포트 | 역할 |
|---------|------|------|
| `investment-bot` | 8421 | Flask API + 내부 cron 스케줄러 |
| `mc-web` | 3000 | Next.js standalone 프론트엔드 |

**볼륨 마운트 (Python 소스):**
`web/`, `analysis/`, `data/`, `reports/`, `scripts/`, `config.py`, `run_pipeline.py`

**HOST launchd는 전부 비활성화.** 스케줄 작업은 Docker 내부 cron만 사용.

### 현재 cron 스케줄 (KST)

| 잡 | 스케줄 | 스크립트 |
|----|--------|---------|
| alerts_watch | 매 5분 | `analysis/alerts_watch.py` |
| refresh_prices | 매 10분 | `scripts/refresh_prices.py` |
| marcus | 평일 05:30 | `scripts/run_marcus.py` |
| jarvis | 평일 07:30 | `scripts/run_jarvis.py` |
| pipeline | 평일 07:40 | `run_pipeline.py` |
| news | 평일 08:00 | `scripts/refresh_news.py` |
| monthly-deposit | 매월 1일 00:00 | `scripts/monthly_deposit_cron.py` |

스케줄 변경 시: `crontab.docker` 수정 → `smart-deploy.sh build`.

---

## 배포 후 헬스 체크

```bash
docker ps --format "{{.Names}}\t{{.Status}}"
docker exec investment-bot curl -sf http://localhost:8421/api/status
```

스크립트 실행 시 자동으로 헬스 체크가 출력된다.

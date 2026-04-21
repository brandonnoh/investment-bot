---
name: deploy
description: >
  investment-bot 프로젝트 배포/빌드 시 반드시 참조. '배포', 'deploy', 'docker',
  '빌드', 'build', '컨테이너', 'docker compose', 'docker cp', '반영', '적용',
  '스케줄', 'cron', 'launchd' 키워드가 나오면 자동 적용. Python 소스 변경과
  Next.js 변경은 배포 방식이 완전히 다르므로 반드시 이 스킬을 먼저 확인.
---

# investment-bot 배포 규칙

## Step 0: Git Push (항상 먼저)

배포 전 반드시 코드를 GitHub에 백업한다.

```bash
# 미커밋 변경사항 확인
git status

# 스테이징 + 커밋 (변경사항이 있을 때)
git add -p   # 파일별로 확인하며 추가
git commit -m "커밋 메시지"

# 푸시
git push
```

- 커밋이 이미 되어 있으면 `git push`만 실행
- 미커밋 파일이 있으면 먼저 `/commit` 스킬로 커밋 후 push
- git push 완료 후 Docker 배포 진행

---

## 컨테이너 구조

| 컨테이너 | 포트 | 역할 |
|---------|------|------|
| `investment-bot` | 8421 | Flask API + 내부 cron 스케줄러 |
| `mc-web` | 3000 | Next.js standalone 프론트엔드 |

**볼륨 마운트 (docker-compose.yml):** `db/`, `output/`, `logs/`, `docs/` 만 마운트됨.
`web/`, `scripts/`, `analysis/`, `reports/`, `data/` 등 Python 소스는 이미지에 COPY되므로
로컬 수정이 실행 중 컨테이너에 자동 반영되지 않는다. 반드시 리빌드 필요.

**⚠️ HOST launchd는 전부 비활성화됨.** 스케줄 작업은 Docker 내부 cron만 사용.

---

## Track A: Python 소스 변경 시

대상: `web/`, `scripts/`, `analysis/`, `reports/`, `data/`, `config.py` 등

```bash
docker compose up -d --build investment-bot
```

- `docker cp`로 우회 불가 — 반드시 이미지 리빌드
- Docker 내부 python: `python3` (`/usr/local/bin/python3`, 3.12)
- `/opt/homebrew/bin/python3` 은 Docker 안에 없음 — 사용 금지

---

## Track B: Next.js 변경 시

대상: `web-next/src/`, `web-next/public/` 등

```bash
cd web-next && npm run build && cd ..
docker cp web-next/.next/standalone/. mc-web:/app/
docker cp web-next/.next/static/. mc-web:/app/.next/static/
docker restart mc-web
```

- 반드시 `/. ` (슬래시-점) 형태 — 단순 `/` 사용 시 `static/static/` 중첩 버그 발생
- `npm run build` 없이 `docker cp`만 하면 안 됨

---

## Track C: 스케줄/인프라 변경 시

대상: `crontab.docker`, `docker-entrypoint.sh`, `Dockerfile`, `docker-compose.yml`

```bash
docker compose up -d --build investment-bot
```

### 스케줄 확인 (컨테이너 내부)

```bash
docker exec investment-bot cat /etc/cron.d/investment-bot
docker exec investment-bot date   # 타임존 KST 확인
```

### 현재 스케줄 (KST 기준)

| 잡 | 스케줄 | 스크립트 |
|----|--------|---------|
| alerts_watch | 매 5분 | `analysis/alerts_watch.py` |
| refresh_prices | 매 10분 | `scripts/refresh_prices.py` |
| marcus | 평일 05:30 | `scripts/run_marcus.py` |
| jarvis | 평일 07:30 | `scripts/run_jarvis.py` |
| pipeline | 평일 07:40 | `run_pipeline.py` |
| news | 평일 08:00 | `scripts/refresh_news.py` |
| monthly-deposit | 매월 1일 00:00 | `scripts/monthly_deposit_cron.py` |

---

## Track A+B: 둘 다 변경 시

A 먼저, B 다음 순서:

```bash
docker compose up -d --build investment-bot
cd web-next && npm run build && cd ..
docker cp web-next/.next/standalone/. mc-web:/app/
docker cp web-next/.next/static/. mc-web:/app/.next/static/
docker restart mc-web
```

---

## 배포 후 헬스 체크

```bash
docker ps --format "{{.Names}}\t{{.Status}}"
docker exec investment-bot sh -c "cat /proc/*/cmdline 2>/dev/null | tr '\0' ' ' | grep -o '/usr/sbin/cron'"
```

cron 프로세스가 출력되면 스케줄러 정상 동작.

---

## 키체인 오류 시

`error getting credentials - keychain cannot be accessed` → 사용자가 직접 실행:

```
! security unlock-keychain ~/Library/Keychains/login.keychain-db
```

해제 후 `docker compose up -d --build` 재시도.

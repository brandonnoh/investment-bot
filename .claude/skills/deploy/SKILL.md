---
name: deploy
description: >
  investment-bot 배포/반영/재시작. '배포', 'deploy', '반영', '적용', 'docker',
  '빌드', 'build', '재시작', 'restart', 'docker cp', 'docker compose' 키워드가
  나오면 자동 적용. 변경한 파일 종류에 따라 명령이 완전히 다르므로 반드시 이 스킬을 먼저 확인할 것.
---

# investment-bot 배포 스킬

## 볼륨 마운트 구조 — 이게 전부다

`docker-compose.yml`에 마운트된 파일은 로컬과 컨테이너가 실시간 공유된다.
**빌드 없이, 재시작만으로 반영된다.**

```
볼륨 마운트 목록 (변경 → docker restart만으로 반영):
  web/                  ← server.py, investment_advisor.py, api.py 등
  analysis/
  data/
  reports/
  scripts/
  db/                   ← connection.py, ssot.py, maintenance.py 등
  utils/                ← json_io.py 등
  config.py
  run_pipeline.py
  crontab.docker        → /etc/cron.d/investment-bot (재시작 후 cron 자동 반영)
```

---

## 상황별 명령 — 이것만 보면 된다

### 1. Python 소스 수정 (가장 흔함)
위 볼륨 목록 안의 파일을 수정한 경우.

```bash
docker restart investment-bot
```

헬스 체크:
```bash
docker exec investment-bot python3 -c \
  "import urllib.request; print(urllib.request.urlopen('http://localhost:8421/api/status').read().decode()[:80])"
```

---

### 2. docker-compose.yml 수정
볼륨 추가/삭제, 환경변수 추가, 포트 변경 등 컨테이너 설정이 바뀐 경우.
컨테이너를 새로 만들어야 한다. **빌드는 하지 않는다.**

```bash
docker compose up -d --no-build --no-deps investment-bot
```

---

### 3. Next.js 소스 수정 (web-next/)
Next.js는 볼륨 마운트 없음 — 빌드 후 직접 복사해야 한다.

```bash
cd web-next && npm run build && cd ..
docker cp web-next/.next/standalone/. mc-web:/app/
docker cp web-next/.next/static/. mc-web:/app/.next/static/
docker restart mc-web
```

반드시 `/. ` 형태로 복사 — 슬래시만 쓰면 `static/static/` 중첩 버그.

---

### 4. Dockerfile / requirements.txt 수정 (매우 드묾)
패키지 설치, OS 설정 등 이미지 자체가 바뀔 때만.
볼륨 마운트 덕분에 **실질적으로 Dockerfile을 건드릴 일이 거의 없다.**
`crontab.docker`도 이제 볼륨 마운트이므로 빌드 불필요.

Docker Desktop Keychain이 잠겨 있으면 빌드가 실패한다.
이 경우 터미널(! 명령)에서 먼저 잠금 해제:
```
! security -v unlock-keychain ~/Library/Keychains/login.keychain-db
```
그 다음 빌드:
```bash
docker compose build investment-bot
docker compose up -d --no-deps investment-bot
```

---

## 복합 변경 시 순서

Python + docker-compose.yml 동시 수정:
```bash
docker compose up -d --no-build --no-deps investment-bot
# compose up이 재시작을 포함하므로 별도 restart 불필요
```

Python + Next.js 동시 수정:
```bash
docker restart investment-bot
cd web-next && npm run build && cd ..
docker cp web-next/.next/standalone/. mc-web:/app/
docker cp web-next/.next/static/. mc-web:/app/.next/static/
docker restart mc-web
```

---

## Git Push

배포 전 커밋 확인:
```bash
git status
git add <파일> && git commit -m "..."
git push
```

---

## 컨테이너 상태 확인

```bash
docker ps --format "{{.Names}}\t{{.Status}}"
docker inspect investment-bot --format='{{.State.Health.Status}}'
```

---

## 컨테이너 구조

| 컨테이너 | 포트 | 역할 |
|---------|------|------|
| `investment-bot` | 8421 | Python API + 내부 cron 스케줄러 |
| `mc-web` | 3000 | Next.js standalone 프론트엔드 |

---

## cron 스케줄 (KST)

`crontab.docker` 수정 → `docker restart investment-bot`으로 바로 반영.

| 잡 | 스케줄 | 스크립트 |
|----|--------|---------|
| refresh_prices | 매 1분 | `scripts/refresh_prices.py` |
| alerts_watch | 매 5분 | `analysis/alerts_watch.py` |
| marcus | 평일 05:30 | `scripts/run_marcus.py` |
| universe_daily | 평일 07:00 | `data/fetch_universe_daily.py` |
| jarvis | 평일 07:30 | `scripts/run_jarvis.py` |
| pipeline | 평일 07:40 | `run_pipeline.py` |
| news | 평일 08:00 | `scripts/refresh_news.py` |
| refresh_solar | 매일 08:30, 19:00 | `scripts/refresh_solar.py` |
| db_maintenance | 매주 일요일 03:00 | `db/maintenance.py` |
| log_rotation | 매일 00:05 | find + gzip |
| monthly-deposit | 매월 1일 00:00 | `scripts/monthly_deposit_cron.py` |

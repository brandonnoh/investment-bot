#!/bin/bash
set -e

# Docker env_file로 주입된 변수를 /etc/environment에 등록 (cron 데몬이 읽음)
# .env는 .dockerignore에서 제외되므로 현재 프로세스 환경에서 직접 추출
for var in DISCORD_WEBHOOK_URL BRAVE_API_KEY KIWOOM_APPKEY KIWOOM_SECRETKEY; do
    val=$(printenv "$var" 2>/dev/null || true)
    if [ -n "$val" ]; then
        echo "$var=$val" >> /etc/environment
    fi
done

# Claude 인증 파일 — 호스트 마운트를 writable 위치에 복사 (ro 마운트라 symlink 불가)
if [ -f /root/.claude-host.json ]; then
    cp /root/.claude-host.json /root/.claude.json
    echo "[entrypoint] claude.json 복사 완료"
fi
if [ -d /root/.claude-host ]; then
    cp -r /root/.claude-host/. /root/.claude/
    echo "[entrypoint] .claude/ 복사 완료"
fi

# DB 스키마 초기화 (테이블 생성 + 마이그레이션)
python3 -c "from db.init_db import init_db; init_db()"

# 로그 디렉토리 보장
mkdir -p /app/logs

# cron 데몬 백그라운드 시작
/usr/sbin/cron

echo "[entrypoint] cron 시작됨"
echo "[entrypoint] Flask 서버 시작..."

# Flask 서버 메인 프로세스 (PID 1)
exec python3 web/server.py

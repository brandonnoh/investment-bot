#!/bin/bash
set -e

# .env 환경변수를 /etc/environment에 주입 (cron 데몬이 읽음)
# Docker의 env_file로 주입된 변수가 cron job에서도 사용 가능하도록
if [ -f /app/.env ]; then
    # 'export KEY=VALUE' 형식과 'KEY=VALUE' 형식 모두 처리
    # /etc/environment는 export 키워드 미지원 → sed로 제거
    grep -v '^#' /app/.env | grep '=' | sed 's/^export //' >> /etc/environment
fi

# Claude 인증 파일 — 호스트 마운트를 writable 위치에 복사 (atomic rename으로 인한 stale inode 방지)
if [ -f /root/.claude-host.json ]; then
    cp /root/.claude-host.json /root/.claude.json
    echo "[entrypoint] claude.json 복사 완료"
fi
if [ -d /root/.claude-host ]; then
    cp -r /root/.claude-host/. /root/.claude/
    echo "[entrypoint] .claude/ 복사 완료"
fi

# 로그 디렉토리 보장
mkdir -p /app/logs

# cron 데몬 백그라운드 시작
/usr/sbin/cron

echo "[entrypoint] cron 시작됨"
echo "[entrypoint] Flask 서버 시작..."

# Flask 서버 메인 프로세스 (PID 1)
exec python3 web/server.py

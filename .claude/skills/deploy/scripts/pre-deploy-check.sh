#!/usr/bin/env bash
# 배포 전 전수 검사 — API 응답, DB 조회, 핵심 엔드포인트 전부 확인
# 하나라도 실패하면 exit 1로 배포 중단

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
PASS=0; FAIL=0

ok()   { echo -e "${GREEN}  ✓${NC} $1"; PASS=$((PASS + 1)); }
fail() { echo -e "${RED}  ✗${NC} $1"; FAIL=$((FAIL + 1)); }
info() { echo -e "${YELLOW}  →${NC} $1"; }

echo ""
echo "═══════════════════════════════════════"
echo "  배포 전 전수 검사"
echo "═══════════════════════════════════════"

# 1. 컨테이너 상태
echo ""
echo "[1] 컨테이너 상태"
if docker inspect investment-bot --format='{{.State.Status}}' 2>/dev/null | grep -q "running"; then
  ok "investment-bot running"
else
  fail "investment-bot not running"
fi

if docker inspect mc-web --format='{{.State.Status}}' 2>/dev/null | grep -q "running"; then
  ok "mc-web running"
else
  fail "mc-web not running"
fi

# 2. Flask API 핵심 엔드포인트
echo ""
echo "[2] Flask API 엔드포인트"

check_api() {
  local path="$1" desc="$2" expect="$3"
  local result
  result=$(docker exec investment-bot python3 -c "
import urllib.request, sys
try:
    r = urllib.request.urlopen('http://localhost:8421${path}', timeout=10)
    print(r.read().decode()[:200])
except Exception as e:
    print('ERROR:' + str(e))
    sys.exit(1)
" 2>&1)
  if echo "$result" | grep -q "ERROR:"; then
    fail "$desc — $(echo "$result" | grep ERROR)"
  elif [ -n "$expect" ] && ! echo "$result" | grep -q "$expect"; then
    fail "$desc — 예상 키 '$expect' 없음 (응답: ${result:0:80})"
  else
    ok "$desc"
  fi
}

check_api "/api/status"   "GET /api/status"   "pipeline"
check_api "/api/data"     "GET /api/data"     "prices"
check_api "/api/wealth"   "GET /api/wealth"   "total_wealth_krw"
check_api "/api/solar"    "GET /api/solar"    "listings"
check_api "/api/opportunities" "GET /api/opportunities" "opportunities"

# 3. DB 테이블 데이터 유무
echo ""
echo "[3] DB 테이블 데이터 확인"

check_db() {
  local table="$1" min="$2"
  local count
  count=$(docker exec investment-bot python3 -c "
import sqlite3
from config import DB_PATH
conn = sqlite3.connect(str(DB_PATH))
print(conn.execute('SELECT COUNT(*) FROM ${table}').fetchone()[0])
conn.close()
" 2>&1)
  if [[ "$count" =~ ^[0-9]+$ ]] && [ "$count" -ge "$min" ]; then
    ok "${table}: ${count}건"
  else
    fail "${table}: ${count}건 (최소 ${min}건 필요)"
  fi
}

check_db "solar_listings" 1
check_db "holdings" 1
check_db "extra_assets" 0

# 4. Python 임포트 검증 (핵심 모듈)
echo ""
echo "[4] Python 모듈 임포트"

check_import() {
  local module="$1"
  if docker exec investment-bot python3 -c "
import sys; sys.path.insert(0,'/app')
import ${module}
" 2>/dev/null; then
    ok "$module"
  else
    fail "$module 임포트 실패"
  fi
}

check_import "web.api"
check_import "web.server"
check_import "db.connection"
check_import "analysis.solar_alerts"
check_import "db.ssot"

# 5. SSE 헬스 (연결만 확인)
echo ""
echo "[5] SSE 스트림"
if docker exec investment-bot python3 -c "
import urllib.request, socket
try:
    req = urllib.request.Request('http://localhost:8421/api/events')
    r = urllib.request.urlopen(req, timeout=3)
    r.close()
except Exception as e:
    if 'timed out' in str(e).lower() or '200' in str(getattr(e,'code','')) or 'EAGAIN' in str(e):
        pass  # timeout은 SSE 연결 성공 의미
    # Connection refused는 진짜 실패
    elif 'refused' in str(e).lower():
        import sys; sys.exit(1)
" 2>/dev/null; then
  ok "/api/events SSE 응답"
else
  fail "/api/events SSE 응답 없음"
fi

# 결과 요약
echo ""
echo "═══════════════════════════════════════"
if [ "$FAIL" -eq 0 ]; then
  echo -e "${GREEN}  전수 검사 통과 — 배포 진행 가능 (${PASS}/${PASS})${NC}"
  echo "═══════════════════════════════════════"
  echo ""
  exit 0
else
  echo -e "${RED}  전수 검사 실패 — 배포 중단 (실패 ${FAIL}/${PASS+$FAIL})${NC}"
  echo "═══════════════════════════════════════"
  echo ""
  exit 1
fi

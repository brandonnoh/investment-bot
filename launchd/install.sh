#!/bin/bash
# LaunchAgent 설치 스크립트
# 사용법: bash launchd/install.sh
#
# 수행 작업:
#   1. 현재 쉘 환경변수를 pipeline plist의 placeholder에 치환
#   2. ~/Library/LaunchAgents/ 에 3개 plist 복사
#   3. launchctl load 로 서비스 등록
#   4. launchctl list 로 등록 결과 확인

set -euo pipefail

# ── 색상 출력 헬퍼 ──────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # 색상 초기화

info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── 경로 설정 ───────────────────────────────────────────────────
# 스크립트 위치 기준으로 프로젝트 루트 결정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LAUNCHD_DIR="$SCRIPT_DIR"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

# plist 파일명 목록
PIPELINE_PLIST="com.investment-bot.pipeline.plist"
ALERTS_PLIST="com.investment-bot.alerts-watch.plist"
MONTHLY_PLIST="com.investment-bot.monthly-deposit.plist"
MARCUS_PLIST="com.investment-bot.marcus.plist"
JARVIS_PLIST="com.investment-bot.jarvis.plist"
DASHBOARD_PLIST="com.investment-bot.dashboard.plist"
PRICES_KRX_PLIST="com.investment-bot.prices-krx.plist"
PRICES_US_PLIST="com.investment-bot.prices-us.plist"
NEWS_MORNING_PLIST="com.investment-bot.news-morning.plist"

info "=== investment-bot LaunchAgent 설치 시작 ==="
info "프로젝트 루트: $PROJECT_ROOT"
info "LaunchAgents 경로: $LAUNCH_AGENTS_DIR"
echo ""

# ── 1단계: 환경변수 확인 및 pipeline plist 치환 ─────────────────
info "[1/4] 환경변수 확인 및 pipeline plist 치환"

# 필수 환경변수 체크 (없으면 경고만, 설치는 계속 진행)
MISSING_VARS=()
for VAR in KIWOOM_APPKEY KIWOOM_SECRETKEY BRAVE_API_KEY; do
    if [[ -z "${!VAR:-}" ]]; then
        MISSING_VARS+=("$VAR")
    fi
done

if [[ ${#MISSING_VARS[@]} -gt 0 ]]; then
    warn "다음 환경변수가 설정되지 않았습니다: ${MISSING_VARS[*]}"
    warn "pipeline plist에 빈 값으로 치환됩니다."
    warn "나중에 ~/Library/LaunchAgents/$PIPELINE_PLIST 를 직접 편집하거나"
    warn "환경변수 설정 후 이 스크립트를 다시 실행하세요."
    echo ""
fi

# 임시 파일에 치환 결과 저장 (원본 보존)
TMP_PIPELINE=$(mktemp /tmp/com.investment-bot.pipeline.XXXXXX.plist)
trap 'rm -f "$TMP_PIPELINE"' EXIT  # 스크립트 종료 시 임시 파일 삭제

sed \
    -e "s|__KIWOOM_APPKEY__|${KIWOOM_APPKEY:-}|g" \
    -e "s|__KIWOOM_SECRETKEY__|${KIWOOM_SECRETKEY:-}|g" \
    -e "s|__BRAVE_API_KEY__|${BRAVE_API_KEY:-}|g" \
    "$LAUNCHD_DIR/$PIPELINE_PLIST" > "$TMP_PIPELINE"

info "환경변수 치환 완료 → 임시 파일: $TMP_PIPELINE"
echo ""

# ── 2단계: ~/Library/LaunchAgents/ 에 복사 ──────────────────────
info "[2/4] ~/Library/LaunchAgents/ 에 plist 복사"

# LaunchAgents 디렉토리 없으면 생성
mkdir -p "$LAUNCH_AGENTS_DIR"

# pipeline plist: 치환된 임시 파일에서 복사
cp "$TMP_PIPELINE" "$LAUNCH_AGENTS_DIR/$PIPELINE_PLIST"
info "  복사됨: $PIPELINE_PLIST (환경변수 치환 포함)"

# 나머지 plist: 원본에서 직접 복사
cp "$LAUNCHD_DIR/$ALERTS_PLIST"    "$LAUNCH_AGENTS_DIR/$ALERTS_PLIST"
info "  복사됨: $ALERTS_PLIST"

cp "$LAUNCHD_DIR/$MONTHLY_PLIST"   "$LAUNCH_AGENTS_DIR/$MONTHLY_PLIST"
info "  복사됨: $MONTHLY_PLIST"

cp "$LAUNCHD_DIR/$MARCUS_PLIST"    "$LAUNCH_AGENTS_DIR/$MARCUS_PLIST"
info "  복사됨: $MARCUS_PLIST (Marcus 05:30 KST 분석)"

cp "$LAUNCHD_DIR/$JARVIS_PLIST"    "$LAUNCH_AGENTS_DIR/$JARVIS_PLIST"
info "  복사됨: $JARVIS_PLIST (Jarvis 07:30 KST 브리핑)"

cp "$LAUNCHD_DIR/$DASHBOARD_PLIST" "$LAUNCH_AGENTS_DIR/$DASHBOARD_PLIST"
info "  복사됨: $DASHBOARD_PLIST (미션컨트롤 웹 서버 상시 실행)"

# 장중 가격 갱신 plist: 환경변수 치환 후 복사
TMP_PRICES_KRX=$(mktemp /tmp/com.investment-bot.prices-krx.XXXXXX.plist)
TMP_PRICES_US=$(mktemp /tmp/com.investment-bot.prices-us.XXXXXX.plist)
TMP_NEWS_MORNING=$(mktemp /tmp/com.investment-bot.news-morning.XXXXXX.plist)
trap 'rm -f "$TMP_PIPELINE" "$TMP_PRICES_KRX" "$TMP_PRICES_US" "$TMP_NEWS_MORNING"' EXIT

for SRC_PLIST in "$PRICES_KRX_PLIST" "$PRICES_US_PLIST" "$NEWS_MORNING_PLIST"; do
    TMP_VAR="TMP_$(echo "$SRC_PLIST" | sed 's/com\.investment-bot\.\(.*\)\.plist/\1/' | tr '[:lower:]-' '[:upper:]_')"
    TMP_FILE="${!TMP_VAR}"
    sed \
        -e "s|__KIWOOM_APPKEY__|${KIWOOM_APPKEY:-}|g" \
        -e "s|__KIWOOM_SECRETKEY__|${KIWOOM_SECRETKEY:-}|g" \
        -e "s|__BRAVE_API_KEY__|${BRAVE_API_KEY:-}|g" \
        "$LAUNCHD_DIR/$SRC_PLIST" > "$TMP_FILE"
    cp "$TMP_FILE" "$LAUNCH_AGENTS_DIR/$SRC_PLIST"
    info "  복사됨: $SRC_PLIST (환경변수 치환 포함)"
done
echo ""

# ── 3단계: launchctl load 로 서비스 등록 ────────────────────────
info "[3/4] launchctl 로 서비스 등록"

# macOS 버전에 따라 launchctl 문법이 다름 (Monterey 이상: bootstrap/bootout)
# 하위 호환을 위해 load/unload 사용
for PLIST in "$PIPELINE_PLIST" "$ALERTS_PLIST" "$MONTHLY_PLIST" "$MARCUS_PLIST" "$JARVIS_PLIST" "$DASHBOARD_PLIST" "$PRICES_KRX_PLIST" "$PRICES_US_PLIST" "$NEWS_MORNING_PLIST"; do
    FULL_PATH="$LAUNCH_AGENTS_DIR/$PLIST"
    LABEL="${PLIST%.plist}"  # 확장자 제거 → Label 값

    # 이미 등록된 경우 먼저 unload (오류 무시)
    launchctl unload "$FULL_PATH" 2>/dev/null || true

    # 등록
    if launchctl load "$FULL_PATH" 2>&1; then
        info "  등록 성공: $LABEL"
    else
        error "  등록 실패: $LABEL"
        error "  직접 확인: launchctl load $FULL_PATH"
    fi
done
echo ""

# ── 4단계: 등록 결과 확인 ────────────────────────────────────────
info "[4/4] 등록된 서비스 확인"
echo ""
echo "─────────────────────────────────────────────────────"
printf "%-6s %-8s %s\n" "PID" "Status" "Label"
echo "─────────────────────────────────────────────────────"
launchctl list | grep "investment-bot" || warn "  등록된 investment-bot 서비스 없음"
echo "─────────────────────────────────────────────────────"
echo ""

# ── 설치 완료 안내 ───────────────────────────────────────────────
info "=== 설치 완료 ==="
echo ""
echo "  서비스 상태 확인:"
echo "    launchctl list | grep investment-bot"
echo ""
echo "  수동 실행 (테스트용):"
echo "    launchctl start com.investment-bot.pipeline"
echo "    launchctl start com.investment-bot.alerts-watch"
echo "    launchctl start com.investment-bot.monthly-deposit"
echo "    launchctl start com.investment-bot.prices-krx"
echo "    launchctl start com.investment-bot.prices-us"
echo "    launchctl start com.investment-bot.news-morning"
echo ""
echo "  서비스 중지:"
echo "    launchctl stop com.investment-bot.alerts-watch"
echo ""
echo "  서비스 제거:"
echo "    launchctl unload ~/Library/LaunchAgents/com.investment-bot.pipeline.plist"
echo "    launchctl unload ~/Library/LaunchAgents/com.investment-bot.alerts-watch.plist"
echo "    launchctl unload ~/Library/LaunchAgents/com.investment-bot.monthly-deposit.plist"
echo "    launchctl unload ~/Library/LaunchAgents/com.investment-bot.prices-krx.plist"
echo "    launchctl unload ~/Library/LaunchAgents/com.investment-bot.prices-us.plist"
echo "    launchctl unload ~/Library/LaunchAgents/com.investment-bot.news-morning.plist"
echo ""
echo "  로그 확인:"
echo "    tail -f $PROJECT_ROOT/logs/launchd_pipeline.log"
echo "    tail -f $PROJECT_ROOT/logs/launchd_alerts.log"
echo "    tail -f $PROJECT_ROOT/logs/launchd_monthly.log"
echo "    tail -f $PROJECT_ROOT/logs/launchd_prices_krx.log"
echo "    tail -f $PROJECT_ROOT/logs/launchd_prices_us.log"
echo "    tail -f $PROJECT_ROOT/logs/launchd_news_morning.log"

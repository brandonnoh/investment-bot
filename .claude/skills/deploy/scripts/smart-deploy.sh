#!/usr/bin/env bash
# investment-bot 스마트 배포 스크립트
# 변경 파일을 분석해서 최소 필요 작업만 실행 (Keychain 불필요)
#
# Usage: smart-deploy.sh [auto|python|build|web] [--dry-run]
#
# Modes:
#   auto   (기본) git diff로 자동 판단
#   python Python 소스만 변경 → docker restart
#   build  Dockerfile/requirements 변경 → --no-pull 빌드
#   web    Next.js 변경 → npm build + docker cp

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/../../../.." && pwd)"
MODE="${1:-auto}"
DRY_RUN=false
[[ "${2:-}" == "--dry-run" ]] && DRY_RUN=true

NEED_BUILD=false
NEED_PYTHON=false
NEED_WEB=false

cd "$PROJECT_DIR"

# ── 색상 출력 ────────────────────────────────────────────────
green()  { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
red()    { printf '\033[31m%s\033[0m\n' "$*"; }
run()    { echo "  $ $*"; $DRY_RUN || eval "$@"; }

# ── 변경 파일 목록 수집 (auto 모드) ─────────────────────────
detect_tracks() {
    # 1순위: 스테이지되지 않은 + 스테이지된 변경
    local changed
    changed=$(git diff --name-only HEAD 2>/dev/null)

    # 변경 없으면 마지막 커밋 기준
    if [[ -z "$changed" ]]; then
        changed=$(git diff --name-only HEAD~1 HEAD 2>/dev/null)
    fi

    NEED_BUILD=false
    NEED_PYTHON=false
    NEED_WEB=false

    while IFS= read -r file; do
        [[ -z "$file" ]] && continue

        # 인프라/빌드 파일
        if [[ "$file" =~ ^(Dockerfile|requirements\.txt|crontab\.docker|docker-entrypoint\.sh)$ ]]; then
            NEED_BUILD=true
        # Python 소스 (볼륨 마운트됨 → restart만)
        elif [[ "$file" =~ ^(web|analysis|data|reports|scripts|config\.py|run_pipeline\.py|utils|lib)/ ]] \
          || [[ "$file" =~ ^(config\.py|run_pipeline\.py)$ ]]; then
            NEED_PYTHON=true
        # Next.js
        elif [[ "$file" =~ ^web-next/ ]]; then
            NEED_WEB=true
        fi
    done <<< "$changed"
}

# ── Track B: Python 소스 → restart ──────────────────────────
deploy_python() {
    green "▶ [Python] 볼륨 마운트 → docker restart investment-bot"
    run docker restart investment-bot
}

# ── Track C: 빌드 필요 → --no-pull (Keychain 불필요) ────────
deploy_build() {
    green "▶ [Build] Dockerfile/requirements 변경 → --no-pull 리빌드"

    # python:3.12-slim 캐시 확인
    if ! docker image inspect python:3.12-slim &>/dev/null; then
        red "  경고: python:3.12-slim 이미지가 로컬에 없습니다."
        yellow "  인터랙티브 터미널에서 먼저 실행하세요:"
        yellow "  ! docker pull python:3.12-slim"
        exit 1
    fi

    run docker compose build --no-pull investment-bot
    run docker compose up -d --no-deps investment-bot
}

# ── Track A: Next.js → npm build + docker cp ────────────────
deploy_web() {
    green "▶ [Web] Next.js 변경 → 빌드 + docker cp"
    run "cd web-next && npm run build && cd .."
    run "docker cp web-next/.next/standalone/. mc-web:/app/"
    run "docker cp web-next/.next/static/. mc-web:/app/.next/static/"
    run docker restart mc-web
}

# ── 헬스 체크 ────────────────────────────────────────────────
health_check() {
    green "▶ 헬스 체크"
    echo ""
    docker ps --format "  {{.Names}}\t{{.Status}}" 2>/dev/null || true
    echo ""

    # investment-bot API 확인
    local api_ok
    api_ok=$(docker exec investment-bot sh -c "curl -sf http://localhost:8421/api/status" 2>/dev/null && echo "ok" || echo "fail")
    if [[ "$api_ok" == "ok" ]]; then
        green "  investment-bot API: OK"
    else
        yellow "  investment-bot API: 응답 대기 중 (정상 기동 시 수초 소요)"
    fi
}

# ── 메인 ─────────────────────────────────────────────────────
main() {
    echo ""
    yellow "=== investment-bot 스마트 배포 (mode: $MODE) ==="
    $DRY_RUN && yellow "  [DRY RUN - 실제 실행 없음]"
    echo ""

    case "$MODE" in
        auto)
            detect_tracks
            echo "  변경 감지:"
            echo "    BUILD  : $NEED_BUILD"
            echo "    PYTHON : $NEED_PYTHON"
            echo "    WEB    : $NEED_WEB"
            echo ""

            if ! $NEED_BUILD && ! $NEED_PYTHON && ! $NEED_WEB; then
                yellow "  변경사항 없음. 종료."
                exit 0
            fi

            # 빌드가 필요하면 restart는 포함됨
            $NEED_BUILD  && deploy_build
            # 빌드 없이 Python만 변경
            $NEED_PYTHON && ! $NEED_BUILD && deploy_python
            $NEED_WEB    && deploy_web
            ;;
        python)
            deploy_python
            ;;
        build)
            deploy_build
            ;;
        web)
            deploy_web
            ;;
        *)
            red "Unknown mode: $MODE"
            echo "Usage: smart-deploy.sh [auto|python|build|web] [--dry-run]"
            exit 1
            ;;
    esac

    # investment-bot 항상 최종 재시작 (Claude 토큰 갱신)
    if [[ "$MODE" != "web" ]] || $NEED_PYTHON || $NEED_BUILD; then
        green "▶ investment-bot 최종 재시작 (Claude 토큰 갱신)"
        run docker restart investment-bot
    fi

    echo ""
    health_check
    echo ""
    green "=== 배포 완료 ==="
    echo ""
}

main

#!/usr/bin/env bash
# ralph.sh — Ralph v2 Autonomous Development Loop
# 5-Stage Pipeline: Pre-Gate → Planner → Workers → Quality-Gate → Reviewer → Post-Gate
#
# 사용법:
#   bash ralph.sh                       # 기본 10 iteration
#   bash ralph.sh --iter 30             # 30회 실행
#   bash ralph.sh --parallel 3          # 3개 worker 병렬
#   bash ralph.sh --no-reviewer         # reviewer stage 스킵
#   bash ralph.sh --task TASK_ID        # 단일 task만
#   bash ralph.sh --strict              # 품질 델타 엄격 모드
#   bash ralph.sh --dry-run             # 실제 실행 없이 단계만 출력
#   bash ralph.sh --help

set -euo pipefail

# ─── 색상 ────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'
export RED GREEN YELLOW BLUE CYAN BOLD NC

# ─── 경로 ────────────────────────────────────────────
RALPH_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR=".ralph-state"
LOG_DIR="$STATE_DIR/logs"
LIB_DIR="$RALPH_ROOT/lib"
PROMPTS_DIR="$RALPH_ROOT/prompts"
SCHEMAS_DIR="$RALPH_ROOT/schemas"
export RALPH_ROOT STATE_DIR LOG_DIR LIB_DIR PROMPTS_DIR SCHEMAS_DIR

# ─── 기본 인자 ───────────────────────────────────────
MAX_ITER=10
PARALLEL=1
USE_REVIEWER=1
SINGLE_TASK=""
STRICT=0
DRY_RUN=0

# ─── 헬프 ────────────────────────────────────────────
print_help() {
  cat <<'EOF'
Ralph v2 — Autonomous Development Loop

USAGE:
  bash ralph.sh [OPTIONS]

OPTIONS:
  --iter N           최대 iteration 수 (기본 10)
  --parallel N       worker 병렬 수 (기본 1)
  --no-reviewer      Reviewer stage 생략
  --task TASK_ID     특정 task만 실행
  --strict           품질 델타 엄격 모드 (회귀 시 즉시 중단)
  --dry-run          실행 없이 5-stage 파이프라인만 출력
  --help             이 도움말 표시

PIPELINE (per iteration):
  Stage 0  Pre-Iteration Gate   git clean + 품질 스냅샷 + 회귀 감지
  Stage 1  Planner (haiku)      eligible task 선별 + 병렬 그룹
  Stage 2  Workers (sonnet)     TDD 구현 (병렬 가능)
  Stage 3  Quality Gate         빌드/테스트 + 300줄/any/!. 델타
  Stage 4  Reviewer (opus)      diff 리뷰 + HIGH_QUALITY 체크리스트
  Stage 5  Post-Iteration       commit + metrics + progress 갱신

STATE:
  .ralph-state/logs/            iteration별 stage 로그
  .ralph-state/metrics.jsonl    append-only 메트릭
  .ralph-state/stack.json       프로젝트 스택 감지 결과
EOF
}

# ─── 인자 파싱 ───────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --iter)         MAX_ITER="$2"; shift 2 ;;
    --parallel)     PARALLEL="$2"; shift 2 ;;
    --no-reviewer)  USE_REVIEWER=0; shift ;;
    --task)         SINGLE_TASK="$2"; shift 2 ;;
    --strict)       STRICT=1; shift ;;
    --dry-run)      DRY_RUN=1; shift ;;
    --help|-h)      print_help; exit 0 ;;
    *) echo -e "${RED}알 수 없는 옵션: $1${NC}"; print_help; exit 1 ;;
  esac
done
export MAX_ITER PARALLEL USE_REVIEWER SINGLE_TASK STRICT DRY_RUN

# ─── lib 로드 ────────────────────────────────────────
source "$LIB_DIR/metrics.sh"
source "$LIB_DIR/detect-stack.sh"
source "$LIB_DIR/pre-gate.sh"
source "$LIB_DIR/quality-gate.sh"
source "$LIB_DIR/post-gate.sh"
source "$LIB_DIR/rollback.sh"

# ─── 초기 준비 ───────────────────────────────────────
mkdir -p "$STATE_DIR" "$LOG_DIR"

log() { echo -e "${CYAN}[ralph]${NC} $*"; }
banner() {
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}${YELLOW}$*${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# ─── dry-run ─────────────────────────────────────────
if [[ "$DRY_RUN" == "1" ]]; then
  banner "Ralph v2 — DRY RUN"
  log "max_iter=$MAX_ITER parallel=$PARALLEL reviewer=$USE_REVIEWER strict=$STRICT task=${SINGLE_TASK:-auto}"
  for stage in "Stage 0: Pre-Iteration Gate" "Stage 1: Planner (haiku)" "Stage 2: Workers x$PARALLEL (sonnet)" "Stage 3: Quality Gate" "Stage 4: Reviewer (opus)" "Stage 5: Post-Iteration"; do
    echo -e "  ${GREEN}→${NC} $stage"
  done
  log "dry-run 종료"
  exit 0
fi

# ─── claude CLI 확인 ─────────────────────────────────
if ! command -v claude >/dev/null 2>&1; then
  echo -e "${RED}claude CLI가 설치되지 않았습니다.${NC}"
  exit 1
fi

# ─── stack 감지 ──────────────────────────────────────
banner "Ralph v2 Autonomous Loop"
log "스택 감지 중..."
detect_stack > "$STATE_DIR/stack.json"
log "스택: $(jq -r '.package_manager + " / " + (.monorepo|tostring)' "$STATE_DIR/stack.json")"

# ─── 실행 루프 ───────────────────────────────────────
CONSECUTIVE_FAILS=0
MAX_CONSECUTIVE_FAILS=3

run_claude_stage() {
  local stage_name="$1"
  local model="$2"
  local prompt_file="$3"
  local log_file="$4"
  local extra_args="${5:-}"

  if [[ ! -f "$prompt_file" ]]; then
    echo -e "${RED}프롬프트 파일 없음: $prompt_file${NC}" >&2
    return 1
  fi

  log "→ $stage_name (model=$model)"
  # shellcheck disable=SC2086
  claude -p "$(cat "$prompt_file")" \
    --model "$model" \
    --dangerously-skip-permissions \
    --max-turns 200 \
    $extra_args \
    2>&1 | tee "$log_file"
}

for i in $(seq -w 1 "$MAX_ITER"); do
  ITER_START=$(date +%s)
  ITER_LOG_PREFIX="$LOG_DIR/iter-${i}"
  banner "Iteration ${i}/${MAX_ITER} — $(date +%H:%M:%S)"

  # Stage 0
  log "${BOLD}Stage 0${NC} Pre-Iteration Gate"
  if ! pre_gate_run "$i" > "${ITER_LOG_PREFIX}-0-pregate.log" 2>&1; then
    echo -e "${RED}Stage 0 실패 → 중단${NC}"
    cat "${ITER_LOG_PREFIX}-0-pregate.log"
    exit 1
  fi

  # Stage 1 — Planner
  log "${BOLD}Stage 1${NC} Planner"
  PLAN_FILE="$STATE_DIR/plan-${i}.json"
  export PLAN_FILE RALPH_ITER="$i" RALPH_SINGLE_TASK="$SINGLE_TASK"
  if ! run_claude_stage "Planner" "claude-haiku-4-5" \
       "$PROMPTS_DIR/planner.md" "${ITER_LOG_PREFIX}-1-planner.log"; then
    echo -e "${RED}Planner 실패${NC}"
    rollback_iteration "$i" "planner-fail"
    CONSECUTIVE_FAILS=$((CONSECUTIVE_FAILS + 1))
    [[ $CONSECUTIVE_FAILS -ge $MAX_CONSECUTIVE_FAILS ]] && { echo -e "${RED}연속 실패 $MAX_CONSECUTIVE_FAILS회 → 중단${NC}"; exit 1; }
    continue
  fi

  # 완료 감지
  if grep -q "ALL_TASKS_COMPLETE" "${ITER_LOG_PREFIX}-1-planner.log" 2>/dev/null; then
    echo -e "\n${GREEN}${BOLD}모든 task 완료 (iter=${i})${NC}"
    break
  fi

  # Stage 2 — Workers
  log "${BOLD}Stage 2${NC} Workers (병렬 $PARALLEL)"
  WORKER_PIDS=()
  for w in $(seq 1 "$PARALLEL"); do
    WORKER_LOG="${ITER_LOG_PREFIX}-2-worker-${w}.log"
    (
      export RALPH_WORKER_ID="$w"
      run_claude_stage "Worker#$w" "claude-sonnet-4-5" \
        "$PROMPTS_DIR/worker.md" "$WORKER_LOG"
    ) &
    WORKER_PIDS+=($!)
  done
  WORKER_FAIL=0
  for pid in "${WORKER_PIDS[@]}"; do
    wait "$pid" || WORKER_FAIL=1
  done
  if [[ $WORKER_FAIL -eq 1 ]]; then
    echo -e "${RED}Worker 실패${NC}"
    rollback_iteration "$i" "worker-fail"
    CONSECUTIVE_FAILS=$((CONSECUTIVE_FAILS + 1))
    [[ $CONSECUTIVE_FAILS -ge $MAX_CONSECUTIVE_FAILS ]] && { echo -e "${RED}연속 실패 $MAX_CONSECUTIVE_FAILS회 → 중단${NC}"; exit 1; }
    continue
  fi

  # Stage 3 — Quality Gate
  log "${BOLD}Stage 3${NC} Quality Gate"
  if ! quality_gate_run "$i" > "${ITER_LOG_PREFIX}-3-quality.log" 2>&1; then
    echo -e "${RED}Quality Gate 실패${NC}"
    tail -40 "${ITER_LOG_PREFIX}-3-quality.log"
    rollback_iteration "$i" "quality-fail"
    CONSECUTIVE_FAILS=$((CONSECUTIVE_FAILS + 1))
    [[ $CONSECUTIVE_FAILS -ge $MAX_CONSECUTIVE_FAILS ]] && { echo -e "${RED}연속 실패 $MAX_CONSECUTIVE_FAILS회 → 중단${NC}"; exit 1; }
    continue
  fi

  # Stage 4 — Reviewer
  if [[ "$USE_REVIEWER" == "1" ]]; then
    log "${BOLD}Stage 4${NC} Reviewer"
    REVIEW_LOG="${ITER_LOG_PREFIX}-4-reviewer.log"
    if ! run_claude_stage "Reviewer" "claude-opus-4-6" \
         "$PROMPTS_DIR/reviewer.md" "$REVIEW_LOG"; then
      echo -e "${YELLOW}Reviewer 에러 (계속 진행)${NC}"
    fi
    if grep -q "CHANGES_REQUESTED" "$REVIEW_LOG" 2>/dev/null; then
      echo -e "${YELLOW}Reviewer: CHANGES_REQUESTED → 다음 iteration에 반영${NC}"
    fi
  fi

  # Stage 5 — Post-Iteration
  log "${BOLD}Stage 5${NC} Post-Iteration"
  ITER_END=$(date +%s)
  ITER_DURATION=$((ITER_END - ITER_START))
  if ! post_gate_run "$i" "$ITER_DURATION" > "${ITER_LOG_PREFIX}-5-postgate.log" 2>&1; then
    echo -e "${YELLOW}Post-Gate 경고${NC}"
    tail -20 "${ITER_LOG_PREFIX}-5-postgate.log"
  fi

  CONSECUTIVE_FAILS=0
  echo -e "${GREEN}iter=${i} 완료 (${ITER_DURATION}s)${NC}"
  sleep 3
done

banner "Ralph v2 종료"
log "로그: $LOG_DIR/"
log "메트릭: $STATE_DIR/metrics.jsonl"

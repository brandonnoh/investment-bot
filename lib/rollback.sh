#!/usr/bin/env bash
# rollback.sh — iteration 실패 시 git reset 복원
set -euo pipefail

rollback_iteration() {
  local iter="$1"
  local reason="${2:-unknown}"
  local state="${STATE_DIR:-.ralph-state}"
  local sha_file="$state/checkpoint-${iter}.sha"

  echo "[rollback] iter=$iter reason=$reason"

  if [[ ! -f "$sha_file" ]]; then
    echo "[rollback] WARNING: 체크포인트 SHA 없음 → HEAD 유지"
    return 0
  fi

  local sha; sha=$(cat "$sha_file")
  echo "[rollback] git reset --hard $sha"
  git reset --hard "$sha" 2>&1 || {
    echo "[rollback] ERROR: reset 실패"
    return 1
  }

  # rollback 기록
  local ts; ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  jq -n \
    --argjson iter "$iter" \
    --arg ts "$ts" \
    --arg reason "$reason" \
    '{iter: $iter, timestamp: $ts, rollback: true, reason: $reason}' \
    >> "$state/metrics.jsonl"

  echo "[rollback] OK"
  return 0
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  rollback_iteration "${1:-manual}" "${2:-manual}"
fi

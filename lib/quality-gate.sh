#!/usr/bin/env bash
# quality-gate.sh — Stage 3: 빌드/테스트/품질 델타
set -euo pipefail

if ! declare -f collect_quality_metrics >/dev/null 2>&1; then
  source "$(dirname "${BASH_SOURCE[0]}")/metrics.sh"
fi

quality_gate_run() {
  local iter="$1"
  local state="${STATE_DIR:-.ralph-state}"
  mkdir -p "$state"

  echo "[quality-gate] iter=$iter 시작"

  # 1. stack 로드
  local build_cmd test_cmd
  if [[ -f "$state/stack.json" ]]; then
    build_cmd=$(jq -r '.build_cmd' "$state/stack.json")
    test_cmd=$(jq -r '.test_cmd' "$state/stack.json")
  else
    build_cmd="pnpm turbo build"
    test_cmd="pnpm turbo test"
  fi

  echo "[quality-gate] build: $build_cmd"
  if ! eval "$build_cmd --force 2>&1 || $build_cmd"; then
    echo "[quality-gate] BUILD FAILED"
    return 1
  fi

  echo "[quality-gate] test: $test_cmd"
  if ! eval "$test_cmd"; then
    echo "[quality-gate] TESTS FAILED"
    return 1
  fi

  # 2. 품질 스냅샷
  local curr="$state/quality-${iter}.json"
  collect_quality_metrics > "$curr"
  echo "[quality-gate] 스냅샷: $(cat "$curr")"

  # 3. 델타 비교
  local prev="$state/prev-metrics.json"
  if [[ -f "$prev" ]]; then
    local delta; delta=$(get_delta "$prev" "$curr")
    echo "[quality-gate] 델타: $delta"
    local d_over d_any d_nn
    d_over=$(echo "$delta" | jq '.files_over_300_delta')
    d_any=$(echo "$delta" | jq '.any_count_delta')
    d_nn=$(echo "$delta" | jq '.nonnull_count_delta')
    if (( d_over > 0 || d_any > 0 || d_nn > 0 )); then
      echo "[quality-gate] WARNING: 품질 회귀 감지"
      echo "  files_over_300 델타: $d_over"
      echo "  any_count 델타: $d_any"
      echo "  nonnull_count 델타: $d_nn"
      if [[ "${STRICT:-0}" == "1" ]]; then
        echo "[quality-gate] STRICT 모드 → FAIL"
        return 1
      fi
    fi
  fi

  # 4. 다음 iteration을 위해 저장 (post-gate에서 최종 확정 but 안전장치)
  cp "$curr" "$state/prev-metrics.json"

  echo "[quality-gate] OK"
  return 0
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  quality_gate_run "${1:-manual}"
fi

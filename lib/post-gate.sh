#!/usr/bin/env bash
# post-gate.sh — Stage 5: 커밋 검증 + 메트릭 기록
set -euo pipefail

if ! declare -f append_iteration_metrics >/dev/null 2>&1; then
  source "$(dirname "${BASH_SOURCE[0]}")/metrics.sh"
fi

post_gate_run() {
  local iter="$1"
  local duration="$2"
  local state="${STATE_DIR:-.ralph-state}"

  echo "[post-gate] iter=$iter duration=${duration}s"

  # 1. tests.json summary 재계산
  if [[ -f tests.json ]]; then
    local total passing failing
    total=$(jq '[.features[]] | length' tests.json 2>/dev/null || echo 0)
    passing=$(jq '[.features[] | select(.status == "passing")] | length' tests.json 2>/dev/null || echo 0)
    failing=$(( total - passing ))
    jq --argjson t "$total" --argjson p "$passing" --argjson f "$failing" \
      '.summary = {total: $t, passing: $p, failing: $f}' tests.json > tests.json.tmp \
      && mv tests.json.tmp tests.json
    echo "[post-gate] tests.json summary: $passing/$total"
  fi

  # 2. Claude가 commit 스킬로 이미 커밋했는지 확인
  local last_msg; last_msg=$(git log -1 --pretty=%s 2>/dev/null || echo "")
  echo "[post-gate] last commit: $last_msg"

  # 3. 현재 품질 메트릭
  local curr="$state/quality-${iter}.json"
  [[ ! -f "$curr" ]] && collect_quality_metrics > "$curr"

  # 4. metrics.jsonl append
  append_iteration_metrics "$iter" "$duration" "false" "$(cat "$curr")" 0

  # 5. prev-metrics 갱신 (다음 iteration 비교 기준)
  cp "$curr" "$state/prev-metrics.json"

  # 6. progress.md append
  if [[ -f progress.md ]]; then
    {
      echo ""
      echo "## iter-$iter — $(date +%Y-%m-%d\ %H:%M)"
      echo "- duration: ${duration}s"
      echo "- commit: $last_msg"
      echo "- quality: $(cat "$curr")"
    } >> progress.md
  fi

  echo "[post-gate] OK"
  return 0
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  post_gate_run "${1:-manual}" "${2:-0}"
fi

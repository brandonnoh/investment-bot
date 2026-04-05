#!/usr/bin/env bash
# metrics.sh — 품질 메트릭 수집/비교 유틸
# 의존: jq
set -euo pipefail

# 현재 코드 품질 스냅샷 → JSON stdout
collect_quality_metrics() {
  local over300 any_count nonnull_count tests_passing tests_total
  # 300줄 초과 파일 (src/ 하위 ts/tsx/js/jsx)
  over300=0
  if [[ -d src ]] || compgen -G "*/src" >/dev/null; then
    over300=$(find . -type f \( -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.jsx' \) \
      -not -path '*/node_modules/*' -not -path '*/.ralph-state/*' -not -path '*/dist/*' -not -path '*/.next/*' 2>/dev/null \
      | xargs -I{} wc -l {} 2>/dev/null | awk '$1 > 300 && $2 != "total" {c++} END {print c+0}')
  fi
  # `: any` 출현 횟수
  any_count=$(grep -rEn ': any(\b|[^a-zA-Z])' --include='*.ts' --include='*.tsx' \
    --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=.ralph-state . 2>/dev/null | wc -l | tr -d ' ')
  # non-null assertion `!.`
  nonnull_count=$(grep -rEn '!\.' --include='*.ts' --include='*.tsx' \
    --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=.ralph-state . 2>/dev/null | wc -l | tr -d ' ')
  # tests.json
  tests_passing=0
  tests_total=0
  if [[ -f tests.json ]]; then
    tests_passing=$(jq '.summary.passing // 0' tests.json 2>/dev/null || echo 0)
    tests_total=$(jq '.summary.total // 0' tests.json 2>/dev/null || echo 0)
  fi

  jq -n \
    --argjson over300 "${over300:-0}" \
    --argjson any_count "${any_count:-0}" \
    --argjson nonnull_count "${nonnull_count:-0}" \
    --argjson tests_passing "${tests_passing:-0}" \
    --argjson tests_total "${tests_total:-0}" \
    '{files_over_300: $over300, any_count: $any_count, nonnull_count: $nonnull_count, tests_passing: $tests_passing, tests_total: $tests_total}'
}

# metrics.jsonl append
append_iteration_metrics() {
  local iter="$1"
  local duration="$2"
  local rollback="$3"
  local metrics_json="$4"
  local tokens="${5:-0}"
  local ts; ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  echo "$metrics_json" | jq -c \
    --argjson iter "$iter" \
    --arg ts "$ts" \
    --argjson duration "$duration" \
    --argjson tokens "$tokens" \
    --argjson rollback "$rollback" \
    '. + {iter: $iter, timestamp: $ts, duration_sec: $duration, tokens_used: $tokens, rollback: $rollback}' \
    >> "${STATE_DIR:-.ralph-state}/metrics.jsonl"
}

# 이전 대비 델타 계산 (회귀: exit 1)
# 사용: get_delta prev.json curr.json
get_delta() {
  local prev="$1" curr="$2"
  [[ ! -f "$prev" ]] && { echo "{}"; return 0; }
  jq -n --slurpfile p "$prev" --slurpfile c "$curr" '{
    files_over_300_delta: ($c[0].files_over_300 - $p[0].files_over_300),
    any_count_delta: ($c[0].any_count - $p[0].any_count),
    nonnull_count_delta: ($c[0].nonnull_count - $p[0].nonnull_count)
  }'
}

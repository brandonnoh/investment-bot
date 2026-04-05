#!/usr/bin/env bash
# detect-stack.sh — 프로젝트 스택 자동 감지
set -euo pipefail

detect_stack() {
  local pm="npm" turbo=false monorepo=false build_cmd="npm run build" test_cmd="npm test"

  if [[ -f pnpm-lock.yaml ]]; then
    pm="pnpm"
  elif [[ -f yarn.lock ]]; then
    pm="yarn"
  elif [[ -f package-lock.json ]]; then
    pm="npm"
  fi

  if [[ -f package.json ]]; then
    if jq -e '.devDependencies.turbo // .dependencies.turbo' package.json >/dev/null 2>&1; then
      turbo=true
    fi
    if jq -e '.workspaces' package.json >/dev/null 2>&1; then
      monorepo=true
    fi
  fi
  [[ -f pnpm-workspace.yaml ]] && monorepo=true

  if [[ "$turbo" == "true" ]]; then
    build_cmd="$pm turbo build"
    test_cmd="$pm turbo test"
  else
    if [[ -f package.json ]]; then
      jq -e '.scripts.build' package.json >/dev/null 2>&1 && build_cmd="$pm run build"
      jq -e '.scripts.test' package.json >/dev/null 2>&1 && test_cmd="$pm run test"
    fi
  fi

  jq -n \
    --arg pm "$pm" \
    --argjson turbo "$turbo" \
    --argjson monorepo "$monorepo" \
    --arg build "$build_cmd" \
    --arg test "$test_cmd" \
    '{package_manager: $pm, turbo: $turbo, monorepo: $monorepo, build_cmd: $build, test_cmd: $test}'
}

# 직접 실행 지원
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  detect_stack
fi

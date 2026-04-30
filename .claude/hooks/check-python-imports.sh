#!/bin/bash
# PostToolUse(Edit) — Python 파일 편집 후 핵심 웹 모듈 임포트 자동 검증
# web/ 또는 server.py 편집 시 즉시 import 체인 전체를 확인

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Python 파일이 아니면 skip
[[ "$FILE_PATH" == *.py ]] || exit 0

PROJECT_ROOT=$(git -C "$(dirname "$FILE_PATH")" rev-parse --show-toplevel 2>/dev/null || echo "/Users/jarvis/Projects/investment-bot")

# 핵심 모듈 목록 (import 체인 상 상위 → 하위 순)
MODULES=(
    "web.api"
    "web.api_company"
    "web.api_advisor"
    "web.api_history"
    "web.server"
    "web.investment_advisor"
    "analysis.solar_alerts"
)

FAILED=()
for mod in "${MODULES[@]}"; do
    if ! python3 -c "import sys; sys.path.insert(0,'$PROJECT_ROOT'); import $mod" 2>/dev/null; then
        FAILED+=("$mod")
    fi
done

if [ ${#FAILED[@]} -gt 0 ]; then
    echo ""
    echo "[import-check] ❌ 임포트 실패 — 배포 전 반드시 수정:"
    for f in "${FAILED[@]}"; do
        echo "  - $f"
        python3 -c "import sys; sys.path.insert(0,'$PROJECT_ROOT'); import $f" 2>&1 | grep -E "Error|Import|No module" | head -2 | sed 's/^/    /'
    done
    echo ""
fi

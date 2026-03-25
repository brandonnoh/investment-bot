#!/bin/bash
if [ -n "${RALF_RUNNING:-}" ]; then exit 0; fi
if [ -f "tests.json" ]; then
    FAILING=$(cat tests.json | jq '[.features[] | select(.status == "failing")] | length' 2>/dev/null || echo 0)
    if [ "$FAILING" -gt 0 ]; then
        NEXT=$(cat tests.json | jq -r '.features[] | select(.status == "failing") | .id + ": " + .description' 2>/dev/null | head -1)
        echo "📋 참고: tests.json에 미완료 기능이 ${FAILING}개 남아있습니다."
        echo "➡️  다음 작업: ${NEXT}"
    fi
fi

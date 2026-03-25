#!/bin/bash
echo "=== 투자봇 프로젝트 상태 ==="
echo ""
echo "📌 현재 브랜치: $(git branch --show-current 2>/dev/null || echo 'unknown')"
echo "📝 최근 커밋 3개:"
git log --oneline -3 2>/dev/null || echo "  (git log 불가)"
echo ""
if [ -f "tests.json" ]; then
    TOTAL=$(cat tests.json | jq '.summary.total // 0')
    PASSING=$(cat tests.json | jq '.summary.passing // 0')
    FAILING=$(cat tests.json | jq '.summary.failing // 0')
    echo "📊 기능 진행: ${PASSING}/${TOTAL} 완료 (${FAILING}개 남음)"
    NEXT=$(cat tests.json | jq -r '.features[] | select(.status == "failing") | .id + " — " + .description' 2>/dev/null | head -1)
    if [ -n "$NEXT" ]; then echo "➡️  다음 작업: $NEXT"; fi
    echo ""
fi
if [ -f "LESSONS.md" ]; then
    LESSON_COUNT=$(grep -c "^### " LESSONS.md 2>/dev/null || echo 0)
    echo "⚠️  기록된 교훈: ${LESSON_COUNT}개 (LESSONS.md 참조)"
fi
echo ""
echo "=== 세션 시작 ==="

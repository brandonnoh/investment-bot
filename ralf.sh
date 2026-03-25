#!/bin/bash
# ralf.sh — RALF Autonomous Loop (Investment Bot)
# 사용법: bash ralf.sh [반복횟수]
# 예: tmux new -s ralf "bash ralf.sh 30"

set -euo pipefail

MAX=${1:-10}
LOG_DIR=".claude-logs"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

mkdir -p "$LOG_DIR"

echo -e "${BLUE}📌 Git 체크포인트 생성 중...${NC}"
git add -A 2>/dev/null || true
git commit -m "checkpoint: pre-ralf $TIMESTAMP" --allow-empty 2>/dev/null || true

echo -e "${GREEN}🚀 RALF Loop 시작${NC}"
echo -e "   최대 반복: ${MAX}회"
echo -e "   로그 위치: ${LOG_DIR}/"
echo -e "   시작 시간: $(date)"
echo ""

for i in $(seq -w 1 $MAX); do
    ITER_START=$(date +%s)

    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}🔄 Iteration ${i}/${MAX}${NC} — $(date +%H:%M:%S)"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    REMAINING=$(grep -c '^\- \[ \]' prd.md 2>/dev/null || echo "?")
    echo -e "   📋 남은 task: ${REMAINING}"

    if [ -f "tests.json" ]; then
        PASSING=$(cat tests.json | jq '.summary.passing // 0')
        TOTAL=$(cat tests.json | jq '.summary.total // 0')
        echo -e "   📊 기능 진행: ${GREEN}${PASSING}${NC}/${TOTAL} 완료"
    fi

    if [ "$REMAINING" = "0" ]; then
        echo -e "\n${GREEN}🎉🎉🎉 모든 task 완료! 🎉🎉🎉${NC}"
        break
    fi

    # API 에러 시 최대 3회 재시도
    RETRY=0
    MAX_RETRY=3
    while [ $RETRY -lt $MAX_RETRY ]; do
        RALF_RUNNING=1 claude -p "
prd.md를 읽어라. 체크되지 않은([ ]) 첫 번째 task를 구현하라.

작업 절차:
1. CLAUDE.md, LESSONS.md, ARCHITECTURE.md, JARVIS_INTEGRATION.md, progress.md를 읽어 프로젝트 맥락과 이전 진행 상황을 파악
2. prd.md에서 첫 번째 미완료 task를 선택
3. tests.json에서 해당 task의 상세 정보(acceptance_criteria, depends_on 등) 확인
4. depends_on의 모든 기능이 passing인지 확인. 아니면 다음 eligible task로 이동
5. 관련 코드를 읽고 이해
6. 테스트 먼저 작성 (TDD) — tests/ 디렉토리에 pytest 테스트
7. 구현 코드 작성 (stdlib만 사용, config.py 중앙 관리, 한국어 주석)
8. python3 -m pytest tests/ -v 통과 확인
9. 통과하면:
   - prd.md에서 해당 task를 [x]로 체크
   - tests.json에서 해당 기능 status를 passing으로 변경, summary 업데이트
   - progress.md에 완료 내용 기록 (날짜, task ID, 변경 파일, 메모)
   - git add -A && git commit -m 'feat(기능ID): 기능 설명'
10. 실패하면:
    - progress.md에 시도 내용과 에러 기록
    - LESSONS.md에 교훈 추가 (3회 이상 같은 방식 실패 시)

모든 task가 완료되면 'ALL_TASKS_COMPLETE'를 출력하라.
" --dangerously-skip-permissions \
  --max-turns 30 \
  2>&1 | tee "$LOG_DIR/iteration-${i}.log"

        if grep -qE "API Error: (500|529)" "$LOG_DIR/iteration-${i}.log" 2>/dev/null; then
            RETRY=$((RETRY + 1))
            echo -e "   ${RED}⚠️ API 에러 감지. 재시도 ${RETRY}/${MAX_RETRY} (60초 대기)${NC}"
            sleep 60
        else
            break
        fi
    done

    ITER_END=$(date +%s)
    ITER_DURATION=$((ITER_END - ITER_START))
    echo -e "\n   ⏱️  소요 시간: ${ITER_DURATION}초"

    if grep -q "ALL_TASKS_COMPLETE" "$LOG_DIR/iteration-${i}.log" 2>/dev/null; then
        echo -e "\n${GREEN}🎉🎉🎉 모든 task 완료! (iteration ${i}) 🎉🎉🎉${NC}"
        break
    fi

    echo -e "   ${YELLOW}⏳ 쿨다운 10초...${NC}"
    sleep 10
done

echo ""
echo -e "${BLUE}━━━ RALF 종료 ━━━${NC}"
echo -e "   총 반복: ${i}회"
DONE=$(grep -c '^\- \[x\]' prd.md 2>/dev/null || echo 0)
TOTAL_TASKS=$(grep -c '^\- \[' prd.md 2>/dev/null || echo 0)
echo -e "   완료: ${GREEN}${DONE}${NC}/${TOTAL_TASKS} tasks"
echo -e "   종료 시간: $(date)"

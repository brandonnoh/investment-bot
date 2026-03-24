#!/bin/bash
# 뉴스 수집 + 결과 텔레그램 알림

PYTHON=/opt/homebrew/bin/python3
PROJECT=/Users/jarvis/Projects/investment-bot
OPENCLAW=/opt/homebrew/bin/openclaw
LOG=$PROJECT/logs/news.log

START=$(date '+%H:%M')

# 뉴스 수집 실행
OUTPUT=$($PYTHON $PROJECT/data/fetch_news.py 2>&1)
EXIT_CODE=$?

# 로그 기록
echo "$OUTPUT" >> $LOG

# 결과 파싱
SAVED=$(echo "$OUTPUT" | grep "DB 저장" | grep -oE '[0-9]+건' | head -1)
SKIPPED=$(echo "$OUTPUT" | grep "중복" | grep -oE '[0-9]+건' | head -1)
TOTAL=$(echo "$OUTPUT" | grep "수집 완료" | grep -oE '[0-9]+건' | head -1)

# 결과 메시지
if [ $EXIT_CODE -eq 0 ]; then
    MSG="📰 뉴스 수집 완료 — ${START} KST

✅ 성공
신규: ${SAVED:-0건} | 중복 스킵: ${SKIPPED:-0건} | 누적: ${TOTAL:-0건}"
else
    MSG="📰 뉴스 수집 실패 — ${START} KST

❌ 오류 발생
$(echo "$OUTPUT" | tail -3)"
fi

# 텔레그램 전송 (one-shot 크론잡)
$OPENCLAW cron add \
    --name "뉴스수집결과" \
    --at "1m" \
    --session isolated \
    --message "$MSG" \
    --announce \
    --channel telegram \
    --to "2111337920" \
    --delete-after-run \
    --light-context \
    > /dev/null 2>&1

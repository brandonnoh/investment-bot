#!/bin/bash
# 뉴스 수집 전용 (알림 없음 — 모닝 브리핑에서 커버)

PYTHON=/opt/homebrew/bin/python3
PROJECT=/Users/jarvis/Projects/investment-bot
LOG=$PROJECT/logs/news.log

# 뉴스 수집 실행 (로그만 기록, 알림 없음)
$PYTHON $PROJECT/data/fetch_news.py >> $LOG 2>&1

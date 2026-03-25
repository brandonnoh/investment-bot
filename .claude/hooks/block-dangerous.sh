#!/bin/bash
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
BLOCKED=('rm -rf /' 'rm -rf ~' 'rm -rf \.' 'rm -rf \*' '> /dev/sd' 'mkfs\.' 'dd if=' ':(){:|:&};:' 'curl.*\| bash' 'curl.*\| sh' 'wget.*\| bash' 'wget.*\| sh' 'chmod -R 777' 'git push' 'git rebase' 'DROP TABLE' 'DROP DATABASE' 'TRUNCATE')
for pattern in "${BLOCKED[@]}"; do
    if echo "$COMMAND" | grep -qiE "$pattern"; then
        echo '{"permissionDecision":"deny","message":"🚫 차단됨: '"$pattern"'"}'
        exit 0
    fi
done
if echo "$COMMAND" | grep -qE '\.(env|env\.local|env\.production)'; then
    echo '{"permissionDecision":"deny","message":"🚫 차단됨: .env 파일 접근 금지"}'
    exit 0
fi
# DB 직접 삭제 방지
if echo "$COMMAND" | grep -qiE 'rm.*history\.db'; then
    echo '{"permissionDecision":"deny","message":"🚫 차단됨: DB 파일 삭제 금지"}'
    exit 0
fi

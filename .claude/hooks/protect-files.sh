#!/bin/bash
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
PROTECTED=('.env' '.kiwoom_token.json' 'db/history.db' '.git/' '.claude/settings.json' '.claude/hooks/')
for pattern in "${PROTECTED[@]}"; do
    if echo "$FILE_PATH" | grep -q "$pattern"; then
        echo '{"permissionDecision":"deny","message":"🔒 보호됨: '"$FILE_PATH"' 수정 불가"}'
        exit 0
    fi
done

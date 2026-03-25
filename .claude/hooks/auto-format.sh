#!/bin/bash
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
if [[ "$FILE_PATH" == *.py ]]; then
    ruff format "$FILE_PATH" 2>/dev/null || true
    ruff check --fix "$FILE_PATH" 2>/dev/null || true
fi

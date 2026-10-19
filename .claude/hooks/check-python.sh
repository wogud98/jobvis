#!/usr/bin/env bash
# AI가 파이썬 파일을 고칠 때마다 포맷과 린트를 바로 돌린다.
# 문제가 있으면 exit 2로 결과를 AI에게 돌려줘서 스스로 고치게 한다.
file=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))')
[[ "$file" == *.py ]] || exit 0
command -v ruff >/dev/null || exit 0
ruff format --quiet "$file"
if ! out=$(ruff check "$file" 2>&1); then
  echo "$out" >&2
  exit 2
fi

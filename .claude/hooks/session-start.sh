#!/usr/bin/env bash
# 클라우드에서 Claude Code 세션이 시작되면 개발 도구를 설치해 테스트와 린트를 바로 돌릴 수 있게 한다.
[ "$CLAUDE_CODE_REMOTE" = "true" ] || exit 0
pip install -q -r "$CLAUDE_PROJECT_DIR/requirements-dev.txt"

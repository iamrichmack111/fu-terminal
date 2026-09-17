#!/usr/bin/env bash
set -euo pipefail
REPO="${1:-iamrichmack111/fu-terminal}"
gh repo edit "$REPO" \
  --add-topic terminal --add-topic linux --add-topic devops --add-topic cli \
  --add-topic local-ai --add-topic ollama --add-topic kubernetes --add-topic shell \
  --add-topic command-line --add-topic developer-tools --add-topic terminal-assistant \
  --add-topic system-administration --add-topic python --add-topic automation --add-topic ai-assistant
echo "Topics updated for $REPO"

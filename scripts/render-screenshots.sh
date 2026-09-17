#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/demo"
if command -v npx >/dev/null 2>&1; then
  npm install
  npx playwright install chromium
  npm run screenshots
else
  echo "Node/npm required for Playwright screenshots" >&2; exit 1
fi

#!/usr/bin/env bash
set -euo pipefail
VERSION="${1:-$(cat VERSION)}"
git tag -a "v$VERSION" -m "FU Terminal v$VERSION" 2>/dev/null || true
git push origin main
git push origin "v$VERSION"
gh release create "v$VERSION" --title "FU Terminal v$VERSION" --notes-file RELEASE_NOTES.md fu-terminal-v${VERSION}.zip 2>/dev/null || gh release create "v$VERSION" --title "FU Terminal v$VERSION" --notes-file RELEASE_NOTES.md

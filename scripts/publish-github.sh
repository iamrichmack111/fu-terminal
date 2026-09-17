#!/usr/bin/env bash
set -euo pipefail
REPO="${1:-iamrichmack111/fu-terminal}"
VERSION="${2:-$(cat VERSION)}"
SSH_URL="git@github.com:${REPO}.git"

command -v git >/dev/null || { echo "git required" >&2; exit 1; }
command -v gh >/dev/null || { echo "GitHub CLI (gh) required" >&2; exit 1; }
ssh -T git@github.com 2>&1 || true

[ -d .git ] || git init
git branch -M main

git add .
if ! git diff --cached --quiet; then
  git commit -m "release: FU Terminal v${VERSION}"
fi

if ! gh repo view "$REPO" >/dev/null 2>&1; then
  gh repo create "$REPO" --public --description "Local-first terminal intelligence, safety, diagnostics, verification, and learning engine"
fi

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$SSH_URL"
else
  git remote add origin "$SSH_URL"
fi

git push -u origin main
./scripts/set-github-topics.sh "$REPO"

ZIP="fu-terminal-v${VERSION}.zip"
rm -f "$ZIP"
zip -qr "$ZIP" . -x '.git/*' '.venv/*' 'node_modules/*' 'demo/.venv/*' '*.pyc' '__pycache__/*'

git tag -a "v${VERSION}" -m "FU Terminal v${VERSION}" 2>/dev/null || true
git push origin "v${VERSION}"

if ! gh release view "v${VERSION}" >/dev/null 2>&1; then
  gh release create "v${VERSION}" "$ZIP" --title "FU Terminal v${VERSION}" --notes-file RELEASE_NOTES.md
else
  gh release upload "v${VERSION}" "$ZIP" --clobber
fi

echo
echo "✓ Published $REPO over SSH"
echo "✓ Release v${VERSION} created/uploaded"
echo "✓ Tag triggers GHCR container publishing workflow"

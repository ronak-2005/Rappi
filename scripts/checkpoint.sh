#!/usr/bin/env bash
# Commit, tag and push a checkpoint — ONLY if the full test suite passes and no secrets are staged.
# Usage: scripts/checkpoint.sh <tag> <tag-description> <commit-message-file>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAG="$1"; DESC="$2"; MSG_FILE="$3"
cd "$ROOT"

echo "▶ running tests"
(cd backend && .venv/bin/pytest -q) || { echo "✗ tests failed — no commit, no tag, no push"; exit 1; }

git add -A
if git diff --cached --name-only | grep -E '(^|/)(\.env|llm\.env)$|backend/var/.*\.db$'; then
  echo "✗ secret or runtime file staged — aborting"; exit 1
fi

git commit -q -F "$MSG_FILE"
git tag -a "$TAG" -m "$DESC"
git push -q origin main
git push -q origin "$TAG"
echo "✓ pushed $(git log --oneline -1) as $TAG"

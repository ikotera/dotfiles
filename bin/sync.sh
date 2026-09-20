#!/bin/bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRET_RE='ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY'

cd "$REPO_DIR"

git pull --rebase --autostash origin main

if [ -n "$(git status --porcelain)" ]; then
  git add -A
  added="$(git diff --cached | grep '^+' || true)"
  if grep -q -E "$SECRET_RE" <<<"$added"; then
    git reset -q
    echo "secret-like string found in pending changes; auto-commit aborted (this repo is public)" >&2
    exit 1
  fi
  git commit -m "chore: auto-sync $(date '+%Y-%m-%d %H:%M:%S')"
fi

git push origin main

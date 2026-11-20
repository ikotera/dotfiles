#!/usr/bin/env bash
# Apply local overlays to the Hermes source tree, without touching its Git index.
set -euo pipefail
patches="$(cd "$(dirname "${BASH_SOURCE[0]}")/../patches" && pwd)"
repo="${HERMES_AGENT_DIR:-$HOME/.hermes/hermes-agent}"
if ! root=$(git -C "$repo" rev-parse --show-toplevel 2>/dev/null) ||
   [[ $(cd "$repo" && pwd -P) != "$(cd "$root" && pwd -P)" ]]; then
  printf 'Warning: not a Hermes Git checkout root: %s; skipping patches.\n' "$repo" >&2
  exit 0
fi
shopt -s nullglob
for patch in "$patches"/*.patch; do
  if git -C "$repo" apply --check "$patch" 2>/dev/null; then
    if git -C "$repo" apply "$patch"; then
      printf 'Applied: %s\n' "${patch##*/}"
    else
      printf 'Warning: apply failed: %s; continuing.\n' "${patch##*/}" >&2
    fi
  elif git -C "$repo" apply --reverse --check "$patch" 2>/dev/null; then
    printf 'Already applied: %s\n' "${patch##*/}"
  else
    printf 'Warning: %s conflicts or was superseded upstream; left unchanged.\n' "${patch##*/}" >&2
  fi
done

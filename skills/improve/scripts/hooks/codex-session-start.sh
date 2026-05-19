#!/usr/bin/env bash
# Codex SessionStart hook adapter.

set -euo pipefail

if [ -z "${1:-}" ]; then
  cat >/dev/null || true
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$script_dir/check-signal-queue.sh"

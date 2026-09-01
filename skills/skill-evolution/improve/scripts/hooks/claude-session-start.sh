#!/usr/bin/env bash
# Claude Code SessionStart hook adapter.

set -euo pipefail

cat >/dev/null || true
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$script_dir/check-signal-queue.sh"

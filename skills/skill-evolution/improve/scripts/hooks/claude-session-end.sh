#!/usr/bin/env bash
# Claude Code SessionEnd hook adapter.
# Input (stdin): Claude Code SessionEnd hook JSON (carries transcript_path).
# Install: add to settings.json hooks.SessionEnd
#
# The classifier reads the payload itself — parsing a transcript is JSON work, and jq
# pipelines here would be a second place for the gates to drift out of sync.

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
log="$script_dir/../memory/classifier.log"
mkdir -p "$(dirname "$log")"
{ printf '%s ' "$(date -Iseconds)"; python3 "$script_dir/session_classifier.py" "$@"; } >> "$log" 2>&1

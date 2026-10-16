#!/usr/bin/env bash
# Block `gh pr create` / `gh-axi pr create` without an assignee, so every PR
# lands in the GitHub Project auto-import workflow (filters on assignee).
# Blocks instead of rewriting: rtk-rewrite.sh already owns updatedInput for gh.
CMD=$(jq -r '.tool_input.command // empty')
echo "$CMD" | grep -qE '(^|[;&|(][[:space:]]*)(rtk[[:space:]]+)?gh(-axi)?[[:space:]]+pr[[:space:]]+create\b' || exit 0
echo "$CMD" | grep -qE -- '(--assignee|-a)[[:space:]=]' && exit 0
echo 'BLOCK: PR 預設 assignee 給自己。加上 `--assignee @me` 後重跑。' >&2
exit 2

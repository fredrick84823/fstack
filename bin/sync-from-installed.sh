#!/usr/bin/env bash
# ⚠️  BETA — 手動觸發專用，尚未接排程。
#
# 這支腳本還在試跑階段：sanitize 規則是列舉式的，只擋得住「已知會出現」的
# 內部指涉。每次跑完都要人眼看過 git diff 再 commit，不要當成自動化。
# 等連續幾次同步都不需要人工修正，再考慮接進 hook 或排程。
#
# 把本機安裝版 skill 掉齊進 fstack，並把公司特定事實換成佔位符。
# canonical 是 fstack；安裝版是實際被編輯的那份，所以檔案方向固定 installed → repo。
#
# 用法
#   sync-from-installed.sh [SRC]        同步 SRC（預設安裝版）到 repo，然後跑 guard
#   sync-from-installed.sh --check [DIR] 只跑 guard，不動任何檔案（DIR 預設 repo 內的 skill）
#
# 退出碼
#   0  同步完成且 guard 乾淨 ／ --check 乾淨
#   1  用法或環境錯誤（SRC 不存在、不像 skill 目錄）
#   2  guard 命中內部指涉 —— 不要 commit
#
# ponytail: SKILL.md 的「版本來源檢查」在 repo 側被改寫成 fstack canonical，安裝版
#           還是舊文字，下次同步會蓋回去。靠上面那句「commit 前人眼看 git diff」擋。
#           要根治得改安裝版那一份。
set -euo pipefail

DST="$(cd "$(dirname "$0")/.." && pwd)/skills/comms/generate-meeting-notes"

# ── guard：殘留內部指涉 ───────────────────────────────────────────────────
# 兩段 pattern：人名／組織名要 word-boundary（否則 'mark' 命中 'Markdown'），
# 路徑與含空白的片語不能加 -w。
# BSD grep 不吃 \?，一律 -E / -F。
guard() {
  local dir=$1
  echo
  echo "── 殘留內部指涉（應為空）─────────────────────────"
  local leaks
  leaks="$(
    {
      # 人名大小寫敏感：'Mark'/'Frank' 本身是英文常用字，不列入（改用大寫專名比對）
      grep -rnwE 'Fredrick|Brian|Nina|家樂福|萬家福|熊寶貝|鮮乳坊' \
        "$dir" --include='*.md' --include='*.py' --include='*.toml' --include='*.yaml'
      grep -rniwE 'tagtoo|internal-cli-desktop' \
        "$dir" --include='*.md' --include='*.py' --include='*.toml' --include='*.yaml'
      grep -rniE 'thoughts/|Open Point|600 億' \
        "$dir" --include='*.md' --include='*.py' --include='*.toml' --include='*.yaml'
    } 2>/dev/null | sort -u || true
  )"
  if [[ -n $leaks ]]; then
    echo "$leaks"
    echo "⚠️  上面還有內部指涉，處理完再 commit" >&2
    return 2
  fi
  echo "  （無）"
}

if [[ ${1:-} == --check ]]; then
  guard "${2:-$DST}"
  exit $?
fi

SRC="${1:-$HOME/.agents/skills/generate-meeting-notes}"
[[ -f $SRC/SKILL.md ]] || { echo "SRC 不像 generate-meeting-notes 安裝目錄：$SRC" >&2; exit 1; }

echo "⚠️  BETA：sanitize 是列舉式的，commit 前務必人眼看過 git diff"
echo

# --delete 讓兩份真的掉齊；被 --exclude 的路徑在目的端不會被刪掉。
# -m 丟掉只剩排除項的空目錄（例如只有 __pycache__ 的 tests/）。
rsync -a --delete -m --itemize-changes \
  --exclude='.venv/' --exclude='__pycache__/' \
  --exclude='.pytest_cache/' --exclude='.DS_Store' \
  "$SRC/" "$DST/"

# ── sanitization：公司特定事實 → 佔位符 ──────────────────────────────────
# 人名不做自動替換：'Mark' 會命中 'Markdown'。人名一律在安裝版就用
# Alice / Bob / Carol，真名若重新出現由 guard 擋下來，人工處理。
find "$DST" \( -name '*.md' -o -name '*.py' -o -name '*.toml' -o -name '*.yaml' \) -print0 |
  xargs -0 sed -i '' \
    -e 's/`internal-cli-desktop`/`<your-oauth-client-name>`/g' \
    -e 's/`tagtoo-staging`/`<your-gcp-project>`/g' \
    -e 's/tagtoo-staging/<your-gcp-project>/g' \
    -e 's/「Tagtoo Line KMS」/「你的 consent screen 名稱」/g' \
    -e 's/那是 staging 的 consent screen 名稱/那是該 GCP project 的 consent screen 名稱/g' \
    -e 's/Admin console/Google Workspace 管理主控台/g' \
    -e 's|^\([[:space:]]*>*[[:space:]]*\)背景見 `~/thoughts/.*$|\1背景與決策脈絡請記錄在你自己的團隊文件中。|'

guard "$DST"

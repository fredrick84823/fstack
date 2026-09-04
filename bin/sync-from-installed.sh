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
# 設定（不進版控，見下方「設定」一節）
#   ~/.config/generate-meeting-notes/guard-patterns.txt
#   ~/.config/generate-meeting-notes/sanitize.sed
#
# 退出碼
#   0  同步完成且 guard 乾淨 ／ --check 乾淨
#   1  用法或環境錯誤（SRC 不存在、不像 skill 目錄、掃描目標不存在、設定檔未建立）
#   2  guard 命中內部指涉 —— 不要 commit
#
# macOS 限定：`sed -i ''` 與 BSD `grep` 的旗標。
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DST="$(cd "$HERE/.." && pwd)/skills/comms/generate-meeting-notes"

# ── 設定 ────────────────────────────────────────────────────────────────
# fstack 是 public repo，而「內部指涉清單」本身就是一份同事名 ＋ 客戶名 ＋
# GCP project ＋ OAuth client 的集合 —— 那正是這道 guard 要擋的東西。
# 所以 repo 只留機制與佔位符範例，值放使用者自己的設定檔。
CONF="$HOME/.config/generate-meeting-notes"
PATTERNS="$CONF/guard-patterns.txt"
SANITIZE="$CONF/sanitize.sed"

need_conf() { # $1=設定檔 $2=repo 內的範例檔名
  [[ -f $1 ]] && return 0
  echo "未設定：$1 不存在。複製 $HERE/$2 過去並填上自己的值。" >&2
  exit 1
}

# 設定檔一行一個 ERE pattern，前綴決定比對方式（見範例檔）。串成一條 alternation。
# `..*` 要求至少一個字元：空的分支（只打了 `w:` 的一行）會配到所有東西。
pats() { sed -n "s|^$1:\(..*\)|\1|p" "$PATTERNS" | paste -sd'|' -; }

# guard 與 sanitize 掃同一組副檔名。
INC=(--include='*.md' --include='*.py' --include='*.toml' --include='*.yaml')

# ── guard：殘留內部指涉 ───────────────────────────────────────────────────
# BSD grep 不吃 \?，一律 -E / -F。
guard() {
  local dir=$1
  need_conf "$PATTERNS" guard-patterns.example.txt
  [[ -d $dir ]] || { echo "掃描目標不存在：$dir" >&2; return 1; }

  local w iw i
  w="$(pats w)"; iw="$(pats iw)"; i="$(pats i)"
  # 一個 pattern 都沒有就是沒設定。空的命中集合被讀成「內容乾淨」正是這道
  # guard 要擋的失敗類別，不能靜默回 0。
  [[ -n "$w$iw$i" ]] || { echo "未設定：$PATTERNS 一個 pattern 都沒有" >&2; return 1; }

  echo
  echo "── 殘留內部指涉（應為空）─────────────────────────"
  local leaks
  leaks="$(
    {
      [[ -z $w  ]] || grep -rnwE  "$w"  "$dir" "${INC[@]}" || :
      [[ -z $iw ]] || grep -rniwE "$iw" "$dir" "${INC[@]}" || :
      [[ -z $i  ]] || grep -rniE  "$i"  "$dir" "${INC[@]}" || :
    } 2>/dev/null | sort -u
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
need_conf "$SANITIZE" sanitize.example.sed
need_conf "$PATTERNS" guard-patterns.example.txt

echo "⚠️  BETA：sanitize 是列舉式的，commit 前務必人眼看過 git diff"
echo

# --delete 讓兩份真的掉齊；被 --exclude 的路徑在目的端不會被刪掉。
# -m 丟掉只剩排除項的空目錄（例如只有 __pycache__ 的 tests/）。
rsync -a --delete -m --itemize-changes \
  --exclude='.venv/' --exclude='__pycache__/' \
  --exclude='.pytest_cache/' --exclude='.DS_Store' \
  "$SRC/" "$DST/"

# ── sanitization：公司特定事實 → 佔位符 ──────────────────────────────────
# 替換表同樣含真名，跟 guard pattern 一起放使用者設定檔。
find "$DST" \( -name '*.md' -o -name '*.py' -o -name '*.toml' -o -name '*.yaml' \) -print0 |
  xargs -0 sed -i '' -f "$SANITIZE"

guard "$DST"

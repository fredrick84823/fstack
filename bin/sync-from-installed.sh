#!/usr/bin/env bash
# ⚠️  BETA — 手動觸發專用，尚未接排程。
#
# 這支腳本還在試跑階段：sanitize 規則是列舉式的，只擋得住「已知會出現」的
# 內部指涉。每次跑完都要人眼看過 git diff 再 commit，不要當成自動化。
# 等連續幾次同步都不需要人工修正，再考慮接進 hook 或排程。
#
# 把本機安裝版 skill 掉齊進 fstack，並把公司特定事實換成佔位符。
# canonical 是 fstack，改動也從 repo 端開始（repo-first）—— 所以這個方向是**補救用**：
# 有人直接改了安裝版，把那些改動撿回 repo。日常掉齊走反向的 sync-to-installed.sh。
#
# 這支帶 `rsync --delete`：repo 端新增的檔案會被刪掉、修改過的會被安裝版的舊內容蓋回去，
# 而蓋回去之後兩邊又一致，parity 會在**舊內容上**轉綠 —— 合併的工作靜靜消失（#29）。
# 所以動檔案之前先問方向，repo 較新就拒絕執行。
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
#   3  repo 比安裝版新 —— 拒絕同步，先跑 bin/sync-to-installed.sh 掉齊
#
# macOS 限定：`sed -i ''` 與 BSD `grep` 的旗標。
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
SKILL_REL="skills/comms/generate-meeting-notes"
DST="$REPO/$SKILL_REL"

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

# ── 方向閘門 ──────────────────────────────────────────────────────────────
# 目的地還沒有 skill（parity 把這支複製進暫存假 repo 那種跑法）時沒有東西要保護，
# 跳過。這同時擋掉遞迴：方向判斷自己會再叫一次這支腳本去產 sanitize 過的基準，
# 那一次的目的地就是空的。
if [[ -f $DST/SKILL.md ]]; then
  PARITY="$DST/scripts/parity.py"
  # 找不到就停，不要當成「沒有意見」放行 —— 一道靜默跳過的閘門等於沒有閘門。
  [[ -f $PARITY ]] || { echo "找不到方向判斷：$PARITY" >&2; exit 1; }
  DIRECTION="$(python3 "$PARITY" --direction "$SRC" "$REPO")"
  # 白名單而不是黑名單：認得的兩個值才放行。parity.py 的常數改了字面值、或哪天多出
  # 第四種方向時，這裡配不到就是**拒絕**，不是放行 —— 一個跨語言的字串比對遲早會對不
  # 上，而對不上的那一次不能剛好是 rsync --delete 照跑。
  case $DIRECTION in
    "安裝版較新" | "一致") ;;
    *)
      {
        echo "⛔ 拒絕同步（方向：${DIRECTION}）。"
        echo "   這個方向帶 --delete：照跑會刪掉 repo 端新增的檔案、把修改過的蓋回舊內容，"
        echo "   而蓋回去之後 parity 會在舊內容上轉綠，沒有任何東西會叫。"
        echo "   先掉齊安裝版：bin/sync-to-installed.sh"
      } >&2
      exit 3
      ;;
  esac
fi

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

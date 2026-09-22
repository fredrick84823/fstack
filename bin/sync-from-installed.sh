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
# 涵蓋哪些 skill 是**資料**，不寫死在這支裡：清單見 bin/parity_skills.py 的 `SKILLS`。
# 這支只吃 `--skill`，不給就是 generate-meeting-notes（日常唯一會手動跑的那支）。
#
# 用法
#   sync-from-installed.sh [--skill REL] [SRC]
#       同步 SRC（預設 ~/.agents/skills/<skill 目錄名>）到 repo 的 REL，然後跑 guard
#   sync-from-installed.sh [--skill REL] --check [DIR]
#       只跑 guard，不動任何檔案（DIR 預設 repo 內那支 skill）
#
#   --skill REL    repo 相對路徑，預設 skills/comms/generate-meeting-notes
#
# 「要不要跑去識別化」**不是旗標**，是問 `SKILLS`：那個布林在 CLI 上再抄一次就會有人
# 忘了打，而忘了打的症狀是 sed 掃過一支不該被 sanitize 的 skill，把佔位符寫進它的機制檔。
# **guard 不跟著跳過**：去識別化沒需求不等於內部指涉沒需求，slack-pm 那起事故就是這樣漏的。
#
# 設定（不進版控，見下方「設定」一節）
#   ~/.config/generate-meeting-notes/guard-patterns.txt
#   ~/.config/generate-meeting-notes/sanitize.sed
#
# 退出碼
#   0  同步完成且 guard 乾淨 ／ --check 乾淨
#   1  用法或環境錯誤（SRC 不存在、不像 skill 目錄、掃描目標不存在、設定檔未建立、
#      --skill 的路徑不合法、或那支 skill 不在 bin/parity_skills.py 的涵蓋清單裡）
#   2  guard 命中內部指涉 —— 不要 commit
#   3  repo 比安裝版新 —— 拒絕同步，先跑 bin/sync-to-installed.sh 掉齊
#
# macOS 限定：`sed -i ''` 與 BSD `grep` 的旗標。
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
# 預設值就是「不給參數時的日常用法」，所以放在參數解析之前當底。
SKILL_REL="skills/comms/generate-meeting-notes"
if [[ ${1:-} == --skill ]]; then
  SKILL_REL="${2:-}"
  # 一定要是落在 skills/ 底下兩層的 repo 相對路徑。這支帶 `rsync --delete`：
  # 一個 `../..` 或絕對路徑會把 --delete 指到工作樹外面去。
  [[ $SKILL_REL == skills/*/* && $SKILL_REL != *..* ]] ||
    { echo "--skill 要帶 skills/<分類>/<skill> 形式的 repo 相對路徑：${SKILL_REL:-（空）}" >&2; exit 1; }
  shift 2
fi

DST="$REPO/$SKILL_REL"

# ── 設定 ────────────────────────────────────────────────────────────────
# fstack 是 public repo，而「內部指涉清單」本身就是一份同事名 ＋ 客戶名 ＋
# GCP project ＋ OAuth client 的集合 —— 那正是這道 guard 要擋的東西。
# 所以 repo 只留機制與佔位符範例，值放使用者自己的設定檔。
# 設定目錄沿用 generate-meeting-notes 這個名字，即使 guard 現在涵蓋多支 skill：裡面那份
# 清單是**公司層級**的（同事名、客戶名、GCP project），跟哪一支 skill 無關。改名只是逼
# 每個人手動搬一次檔案，換不到任何東西。
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

# ── 涵蓋檢查 ＋ 要不要去識別化 ──────────────────────────────────────────
# 兩件事同一個答案來源：bin/parity_skills.py 的 SKILLS。未涵蓋的 skill 在這裡就以非零
# 收場（`set -e`），而這一步在 SRC 檢查與 rsync **之前** —— 首次把一支新 skill 拉進
# repo 也要先被涵蓋，否則就是「同步得進來、但從此沒有任何東西在比對它」，正是 improve
# 漂移五天沒人發現的那個形狀。
#
# 暫存假 repo 裡沒有 parity_skills.py（parity 只把這支腳本複製進去產基準），那條路徑上
# skill 是呼叫端指定的、已經查過 SKILLS 的那支，而且要的就是 sanitize 過的基準 ——
# 所以缺席時照舊 sanitize。反向掉齊也會造暫存假 repo，它**有**把 parity_skills.py 一起
# 複製進去（見 sync-to-installed.sh），因為它要替非 sanitize 的 skill 產基準。
SKILLS_PY="$REPO/bin/parity_skills.py"
DO_SANITIZE=1
if [[ -f $SKILLS_PY ]]; then
  DO_SANITIZE="$(python3 "$SKILLS_PY" --sanitize "$SKILL_REL")"
fi

# 安裝版是**攤平**的：repo 的分類目錄（comms/、skill-evolution/…）在 ~/.agents/skills
# 底下沒有對應層級。同一條規則在 bin/parity_skills.py 是 installed_dir()。
SKILL_NAME="${SKILL_REL##*/}"
SRC="${1:-$HOME/.agents/skills/$SKILL_NAME}"
[[ -f $SRC/SKILL.md ]] || { echo "SRC 不像 $SKILL_NAME 安裝目錄：$SRC" >&2; exit 1; }
# 替換表只在真的要 sanitize 時才是必要條件；guard pattern 兩種 skill 都要。
# 兩個 need_conf 都在 rsync **之前** —— 缺設定的那次同步不可以先把檔案寫出去再喊停。
if (( DO_SANITIZE )); then need_conf "$SANITIZE" sanitize.example.sed; fi
need_conf "$PATTERNS" guard-patterns.example.txt

# ── 方向閘門 ──────────────────────────────────────────────────────────────
# 目的地還沒有 skill（parity 把這支複製進暫存假 repo 那種跑法）時沒有東西要保護，
# 跳過。這同時擋掉遞迴：方向判斷自己會再叫一次這支腳本去產 sanitize 過的基準，
# 那一次的目的地就是空的。
if [[ -f $DST/SKILL.md ]]; then
  # 方向判斷住在 repo 層（bin/），不在被同步的 skill 目錄裡：它現在要替多支 skill 回答，
  # 而且住在 skill 裡的話 `rsync --delete` 會把自己的判斷依據一起蓋掉。
  # 找不到就停，不要當成「沒有意見」放行 —— 一道靜默跳過的閘門等於沒有閘門。
  [[ -f $SKILLS_PY ]] || { echo "找不到方向判斷：$SKILLS_PY" >&2; exit 1; }
  DIRECTION="$(python3 "$SKILLS_PY" --direction "$SKILL_REL" "$SRC" "$REPO")"
  # 白名單而不是黑名單：認得的兩個值才放行。parity_skills.py 的常數改了字面值、或哪天多出
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
        echo "   （若確定是安裝版比較新、要把它的改動撿回 repo：那幾個檔案手動複製過來。"
        echo "     剛開的 worktree 裡 repo 端每個檔案的 mtime 都是 checkout 當下，這條會擋。）"
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
# `SKILLS` 是 False 的 skill 跳過這一步：它的 repo 版就是安裝版的原樣，跑 sed 只會讓
# repo 版與安裝版長得不一樣，而兩邊不一樣正是 parity 要叫的事。guard 不跳。
if (( DO_SANITIZE )); then
  find "$DST" \( -name '*.md' -o -name '*.py' -o -name '*.toml' -o -name '*.yaml' \) -print0 |
    xargs -0 sed -i '' -f "$SANITIZE"
fi

guard "$DST"

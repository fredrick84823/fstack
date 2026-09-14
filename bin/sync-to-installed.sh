#!/usr/bin/env bash
# 反向掉齊：把 fstack 的 skill 掉齊進本機安裝版。**PR 合併之後跑這支。**
#
# canonical 是 fstack，改動從 repo 端開始（一票一 worktree 是硬規則）。安裝版只有一份、
# 所有 worktree 共用，所以它是掉齊的產物，不是編輯的對象 —— 未合併的碼寫進去會同時
# 弄紅 main 與其他每一張票的 parity。
#
# **不是單純的反向 rsync。** repo 版是 sanitize 過的：GCP project、OAuth client 那些欄位
# 在 repo 是佔位符。直接複製回去等於把使用者的真實設定洗掉，比這支要修的問題更糟。
# 所以走三方合併：
#
#   base   = sanitize(安裝版)   ← 正向腳本跑進暫存目錄的結果
#   ours   = 安裝版             ← 帶真實設定
#   theirs = repo 版            ← 帶已合併的改動
#
# 佔位符那幾行在 base 與 theirs 之間沒有變化 → 合併保留 ours 的真實值；已合併的改動在
# base→theirs 有變化、ours 沒有 → 照樣帶過去。兩邊改到同一行才是衝突，那時留下衝突
# 合不起來，那時該檔的安裝版**保持原樣**並回非零 —— 不要靜靜挑一邊，也不要把衝突標記
# 留在使用者正在用的 skill 裡。
#
# 內容已經一致（`cmp` 相同）的檔案**完全不碰**。碰了就是把佔位符寫進去。
#
# 用法
#   sync-to-installed.sh [DST]    DST 預設 ~/.agents/skills/generate-meeting-notes
#
# 退出碼
#   0  掉齊完成
#   1  用法或環境錯誤（repo 或 DST 不像 skill 目錄）
#   2  基準產不出來 —— 正向腳本沒有乾淨收尾，這時沒有可信的 base，不做任何事
#   3  有衝突 —— 那些檔案的安裝版保持原樣，其餘照樣掉齊
#
# macOS 限定：與正向腳本同一組假設。
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
SKILL_REL="skills/comms/generate-meeting-notes"
SRC="$REPO/$SKILL_REL"
DST="${1:-$HOME/.agents/skills/generate-meeting-notes}"

[[ -f $SRC/SKILL.md ]] || { echo "repo 內找不到 skill：$SRC" >&2; exit 1; }
[[ -f $DST/SKILL.md ]] || { echo "DST 不像 generate-meeting-notes 安裝目錄：$DST" >&2; exit 1; }

# rsync 排除的那四類在 base 裡不會出現，所以走檔案時也要跳過，否則每一顆
# __pycache__ 都會被當成「repo 新增的檔案」複製過去。
PRUNE=(! -path '*/.venv/*' ! -path '*/__pycache__/*' ! -path '*/.pytest_cache/*' ! -name '.DS_Store')

# ── 基準：sanitize(安裝版) ────────────────────────────────────────────────
# 正向腳本的目的地是從它自己的位置推出來的，所以複製進暫存假 repo 再跑（與 parity.py
# 同一招）。走腳本而不是自己再寫一次 rsync ＋ sed：sanitize 規則只能有一份。
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/bin"
cp "$HERE/sync-from-installed.sh" "$STAGE/bin/"
"$STAGE/bin/sync-from-installed.sh" "$DST" >/dev/null || {
  echo "基準產不出來：正向腳本對 $DST 沒有乾淨收尾。沒有可信的 base，不動任何檔案。" >&2
  exit 2
}
BASE="$STAGE/$SKILL_REL"

echo "── 掉齊 $SRC → $DST ──"
conflicts=0

while IFS= read -r -d '' f; do
  rel="${f#"$SRC/"}"
  ours="$DST/$rel"
  base="$BASE/$rel"
  if [[ ! -e $ours ]]; then
    mkdir -p "$(dirname "$ours")"
    cp "$f" "$ours"
    echo "  + $rel"
    continue
  fi
  # 內容已經一致就不要碰。
  if cmp -s "$base" "$f"; then
    continue
  fi
  # base 缺席（安裝版有、但正向同步排除掉的路徑）時當成空檔：寧可衝突也不要無聲覆蓋。
  [[ -e $base ]] || base=/dev/null
  # 合併寫在暫存檔，乾淨了才搬進安裝版。衝突時安裝版**保持原樣** —— 不要把衝突標記
  # 留在使用者正在用的 skill 裡，那比沒掉齊更糟。
  # ponytail: diff3 是逐 hunk 的，佔位符與已合併的改動落在相鄰行時會判成衝突（中間沒有
  # context 行可分開），即使兩邊改的是不同行。目前佔位符只有 troubleshooting.md 的三行，
  # 撞上算少數，而撞上時的輸出是「請人看一眼」不是「靜靜挑一邊」。真的常撞再換成
  # 以 base↔安裝版的逐行對照表反推佔位符。
  cp "$ours" "$STAGE/.merge"
  if git merge-file "$STAGE/.merge" "$base" "$f"; then
    cp "$STAGE/.merge" "$ours"
    echo "  ~ $rel"
  else
    echo "  ! ${rel}（衝突，安裝版保持原樣）"
    conflicts=$((conflicts + 1))
  fi
done < <(find "$SRC" -type f "${PRUNE[@]}" -print0)

# repo 端刪掉的檔案。判準是 base 而不是安裝版本身 —— base 已經套過同一組排除規則，
# 所以 .venv/ 與 __pycache__ 不會被誤判成「repo 刪掉了」。
while IFS= read -r -d '' f; do
  rel="${f#"$BASE/"}"
  if [[ ! -e $SRC/$rel ]]; then
    rm -f "$DST/$rel"
    echo "  - $rel"
  fi
done < <(find "$BASE" -type f -print0)

if (( conflicts )); then
  echo "⚠️  $conflicts 個檔案合不起來，安裝版保持原樣。人工處理完再跑一次。" >&2
  exit 3
fi
echo "✅ 掉齊完成：$DST"

#!/usr/bin/env bash
# ⚠️  BETA — 手動觸發專用，尚未接排程。
#
# 這支腳本還在試跑階段：sanitize 規則是列舉式的，只擋得住「已知會出現」的
# 內部指涉。每次跑完都要人眼看過 git diff 再 commit，不要當成自動化。
# 等連續幾次同步都不需要人工修正，再考慮接進 hook 或排程。
#
# 把本機安裝版 skill 同步進 fstack，並把公司特定事實換成佔位符。
#
# 安裝版是嚴格超集，所以方向固定是 installed → repo。
# 執行後一定要看最後的「殘留內部指涉」清單：非空就是漏了，不要 commit。
set -euo pipefail

SRC="${1:-$HOME/.claude/skills/generate-meeting-notes}"
DST="$(cd "$(dirname "$0")/.." && pwd)/skills/comms/generate-meeting-notes"

[[ -d $SRC ]] || { echo "找不到安裝版：$SRC" >&2; exit 1; }

echo "⚠️  BETA：sanitize 是列舉式的，commit 前務必人眼看過 git diff"
echo

# 逐檔列出而非整個目錄 rsync：避免 .venv / .pytest_cache / __pycache__ 混進去
FILES=(SKILL.md README.md pyproject.toml uv.lock
        scripts/create_gdoc_from_md.py scripts/extract_audio_sources.py
        scripts/setup.py scripts/send_slack_notification.py
        scripts/replace_speakers.py scripts/generate_meeting_notes.py
        references/setup.md references/glossary.md
        references/multi-session.md references/troubleshooting.md
        references/default-prompt.md
        agents/openai.yaml)

for f in "${FILES[@]}"; do
  [[ -f $SRC/$f ]] || { echo "  skip（來源不存在）: $f"; continue; }
  mkdir -p "$(dirname "$DST/$f")"
  cp "$SRC/$f" "$DST/$f"
  echo "  copied: $f"
done

# ── sanitization：公司特定事實 → 佔位符 ──────────────────────────────────
sanitize() {
  local f=$1
  [[ -f $f ]] || return 0
  # GCP / consent screen / OAuth client 名稱
  sed -i '' \
    -e 's/`internal-cli-desktop`/`<your-oauth-client-name>`/g' \
    -e 's/`tagtoo-staging`/`<your-gcp-project>`/g' \
    -e 's/tagtoo-staging/<your-gcp-project>/g' \
    -e 's/「Tagtoo Line KMS」/「你的 consent screen 名稱」/g' \
    -e 's/那是 staging 的 consent screen 名稱/那是該 GCP project 的 consent screen 名稱/g' \
    -e 's/Admin console/Google Workspace 管理主控台/g' \
    "$f"
  # 人名不做自動替換：'Mark' 會命中 'Markdown'。人名一律在安裝版就用
  # Alice / Bob / Carol，真名若重新出現由結尾的 grep 擋下來，人工處理。
  # 指向私有 thoughts 的路徑：整行換成一般性說明
  sed -i '' \
    -e 's|^\([[:space:]]*>*[[:space:]]*\)背景見 `~/thoughts/.*$|\1背景與決策脈絡請記錄在你自己的團隊文件中。|' \
    "$f"
}

for f in "${FILES[@]}"; do sanitize "$DST/$f"; done

echo
echo "── 殘留內部指涉（應為空）─────────────────────────"
# 兩段 pattern：人名／組織名要 word-boundary（否則 'mark' 命中 'Markdown'），
# 路徑與含空白的片語不能加 -w。
LEAKS="$(
  {
    # 人名大小寫敏感：'Mark'/'Frank' 本身是英文常用字，不列入（改用大寫專名比對）
    grep -rnwE 'Fredrick|Brian|Nina|家樂福|萬家福|熊寶貝|鮮乳坊' \
      "$DST" --include='*.md' --include='*.py' --include='*.toml'
    grep -rniwE 'tagtoo|internal-cli-desktop' \
      "$DST" --include='*.md' --include='*.py' --include='*.toml'
    grep -rniE 'thoughts/|Open Point|600 億' \
      "$DST" --include='*.md' --include='*.py' --include='*.toml'
  } 2>/dev/null | sort -u || true
)"

if [[ -n $LEAKS ]]; then
  echo "$LEAKS"
  echo "⚠️  上面還有內部指涉，處理完再 commit"
  exit 1
fi
echo "  （無）"

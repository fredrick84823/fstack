#!/bin/bash

# ========================================
# Beautiful Mermaid - 批量渲染腳本
# ========================================
#
# 用途：批量渲染目錄中的所有 .mmd 檔案
#
# 使用方式：
#   ./batch-render.sh
#   ./batch-render.sh <input_dir> <output_dir> <theme>
#
# 範例：
#   ./batch-render.sh diagrams rendered tokyo-night
#
# ========================================

set -e  # 遇到錯誤時退出

# ========================================
# 配置參數
# ========================================

# 預設值
DEFAULT_INPUT_DIR="./diagrams"
DEFAULT_OUTPUT_DIR="./rendered"
DEFAULT_THEME="tokyo-night"
DEFAULT_FORMAT="svg"

# 從命令列參數取得設定，或使用預設值
INPUT_DIR="${1:-$DEFAULT_INPUT_DIR}"
OUTPUT_DIR="${2:-$DEFAULT_OUTPUT_DIR}"
THEME="${3:-$DEFAULT_THEME}"
FORMAT="${4:-$DEFAULT_FORMAT}"

# 顏色輸出（optional）
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ========================================
# 輔助函數
# ========================================

print_header() {
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  Beautiful Mermaid - 批量渲染工具${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_config() {
    echo -e "${BLUE}配置：${NC}"
    echo -e "  輸入目錄: ${YELLOW}$INPUT_DIR${NC}"
    echo -e "  輸出目錄: ${YELLOW}$OUTPUT_DIR${NC}"
    echo -e "  主題:     ${YELLOW}$THEME${NC}"
    echo -e "  格式:     ${YELLOW}$FORMAT${NC}"
    echo ""
}

# ========================================
# 驗證環境
# ========================================

print_header
print_config

# 檢查 Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ 錯誤: 找不到 Node.js${NC}"
    echo -e "${YELLOW}請先安裝 Node.js: https://nodejs.org/${NC}"
    exit 1
fi

# 檢查輸入目錄
if [ ! -d "$INPUT_DIR" ]; then
    echo -e "${RED}❌ 錯誤: 輸入目錄不存在: $INPUT_DIR${NC}"
    exit 1
fi

# 檢查是否有 .mmd 檔案
mmd_count=$(find "$INPUT_DIR" -name "*.mmd" -type f | wc -l | tr -d ' ')
if [ "$mmd_count" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  警告: 在 $INPUT_DIR 中找不到 .mmd 檔案${NC}"
    exit 0
fi

echo -e "${GREEN}✅ 環境檢查通過${NC}"
echo -e "${BLUE}發現 $mmd_count 個 .mmd 檔案${NC}"
echo ""

# ========================================
# 創建輸出目錄
# ========================================

if [ ! -d "$OUTPUT_DIR" ]; then
    echo -e "${BLUE}📁 創建輸出目錄: $OUTPUT_DIR${NC}"
    mkdir -p "$OUTPUT_DIR"
fi

# ========================================
# 渲染所有圖表
# ========================================

echo -e "${CYAN}開始渲染...${NC}"
echo ""

success_count=0
failed_count=0
failed_files=()

# 計算進度用
current=0
total=$mmd_count

for mmd_file in "$INPUT_DIR"/*.mmd; do
    # 跳過不存在的檔案（防止 glob 擴展失敗）
    [ -e "$mmd_file" ] || continue

    # 增加計數
    ((current++))

    # 取得檔案名稱（不含路徑和副檔名）
    filename=$(basename "$mmd_file" .mmd)

    # 輸出檔案路徑
    output_file="$OUTPUT_DIR/${filename}.${FORMAT}"

    # 顯示進度
    echo -e "${BLUE}[$current/$total]${NC} 渲染: ${YELLOW}$filename${NC}"

    # 執行渲染
    if node scripts/render_mermaid.js \
        -i "$mmd_file" \
        -o "$output_file" \
        -t "$THEME" \
        -f "$FORMAT" \
        > /dev/null 2>&1; then

        # 成功
        echo -e "       ${GREEN}✅ 完成: $output_file${NC}"
        ((success_count++))
    else
        # 失敗
        echo -e "       ${RED}❌ 失敗: $filename${NC}"
        ((failed_count++))
        failed_files+=("$filename")
    fi

    echo ""
done

# ========================================
# 顯示結果摘要
# ========================================

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  渲染完成${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}✅ 成功: $success_count 個檔案${NC}"

if [ $failed_count -gt 0 ]; then
    echo -e "${RED}❌ 失敗: $failed_count 個檔案${NC}"
    echo ""
    echo -e "${YELLOW}失敗的檔案：${NC}"
    for failed_file in "${failed_files[@]}"; do
        echo -e "  - $failed_file"
    done
    echo ""
fi

echo -e "${BLUE}輸出位置: $OUTPUT_DIR${NC}"
echo ""

# ========================================
# 退出狀態
# ========================================

if [ $failed_count -gt 0 ]; then
    exit 1
else
    exit 0
fi

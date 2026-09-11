r"""Docs 匯出的 `\[` 轉義不能漏進 Google Doc 內文。

這個 bug 的來源是回饋迴圈：Docs 匯出 markdown 會把 `[` 寫成 `\[`，agent 讀歷史
正式稿求連續性時照抄，草稿就帶著轉義送進 `_markdown_to_gdocs`。#7 的歷史索引會
放大它 —— 索引讀進來的每一份都是 Docs 匯出的。

住在 repo root 的 `tests/unit/` 而不是 `skills/comms/generate-meeting-notes/tests/`：
那個目錄是 `bin/sync-from-installed.sh` 用 `rsync --delete` 掉齊出來的鏡像，內容由安裝版
決定，放測試等於把測試套件交給鏡像管。而且 `setup.cfg` 的 `testpaths` 與 mutmut 的
`pytest_add_cli_args_test_selection` 都只看 `tests/unit`，放那邊的測試殺不到任何 mutant。
"""

import pytest

from tests.unit.conftest import _qid, load_script

mod = load_script("extract_audio_sources")

# 這個 skill 真的會遇到的轉義字元：Docs 匯出只轉義 markdown 有意義的標點。
UNESCAPED = [
    (r"\[待確認\]", "[待確認]"),
    (r"\(附註\)", "(附註)"),
    (r"3\. 第三點", "3. 第三點"),
    (r"\- 破折", "- 破折"),
    (r"\| 管線", "| 管線"),
]


@pytest.mark.parametrize("raw,expected", UNESCAPED, ids=[_qid(r) for r, _ in UNESCAPED])
def test_parse_inline_unescapes_the_punctuation_docs_escaped(raw, expected):
    plain, _, _ = mod._parse_inline(raw)

    assert plain == expected


def test_bold_range_still_covers_the_unescaped_text():
    """還原發生在 span 計算之前，否則 range 會照著轉義前的長度算、標到隔壁字。"""
    plain, bolds, _ = mod._parse_inline(r"**A \[B\]** C")

    assert plain == "A [B] C"
    ((start, end),) = bolds
    assert plain[start:end] == "A [B]"


def test_escaped_asterisk_left_alone_so_bold_parsing_survives():
    """`*` 與 backtick 刻意不還原：先還原會讓 `\\*\\*` 變成真的 bold 標記。

    代價寫在下面那條斷言裡，不要只斷 `bolds == []` —— 那樣會把「反斜線漏進內文」
    這個已知缺口靜靜釘住，看起來像沒有缺口。
    """
    plain, bolds, codes = mod._parse_inline(r"\*\*不是粗體\*\*")

    assert bolds == []
    assert codes == []
    # 已知缺口：這兩個反斜線會以字面樣貌進 Doc，正是這支修正要消滅的症狀。
    # 修法是把還原移到 _parse_inline 的 span 切分**之後**逐段做，不在本票範圍。
    assert plain == r"\*\*不是粗體\*\*"


def test_table_cells_and_body_both_unescaped():
    """表格 cell 走的是另一條路徑（`_parse_inline_bold`），要分別釘住。"""
    md = "\n".join([
        r"# 會議記錄",
        r"* 歸屬 \[待確認\]",
        r"| 負責人 | 狀態 |",
        r"| --- | --- |",
        r"| Zorblax | \[執行中\] |",
    ])

    plain, _, tables = mod._markdown_to_gdocs(md)

    assert "\\" not in plain
    # tables 回傳原始 cell 字串；unescape 在插入時的 _parse_inline_bold 才發生，
    # 所以要斷在那條真正寫進 Doc 的路徑上。
    cells = [c for _, rows in tables for row in rows for c in row]
    inserted = [mod._parse_inline_bold(c)[0] for c in cells]

    assert all("\\" not in c for c in inserted), inserted
    assert "[執行中]" in inserted

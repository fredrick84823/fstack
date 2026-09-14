"""`_markdown_to_gdocs` 吐出來的 request **形狀**逐字釘住：型別 key、range、樣式值、fields。

既有的 `test_inline_style_requests.py` 只驗「range 切回來等於那段字」，所以組 request 的
那些字串一個都沒被看過 —— `"HEADING_4"` 寫成 `"heading_4"`、`"fields"` 寫成 `"FIELDS"`、
`"bulletPreset"` 寫成 `"bulletpreset"`，Docs 會回 400 或靜靜忽略，而本機測試全綠。
mutmut 實跑把這件事說完了：`_markdown_to_gdocs` 的存活 mutant 幾乎全部集中在這些字面值上。

期望值**不是**從實作印出來抄的，是從 Google Docs API 規格與 Markdown 語意推的：

- `updateParagraphStyle` = `{range, paragraphStyle: {namedStyleType}, fields}`，
  `NamedStyleType` 的列舉值全大寫（`HEADING_1` … `HEADING_6`）
- `createParagraphBullets` = `{range, bulletPreset}`，`BULLET_DISC_CIRCLE_SQUARE` 全大寫
- `updateTextStyle` = `{range, textStyle, fields}`，`fields` 是逗號分隔的屬性名
- `range` 的單位是 **UTF-16 code unit、1-based**（index 0 是文件開頭的 section break）、半開區間
- **段落樣式的 range 要蓋到段落結尾的換行**，否則 Docs 不把它當整段；
  `createParagraphBullets` 尤其 —— 範圍沒蓋到段落標記時項目符號不會生效。
  所以段落類的 `endIndex` = 該行文字結尾 +1，文字樣式類則只蓋文字本身。

語料的手算過程（每行貢獻 `u16len(plain) + 1`，那個 +1 是段落結尾的換行；
`🎉` 在 UTF-16 是 2 個 code unit、在 Python 是 1 個字元，所以第 1 行之後每個 index
都分得出兩種算法）：

```
 #  markdown                                 kind   plain                          u16  start  end   段落 range
 1  # Report 🎉                              H1     Report 🎉                        9      1    10   1–11
 2  ## Agenda                                H2     Agenda                          6     11    17   11–18
 3  ### Notes                                H3     Notes                           5     18    23   18–24
 4  #### Detail                              H4     Detail                          6     24    30   24–31
 5  ##### Minor                              H5     Minor                           5     31    36   31–37
 6  ###### Tiny                              H6     Tiny                            4     37    41   37–42
 7  - ship `deploy.sh` now                   bullet ship deploy.sh now             18     42    60   42–61
 8  * review **the plan**                    bullet review the plan                15     61    76   61–77
 9  ---                                      分隔線 (空)                             0     77    77   （無）
10  plain line with **bold** and `code`      normal plain line with bold and code   29     78   107   （無）
```

總長 = 9+6+5+6+5+4+18+15+0+29（文字）+ 10（每行一個換行）= 107 code unit，
占 index [1, 108)，所以最後一行的結尾 107 同時是整份文字的結尾。

行內樣式的絕對 index = 該行 start + 行內 offset：
- 第 7 行 `deploy.sh`：`ship ` 占 5 → 行內 [5, 14) → 42+5=47, 42+14=56
- 第 8 行 `the plan`：`review ` 占 7 → 行內 [7, 15) → 61+7=68, 61+15=76
- 第 10 行 `bold`：`plain line with ` 占 16 → 行內 [16, 20) → 78+16=94, 78+20=98
- 第 10 行 `code`：`plain line with bold and ` 占 25 → 行內 [25, 29) → 78+25=103, 78+29=107
"""

from __future__ import annotations

import pytest

from tests.unit.conftest import _qid, load_script

mod = load_script("extract_audio_sources")

CORPUS = "\n".join([
    "# Report 🎉",
    "## Agenda",
    "### Notes",
    "#### Detail",
    "##### Minor",
    "###### Tiny",
    "- ship `deploy.sh` now",
    "* review **the plan**",
    "---",
    "plain line with **bold** and `code`",
])

EXPECTED_TEXT = (
    "Report 🎉\n"
    "Agenda\n"
    "Notes\n"
    "Detail\n"
    "Minor\n"
    "Tiny\n"
    "ship deploy.sh now\n"
    "review the plan\n"
    "\n"
    "plain line with bold and code\n"
)


@pytest.fixture
def converted() -> tuple[str, list[dict], list]:
    """**不准加 `scope="module"`。** 快取一次之後，只有第一條測試真的呼叫到
    `_markdown_to_gdocs`，其餘都是拿現成的 tuple。

    mutmut 靠 trampoline 記「哪條測試碰過哪個函式」，快取住的呼叫不會再碰 ——
    實測 module scope 時 mutmut 只認得本檔的一條測試覆蓋 `_markdown_to_gdocs`，
    於是挑覆蓋測試時整份 heading／bullet／fields 的比對都沒被選上，
    `"HEADING_3"` → `"heading_3"` 這種 mutant 就活著（手動改產品碼跑 `make test`
    明明是紅的）。症狀是 mutation 分數難看，而不是任何東西變紅 ——
    沒人會去查一個「本來就沒殺光」的數字。
    """
    return mod._markdown_to_gdocs(CORPUS)


def of_kind(requests: list[dict], kind: str) -> list[dict]:
    """挑出某一種 request 的內容。用 `in` 而不是 `.get()` —— 型別 key 被改名時
    這裡要挑不到東西（然後下面的比對紅），不是挑到 `None` 之後靜靜略過。"""
    return [r[kind] for r in requests if kind in r]


# --------------------------------------------------------------------------
# 基準：整份純文字。下面每個 index 都是從這串字算出來的
# --------------------------------------------------------------------------


def test_plain_text_is_one_paragraph_per_markdown_line(converted):
    """擋「分隔線被吃掉」與「最後一段沒有段落標記」這兩種會讓後面所有 index 整排偏移的壞法。

    分隔線的純文字是空的但**段落還在**（Docs 沒有水平線元素，這個 skill 用空段落代替），
    少掉那一行的話第 10 行的 index 會整個往前 1，而所有樣式仍然「切得回來一段字」——
    只是切到隔壁去。每行結尾的換行也一樣：段落樣式的 endIndex 是 `文字結尾 + 1`，
    最後一行沒有換行的話那個 +1 會指到文件外。
    """
    text, _, _ = converted

    assert text == EXPECTED_TEXT
    assert mod._u16len(text) == 107


# --------------------------------------------------------------------------
# 段落樣式：型別 key、range、namedStyleType、fields
# --------------------------------------------------------------------------

EXPECTED_PARAGRAPH_STYLES = [
    {"range": {"startIndex": 1, "endIndex": 11},
     "paragraphStyle": {"namedStyleType": "HEADING_1"}, "fields": "namedStyleType"},
    {"range": {"startIndex": 11, "endIndex": 18},
     "paragraphStyle": {"namedStyleType": "HEADING_2"}, "fields": "namedStyleType"},
    {"range": {"startIndex": 18, "endIndex": 24},
     "paragraphStyle": {"namedStyleType": "HEADING_3"}, "fields": "namedStyleType"},
    {"range": {"startIndex": 24, "endIndex": 31},
     "paragraphStyle": {"namedStyleType": "HEADING_4"}, "fields": "namedStyleType"},
    {"range": {"startIndex": 31, "endIndex": 37},
     "paragraphStyle": {"namedStyleType": "HEADING_5"}, "fields": "namedStyleType"},
    {"range": {"startIndex": 37, "endIndex": 42},
     "paragraphStyle": {"namedStyleType": "HEADING_6"}, "fields": "namedStyleType"},
]


def test_heading_paragraph_style_requests_are_pinned_verbatim(converted):
    """六級標題的 `namedStyleType` 逐字釘死，連 `fields` 的字串都比。

    擋的是「列舉值大小寫寫錯」「level → style 的對照表某一格接錯級」「`fields` 沒點名
    `namedStyleType`」這三種：Docs 對前兩種回 400（但只有真的建 Doc 才看得到），
    對第三種回 200 然後什麼都不套 —— 產出一份所有標題都是內文的會議記錄。

    比整串 list 而不是逐條挑：少送一條、多送一條、或把一般段落也套上樣式，
    逐條比對都可能是綠的。順序也一起釘住 —— 段落樣式要照文件順序送。
    """
    _, requests, _ = converted

    assert of_kind(requests, "updateParagraphStyle") == EXPECTED_PARAGRAPH_STYLES


def test_bullets_and_plain_lines_get_no_paragraph_style(converted):
    """上面那條的另一半：只有標題有段落樣式。

    分開寫是因為「把 bullet 也送成 HEADING_x」跟「標題對照表接錯」是兩種不同的壞法，
    而且這條是 `elif kind == "bullet"` 被改成 `!=` 之後第一個紅的東西。
    """
    _, requests, _ = converted
    styled_ranges = [r["range"]["startIndex"] for r in of_kind(requests, "updateParagraphStyle")]

    assert styled_ranges == [1, 11, 18, 24, 31, 37]


# --------------------------------------------------------------------------
# 項目符號：range 必須蓋到段落標記，preset 必須是列舉值
# --------------------------------------------------------------------------


def test_bullet_requests_cover_the_paragraph_mark_with_the_disc_preset(converted):
    """`createParagraphBullets` 的 range 沒蓋到段落結尾的換行時，Docs 收下但不長項目符號。

    所以 endIndex 是行尾 +1（42–61 而不是 42–60）。這是整份檔案裡最沉默的壞法：
    request 送得出去、回 200、文件建得起來，只是條列全部變成一般段落。
    preset 也一起釘住 —— `BulletGlyphPreset` 是列舉值，小寫或加料都是 400。
    """
    _, requests, _ = converted

    assert of_kind(requests, "createParagraphBullets") == [
        {"range": {"startIndex": 42, "endIndex": 61},
         "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"},
        {"range": {"startIndex": 61, "endIndex": 77},
         "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"},
    ]


# --------------------------------------------------------------------------
# 文字樣式：H1 的整段加粗、行內 bold、行內 code
# --------------------------------------------------------------------------


def text_styles(requests: list[dict], style: dict) -> list[dict]:
    return [r for r in of_kind(requests, "updateTextStyle") if r["textStyle"] == style]


def test_bold_text_style_requests_are_pinned_verbatim(converted):
    """三條 bold：H1 整段（1–11）＋ 兩段行內粗體（68–76、94–98）。

    擋兩種：`if level == 1` 那條分支被改掉（H1 不再加粗，或六級標題全部加粗），
    以及 `fields` 沒寫 `bold`（Docs 回 200，標題看起來就只是字大一點）。

    H1 那條的 `endIndex` 是 **11 不是 10** —— 它沿用段落的 range，連段落標記
    （行尾那個換行）一起加粗。手算時推的是 10：`updateTextStyle` 套的是文字，
    「範圍要蓋到段落標記」那條規格是給 `updateParagraphStyle` 與
    `createParagraphBullets` 的。11 是**實作的選擇**，不是規格要求：
    段落非空時段落標記的粗體看不出來，效果只有「之後在行尾接著打字會延續粗體」。
    釘 11 是記錄現狀，不是同意它是唯一正確答案；真要改成 10 是產品決定，
    不在 #9 的範圍內。改動這條分支時這行會紅，那時再決定。
    """
    _, requests, _ = converted
    bold = {"bold": True}

    assert text_styles(requests, bold) == [
        {"range": {"startIndex": 1, "endIndex": 11}, "textStyle": bold, "fields": "bold"},
        {"range": {"startIndex": 68, "endIndex": 76}, "textStyle": bold, "fields": "bold"},
        {"range": {"startIndex": 94, "endIndex": 98}, "textStyle": bold, "fields": "bold"},
    ]


def test_inline_code_text_style_requests_are_pinned_verbatim(converted):
    """兩段 inline code 的 range 逐字釘住（47–56、103–107）。

    `fields` 比 set 不比字串：三個屬性的**順序**不是規格決定的（Docs 不在意），
    比字串等於把實作的 dict 排列順序也釘住，那是假的鑑別力。但三個都要在 —— 漏一個
    的症狀是「有灰底但字不是紅的」，沒有人會回報。
    """
    _, requests, _ = converted
    got = text_styles(requests, mod.INLINE_CODE_STYLE)

    assert [r["range"] for r in got] == [
        {"startIndex": 47, "endIndex": 56},
        {"startIndex": 103, "endIndex": 107},
    ]
    for req in got:
        assert set(req["fields"].split(",")) == set(mod.INLINE_CODE_STYLE)


def test_no_other_request_types_are_emitted(converted):
    """整份 request 只有這三種型別。

    擋的是型別 key 被改名 —— `"updateParagraphStyle"` 改成 `"UpdateParagraphStyle"` 之後
    上面每條比對都只是「挑不到東西，跟空 list 比」，沒有一條會紅。這條把「有哪些型別」
    本身變成斷言。
    """
    _, requests, _ = converted
    kinds = sorted({k for r in requests for k in r})

    assert kinds == ["createParagraphBullets", "updateParagraphStyle", "updateTextStyle"]
    assert [len(r) for r in requests] == [1] * len(requests), "一個 request dict 只放一種型別"


# --------------------------------------------------------------------------
# `_classify_line`：分隔線與空行的三個回傳值釘成確切的值
# --------------------------------------------------------------------------

SEPARATORS = ["---", "***", "___", "-----", "*****", "___________", "---   "]


@pytest.mark.parametrize("line", SEPARATORS, ids=[_qid(s) for s in SEPARATORS])
def test_separator_lines_are_empty_paragraphs(line):
    """分隔線：kind 不是 heading 也不是 bullet、level 0、純文字是空的。

    既有的 `test_every_kind_of_line_returns_all_five_values` 只斷型別（`kind in {...}`、
    `isinstance(level, int)`），所以分隔線回什麼值都過。這條把值本身釘死，擋三種：
    辨識分隔線的 regex 被改掉（`---` 退化成一般段落，三個減號原樣出現在 Doc 裡）、
    level 回 0 以外的值（下游拿 level 當標題級數或縮排，會多一層縮排或變成 H1）、
    plain 回非空字串（分隔線的內容會被印出來）。

    `***` 與 `___` 一起測：`*` 開頭同時也是 bullet 的標記，分隔線要贏。
    """
    assert mod._classify_line(line) == ("normal", 0, "", [], [])


def test_blank_line_is_an_empty_paragraph_too():
    """空行跟分隔線走同一條出口。兩者都是「有段落、沒內容」，差別只在 Markdown 寫法。"""
    assert mod._classify_line("") == ("normal", 0, "", [], [])


NOT_SEPARATORS = ["--", "**", "__", "- 只有一個減號開頭"]


@pytest.mark.parametrize("line", NOT_SEPARATORS, ids=[_qid(s) for s in NOT_SEPARATORS])
def test_two_markers_are_not_a_separator(line):
    """Markdown 的分隔線要 3 個以上。擋的是 regex 的 `{3,}` 被放寬成 `{2,}` 或 `+`：
    那會讓 `**` 開頭的行（沒收尾的粗體）整行消失在 Doc 裡。"""
    _, _, plain, _, _ = mod._classify_line(line)

    assert plain != ""


# --------------------------------------------------------------------------
# 表格：插入 index、rows、以及「表格不推走後面的 index」
# --------------------------------------------------------------------------
#
# 表格走的是 `_markdown_to_gdocs` 裡另一條分支，跟上面那份語料完全沒有交集：
# 表格的文字**不進** `plain_text`（Docs 的表格是另一種結構，不是內文），但它要插在
# 文件的哪一格，是拿「前面所有**非表格**文字」累加出來的同一個 `char_pos` 算的。
# 也就是說：樣式 range 會犯的偏移病，表格插入 index 一字不差地會再犯一次 ——
# 表格接在含 emoji 的行後面時，用 Python 字元算就會少算，整個表格插到前一個字中間。
#
# 手算（同樣是每行 `u16len(plain) + 1`，表格那幾行不計；`🎉` `🚀` 各占 2 個 code unit）：
#
# ```
#  #  markdown                 進 plain?  plain               py  u16  累積 char_pos
#  1  # Notes 🎉               是         Notes 🎉             7    8   0 → 9
#  2  | 負責人 | 狀態 |         否（表格）                            9   ← 表格 ① 插在 1+9 = 10
#  3  | --- | --- |            否（分隔列）
#  4  | A | **進行中** |        否（表格）
#  5  - between 🚀 lines       是         between 🚀 lines    15   16   9 → 26
#  6  | 項目 | 期限 |           否（表格）                           26   ← 表格 ② 插在 1+26 = 27
#  7  | --- | --- |            否（分隔列）
#  8  | B | 2026-09-14 |       否（表格）
#  9  | C | TBD |              否（表格）
# 10  ## tail line             是         tail line            9    9   26 → 36
# ```
#
# plain_text 只有三行，總長 (8+1)+(16+1)+(9+1) = 36 個 code unit，占 index [1, 37)。
# 用 Python 字元算的話總長是 34，兩個表格的插入 index 會是 9 與 25 而不是 10 與 27 ——
# 這就是這份語料要的鑑別力，兩個 emoji 一個在表格 ① 之前、一個在表格 ② 之前。

TABLE_CORPUS = "\n".join([
    "# Notes 🎉",
    "| 負責人 | 狀態 |",
    "| --- | --- |",
    "| A | **進行中** |",
    "- between 🚀 lines",
    "| 項目 | 期限 |",
    "| --- | --- |",
    "| B | 2026-09-14 |",
    "| C | TBD |",
    "## tail line",
])

EXPECTED_TABLE_TEXT = "Notes 🎉\nbetween 🚀 lines\ntail line\n"

EXPECTED_TABLES = [
    (10, [["負責人", "狀態"], ["A", "**進行中**"]]),
    (27, [["項目", "期限"], ["B", "2026-09-14"], ["C", "TBD"]]),
]


@pytest.fixture
def with_tables() -> tuple[str, list[dict], list]:
    """跟 `converted` 一樣是函式 scope —— 理由見那支 fixture 的 docstring。"""
    return mod._markdown_to_gdocs(TABLE_CORPUS)


def test_both_tables_are_returned_with_their_insert_index(with_tables):
    """兩個表格的插入 index 與 rows 逐字釘住。

    擋三種都不會報錯的壞法：
      - index 用 Python 字元算（10 → 9、27 → 25）：表格插進前一個字中間，
        emoji 愈多偏愈遠，而純中英文的記錄完全正常
      - index 的基底算錯（`1 + char_pos` 寫成 `2 + char_pos` 或 `1 - char_pos`）：
        前者整個表格晚一格、後者是負數 index，兩種都要送到 Docs 才看得到
      - 掃到第一個表格就停（分支結尾 `continue` 寫成 `break`）：第二個表格與它
        之後的所有內容靜靜消失，產出的會議記錄少一半而且沒有任何錯誤訊息

    `rows` 一起比：分隔列 `| --- | --- |` 不算一列（表格 ① 兩列、② 三列），
    cell 是**原始** markdown 字串（`**進行中**` 的標記留著，還原與樣式在插入時
    才由 `_parse_inline_bold` 處理 —— 見 `test_md_unescape.py`）。
    """
    _, _, tables = with_tables

    assert tables == EXPECTED_TABLES


def test_table_text_never_reaches_the_body_text(with_tables):
    """表格的字不進內文。漏進去的症狀是 Doc 裡先出現一整段 `| 負責人 | 狀態 |`
    的純文字、下面才是真的表格，而且後面每一行的 index 都被那段字推走。"""
    text, _, _ = with_tables

    assert text == EXPECTED_TABLE_TEXT
    assert "|" not in text


def test_lines_after_a_table_keep_the_index_the_table_did_not_move(with_tables):
    """第 3 點：表格**不推進** `char_pos`，所以表格後面那些行的 index 跟沒有表格時一樣。

    這條跟上面那條分開：內文裡沒有 `|` 不代表 `char_pos` 沒被加過 —— 只要表格那幾行
    的長度被算進累加值（文字卻沒進去），後面每一段的樣式就會整排往右飄，
    而 `plain_text` 看起來完全正常。

    `break` 那顆 mutant 也在這裡再死一次：跳出迴圈之後 `## tail line` 從來沒被分類過，
    HEADING_2 那條 request 根本不存在。
    """
    _, requests, _ = with_tables

    assert of_kind(requests, "updateParagraphStyle") == [
        {"range": {"startIndex": 1, "endIndex": 10},
         "paragraphStyle": {"namedStyleType": "HEADING_1"}, "fields": "namedStyleType"},
        {"range": {"startIndex": 27, "endIndex": 37},
         "paragraphStyle": {"namedStyleType": "HEADING_2"}, "fields": "namedStyleType"},
    ]
    assert of_kind(requests, "createParagraphBullets") == [
        {"range": {"startIndex": 10, "endIndex": 27},
         "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"},
    ]


def test_cell_markup_does_not_leak_into_body_text_styles(with_tables):
    """`| A | **進行中** |` 裡的粗體是 **cell 的**，不是內文的。

    擋的是「表格那行也被丟去跑一次 inline 解析」：那會多送一條 bold request，
    range 指向內文裡毫不相干的位置，把隔壁的字加粗。
    內文唯一的粗體是 H1 整段那條（1–10，沿用段落 range，理由見上面那支測試）。
    """
    _, requests, _ = with_tables

    assert of_kind(requests, "updateTextStyle") == [
        {"range": {"startIndex": 1, "endIndex": 10},
         "textStyle": {"bold": True}, "fields": "bold"},
    ]


def test_table_corpus_can_tell_the_two_unit_systems_apart(with_tables):
    """語料的鑑別力本身：兩個 emoji 一個在表格 ① 之前、一個在表格 ② 之前，
    所以兩個插入 index 都分得出「UTF-16 code unit」與「Python 字元」。

    差距歸零代表有人把 emoji 從語料裡拿掉了，這時上面那些 index 就再也擋不住
    用 Python 字元算的寫法 —— 而測試會全綠。
    """
    text, _, _ = with_tables

    assert mod._u16len(text) - len(text) == 2

"""2026-08-31 把「解析粗體」與「解析 inline code」併成同一次掃描之後的回歸網。

那次改動只有 11 條 assert 驗過，而那 11 條隨 scratchpad 消失了。合併掃描會壞的地方
都在**兩種標記互相踩到**：一次掃描要同時記兩組 range，很容易讓 code 的 range 用剝掉
粗體標記**之前**的 offset、或讓 code 內容裡的 `**` 被當成真的粗體。

期望值一律從 Markdown 的語意推：code span 內的標記是字面值，沒有配對的標記也是字面值。
斷言用 `plain[start:end]` 取回內容再比對，不比對裸 offset —— 裸 offset 換一份語料就要
重算，而且錯了看不出是哪個標記算歪。

送進 Docs 的 index（UTF-16、1-based）不在這裡驗，在 `test_inline_style_requests.py`。
"""

from __future__ import annotations

import pytest

from tests.unit.conftest import _qid, load_script

mod = load_script("extract_audio_sources")


def spans(plain: str, ranges: list[tuple[int, int]]) -> list[str]:
    """把 range 換回它標到的那段文字 —— 斷言讀得懂，失敗訊息也讀得懂。"""
    return [plain[s:e] for s, e in ranges]


def overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return max(a[0], b[0]) < min(a[1], b[1])


# --------------------------------------------------------------------------
# 驗收 ① 粗體與 inline code 交錯
# --------------------------------------------------------------------------

INTERLEAVED = [
    # (markdown, plain, bold 標到的字, code 標到的字)
    ("**甲** 與 `乙` 混排", "甲 與 乙 混排", ["甲"], ["乙"]),
    ("`乙` 在前 **甲** 在後", "乙 在前 甲 在後", ["甲"], ["乙"]),
    ("**甲**與`乙`與**丙**與`丁`", "甲與乙與丙與丁", ["甲", "丙"], ["乙", "丁"]),
    ("前綴 **負責人** 狀態 `進行中` 後綴", "前綴 負責人 狀態 進行中 後綴", ["負責人"], ["進行中"]),
    ("`gcloud run deploy` 要先 **跑過一次**", "gcloud run deploy 要先 跑過一次", ["跑過一次"], ["gcloud run deploy"]),
]


@pytest.mark.parametrize(
    "raw,plain,bold_texts,code_texts", INTERLEAVED, ids=[_qid(r) for r, *_ in INTERLEAVED]
)
def test_interleaved_bold_and_code_keep_their_own_ranges(raw, plain, bold_texts, code_texts):
    """擋「一次掃描算出來的第二組 range 用了剝標記之前的 offset」。

    症狀是 Doc 裡樣式整段往右偏 —— 偏移量剛好等於前面被剝掉的標記字元數，
    所以只有**同一行同時有兩種標記**時才看得出來。單獨一種標記的行永遠是對的。
    """
    got_plain, bolds, codes = mod._parse_inline(raw)

    assert got_plain == plain
    assert spans(got_plain, bolds) == bold_texts
    assert spans(got_plain, codes) == code_texts


@pytest.mark.parametrize(
    "raw", [r for r, *_ in INTERLEAVED], ids=[_qid(r) for r, *_ in INTERLEAVED]
)
def test_bold_and_code_ranges_never_overlap(raw):
    """兩組 range 疊在一起代表同一段字被算了兩次樣式。

    跟上面那條分開：上面比對「標到什麼」，這條比對「兩組之間的關係」。
    兩組同時整體偏移同樣的量時，上面那條會紅、這條照樣綠；反過來一邊偏一邊沒偏時
    這條才是先紅的那個。
    """
    _, bolds, codes = mod._parse_inline(raw)

    clashes = [(b, c) for b in bolds for c in codes if overlaps(b, c)]
    assert clashes == []


# --------------------------------------------------------------------------
# 驗收 ② 惡意輸入：不 crash，也不吃掉半行
# --------------------------------------------------------------------------

HOSTILE = [
    # 沒有配對的 backtick：Markdown 語意是字面值，整行的字一個都不准掉
    ("狀態：`進行中", "狀態：`進行中", [], []),
    # 空的 code：兩個 backtick 相鄰，同樣沒有配對的收尾，仍是字面值
    ("這裡有 `` 空的", "這裡有 `` 空的", [], []),
    # code 內含粗體標記：code span 裡的 `**` 是字面值，不是粗體
    ("`**不是粗體**`", "**不是粗體**", [], ["**不是粗體**"]),
    # 粗體內含沒有配對的 backtick：backtick 是字面值，粗體照樣成立
    ("**A`B**", "A`B", ["A`B"], []),
    # 只有開頭的粗體標記
    ("**沒有收尾的粗體", "**沒有收尾的粗體", [], []),
    # 空字串與純標記
    ("", "", [], []),
    ("`", "`", [], []),
]


@pytest.mark.parametrize(
    "raw,plain,bold_texts,code_texts", HOSTILE, ids=[_qid(r) for r, *_ in HOSTILE]
)
def test_unpaired_markers_stay_literal_and_lose_no_text(raw, plain, bold_texts, code_texts):
    """擋「掃到一半找不到收尾就把剩下的行吞掉」。

    真實語料裡沒有配對的 backtick 很常見（agent 寫 `檔案.py 少打一個）。
    吞掉半行在 Doc 上看起來只是「這句話怪怪的」，不會有人聯想到解析器 ——
    所以要逐字比對整段 plain，不是只斷 `not None`。
    """
    got_plain, bolds, codes = mod._parse_inline(raw)

    assert got_plain == plain
    assert spans(got_plain, bolds) == bold_texts
    assert spans(got_plain, codes) == code_texts


@pytest.mark.parametrize(
    "raw,_p,_b,_c", HOSTILE, ids=[_qid(r) for r, *_ in HOSTILE]
)
def test_every_range_is_a_valid_slice_of_the_plain_text(raw, _p, _b, _c):
    """range 必須是 plain 的合法半開區間：0 <= start <= end <= len。

    越界或倒轉的 range 在 Python slice 上是靜靜地回空字串，上面那些比對照樣綠；
    但送進 Docs 會是 400，而且要到真的建 Doc 那一刻才看得到。
    """
    plain, bolds, codes = mod._parse_inline(raw)

    for start, end in [*bolds, *codes]:
        assert 0 <= start <= end <= len(plain), (start, end, plain)


# --------------------------------------------------------------------------
# 驗收 ③ 舊的「只取粗體」介面
# --------------------------------------------------------------------------

BOLD_ONLY = [
    ("**季度回顧**", "季度回顧", ["季度回顧"]),
    ("前綴 **重點** 後綴", "前綴 重點 後綴", ["重點"]),
    ("**甲** 和 **乙**", "甲 和 乙", ["甲", "乙"]),
    ("沒有粗體", "沒有粗體", []),
]


@pytest.mark.parametrize(
    "raw,plain,bold_texts", BOLD_ONLY, ids=[_qid(r) for r, *_ in BOLD_ONLY]
)
def test_bold_only_wrapper_behaves_exactly_as_before_the_merge(raw, plain, bold_texts):
    """表格 cell 唯一走的路徑。合併掃描不准改變它對「只有粗體」的輸入的輸出。

    硬編期望值而不是跟 `_parse_inline` 對照：對照版在兩支一起壞掉時是綠的，
    而表格是整份會議記錄裡最容易被忽略的區域（版型檢查器不看 cell 內容）。
    """
    got_plain, bolds = mod._parse_inline_bold(raw)

    assert got_plain == plain
    assert spans(got_plain, bolds) == bold_texts


WRAPPER_CORPUS = [r for r, *_ in INTERLEAVED] + [r for r, *_ in HOSTILE] + [r for r, *_ in BOLD_ONLY]


@pytest.mark.parametrize("raw", WRAPPER_CORPUS, ids=[_qid(r) for r in WRAPPER_CORPUS])
def test_wrapper_is_the_first_two_values_of_the_full_parser(raw):
    """介面說明寫的是「相容包裝，只取 bold ranges」—— 包裝就不准自己再解析一次。

    擋的是「有人為了修表格而在包裝裡加特例」：那會讓同一段字在內文與 cell 裡
    長得不一樣，而兩邊都沒有測試會紅。
    """
    plain, bolds, _ = mod._parse_inline(raw)

    assert mod._parse_inline_bold(raw) == (plain, bolds)


# --------------------------------------------------------------------------
# 驗收 ④ 行分類：四種行都要回完整的五個值
# --------------------------------------------------------------------------

LINES = [
    ("# 會議記錄", "heading", 1),
    ("## 二、討論事項", "heading", 2),
    ("#### 決議", "heading", 4),
    ("- 第一點", "bullet", 0),
    ("* 第一點", "bullet", 0),
    ("  - 子項目", "bullet", 2),
    ("---", None, None),
    ("這是一般段落", "normal", 0),
    ("", None, None),
]


@pytest.mark.parametrize("line,_k,_l", LINES, ids=[_qid(l) for l, *_ in LINES])
def test_every_kind_of_line_returns_all_five_values(line, _k, _l):
    """2026-08-31 把回傳值從四個改成五個；漏掉一條分支的症狀是 ValueError
    「not enough values to unpack」，而且只在那種行出現在記錄裡時才炸。

    分隔線與空行是最容易漏的兩條 —— 它們不帶任何 inline 樣式，寫的時候很容易
    早早 return 一個短 tuple。
    """
    kind, level, plain, bolds, codes = mod._classify_line(line)

    assert kind in {"heading", "bullet", "normal"}, kind
    assert isinstance(level, int)
    assert isinstance(plain, str)
    assert bolds == [] and codes == []


@pytest.mark.parametrize(
    "line,kind,level",
    [(l, k, v) for l, k, v in LINES if k is not None],
    ids=[_qid(l) for l, k, _ in LINES if k is not None],
)
def test_kind_and_level_match_the_markdown(line, kind, level):
    """heading 的 level 是井號數、bullet 的 level 是縮排空白數、normal 一律 0。

    三種 level 是三種不同的東西擠在同一個位置上，寫錯不會有人發現：
    heading 少算一層只是標題變小，bullet 縮排算錯只是縮排跑掉。
    """
    got_kind, got_level, *_ = mod._classify_line(line)

    assert (got_kind, got_level) == (kind, level)


def test_classify_line_carries_both_kinds_of_inline_ranges():
    """行分類不只是分類 —— 它同時是 inline 解析的入口。

    擋的是「合併掃描之後 bullet 那條分支只接了 bold，code 那組被丟掉」：
    這種 Doc 看起來完全正常，只是狀態字串沒有灰底。
    """
    kind, level, plain, bolds, codes = mod._classify_line("- 部署 `cloud run` 已 **完成**")

    assert (kind, level) == ("bullet", 0)
    assert plain == "部署 cloud run 已 完成"
    assert spans(plain, bolds) == ["完成"]
    assert spans(plain, codes) == ["cloud run"]


def test_heading_text_is_parsed_for_inline_styles_too():
    """標題行也會帶 inline code（版型裡的狀態字串出現在 H4 上過）。"""
    kind, level, plain, bolds, codes = mod._classify_line("### 進度 `blocked`")

    assert (kind, level) == ("heading", 3)
    assert plain == "進度 blocked"
    assert spans(plain, codes) == ["blocked"]

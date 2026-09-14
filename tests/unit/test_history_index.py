"""`scripts/history_index.py` 的黑箱測試 —— 只碰公開介面，不碰網路。

索引是**指標不是語料**：各場只留 heading 大綱＋「要全文去哪讀」，內容行一行都不進去。
所以這裡的斷言分兩種形狀：

- **抽取／邊界**（`outline` / `doc_url` / `find_notes` / `read_session`）用密封小語料，
  一條測試釘一個邊界。日期的 `>` vs `>=`、`limit` 的切法、`max_depth` 的 `<=` vs `<`
  是這支模組唯一會無聲壞掉的地方 —— 壞了的症狀是「agent 讀到自己的產出」或
  「大綱裡混進版型樣板那層」，兩者都不會讓任何流程報錯。
- **壓縮率／覆蓋率**（驗收條件 5、6）用 `corpus/` 底下的**真實正式稿**。
  四種會議的結構差很多（教授會議議題少、Data 內會十一個議題含 Heading 4 子層、
  RD 用 `1\\.` 編號、PM 完全沒有子層），**每份語料一組自己的斷言** ——
  一組斷言掃全部只驗得到最小公倍數。

`corpus/` 是從真實歸檔複製來的，**已去識別化**：heading 原樣保留（人名、客戶名換成
佔位符），其餘每一行換成同形狀的佔位行。行數、表格欄數、heading 階層都與原檔一致，
所以壓縮率的斷言仍然量的是真實體積。不從 `~/thoughts` 直接讀 —— 那條路徑只有一台
機器上存在。
"""

from __future__ import annotations

import inspect
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.unit.conftest import _qid, load_script

SCRIPTS = Path(__file__).resolve().parents[2] / "skills/comms/generate-meeting-notes/scripts"
sys.path.insert(0, str(SCRIPTS))

from local_archive import SIDECAR_SUFFIX  # noqa: E402

hi = load_script("history_index")

CORPUS = Path(__file__).parent / "corpus"
FOLDER = "週一週四_Data_內會"
SERIES = "Data內會"
URL = "https://docs.google.com/document/d/abc123/edit"


# --------------------------------------------------------------------------- helpers


def _note_name(series: str, date: str, suffix: str = "") -> str:
    return f"{hi.NOTE_PREFIX}_{series}_{date}{suffix}.md"


def _put(
    root: Path,
    date: str,
    text: str = "# 會議記錄\n",
    *,
    folder: str = FOLDER,
    name: str | None = None,
    doc_url: str | None = URL,
    sidecar: str | None = None,
) -> Path:
    """在歸檔樹裡放一份正式稿（＋側檔）。

    `doc_url=None` → 側檔整個不寫（側檔缺席）。`sidecar=` → 側檔寫成指定的原始字串
    （用來造壞掉的 JSON）。
    """
    directory = root / folder / date
    directory.mkdir(parents=True, exist_ok=True)
    note = directory / (name or _note_name(SERIES, date))
    note.write_text(text, encoding="utf-8")
    if sidecar is not None:
        _sidecar_of(note).write_text(sidecar, encoding="utf-8")
    elif doc_url is not None:
        _sidecar_of(note).write_text(
            json.dumps({"doc_url": doc_url}, ensure_ascii=False), encoding="utf-8"
        )
    return note


def _sidecar_of(note: Path) -> Path:
    """契約：正式稿檔名去掉 `.md` 再接 `SIDECAR_SUFFIX`。"""
    return note.with_name(note.name[: -len(".md")] + SIDECAR_SUFFIX)


def _unslash(text: str) -> str:
    """Google Doc 匯出的 `1\\.` 跳脫要不要還原，契約沒規定 —— 兩種都放行。

    釘的是「heading 有沒有被收進來」，不是反斜線政策。
    """
    return text.replace("\\", "")


def _headings(markdown: str, max_depth: int = 3) -> list[tuple[int, str]]:
    """語料自己的 heading 真值 —— 從原始 markdown 直接數，不經過受測模組。"""
    out = []
    for line in markdown.split("\n"):
        m = re.match(r"^(#{1,6}) (.*)$", line)
        if m and len(m.group(1)) <= max_depth:
            out.append((len(m.group(1)), m.group(2)))
    return out


def _content_lines(markdown: str) -> list[str]:
    """正式稿裡**不該**出現在索引中的行：非 heading、夠長到不會誤判的內容行。"""
    return [
        line.strip()
        for line in markdown.split("\n")
        if not re.match(r"^#{1,6} ", line) and len(line.strip()) >= 8
    ]


def _write_config(home: Path, archive_root: Path, meetings: dict) -> None:
    d = home / ".config" / "generate-meeting-notes"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.json").write_text(
        json.dumps(
            {"local_archive_root": str(archive_root), "meetings": meetings},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


# --------------------------------------------------------------------------- 常數


def test_documented_constants():
    """SKILL.md 與交棒契約照這些字面值走；打錯字的症狀是「索引產了但沒人找得到」。"""
    assert hi.INDEX_FILENAME == "history-index.md"
    assert hi.NOTE_PREFIX == "會議記錄"
    assert hi.DEFAULT_SESSIONS == 3
    assert hi.MAX_DEPTH == 3


# --------------------------------------------------------------------------- outline


LADDER = """# 一層

前言內容。

## 二層

* 一條內容行

### 三層

| 欄 | 值 |
| :---- | :---- |
| a | b |

#### 四層

內容。

##### 五層
"""


def test_outline_returns_headings_only_never_content():
    """驗收條件 2：索引只含 heading 大綱，不含任何內容行。"""
    got = hi.outline(LADDER)

    assert got == [(1, "一層"), (2, "二層"), (3, "三層")]


@pytest.mark.parametrize(
    "max_depth,expected",
    [
        (1, [(1, "一層")]),
        (2, [(1, "一層"), (2, "二層")]),
        (3, [(1, "一層"), (2, "二層"), (3, "三層")]),
        (4, [(1, "一層"), (2, "二層"), (3, "三層"), (4, "四層")]),
        (5, [(1, "一層"), (2, "二層"), (3, "三層"), (4, "四層"), (5, "五層")]),
    ],
    ids=["d1", "d2", "d3", "d4", "d5"],
)
def test_outline_max_depth_is_inclusive(max_depth, expected):
    """`max_depth` 那一層**要收**，深一層才不收。

    這條刪掉 → `<` 寫成 `<=`（或反過來）不會有人發現：大綱看起來仍然「有東西」，
    只是每一場都少一整層議題，或多出一層版型樣板（討論／狀態／風險），
    而那層的資訊量是零，只會把索引撐胖。
    """
    assert hi.outline(LADDER, max_depth) == expected


FENCED = """# 真 heading

```python
# 這是註解不是 heading
## 也不是
```

~~~
### 波浪圍欄裡的也不是
~~~

## 圍欄結束後的真 heading
"""


def test_outline_ignores_headings_inside_fenced_code_blocks():
    """圍欄裡的 `# 註解` 是程式碼不是 heading。

    這條刪掉 → 正式稿一貼 SQL／bash，索引就長出「-- 撈當日資料」這種假議題，
    agent 會以為那是上週談過的題目。兩種圍欄（``` 與 ~~~）各驗一次。
    """
    assert hi.outline(FENCED) == [(1, "真 heading"), (2, "圍欄結束後的真 heading")]


@pytest.mark.parametrize(
    "line,level,expected",
    [
        ("# **會議記錄：Data 內會**", 1, "會議記錄：Data 內會"),
        ("## 核心要點 **重點**", 2, "核心要點 重點"),
        ("### `history_index.py` 的介面", 3, "history_index.py 的介面"),
        ("## __雙底線粗體__ 也算粗體", 2, "雙底線粗體 也算粗體"),
        ("## 沒有任何標記", 2, "沒有任何標記"),
    ],
    ids=_qid,
)
def test_outline_strips_inline_markup_from_the_title(line, level, expected):
    """標題文字不帶行內標記 —— 索引是給人掃的，`**會議記錄：Data 內會**` 讀起來是雜訊。

    第一格就是真實語料的 H1 形狀（Google Doc 匯出一律把 H1 包粗體）。
    """
    assert hi.outline(line + "\n") == [(level, expected)]


# --------------------------------------------------------------------------- doc_url


def test_doc_url_reads_the_sidecar(tmp_path: Path):
    sidecar = tmp_path / "x.meta.json"
    sidecar.write_text(json.dumps({"doc_url": URL}), encoding="utf-8")

    assert hi.doc_url(sidecar) == URL


@pytest.mark.parametrize(
    "raw",
    [
        None,  # 側檔缺席
        "",  # 空檔
        "{",  # 壞掉的 JSON
        "{}",  # 沒有那個 key（`sidecar_content` 在沒 URL 時就是寫成這樣）
        '{"doc_url": null}',
        '{"doc_url": ""}',
        '{"doc_url": 123}',
        '{"doc_url": ["a"]}',
        '["not", "an", "object"]',
    ],
    ids=_qid,
)
def test_doc_url_degrades_to_none(tmp_path: Path, raw):
    """側檔缺席、壞掉、沒 key、值不是非空字串 —— 一律 None，不 raise。

    這條刪掉 → 歸檔早期那些沒有側檔的場次會讓整個索引流程掛掉，而流程 A/B 產不出
    source artifacts 的原因會是「一個歷史場次缺了一個附屬檔」。
    """
    sidecar = tmp_path / "x.meta.json"
    if raw is not None:
        sidecar.write_text(raw, encoding="utf-8")

    assert hi.doc_url(sidecar) is None


# --------------------------------------------------------------------------- find_notes


def test_find_notes_returns_oldest_first(tmp_path: Path):
    for date in ("20260821", "20260824", "20260831"):
        _put(tmp_path, date)

    got = hi.find_notes(tmp_path, FOLDER, "20260907")

    assert [p.parent.name for p in got] == ["20260821", "20260824", "20260831"]


def test_find_notes_excludes_the_current_date_itself(tmp_path: Path):
    """驗收條件 4：**嚴格早於** —— 同日的那場不算。

    這條刪掉 → `>` 寫成 `>=`，本次產的正式稿（重跑時已經在歸檔裡）會被收進自己的
    索引，agent 讀到自己上一版的產出再抄一次。這是整張票最貴的一種無聲錯誤。
    """
    _put(tmp_path, "20260824")
    _put(tmp_path, "20260831")

    got = hi.find_notes(tmp_path, FOLDER, "20260831")

    assert [p.parent.name for p in got] == ["20260824"]


def test_find_notes_excludes_later_dates(tmp_path: Path):
    """回頭補做舊場次時，歸檔裡已經有更晚的場次 —— 那些也不能進來。"""
    for date in ("20260821", "20260824", "20260831", "20260907"):
        _put(tmp_path, date)

    got = hi.find_notes(tmp_path, FOLDER, "20260825")

    assert [p.parent.name for p in got] == ["20260821", "20260824"]


@pytest.mark.parametrize(
    "limit,expected",
    [
        (1, ["20260831"]),
        (2, ["20260824", "20260831"]),
        (3, ["20260821", "20260824", "20260831"]),
        (10, ["20260713", "20260720", "20260821", "20260824", "20260831"]),
    ],
    ids=["limit1", "limit2", "limit3", "limit-over"],
)
def test_find_notes_takes_the_newest_limit_but_returns_them_oldest_first(
    tmp_path: Path, limit, expected
):
    """取的是**最近** limit 場，排序是由舊到新 —— 兩件事不同，切錯邊就拿到最舊的幾場。

    `limit=1` 那格是關鍵：切成 `[:limit]` 而不是 `[-limit:]` 時，唯一會露餡的就是它
    （其餘格數在小語料上兩種切法會撞在一起）。最後一格驗 limit 大於實際場數不會爆。
    """
    for date in ("20260713", "20260720", "20260821", "20260824", "20260831"):
        _put(tmp_path, date)

    got = hi.find_notes(tmp_path, FOLDER, "20260907", limit)

    assert [p.parent.name for p in got] == expected


def test_find_notes_zero_limit_returns_nothing(tmp_path: Path):
    """`limit=0` 是「一場都不要」，不是「不限制」。

    這條刪掉 → 切法從 `[-limit:]` 退化時 `limit=0` 會回**全部**場次（Python 的
    `xs[-0:]` 就是 `xs`）。症狀是呼叫端想關掉歷史卻拿到整個歸檔，而每一格正數 limit
    都還是對的，所以沒有別條測試會紅。
    """
    for date in ("20260821", "20260824", "20260831"):
        _put(tmp_path, date)

    assert hi.find_notes(tmp_path, FOLDER, "20260907", 0) == []


def test_find_notes_default_limit_is_three_sessions(tmp_path: Path):
    """預設值就是 `DEFAULT_SESSIONS`，不是「全部」也不是別的數字。"""
    for date in ("20260713", "20260720", "20260821", "20260824", "20260831"):
        _put(tmp_path, date)

    assert len(hi.find_notes(tmp_path, FOLDER, "20260907")) == hi.DEFAULT_SESSIONS


def test_find_notes_ignores_the_other_source_artifacts_in_the_same_folder(tmp_path: Path):
    """同一個日期資料夾裡還躺著 transcript／extract／meeting-context —— 只認正式稿。

    這條刪掉 → 近三場會被三個 source artifact 佔滿，索引裡是逐字稿的大綱，
    而逐字稿根本沒有議題 heading。
    """
    _put(tmp_path, "20260824")
    directory = tmp_path / FOLDER / "20260824"
    for junk in ("transcript.md", "extract.md", "meeting-context.md", "history-index.md"):
        (directory / junk).write_text("# 不是正式稿\n", encoding="utf-8")
    (directory / "備忘_Data內會_20260824.md").write_text("# 也不是\n", encoding="utf-8")

    got = hi.find_notes(tmp_path, FOLDER, "20260907")

    assert [p.name for p in got] == [_note_name(SERIES, "20260824")]


@pytest.mark.parametrize(
    "junk_dir",
    ["20260311（失敗）", "20260427 (1)", "2026-07-30_rd-meeting-sources", "備份", "2026083"],
    ids=_qid,
)
def test_find_notes_only_walks_eight_digit_date_folders(tmp_path: Path, junk_dir):
    """不是 8 位數字的資料夾名不算日期資料夾 —— 真實歸檔裡這四種形狀都存在。

    這條刪掉 → `20260311（失敗）` 這種手動標記的資料夾會被拿去跟 `before_date`
    比大小，比較結果無意義（字串比較下它大於 `20260311`），失敗的那場就混進索引。
    """
    _put(tmp_path, "20260824")
    _put(tmp_path, junk_dir, name=_note_name(SERIES, "20260311"))

    got = hi.find_notes(tmp_path, FOLDER, "20260907")

    assert [p.parent.name for p in got] == ["20260824"]


def test_find_notes_counts_notes_not_dates(tmp_path: Path):
    """「場」數的是正式稿份數 —— 同日多場次（`_am` / `_pm`）各算一場。

    真實歸檔裡 PM 會議 9/11 就是同日兩場。數日期的話近三場只會拿到兩場的內容。
    """
    _put(tmp_path, "20260911", name=_note_name("PM會議", "20260911", "_am"))
    _put(tmp_path, "20260911", name=_note_name("PM會議", "20260911", "_afternoon"))
    _put(tmp_path, "20260902", name=_note_name("PM會議", "20260902"))

    got = hi.find_notes(tmp_path, FOLDER, "20260918")

    assert len(got) == 3
    assert {p.name for p in got} >= {
        _note_name("PM會議", "20260911", "_am"),
        _note_name("PM會議", "20260911", "_afternoon"),
    }
    assert got[0].parent.name == "20260902", "由舊到新：9/02 那場排在 9/11 兩場之前"


def test_find_notes_skips_date_folders_with_no_note(tmp_path: Path):
    """只有 source artifacts、沒有正式稿的日期資料夾（發佈失敗的那種）直接跳過。"""
    _put(tmp_path, "20260824")
    empty = tmp_path / FOLDER / "20260830"
    empty.mkdir(parents=True)
    (empty / "transcript.md").write_text("# 逐字稿\n", encoding="utf-8")

    got = hi.find_notes(tmp_path, FOLDER, "20260907")

    assert [p.parent.name for p in got] == ["20260824"]


@pytest.mark.parametrize("missing", ["series", "root"], ids=["series-absent", "root-absent"])
def test_find_notes_returns_empty_when_the_series_folder_is_absent(tmp_path: Path, missing):
    """系列資料夾不存在時回空 list，不 raise —— 第一次用這個會議類型就是這個情形。"""
    root = tmp_path / "archive"
    if missing == "series":
        (root / "別的系列").mkdir(parents=True)

    assert hi.find_notes(root, FOLDER, "20260907") == []


# --------------------------------------------------------------------------- read_session


def test_read_session_carries_outline_path_and_url(tmp_path: Path):
    text = (CORPUS / "data-20260831.md").read_text(encoding="utf-8")
    note = _put(tmp_path, "20260831", text)

    session = hi.read_session(note, SERIES)

    assert session.note_path == note
    assert session.doc_url == URL
    assert [t for lvl, t in session.outline if lvl == 3] == DATA_20260831_ISSUES
    assert "20260831" in re.sub(r"\D", "", session.label), (
        "小標要認得出是哪一場 —— 日期是索引裡唯一能對回歸檔的線索"
    )


@pytest.mark.parametrize(
    "series,suffix,expected",
    [
        (SERIES, "", "20260824"),
        ("PM會議", "_am", "20260824_am"),
        ("PM會議", "_afternoon", "20260824_afternoon"),
    ],
    ids=["plain", "am", "afternoon"],
)
def test_read_session_label_is_the_filename_minus_the_series_prefix(
    tmp_path: Path, series, suffix, expected
):
    """小標 = 正式稿檔名去掉 `會議記錄_{series_name}_` 這個**前綴**之後剩下的。

    去頭與去尾在單場次上長得一樣（兩邊都「有變短」），但去尾拿到的是完整檔名 ——
    索引裡每一場的小標都變成 `會議記錄_PM會議_20260824_am` 這種長字串，同日多場次
    之間的差異被埋在最後兩個字元。這條的三格就是為了讓去頭與去尾分得開。
    """
    note = _put(tmp_path, "20260824", name=_note_name(series, "20260824", suffix))

    assert hi.read_session(note, series).label == expected


def test_read_session_finds_the_sidecar_by_the_documented_name(tmp_path: Path):
    """側檔檔名 = 正式稿檔名去掉 `.md` 再接 `SIDECAR_SUFFIX`。

    名字算錯的症狀是「每一場都沒有 URL」—— 索引照樣產得出來，只是指標少一半。
    """
    note = _put(tmp_path, "20260831", doc_url=None)
    _sidecar_of(note).write_text(json.dumps({"doc_url": URL}), encoding="utf-8")

    assert hi.read_session(note, SERIES).doc_url == URL
    assert _sidecar_of(note).name == f"{hi.NOTE_PREFIX}_{SERIES}_20260831{SIDECAR_SUFFIX}"


@pytest.mark.parametrize(
    "sidecar", [None, "{}", "not json"], ids=["absent", "no-key", "broken"]
)
def test_read_session_degrades_to_no_url(tmp_path: Path, sidecar):
    """驗收條件 7：缺側檔時降級 —— 大綱照抽，`doc_url` 是 None。"""
    note = _put(tmp_path, "20260831", "# 會議記錄\n\n## 核心要點\n", doc_url=None, sidecar=sidecar)

    session = hi.read_session(note, SERIES)

    assert session.doc_url is None
    assert session.outline, "沒有 URL 不影響大綱"


def test_read_session_raises_when_the_note_is_gone(tmp_path: Path):
    """正式稿讀不到是真的壞了 —— 這裡吞掉的話 `build_index` 沒辦法只跳過那一場。"""
    with pytest.raises(OSError):
        hi.read_session(tmp_path / "不存在.md", SERIES)


# --------------------------------------------------------------------------- render


def _session(tmp_path: Path, fixture: str, date: str, doc_url: str | None = URL):
    text = (CORPUS / fixture).read_text(encoding="utf-8")
    note = _put(tmp_path, date, text, doc_url=doc_url)
    return hi.read_session(note, SERIES)


def test_render_points_at_both_the_local_path_and_the_doc_url(tmp_path: Path):
    """驗收條件 3：指標同時給本機路徑與 Doc URL —— 索引的用途就是「要全文去哪讀」。"""
    session = _session(tmp_path, "data-20260831.md", "20260831")

    text = hi.render(SERIES, "20260907", [session])

    assert str(session.note_path) in text
    assert URL in text


def test_render_omits_the_url_field_instead_of_writing_none(tmp_path: Path):
    """驗收條件 3：缺 URL 時該欄位**缺席**，不寫 `None`。

    這條刪掉 → 索引裡出現 `Doc: None`，agent 會把它當成一個可用的值去打開。
    本機路徑仍然要在 —— 沒有 URL 不代表讀不到全文。
    """
    session = _session(tmp_path, "data-20260831.md", "20260831", doc_url=None)

    text = hi.render(SERIES, "20260907", [session])

    assert "None" not in text
    assert str(session.note_path) in text


def test_render_explains_itself_when_there_is_nothing_to_show():
    """沒有任何場次時要說明為什麼，不是留一份空白檔。

    空白檔在流程 C 那端分不出「沒有歷史」與「索引產壞了」，agent 只會去猜。
    """
    text = hi.render(SERIES, "20260907", [])

    assert len([line for line in text.split("\n") if line.strip()]) >= 2
    assert SERIES in text
    assert "20260907" in text, "說明裡要講清楚邊界切在哪一天，否則寫的是「沒有早於 None 的場次」"


def test_render_keeps_every_session_in_oldest_first_order(tmp_path: Path):
    """三場都要在，而且順序與 `find_notes` 交出來的一致（由舊到新）。

    這條刪掉 → `sessions[:1]`、`reversed(sessions)`、或漏掉最後一場都照樣綠：
    索引看起來完整（有大綱、有指標），只是少了兩場，或時間軸整個倒過來。
    後者特別惡劣 —— agent 判斷「延續自上次」時會挑到最舊的那場。
    """
    sessions = [
        _session(tmp_path, "data-20260821.md", "20260821"),
        _session(tmp_path, "data-20260824.md", "20260824"),
        _session(tmp_path, "data-20260831.md", "20260831"),
    ]

    text = hi.render(SERIES, "20260907", sessions)

    marks = ["議題七：客戶乙（成員壬 的需求）", "議題十一：客戶己廣告帳號資料只到 8/8（成員丙）",
             "議題七：AI 課程與客戶現場支援"]
    positions = [text.find(m) for m in marks]
    assert all(p >= 0 for p in positions), f"有場次沒被 render 出來：{marks}"
    assert positions == sorted(positions), "由舊到新"
    assert [text.find(str(s.note_path)) for s in sessions] == sorted(
        text.find(str(s.note_path)) for s in sessions
    ), "指標也要跟著各自那一場"


def test_render_keeps_the_headings_in_document_order(tmp_path: Path):
    """單一場之內，大綱的順序就是原稿的順序 —— 排序或去重都會讓議題對不回全文。"""
    session = _session(tmp_path, "pm-20260902.md", "20260902")

    text = hi.render(SERIES, "20260907", [session])

    positions = [text.find(t) for _, t in session.outline]
    assert all(p >= 0 for p in positions), "大綱每一項都要出現"
    assert positions == sorted(positions)


def test_render_gives_every_heading_its_own_line(tmp_path: Path):
    """大綱是逐行的清單，不是一段接起來的句子。

    這條刪掉 → 把換行接成空白（或反過來把每一項再拆行）都不會有人發現：
    `in text` 照樣成立，只是索引變成一坨，agent 掃不動。下界同時擋住「只印了前幾項」。
    """
    session = _session(tmp_path, "data-20260831.md", "20260831")

    lines = hi.render(SERIES, "20260907", [session]).split("\n")

    assert len(lines) >= len(session.outline)
    for _, title in session.outline:
        owners = [line for line in lines if title in line]
        assert len(owners) == 1, f"{title!r} 應該剛好佔一行，實際 {len(owners)} 行"


OUTLINE_LINE = re.compile(r"( *)- \S.*")


def _line_kind(line: str, series: str, before_date: str) -> str | None:
    """索引裡一行的合法形狀。認不出來就回 None —— 那就是垃圾行。

    寫成「配得到哪一種」而不是「不含某個字串」：後者是照著已知的壞輸出寫的，
    換一種垃圾就漏掉。
    """
    if line == "":
        return "blank"
    if line.startswith("# ") and series in line:
        return "title"
    if line.startswith("## "):
        return "session"
    if line.startswith("本機: "):
        return "local"
    if line.startswith("Doc: "):
        return "url"
    if OUTLINE_LINE.fullmatch(line):
        return "outline"
    if line in hi.INDEX_HEADER.split("\n"):
        return "header"
    if before_date in line:
        return "notice"  # 「近 N 場／早於 <日期>」與「沒有場次」那兩句都帶日期
    return None


def _assert_every_line_is_legal(text: str, series: str, before_date: str) -> set[str]:
    kinds = set()
    for i, line in enumerate(text.split("\n")[:-1]):  # 最後一格是結尾換行切出來的空字串
        kind = _line_kind(line, series, before_date)
        assert kind is not None, f"第 {i} 行不屬於任何一種合法行：{line!r}"
        kinds.add(kind)
    assert text.endswith("\n") and not text.endswith("\n\n"), "輸出以單一換行結尾"
    return kinds


@pytest.mark.parametrize(
    "fixture,date",
    [("data-20260831.md", "20260831"), ("prof-20260812.md", "20260812")],
    ids=_qid,
)
def test_render_emits_nothing_but_legal_lines(tmp_path: Path, fixture, date):
    """驗收條件 2 的另一面：索引裡不得有**憑空長出來**的行。

    `test_render_contains_no_content_line_from_the_notes` 掃的是「原稿的內容行有沒有
    洩進來」，掃不到索引自己長出來的垃圾 —— 空行位置變成一串字、行與行之間多塞東西、
    檔案結尾多一段。那些都讓 agent 讀到不是大綱也不是指標的東西，而行數與 heading
    覆蓋率全都還是對的。
    """
    session = _session(tmp_path, fixture, date)

    text = hi.render(SERIES, "20260907", [session])

    kinds = _assert_every_line_is_legal(text, SERIES, "20260907")
    assert kinds == {"blank", "title", "session", "local", "url", "outline", "header", "notice"}


def test_render_emits_nothing_but_legal_lines_when_empty():
    """沒有場次那條路徑是另一段程式碼，垃圾行也要分開擋一次。"""
    text = hi.render(SERIES, "20260907", [])

    kinds = _assert_every_line_is_legal(text, SERIES, "20260907")
    assert kinds == {"blank", "title", "header", "notice"}
    assert hi.EMPTY_NOTICE.format(before_date="20260907") in text


@pytest.mark.parametrize(
    "fixture,date",
    [("data-20260831.md", "20260831"), ("prof-20260812.md", "20260812"),
     ("pm-20260902.md", "20260902")],
    ids=_qid,
)
def test_render_starts_the_outline_at_column_zero(tmp_path: Path, fixture, date):
    """一場的大綱裡最淺的那一層不帶前導空白。

    相對關係由縮排那條守著，這條守絕對值：Markdown 裡 4 個以上的前導空白是
    **程式區塊**，不是清單。整塊往右位移之後索引仍然層級分明，只是 render 出來的是
    一段程式碼 —— 誰去 render 這份索引都看不到清單結構。
    """
    session = _session(tmp_path, fixture, date)

    text = hi.render(SERIES, "20260907", [session])

    indents = [
        len(m.group(1))
        for m in (OUTLINE_LINE.fullmatch(line) for line in text.split("\n"))
        if m
    ]
    assert indents, "大綱行都不見了"
    assert min(indents) == 0


@pytest.mark.parametrize(
    "fixture,date",
    [("data-20260831.md", "20260831"), ("prof-20260812.md", "20260812"),
     ("pm-20260902.md", "20260902")],
    ids=_qid,
)
def test_render_encodes_the_heading_level_as_indentation(tmp_path: Path, fixture, date):
    """大綱的**階層**要留在索引裡 —— 同一場裡層級每深一層，前導空白就多固定一格。

    #7 把索引定位成「未來議題關係圖的退化版」，退化版的最低要求就是結構化：
    議題掛在「討論過程」底下、收尾幾節掛在「腦力激盪與風險項目」底下。壓平之後索引
    仍然每一條 heading 都在、行數也沒變，只是十幾條並列成一張沒有父子的平表，
    agent 分不出「這是一場的標題」還是「這是其中一個議題」。

    斷言的是**相對關係**不是絕對縮排量（兩格還是四格是版面自由度），所以三份結構不同
    的語料共用同一組判準：每一層剛好一種縮排、逐層遞增、層級差 1 的縮排差固定。
    """
    session = _session(tmp_path, fixture, date)
    lines = hi.render(SERIES, "20260907", [session]).split("\n")

    indents: dict[int, set[int]] = {}
    for lvl, title in session.outline:
        owners = [line for line in lines if title in line]
        assert len(owners) == 1, f"{title!r} 應該剛好佔一行"
        indents.setdefault(lvl, set()).add(len(owners[0]) - len(owners[0].lstrip()))

    levels = sorted(indents)
    assert levels == [1, 2, 3]
    for lvl in levels:
        assert len(indents[lvl]) == 1, f"第 {lvl} 層的縮排不一致：{indents[lvl]}"

    one, two, three = (indents[lvl].pop() for lvl in levels)
    assert one < two < three, f"層級沒有反映在縮排上：{one}/{two}/{three}"
    assert two - one == three - two, f"層級差 1 的縮排差要固定：{one}/{two}/{three}"


def test_render_drops_only_the_missing_url_not_the_whole_session(tmp_path: Path):
    """三場裡有一場沒有側檔時，那場的大綱與本機路徑照樣在，只少了 URL 那個欄位。"""
    with_url = _session(tmp_path, "data-20260821.md", "20260821")
    without = _session(tmp_path, "data-20260824.md", "20260824", doc_url=None)

    text = hi.render(SERIES, "20260907", [with_url, without])

    assert "None" not in text
    assert text.count(URL) == 1
    assert str(without.note_path) in text
    assert "議題十一：客戶己廣告帳號資料只到 8/8（成員丙）" in text


def test_render_contains_no_content_line_from_the_notes(tmp_path: Path):
    """驗收條件 2，端到端那一版：整份索引裡不得出現正式稿的任何內容行。

    `outline` 那條測的是抽取，這條測的是 `render` 沒有在大綱之外偷渡摘要、TL;DR
    或第一段內文 —— 那正是「索引膨脹成語料」的起手式。
    """
    text = (CORPUS / "data-20260824.md").read_text(encoding="utf-8")
    session = _session(tmp_path, "data-20260824.md", "20260824")

    rendered = hi.render(SERIES, "20260907", [session])

    leaked = [line for line in _content_lines(text) if line in rendered]
    assert leaked == []


# --------------------------------------------------------------------------- 真實語料


DATA_20260831_ISSUES = [
    "議題一：客戶甲資料刪除與中繼表盤整",
    "議題二：對外／對業務的資料查詢已全面關閉",
    "議題三：MCP Server 部署與 PR 流程（成員甲）",
    "議題四：BQ 廣告受眾設定除錯（成員乙）",
    "議題五：客戶丙分析工具停用（成員丙）",
    "議題六：Google Ads 指標與週報自動化（成員丙）",
    "議題七：AI 課程與客戶現場支援",
]


def test_data_20260831_every_issue_heading_survives_and_no_template_layer_does():
    """驗收條件 6，Data 內會：七個議題一個不漏，而 Heading 4 的版型樣板一層都不進來。

    這一份是四種會議裡子層最完整的（每個議題底下都有 討論／決策理由／狀態／風險），
    所以它同時是「該收的全收」與「該擋的全擋」的樣本。
    """
    text = (CORPUS / "data-20260831.md").read_text(encoding="utf-8")

    got = hi.outline(text)

    assert [t for lvl, t in got if lvl == 3] == DATA_20260831_ISSUES
    assert [t for lvl, t in got if lvl == 2] == ["核心要點", "討論過程", "行動項目", "風險與未決項目"]
    assert [t for lvl, t in got if lvl == 1] == ["會議記錄：Data 內會"]
    assert max(lvl for lvl, _ in got) == 3


def test_data_20260831_depth_four_would_add_twenty_five_template_headings():
    """把 `max_depth` 放寬一層會多收進 25 個「討論／狀態／風險」—— 資訊量是零。

    這條在講預設值 3 的理由：同一份稿子 37 個 heading，其中 25 個是樣板。
    """
    text = (CORPUS / "data-20260831.md").read_text(encoding="utf-8")

    assert len(hi.outline(text, 3)) == 12
    assert len(hi.outline(text, 4)) == 37


def test_data_20260831_compresses_a_two_hundred_line_note_into_thirty(tmp_path: Path):
    """驗收條件 5：一場 200 行級的正式稿壓到 30 行內。"""
    source = (CORPUS / "data-20260831.md").read_text(encoding="utf-8")
    assert len(source.split("\n")) > 200, "樣本本身必須是 200 行級的，否則這條在量空氣"

    rendered = hi.render(SERIES, "20260907", [_session(tmp_path, "data-20260831.md", "20260831")])

    assert len(rendered.rstrip("\n").split("\n")) <= 30


def test_three_data_sessions_fit_in_one_hundred_lines(tmp_path: Path):
    """驗收條件 5 的另一半：近三場合計 100 行內。

    三場原始稿合計 572 行。索引要能整份被讀進 context 而不擠掉 transcript，
    這個上限就是它存在的理由。
    """
    fixtures = [
        ("data-20260821.md", "20260821"),
        ("data-20260824.md", "20260824"),
        ("data-20260831.md", "20260831"),
    ]
    total = sum(
        len((CORPUS / name).read_text(encoding="utf-8").split("\n")) for name, _ in fixtures
    )
    assert total > 500, "三份樣本合計要真的夠大"

    sessions = [_session(tmp_path, name, date) for name, date in fixtures]
    rendered = hi.render(SERIES, "20260907", sessions)

    assert len(rendered.rstrip("\n").split("\n")) <= 100


def test_data_20260824_keeps_all_eleven_issues_and_drops_the_sub_layers():
    """Data 內會的另一種形狀：十一個議題，子層是**臨時命名**的（「現況盤點」「提議與待決」
    「[否決] 全部功能塞進同一個 MCP」），不是固定樣板。照樣不收 —— 深度規則不看名字。
    """
    got = hi.outline((CORPUS / "data-20260824.md").read_text(encoding="utf-8"))

    issues = [t for lvl, t in got if lvl == 3]
    assert len(issues) == 11
    assert issues[0] == "議題一：客戶丁需求對焦（成員甲）"
    assert issues[-1] == "議題十一：客戶己廣告帳號資料只到 8/8（成員丙）"
    assert "[否決] 全部功能塞進同一個 MCP" not in [t for _, t in got]


def test_data_20260821_keeps_client_sub_headings_out_of_the_outline():
    """8/21 的議題二底下用 Heading 4 分客戶 —— 那是內容不是結構，不進大綱。"""
    got = hi.outline((CORPUS / "data-20260821.md").read_text(encoding="utf-8"))

    assert [t for lvl, t in got if lvl == 3] == [
        "議題一：客戶甲刪除佐證訊息的定稿（成員丁 主導，成員乙／成員丙 覆核）",
        "議題二：刪除期限前的現有報告分派",
        "議題三：SQL runner 的可交接性（成員甲）",
        "議題四：客戶甲客製化報告要不要繼續接（本次最大爭議）",
        "議題五：下週客戶甲 CM 部門新窗口",
        "議題六：未來新數據源（客戶庚、發票）必須設「有限客製空間」",
        "議題七：客戶乙（成員壬 的需求）",
    ]
    assert "客戶丁（[待確認] 正式客戶名以清單為準）" not in [t for _, t in got]
    assert got[0] == (1, "會議記錄：Data內會（客戶甲刪除佐證定稿與現有報告分派）")


def test_pm_20260902_is_flat_and_every_issue_comes_through():
    """PM 會議完全沒有 Heading 4 —— 十二個議題全部落在 H3，一個不漏。

    這一份是「拿 Data 內會的斷言掃全部」會驗不到的那一側：沒有子層可以擋，
    只剩「有沒有全收」。
    """
    got = hi.outline((CORPUS / "pm-20260902.md").read_text(encoding="utf-8"))

    issues = [t for lvl, t in got if lvl == 3]
    assert len(issues) == 12
    assert issues[0] == "議題一：Google Ads P1 欄位與 DXP 進度"
    assert issues[6] == "議題七：Pinterest / Unit 廣告帳號測試"
    assert issues[-1] == "議題十二：培訓課程與 FDE 的收單定位"
    assert len(got) == 17, "12 個議題 ＋ H1 ＋ 四個 H2，沒有別的"


def test_prof_20260812_keeps_numbered_h2_and_the_trailing_appendix():
    """教授會議：H2 帶 `1\\.` 編號、結尾多一節「附註：與歷史會議的關聯」。

    那一節正是這張票的來源 —— 以前靠人在正式稿裡手寫歷史關聯，現在改由索引供給。
    它必須留在大綱裡。
    """
    got = hi.outline((CORPUS / "prof-20260812.md").read_text(encoding="utf-8"))
    titles = [_unslash(t) for _, t in got]

    assert titles[0] == "會議記錄：Tagtoo 知識庫架構與教授論文對焦"
    assert titles[1:3] == ["1. 核心要點", "2. 討論過程"]
    assert titles[-1] == "附註：與歷史會議的關聯"
    assert len([t for lvl, t in got if lvl == 3]) == 13, "十個議題 ＋ 收尾那三節"
    assert "議題十：散會前的收尾" in titles


def test_rd_20260730_numbered_issue_headings_all_survive():
    """RD 會議的議題用 `1\\.` 編號而不是「議題一：」—— 大綱抽取不能認那個前綴。

    這條刪掉 → 有人把 heading 抽取寫成「只收開頭是『議題』的」，RD 整場的大綱會是空的，
    而索引仍然產得出來（只是每場都只剩核心要點與行動項目）。
    """
    got = hi.outline((CORPUS / "rd-20260730.md").read_text(encoding="utf-8"))
    titles = [_unslash(t) for lvl, t in got if lvl == 3]

    assert titles == [
        "1. 活動記錄與廣告數據 DB",
        "2. Dashboard 預算設計與廣告數據部署",
        "3. BigQuery MCP Server",
        "4. Skills over MCP 架構實驗",
        "5. PR 與 Ad Report 資料結構",
        "6. 客戶訪談、產品發表會與團隊分工",
    ]
    assert got[0] == (1, "RD 會議記錄"), "H1 的粗體要脫掉"


@pytest.mark.parametrize(
    "fixture",
    ["data-20260821.md", "data-20260824.md", "data-20260831.md", "pm-20260902.md",
     "prof-20260812.md", "rd-20260730.md"],
    ids=_qid,
)
def test_outline_never_invents_or_loses_a_heading(fixture):
    """六份真實正式稿的共同底線：大綱 == 原檔深度 3 以內的 heading，不多不少。

    上面每一份有自己的斷言（各會議結構不同）；這條只守「沒有任何一份掉東西或多東西」，
    以後新增語料照樣適用。文字比對容忍反斜線跳脫（契約沒規定要不要還原）。
    """
    text = (CORPUS / fixture).read_text(encoding="utf-8")

    got = [(lvl, _unslash(t)) for lvl, t in hi.outline(text)]
    expected = [
        (lvl, _unslash(t.replace("**", ""))) for lvl, t in _headings(text, hi.MAX_DEPTH)
    ]

    assert got == expected


# --------------------------------------------------------------------------- build_index


def test_build_index_writes_the_documented_filename(tmp_path: Path):
    """驗收條件 1：索引檔就叫 `INDEX_FILENAME`，寫在 source artifacts 目錄裡。"""
    root = tmp_path / "archive"
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    _put(root, "20260824", (CORPUS / "data-20260824.md").read_text(encoding="utf-8"))

    path = hi.build_index(source_dir, FOLDER, SERIES, "20260907", root=root)

    assert path == source_dir / hi.INDEX_FILENAME
    assert "議題一：客戶丁需求對焦（成員甲）" in path.read_text(encoding="utf-8")


def test_build_index_creates_the_output_directory_tree(tmp_path: Path):
    """`source_dir` 連上層都還不存在時要一路建出來。

    流程 A 的 source artifacts 目錄是
    `/tmp/meeting_sources/<key>_<date>[_<instance>]` —— 第一次跑某個會議時
    `/tmp/meeting_sources` 本身就不存在。這條刪掉 → 只有第一次跑會炸，而炸的訊息是
    `FileNotFoundError`，看起來像歸檔路徑設錯而不是輸出目錄沒建。
    """
    root = tmp_path / "archive"
    source_dir = tmp_path / "meeting_sources" / "data_20260907" / "巢狀"
    _put(root, "20260831", (CORPUS / "data-20260831.md").read_text(encoding="utf-8"))

    path = hi.build_index(source_dir, FOLDER, SERIES, "20260907", root=root)

    assert path == source_dir / hi.INDEX_FILENAME
    assert "議題七：AI 課程與客戶現場支援" in path.read_text(encoding="utf-8")


def test_build_index_rerun_overwrites_instead_of_failing(tmp_path: Path):
    """對同一個 `source_dir` 重跑是覆寫，不是報錯，也不是接在後面。

    重跑同一場發佈是常態（extract 被判不合格重試、多場次補跑）。這條刪掉 →
    第二次跑要嘛炸在「檔案已存在」，要嘛把兩份索引接成一份（agent 會讀到兩次大綱，
    以為同一個議題談過兩輪）。
    """
    root = tmp_path / "archive"
    source_dir = tmp_path / "sources"
    _put(root, "20260821", (CORPUS / "data-20260821.md").read_text(encoding="utf-8"))
    _put(root, "20260831", (CORPUS / "data-20260831.md").read_text(encoding="utf-8"))

    first = hi.build_index(source_dir, FOLDER, SERIES, "20260907", root=root, limit=2)
    before = first.read_text(encoding="utf-8")
    second = hi.build_index(source_dir, FOLDER, SERIES, "20260907", root=root, limit=1)
    after = second.read_text(encoding="utf-8")

    assert second == first
    assert after != before, "第二次的 limit 不同，內容就該不同 —— 相同表示根本沒重寫"
    assert after.count("議題七：AI 課程與客戶現場支援") == 1, "覆寫不是附加"
    assert "議題七：客戶乙（成員壬 的需求）" not in after


def test_build_index_passes_the_series_and_date_all_the_way_down(tmp_path: Path):
    """`build_index` 收到的 `series_name` 與 `before_date` 要真的傳到下游兩支。

    `render` 與 `read_session` 各自的測試都很密，但它們是**直接呼叫**的；中間那段
    「`build_index` 有沒有把對的東西傳下去」沒有人看。傳錯的症狀全都只出現在寫出去的
    那個檔裡，而檔案存在、是索引、大綱齊全這些都還是對的：

    - `series_name` 沒傳到 `render` → 標題變成「歷史會議索引：None」
    - `series_name` 沒傳到 `read_session` → 每場小標從 `20260824_am` 退化成完整檔名
    - `before_date` 沒傳到 `render` → 「全部早於 None」

    同日兩場（`_am` / `_pm`）是第三條的鑑別力來源：只有前綴真的被拿掉，兩場的小標才
    短到能一眼分辨；退化成完整檔名時差異被埋在最後三個字元。
    """
    root = tmp_path / "archive"
    source_dir = tmp_path / "sources"
    for date, suffix in [("20260821", ""), ("20260824", "_am"), ("20260824", "_pm")]:
        _put(root, date, "# 會議記錄\n\n## 核心要點\n", name=_note_name(SERIES, date, suffix))

    text = hi.build_index(source_dir, FOLDER, SERIES, "20260907", root=root).read_text(
        encoding="utf-8"
    )
    lines = text.split("\n")

    titles = [line for line in lines if line.startswith("# ")]
    assert len(titles) == 1 and SERIES in titles[0]

    notices = [line for line in lines if "20260907" in line and not line.startswith("## ")]
    assert notices, "「近 N 場／日期上限」那行要帶得到 before_date"

    labels = sorted(line[len("## "):] for line in lines if line.startswith("## "))
    assert labels == ["20260821", "20260824_am", "20260824_pm"]


def test_build_index_skips_only_the_broken_session(tmp_path: Path):
    """驗收條件 7：單一份正式稿讀不進來時只跳過那一場，整個流程不掛。

    這條刪掉 → 歸檔裡一份壞檔就讓流程 A/B 整段失敗，而失敗點離原因十萬八千里。
    壞法用非 UTF-8 位元組（真實情境是同步中斷寫了半個檔）。
    """
    root = tmp_path / "archive"
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    _put(root, "20260821", (CORPUS / "data-20260821.md").read_text(encoding="utf-8"))
    broken = _put(root, "20260824")
    broken.write_bytes(b"\xff\xfe\x00# \xc3(")
    _put(root, "20260831", (CORPUS / "data-20260831.md").read_text(encoding="utf-8"))

    text = hi.build_index(source_dir, FOLDER, SERIES, "20260907", root=root).read_text(
        encoding="utf-8"
    )

    assert "議題七：客戶乙（成員壬 的需求）" in text
    assert "議題七：AI 課程與客戶現場支援" in text


def test_build_index_writes_an_index_even_with_no_history(tmp_path: Path):
    """歸檔裡沒有更早的場次是合法結果 —— 照樣寫出檔案（SKILL.md 明文）。"""
    source_dir = tmp_path / "sources"
    source_dir.mkdir()

    path = hi.build_index(source_dir, FOLDER, SERIES, "20260907", root=tmp_path / "空的")

    assert path.is_file()
    assert path.read_text(encoding="utf-8").strip()


def test_build_index_honours_the_session_limit(tmp_path: Path):
    root = tmp_path / "archive"
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    for name, date in [
        ("data-20260821.md", "20260821"),
        ("data-20260824.md", "20260824"),
        ("data-20260831.md", "20260831"),
    ]:
        _put(root, date, (CORPUS / name).read_text(encoding="utf-8"))

    text = hi.build_index(source_dir, FOLDER, SERIES, "20260907", root=root, limit=1).read_text(
        encoding="utf-8"
    )

    assert "議題七：AI 課程與客戶現場支援" in text, "留下的要是最近那場（8/31）"
    assert "議題七：客戶乙（成員壬 的需求）" not in text


# --------------------------------------------------------------------------- CLI（Seam ③）


def _run_cli(home: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "history_index.py"), *args],
        capture_output=True,
        text=True,
        env={"HOME": str(home), "PATH": "/usr/bin:/bin", "LC_ALL": "en_US.UTF-8"},
    )


@pytest.fixture
def cli_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    archive = tmp_path / "archive"
    _write_config(
        home,
        archive,
        {"data": {"series_name": SERIES, "folder_name": FOLDER, "folder_id": "x", "attendees": []}},
    )
    _put(archive, "20260831", (CORPUS / "data-20260831.md").read_text(encoding="utf-8"))
    return home


def test_cli_prints_the_handoff_line_and_writes_that_exact_file(cli_home: Path, tmp_path: Path):
    """驗收條件 1 的交棒契約那一半：stdout 印 `RESULT_HISTORY_INDEX: <路徑>`。

    斷言打在「印出來的那個路徑真的是寫出去的那個檔」—— 只驗檔案存在的話，
    印錯路徑（例如印成 source_dir 本身）照樣綠，而流程 C 只吃 stdout。
    根目錄走 config 的 `local_archive_root`，不另外給 `--root`。
    """
    source_dir = tmp_path / "sources"
    source_dir.mkdir()

    proc = _run_cli(
        cli_home, "--meeting", "data", "--date", "20260907", "--output-dir", str(source_dir)
    )

    assert proc.returncode == 0, proc.stderr
    lines = [l for l in proc.stdout.splitlines() if l.startswith("RESULT_HISTORY_INDEX: ")]
    assert len(lines) == 1, proc.stdout
    path = Path(lines[0].split(": ", 1)[1])
    assert path == source_dir / hi.INDEX_FILENAME
    assert "議題七：AI 課程與客戶現場支援" in path.read_text(encoding="utf-8")


def test_cli_root_flag_overrides_the_configured_archive(cli_home: Path, tmp_path: Path):
    """`--root` 指到別的歸檔樹時，索引就該是那棵樹的內容。"""
    source_dir = tmp_path / "sources2"
    source_dir.mkdir()
    other = tmp_path / "other"
    _put(other, "20260821", (CORPUS / "data-20260821.md").read_text(encoding="utf-8"))

    proc = _run_cli(
        cli_home, "--meeting", "data", "--date", "20260907",
        "--output-dir", str(source_dir), "--root", str(other), "--sessions", "1",
    )

    assert proc.returncode == 0, proc.stderr
    text = (source_dir / hi.INDEX_FILENAME).read_text(encoding="utf-8")
    assert "議題七：客戶乙（成員壬 的需求）" in text
    assert "議題七：AI 課程與客戶現場支援" not in text


@pytest.mark.parametrize(
    "date,ok",
    [
        ("20260914", True),
        ("2026-09-14", False),
        ("2026/09/14", False),
        ("abc", False),
        ("202609141", False),
        ("2026091", False),
        ("", False),
    ],
    ids=_qid,
)
def test_cli_requires_an_eight_digit_date(cli_home: Path, tmp_path: Path, date, ok):
    """`--date` 不是 8 位數字就 exit 2，而且什麼都不產。

    日期比較是字串比較，所以 `2026-09-14` 不會報錯，它會讓**每一場**都被判成
    「本次或之後」（`'0' > '-'`）而排掉：索引靜靜寫成空檔、exit 0、契約行照印。
    下游流程 C 讀到的是一份合法但空的索引，沒有任何訊號說參數給錯了 —— 人會去 debug
    索引內容，病其實在參數。所以這裡要一次釘三件事：退出碼、不留半成品、不印契約行。

    第一格是對照組：合法日期照樣 exit 0 並產檔，免得 guard 寫成「全部擋掉」也綠。
    """
    source_dir = tmp_path / f"sources-{date or 'empty'}".replace("/", "-")
    source_dir.mkdir()

    proc = _run_cli(
        cli_home, "--meeting", "data", "--date", date, "--output-dir", str(source_dir)
    )
    index = source_dir / hi.INDEX_FILENAME

    if ok:
        assert proc.returncode == 0, proc.stderr
        assert index.is_file()
        assert f"RESULT_HISTORY_INDEX: {index}" in proc.stdout
    else:
        assert proc.returncode == 2, proc.stdout + proc.stderr
        assert not index.exists(), "參數錯誤時不該留下一份空索引"
        assert "RESULT_HISTORY_INDEX" not in proc.stdout


def test_cli_exits_two_on_an_unknown_meeting_key(cli_home: Path, tmp_path: Path):
    """config 沒有那個會議 → exit 2，而且不要留下一份空索引讓下游以為成功。"""
    source_dir = tmp_path / "sources3"
    source_dir.mkdir()

    proc = _run_cli(
        cli_home, "--meeting", "no_such_meeting", "--date", "20260907",
        "--output-dir", str(source_dir),
    )

    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert not (source_dir / hi.INDEX_FILENAME).exists()
    assert "RESULT_HISTORY_INDEX" not in proc.stdout


# --------------------------------------------------------------------------- 流程 B（Seam ③）

CONTRACT_KEYS = {"SOURCE_DIR", "TRANSCRIPT", "EXTRACT", "CONTEXT", "DATE", "HISTORY_INDEX"}


def test_flow_b_wires_the_index_builder_in():
    """流程 B 自己產索引，不必 agent 另外跑一次 `history_index.py`（SKILL.md 明文）。

    驗的是模組屬性而不是原始碼字串：`import history_index` 與
    `from history_index import build_index` 兩種寫法都算數，改名或拿掉就抓得到。
    `extract_audio_sources.main()` 是 async 又會打 NotebookLM，這裡不跑它。
    """
    module = load_script("extract_audio_sources")

    assert hasattr(module, "build_index") or hasattr(module, "history_index")


TRANSCRIPT = "# 逐字稿\n\nSpeaker 1：這是本次會議的事實。\n"
EXTRACT = (
    "# 議題\n\n* 議題一：索引接上流程 B\n\n# 決策\n\n* 決策一：交棒契約多一行\n\n"
    "# 行動項目\n\n* 行動一：補測試\n\n# 風險\n\n* 風險一：值印錯沒人發現\n"
)


@pytest.fixture
def flow_b(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    """跑一次流程 B 的 `main()`，回傳 (RESULT_* 的 dict, 索引實際被寫到哪)。

    只有外部相依換成替身（config、音訊切分、NotebookLM、glossary、片段清理）；
    `build_index` 包一層 spy **轉呼真貨**並強制 `root=tmp_path`，所以索引是真的產出來的，
    同時不會去讀使用者真實的歸檔樹。`main()` 的組裝邏輯全部走真的那條路。
    """
    module = load_script("extract_audio_sources")
    archive = tmp_path / "archive"
    source_dir = tmp_path / "sources"
    audio = tmp_path / "data_meeting_20260907.m4a"
    audio.write_bytes(b"not really audio")
    _put(archive, "20260831", (CORPUS / "data-20260831.md").read_text(encoding="utf-8"))

    meeting = {
        "series_name": SERIES,
        "folder_name": FOLDER,
        "folder_id": "series-folder-id",
        "notebook_name": "notebook",
        "slack_channel": "",
        "attendees": [],
    }
    monkeypatch.setattr(module, "load_config", lambda: {"meetings": {"data": meeting}})
    monkeypatch.setattr(module, "load_glossary_entries", lambda *a, **kw: ([], None))
    monkeypatch.setattr(module, "fetch_shared_glossary", lambda *a, **kw: (None, "略過"))
    monkeypatch.setattr(module, "build_glossary_prompt", lambda *a, **kw: "")
    monkeypatch.setattr(module, "load_prompt", lambda *a, **kw: "prompt")
    monkeypatch.setattr(module, "build_meeting_context_markdown", lambda *a, **kw: "# 會議脈絡\n")
    monkeypatch.setattr(module, "get_audio_duration_seconds", lambda *a, **kw: 600.0)
    monkeypatch.setattr(module, "split_audio", lambda *a, **kw: [audio])
    monkeypatch.setattr(module, "cleanup_segments", lambda *a, **kw: None)

    async def fake_upload(*a, **kw):
        return TRANSCRIPT, EXTRACT

    monkeypatch.setattr(module, "upload_and_extract_sources", fake_upload)

    built: list[Path] = []
    real_build = module.build_index

    def spy(*args, **kwargs):
        kwargs["root"] = archive
        path = real_build(*args, **kwargs)
        built.append(path)
        return path

    monkeypatch.setattr(module, "build_index", spy)

    import asyncio

    asyncio.run(
        module.main(str(audio), "data", delete_segments=True, output_dir=str(source_dir))
    )

    results = {
        line.split(": ", 1)[0]: line.split(": ", 1)[1]
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("RESULT_") and ": " in line
    }
    assert built, "流程 B 應該自己產索引"
    return results, built[-1]


def test_flow_b_stdout_value_is_the_index_file_that_was_actually_written(flow_b):
    """交棒契約印出去的**值**必須是那次真的寫出來的索引檔。

    這條刪掉 → 那一行印成 source artifacts 目錄（或 transcript、或別場的索引）都照樣綠：
    行在、值有內插、檔案系統上也真的有東西。下游流程 C 只吃 stdout，拿這個值去
    `read_text()` 會拿到一個目錄。Seam ③ 的斷言要打在送出去的**值**上，不是那行的存在。
    """
    results, written = flow_b

    assert results["RESULT_HISTORY_INDEX"] == str(written)
    assert Path(results["RESULT_HISTORY_INDEX"]).is_file()
    assert results["RESULT_HISTORY_INDEX"] != results["RESULT_SOURCE_DIR"]
    assert Path(results["RESULT_HISTORY_INDEX"]).name == hi.INDEX_FILENAME


def test_flow_b_index_holds_the_outline_not_this_meetings_sources(flow_b):
    """印出去的那個檔內容真的是索引：歷史場次的大綱在，本次的逐字稿與 extract 不在。

    只斷言「檔案存在」的話，把值指到 `transcript.md` 也會綠 —— 而那正是流程 C 最不該
    當成歷史來讀的東西（本次事實混進歷史欄位，接地優先序整個倒過來）。
    """
    results, _ = flow_b
    text = Path(results["RESULT_HISTORY_INDEX"]).read_text(encoding="utf-8")

    assert hi.INDEX_HEADER.split("\n")[0] in text
    assert "議題七：AI 課程與客戶現場支援" in text, "8/31 那場的大綱要在"
    assert "Speaker 1" not in text and "議題一：索引接上流程 B" not in text


def test_flow_b_hands_off_the_index_path_on_stdout():
    """交棒契約多的那一行必須跟其餘五行印在同一段，而且值是算出來的不是寫死的。

    `main()` 打 NotebookLM，所以這條驗的是**印出去的那段文字**本身；那一行的值正不正確
    由上面 CLI 那三條守著（同一個 `build_index` 回傳值）。
    """
    source = inspect.getsource(load_script("extract_audio_sources"))
    printed = set(re.findall(r"RESULT_([A-Z_]+):", source))

    assert CONTRACT_KEYS <= printed, f"少了 {CONTRACT_KEYS - printed}"
    assert re.search(r"RESULT_HISTORY_INDEX:\s*\{", source), "值要內插，不能是寫死的字面路徑"

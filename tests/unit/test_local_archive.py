"""`scripts/local_archive.py` 的黑箱測試 —— 只碰公開介面，不碰網路。

**每條測試都必須傳 `root=tmp_path`。** 不傳的話預設是 `LOCAL_ARCHIVE_ROOT`，
那指向使用者真實的筆記樹，測試跑一次就污染一次。`write_local_archive`
有 `root=` 參數就是為了這件事。

側檔的 JSON 形狀（`ensure_ascii=False` ＋ `indent=2` ＋ 結尾換行）被 #7 的歷史索引
讀，所以下面用**逐字比對整個字串**，不是 `json.loads` 後比 dict —— 後者對縮排與
跳脫完全無感，形狀漂掉也照樣綠。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.unit.conftest import load_script

# **一定要走 `load_script`**，不能 `sys.path.insert` ＋ `import local_archive`：
# mutmut 的 mutant key 是從檔案路徑算的（`skills.comms.….local_archive.x_<函式>`），
# 而 trampoline 記的是模組的 `__name__`。裸名 import 記成 `local_archive.x_<函式>`，
# 兩邊對不上 —— 症狀是這支模組的每顆 mutant 都變成 🫥 no-tests，而測試全綠。
_la = load_script("local_archive")

DATE_DIR_EXAMPLE = _la.DATE_DIR_EXAMPLE
DATE_DIR_SHAPES = _la.DATE_DIR_SHAPES
DEFAULT_ARCHIVE_DIRNAME = _la.DEFAULT_ARCHIVE_DIRNAME
INSTANCE_ORDER = _la.INSTANCE_ORDER
SIDECAR_SUFFIX = _la.SIDECAR_SUFFIX
_configured_root = _la._configured_root
archive_paths = _la.archive_paths
clean_for_filename = _la.clean_for_filename
date_dir_name = _la.date_dir_name
instance_order_key = _la.instance_order_key
instance_rank = _la.instance_rank
note_instance = _la.note_instance
note_title = _la.note_title
parse_date_dir = _la.parse_date_dir
sidecar_content = _la.sidecar_content
write_local_archive = _la.write_local_archive

NOTE = "# 會議記錄\n\n中文內容，結尾沒有多餘換行"


def test_sidecar_suffix_is_the_documented_constant():
    """#7 的索引照這個副檔名去找側檔。打錯字的症狀是「歸檔成功但沒人找得到」。"""
    assert SIDECAR_SUFFIX == ".meta.json"


def _write_config(home: Path, **keys) -> None:
    d = home / ".config" / "generate-meeting-notes"
    d.mkdir(parents=True)
    (d / "config.json").write_text(json.dumps(keys, ensure_ascii=False), encoding="utf-8")


@pytest.mark.parametrize(
    "setup,expected",
    [
        (lambda h: _write_config(h, local_archive_root=str(h / "notes")), "configured"),
        (lambda h: _write_config(h), "default"),
        (lambda h: None, "default"),
    ],
    ids=["configured", "key-absent", "no-config-file"],
)
def test_archive_root_comes_from_config_never_from_a_hardcoded_personal_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, setup, expected
):
    """歸檔根目錄必須由設定決定。

    刪掉這條 → 有人把自己的筆記路徑寫回模組常數，這支公開 skill 就又把個人路徑
    烘進程式碼；別人裝了會寫進一個不屬於他的目錄，而 guard 只擋得到文件裡的字面路徑。
    三格分別是「有設定」「有檔沒 key」「連檔都沒有」，後兩者都要退回預設。
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    setup(tmp_path)

    root = _configured_root()

    if expected == "configured":
        assert root == tmp_path / "notes"
    else:
        assert root == tmp_path / DEFAULT_ARCHIVE_DIRNAME


def test_archive_paths_assembles_only_and_touches_no_filesystem(tmp_path: Path):
    note, sidecar = archive_paths("週四_RD_會議", "20260521", "會議記錄_RD會議_20260521", root=tmp_path)

    assert note == tmp_path / "週四_RD_會議/20260521/會議記錄_RD會議_20260521.md"
    assert sidecar == tmp_path / "週四_RD_會議/20260521/會議記錄_RD會議_20260521.meta.json"
    assert list(tmp_path.iterdir()) == []


def test_archive_paths_uses_date_verbatim_as_the_directory_name(tmp_path: Path):
    """`date` 沒有格式驗證，也**不該**有 —— 但要確定它不會被剖析或正規化。

    真實資料裡有 `20260521_pc` 這種資料夾（識別碼跑到資料夾名上）。本票定的形狀是
    識別碼進檔名、日期資料夾就是日期，這條釘住「傳什麼就是什麼」，讓那種歷史遺留在
    路徑層可重現而不是被悄悄改寫成別的目錄。
    """
    note, _ = archive_paths("週四_RD_會議", "20260521_pc", "T", root=tmp_path)
    assert note.parent == tmp_path / "週四_RD_會議/20260521_pc"


def test_archive_paths_sanitizes_the_title_so_it_cannot_pick_its_own_directory(tmp_path: Path):
    """補齊腳本餵進來的 `title` 是 Drive 上的 Doc 名，而 Drive 允許 `/`。

    不清洗的症狀不是報錯，是檔案安靜地落在別的目錄裡（`mkdir(parents=True)` 會順手
    幫它把目錄建出來），然後 #7 的索引在該在的地方找不到它。
    """
    note, sidecar = archive_paths("週四_RD_會議", "20260521", "會議記錄_RD會議/草稿", root=tmp_path)

    assert note.parent == tmp_path / "週四_RD_會議/20260521"
    assert note.name == "會議記錄_RD會議-草稿.md"
    assert sidecar.name == "會議記錄_RD會議-草稿.meta.json"


def test_write_local_archive_writes_note_and_sidecar(tmp_path: Path):
    url = "https://docs.google.com/document/d/abc123/edit"

    note, sidecar = write_local_archive(
        "週三_PM_會議", "20260708", "會議記錄_PM會議_20260708_pm", NOTE, doc_url=url, root=tmp_path
    )

    assert (note, sidecar) == archive_paths(
        "週三_PM_會議", "20260708", "會議記錄_PM會議_20260708_pm", root=tmp_path
    )
    assert note.read_text(encoding="utf-8") == NOTE
    assert json.loads(sidecar.read_text(encoding="utf-8")) == {"doc_url": url}


def test_write_local_archive_overwrites_and_clears_the_url(tmp_path: Path):
    """覆寫是明訂語意，這條釘住它的代價：重跑發佈會把本機已修訂的正式稿蓋掉，
    而且沒帶 `doc_url` 的那次會把側檔清成 `{}` —— URL 是發佈當下唯一拿得到的東西。
    """
    args = ("週三_PM_會議", "20260708", "會議記錄_PM會議_20260708")
    note, sidecar = write_local_archive(*args, "第一版", doc_url="https://x", root=tmp_path)

    write_local_archive(*args, "第二版", root=tmp_path)

    assert note.read_text(encoding="utf-8") == "第二版"
    assert sidecar.read_text(encoding="utf-8") == "{}\n"


def test_sidecar_json_shape_is_indent2_utf8_and_trailing_newline(tmp_path: Path):
    assert sidecar_content("https://x") == '{\n  "doc_url": "https://x"\n}\n'
    # ensure_ascii=False：非 ASCII 原樣落地，不是 \uXXXX。
    assert "會議" in sidecar_content("https://docs.google.com/會議")


@pytest.mark.parametrize("doc_url", [None, ""], ids=["none", "empty-str"])
def test_missing_url_omits_the_field_instead_of_writing_null(doc_url):
    """`{"doc_url": null}` 會讓下游 agent 以為那是可用的值。空字串與 None 同一路。"""
    assert sidecar_content(doc_url) == "{}\n"


@pytest.mark.parametrize(
    ("suffix", "expected"),
    [
        (None, "會議記錄_PM會議_20260708"),
        ("   ", "會議記錄_PM會議_20260708"),
        (":::", "會議記錄_PM會議_20260708"),
        ("a/b", "會議記錄_PM會議_20260708_a-b"),
    ],
    ids=["none", "blank", "all-illegal", "cleaned"],
)
def test_note_title(suffix, expected):
    """標題不含副檔名，短識別碼清洗後非空才接上去 —— 空的時候不能留一條裸底線。"""
    assert note_title("PM會議", "20260708", suffix) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("第二場", "第二場"),
        (r'a\/:*?"<>|b', "a-b"),
        ("a?b*c", "a-b-c"),
        (" -pm_ ", "pm"),
        (None, ""),
    ],
    ids=["cjk", "all-illegal-chars", "two-groups", "trim", "none"],
)
def test_clean_for_filename(raw, expected):
    """連續非法字元收成單一 `-`，頭尾的空白／`-`／`_` 去掉。`第二場` 那條擋住
    「順手把非 ASCII 也清掉」—— 繁中識別碼是合法檔名。
    """
    assert clean_for_filename(raw) == expected


# ------------------------------------------- 同日多場的共用詞彙（#56 / #53）
#
# 四支腳本吃這幾個函式：掃描層（`reconcile_drive`）、歷史索引（`history_index`）、
# 補齊（`backfill_local_archive`）與發佈層（`create_gdoc_in_shared_drive`）。
# 各抄一份的話版面改了只會改到其中一份，而症狀是「那一場永遠掃不到」或「索引順序反了」。


DATE_DIRS = [
    ("20260916", ("20260916", "")),
    ("20260916_am", ("20260916", "am")),
    ("20260916_project-x", ("20260916", "project-x")),
    ("20260916_part1_combined", ("20260916", "part1_combined")),
]
NOT_DATE_DIRS = ["20260916_", "2026091", "202609161", "9月16日下午", "備份", "", "_am"]


@pytest.mark.parametrize("name,expected", DATE_DIRS, ids=[n for n, _ in DATE_DIRS])
def test_parse_date_dir_splits_the_date_from_the_session(name, expected):
    assert parse_date_dir(name) == expected


@pytest.mark.parametrize("name", NOT_DATE_DIRS, ids=[repr(n) for n in NOT_DATE_DIRS])
def test_parse_date_dir_returns_none_for_a_name_it_cannot_read(name):
    """回 `None` 而不是 `("", "")` —— 掃描層要據此發提醒，兩者不能壓成同一個值。

    `20260916_` 那格是邊界：後綴是空的，形狀上不合法（`_` 後面什麼都沒有），
    `(.+)` 認不得它。認成 `("20260916", "")` 的話會產出 `會議記錄_X_20260916_`。
    """
    assert parse_date_dir(name) is None


NOTE_STEMS = [
    ("會議記錄_PM會議_20260911_am", "am"),
    ("會議記錄_PM會議_20260911_afternoon", "afternoon"),
    ("會議記錄_PM會議_20260911", ""),
    ("會議記錄_PM會議_20260911_part1_combined", "part1_combined"),
    # 系列名自己含 8 位數字：右錨定才不會抽到 `預算會_20260911` 這種半個系列名。
    ("會議記錄_20260101預算會_20260911_pm", "pm"),
    ("會議記錄_沒有日期的檔名", ""),
]


@pytest.mark.parametrize("stem,expected", NOTE_STEMS, ids=[s for s, _ in NOTE_STEMS])
def test_note_instance_reads_the_suffix_off_the_tail_of_the_filename(stem, expected):
    assert note_instance(stem) == expected


def test_instance_rank_orders_the_known_suffixes_by_time_of_day():
    """`am` 在 `afternoon` 之前 —— 字母序剛好是反的（`af` < `am`），而那正是 #53。"""
    assert instance_rank("am") < instance_rank("afternoon")
    assert instance_rank("") < instance_rank("am")
    assert instance_rank("morning") < instance_rank("noon") < instance_rank("pm")


def test_instance_rank_is_case_insensitive():
    """`references/multi-session.md` 規定小寫，但大小寫不同不該變成「定不出序」。"""
    assert instance_rank("AM") == instance_rank("am")


@pytest.mark.parametrize("instance", ["project-x", "part1-combined", "第二場"], ids=repr)
def test_instance_rank_admits_it_cannot_order_an_arbitrary_suffix(instance):
    """回 `None` 而不是一個很大的數字：呼叫端要分得出「排最後」與「不知道排哪」。

    分不出來的話，退化行為就只剩「靜靜地排在後面」，而那是看不見的 —— 這張票要的
    是說得出口的退化。
    """
    assert instance_rank(instance) is None


def test_instance_order_key_puts_the_unorderable_after_every_known_session():
    """截斷（`notes[-limit:]`）留下的是排最後的那幾份 —— 排前面的話會被砍掉。"""
    last_known = max(instance_order_key(i) for i in INSTANCE_ORDER)

    assert instance_order_key("project-x") > last_known


def test_instance_order_key_keeps_the_known_ones_in_time_order():
    assert instance_order_key("am") < instance_order_key("pm")


DIR_NAMES = [
    (("20260916", None), "20260916"),
    (("20260916", ""), "20260916"),
    (("20260916", "am"), "20260916_am"),
    # Doc 名與資料夾名共用 `clean_for_filename`，兩邊才不會漂開。
    (("20260916", "a/b"), "20260916_a-b"),
]


@pytest.mark.parametrize("args,expected", DIR_NAMES, ids=[e for _, e in DIR_NAMES] + [])
def test_date_dir_name_matches_the_suffix_that_goes_into_the_doc_title(args, expected):
    assert date_dir_name(*args) == expected


def test_date_dir_name_and_note_title_agree_on_the_session():
    """資料夾叫 `20260916_am`、Doc 叫 `會議記錄_X_20260916_am` —— 掃描層靠前者認出後者。

    兩邊各自清洗的話，`a/b` 這種後綴會讓 Doc 落在一個掃描層找不到的資料夾裡。
    """
    folder = date_dir_name("20260916", "a/b")
    title = note_title("PM會議", "20260916", "a/b")

    assert title.endswith(folder.split("_", 1)[1])


def test_every_shape_the_messages_promise_is_a_shape_the_parser_accepts():
    """文案與判準共用一份來源 —— 各寫一次的話，判準擴充了而文案沒跟上，人會照著一份
    過期的說明去建資料夾，而那個資料夾照樣掃不到。

    這條量的是**方向**：訊息裡舉的每一個例子都要真的 parse 得過。反過來（判準認得的
    形狀都要出現在文案裡）量不動 —— 形狀是正規表示式，不是一份可以枚舉的清單。
    """
    examples = DATE_DIR_EXAMPLE.split("：", 1)[1].split("、")

    assert examples, DATE_DIR_EXAMPLE
    for example in examples:
        assert parse_date_dir(example) is not None, f"文案舉的例子掃不到：{example}"
    assert any(parse_date_dir(e)[1] for e in examples), "至少要有一個帶場次的例子"


def test_the_shape_sentence_names_both_forms():
    """只講 `YYYYMMDD` 的那一版正是 #57 的訊息在 #56 落地當天變得不完整的樣子。"""
    assert "YYYYMMDD" in DATE_DIR_SHAPES
    assert "YYYYMMDD_〈場次〉" in DATE_DIR_SHAPES
    # 半形角括號在 Slack mrkdwn 裡是實體的開頭。這幾個字串會進 Slack，所以形狀
    # 那句不准帶 `<` —— 靠 Slack 幫忙轉義的話，它改規則的那天沒有人會發現。
    assert "<" not in DATE_DIR_SHAPES and ">" not in DATE_DIR_SHAPES

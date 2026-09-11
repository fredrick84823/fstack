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
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills/comms/generate-meeting-notes/scripts"
sys.path.insert(0, str(SCRIPTS))

from local_archive import (  # noqa: E402
    DEFAULT_ARCHIVE_DIRNAME,
    SIDECAR_SUFFIX,
    _configured_root,
    archive_paths,
    clean_for_filename,
    note_title,
    sidecar_content,
    write_local_archive,
)

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

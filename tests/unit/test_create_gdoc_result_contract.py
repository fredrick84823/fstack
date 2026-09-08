"""Seam ③ —— 發佈流程的交棒契約 stdout。

`RESULT_*` 那幾行是流程之間唯一的介面（spec #14），本票新增的
`RESULT_LOCAL_NOTE` / `RESULT_LOCAL_SIDECAR` 是這個 seam 第一次被斷言。

**不打網路。** Drive 與 config 用替身、Slack 用 `--no-slack`；`write_local_archive`
包一層 spy 再轉呼真貨並強制 `root=tmp_path` —— 這樣既驗得到「`main()` 到底傳了什麼
進去」，寫出來的檔也落在 `tmp_path`，不會碰到 `~/thoughts`。

替身只擋住外部相依，`main()` 的組裝邏輯（folder_name vs series_name、`note_title`
有沒有套上、`doc_url` 有沒有一路帶到側檔）全部走真的那條路。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills/comms/generate-meeting-notes/scripts"
sys.path.insert(0, str(SCRIPTS))

import create_gdoc_from_md as publish  # noqa: E402
import local_archive  # noqa: E402

DOC_URL = "https://docs.google.com/document/d/abc123/edit"
CONTENT = "# 會議記錄\n\n- 日期：2026/07/08\n\n內容"
MEETING = {
    "series_name": "PM會議",
    "folder_name": "週三_PM_會議",
    "folder_id": "series-folder-id",
    "attendees": [],
}


@pytest.fixture
def publish_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    """跑一次 `main()`，回傳 (RESULT_* 的 dict, write_local_archive 收到的 args)。

    `archive_fails=` 讓歸檔那步炸掉，用來驗它不會把 `RESULT_URL` 一起帶走。
    """

    def run(*extra_argv: str, archive_fails: bool = False):
        content_file = tmp_path / "meeting_notes.md"
        content_file.write_text(CONTENT, encoding="utf-8")

        monkeypatch.setattr(publish, "load_config", lambda: {"meetings": {"pm": MEETING}})
        monkeypatch.setattr(
            publish, "create_gdoc_in_shared_drive", lambda *a, **kw: (DOC_URL, "date-folder-id")
        )

        calls: list[tuple[tuple, dict]] = []
        real = local_archive.write_local_archive

        def spy(*args, **kwargs):
            calls.append((args, kwargs))
            if archive_fails:
                raise PermissionError(13, "Permission denied")
            return real(*args, **kwargs, root=tmp_path)

        monkeypatch.setattr(publish, "write_local_archive", spy)
        monkeypatch.setattr(sys, "argv", [
            "create_gdoc_from_md.py",
            "--meeting", "pm",
            "--date", "20260708",
            "--content-file", str(content_file),
            "--no-slack",
            *extra_argv,
        ])

        publish.main()

        results = {
            line.split(": ", 1)[0]: line.split(": ", 1)[1]
            for line in capsys.readouterr().out.splitlines()
            if line.startswith("RESULT_") and ": " in line
        }
        return results, calls

    return run


def test_stdout_hands_off_the_two_local_archive_paths(publish_once, tmp_path: Path):
    """契約的兩行必須印出來，而且印的就是實際寫出去的那兩個檔。"""
    results, _ = publish_once()

    note = Path(results["RESULT_LOCAL_NOTE"])
    sidecar = Path(results["RESULT_LOCAL_SIDECAR"])

    assert note.is_file() and sidecar.is_file()
    assert note.relative_to(tmp_path) == Path("週三_PM_會議/20260708/會議記錄_PM會議_20260708.md")
    assert sidecar == note.with_suffix("").with_name(note.stem + ".meta.json")


def test_sidecar_url_equals_the_published_url(publish_once):
    """驗收條件：「側檔記的 URL 與發佈輸出的 URL 相同」。

    兩邊都從同一個 local 來，所以這條是釘住「不會有人在中間把它改掉」——
    包含「側檔忘記帶 doc_url」這種寫成 `{}` 也照樣不會有人發現的改法。
    """
    results, _ = publish_once()

    sidecar = json.loads(Path(results["RESULT_LOCAL_SIDECAR"]).read_text(encoding="utf-8"))
    assert results["RESULT_URL"] == DOC_URL
    assert sidecar["doc_url"] == results["RESULT_URL"]


def test_local_folder_is_the_drive_folder_name_not_the_series_name(publish_once):
    """驗收條件：「系列資料夾名沿用發佈流程已經算出來的那個值」。

    `series_name`（PM會議）與 `folder_name`（週三_PM_會議）在 config 裡是兩個值，
    傳錯的症狀是本機多長一棵沒人找得到的目錄樹，Drive 那邊卻一切正常。
    """
    results, calls = publish_once()

    (folder_arg, date_arg, title_arg, _content), kwargs = calls[0]
    assert folder_arg == MEETING["folder_name"]
    assert (date_arg, kwargs["doc_url"]) == ("20260708", DOC_URL)
    assert title_arg == "會議記錄_PM會議_20260708"
    assert Path(results["RESULT_LOCAL_NOTE"]).parent.parent.name == MEETING["folder_name"]
    assert results["RESULT_DRIVE_PATH"] == "週三_PM_會議/20260708"


def test_title_suffix_reaches_the_local_filename(publish_once):
    """驗收條件：「同日多場次的短識別碼有反映在本機檔名上」。

    走的是 `--title-suffix` 這條 CLI 路徑，不是直接呼叫 `note_title`——後者已經有
    自己的測試，這裡要驗的是發佈流程真的把它接上了。
    """
    results, _ = publish_once("--title-suffix", "pm")

    assert Path(results["RESULT_LOCAL_NOTE"]).name == "會議記錄_PM會議_20260708_pm.md"
    assert Path(results["RESULT_LOCAL_SIDECAR"]).name == "會議記錄_PM會議_20260708_pm.meta.json"


def test_archive_failure_does_not_swallow_the_published_url(publish_once, capsys):
    """歸檔寫不進去時，Doc 已經建好了 —— 這時把 `RESULT_URL` 一起吞掉才是真的丟資料。

    「URL 只有發佈當下拿得到，事後要靠檔名回頭去 Drive 找」是這張票存在的前提（#6）。
    附屬產物失敗不該毀掉主要交棒；缺的那兩行本身就是「這次沒歸檔」的訊號。
    """
    results, calls = publish_once(archive_fails=True)

    assert calls, "應該有試著歸檔"
    assert results["RESULT_URL"] == DOC_URL
    assert results["RESULT_DRIVE_PATH"] == "週三_PM_會議/20260708"
    assert "RESULT_LOCAL_NOTE" not in results
    assert "RESULT_LOCAL_SIDECAR" not in results

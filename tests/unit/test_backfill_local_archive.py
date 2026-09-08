"""`scripts/backfill_local_archive.py` 的黑箱測試。全部不碰網路。

CLI 那層只測**打網路之前**就能判定的那條路：`--meeting` 指到 config 裡沒有的
key → exit 2。exit 0 / exit 1 兩條要整支跑完才驗得到，那是 Drive I/O 路徑 ——
spec #14 明列在 Out of Scope。

翻頁上限與撞名裁決是純函式，收 `drive` 當參數，用一個只會回罐頭頁的替身就驗得到，
所以在這裡測：翻頁沒上限的症狀是「跑不完」而不是「變紅」（#6 的陷阱清單），
撞名裁錯的症狀是本機悄悄留了舊版本。

這條同時釘住 8/31 那個陷阱的另一半：key 檢查必須排在憑證取得**之前**。反過來的話，
打錯 key 的人看到的會是 `RefreshError`，然後去 debug 憑證 —— 上次就是這樣誤判的。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "skills/comms/generate-meeting-notes/scripts/backfill_local_archive.py"
)


def test_unknown_meeting_key_exits_2_before_touching_credentials(tmp_path: Path):
    conf = tmp_path / ".config/generate-meeting-notes"
    conf.mkdir(parents=True)
    (conf / "config.json").write_text(
        json.dumps({"meetings": {"real": {"series_name": "S", "folder_name": "F"}}}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--meeting", "bogus", "--root", str(tmp_path / "root")],
        capture_output=True,
        text=True,
        env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"},
    )

    assert result.returncode == 2, result.stderr
    assert "bogus" in result.stdout + result.stderr
    assert not (tmp_path / "root").exists()


sys.path.insert(0, str(SCRIPT.parent))
from backfill_local_archive import list_all, resolve_collisions  # noqa: E402


HARD_STOP = 50


class _FakeDrive:
    """只回應 `files().list(...).execute()`。用來驗翻頁，不碰網路。

    翻超過 `HARD_STOP` 頁就 `pytest.fail()`。少了這個閘，「上限被拿掉」的實作會讓
    測試掛在那裡跑不完 —— 而跑不完不是紅燈，是沒人知道發生什麼事（#6 的陷阱）。
    替身自己守住這條，被測的上限壞掉才會變成一句看得懂的失敗訊息。
    """

    def __init__(self, pages: list[dict]):
        self.pages = pages
        self.calls = 0

    def files(self):
        return self

    def list(self, **kwargs):
        return self

    def execute(self) -> dict:
        self.calls += 1
        if self.calls > HARD_STOP:
            pytest.fail(
                f"Drive 替身被翻了 {HARD_STOP} 頁還沒停 —— list_all 的翻頁上限失效了。"
                "真的對著 Drive 跑會變成無聲繞圈，不會報錯。"
            )
        return self.pages[min(self.calls - 1, len(self.pages) - 1)]


def test_list_all_keeps_paging_until_the_token_runs_out():
    """上限的另一半：不能為了「安全」提早收手，缺頁的症狀是差集少算而不是報錯。"""
    drive = _FakeDrive([
        {"files": [{"id": "a"}], "nextPageToken": "t"},
        {"files": [{"id": "b"}]},
    ])

    assert [f["id"] for f in list_all(drive, "q", max_pages=5)] == ["a", "b"]
    assert drive.calls == 2


def test_list_all_raises_with_diagnostics_instead_of_looping_forever():
    """#6 的陷阱：「壞掉的實作要變紅而不是跑不完」。

    Drive 一直給 `nextPageToken` 時，無上限的迴圈會讓整條測試掛在那裡等 ——
    測試不會紅，只會永遠不結束。這條釘住上限存在、會炸、而且炸的時候印得出
    是哪個 query 在繞（沒有 query 的話下一步只能從頭 debug）。
    """
    drive = _FakeDrive([{"files": [{"id": "x"}], "nextPageToken": "t"}])

    with pytest.raises(RuntimeError) as excinfo:
        list_all(drive, "'folder-abc' in parents", max_pages=3)

    assert drive.calls == 3
    assert "3" in str(excinfo.value) and "folder-abc" in str(excinfo.value)


def _gap(note: str, modified: str, doc_id: str) -> dict:
    return {
        "note_path": Path(note),
        "modified": modified,
        "doc_url": f"https://docs.google.com/document/d/{doc_id}/edit",
    }


def test_resolve_collisions_keeps_the_newest_of_the_docs_sharing_a_filename():
    """同一個本機檔名對到多份 Doc 時取 `modifiedTime` 最新的。

    順序反了不會爆炸，只會把舊版本寫成本機的正式稿 —— 沒有任何症狀。
    """
    old = _gap("同名.md", "2026-08-24T10:00:00.000Z", "old")
    new = _gap("同名.md", "2026-08-31T09:00:00.000Z", "new")

    resolved, decisions = resolve_collisions([old, new])

    assert [g["doc_url"] for g in resolved] == [new["doc_url"]]
    assert resolved[0]["newest_wins"] is True
    assert len(decisions) == 1
    assert decisions[0]["chosen"] is new
    assert [c["doc_url"] for c in decisions[0]["candidates"]] == [new["doc_url"], old["doc_url"]]


def test_resolve_collisions_leaves_uncontested_filenames_unmarked():
    """沒撞名就不該標 `[newest-wins]` —— 每場都標等於這個標記沒有資訊。"""
    resolved, decisions = resolve_collisions([
        _gap("甲.md", "2026-08-24T10:00:00.000Z", "a"),
        _gap("乙.md", "2026-08-25T10:00:00.000Z", "b"),
    ])

    assert decisions == []
    assert [g["newest_wins"] for g in resolved] == [False, False]
    assert sorted(g["note_path"].name for g in resolved) == ["乙.md", "甲.md"]

"""`scripts/backfill_local_archive.py` 的 CLI 黑箱測試。

只測**打網路之前**就能判定的那條路：`--meeting` 指到 config 裡沒有的 key → exit 2。
其餘退出碼（0 完成 / 1 執行中出錯，含翻頁超上限）都要有 Drive 替身才驗得到，
不在這條 branch 的範圍。

這條同時釘住 8/31 那個陷阱的另一半：key 檢查必須排在憑證取得**之前**。反過來的話，
打錯 key 的人看到的會是 `RefreshError`，然後去 debug 憑證 —— 上次就是這樣誤判的。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

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

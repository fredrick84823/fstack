"""驗收條件「fstack 與安裝版排除四類後比對無差異」—— 需要本機安裝版，故歸 integration。

不打網路，但吃 `~/.agents/skills/generate-meeting-notes`，在別台機器與 CI 上不存在。
放進預設 `pytest` 會變成一條靠環境決定顏色的測試，所以 `setup.cfg` 的 testpaths
只收 `tests/unit`，這支要明示 `pytest tests/integration` 才跑。

比對邏輯本身已經搬進 `scripts/parity.py`（發佈流程結束後也要跑同一份，#17），所以這裡
只呼叫 `parity.sync_diff`，不再自己 rsync ＋ `filecmp`。**兩份比對邏輯是這條測試最糟的
失敗方式**：發佈流程那邊漂掉了，這裡照樣綠。

作法沒變 —— 用真安裝版跑一次同步到暫存目錄，再拿結果跟 repo 內的版本比對，全程不寫
真實工作樹。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "skills/comms/generate-meeting-notes/scripts"))

import parity  # noqa: E402

INSTALLED = Path.home() / ".agents" / "skills" / "generate-meeting-notes"

pytestmark = pytest.mark.skipif(
    not (INSTALLED / "SKILL.md").exists(), reason=f"本機沒有安裝版：{INSTALLED}"
)


def test_repo_copy_equals_a_fresh_sync_of_the_installed_copy():
    """repo 版 == 對安裝版重跑一次同步的結果。不等就是有人只改了其中一邊。"""
    assert parity.sync_diff(INSTALLED, REPO) == []

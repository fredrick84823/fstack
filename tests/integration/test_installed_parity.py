"""驗收條件「fstack 與安裝版排除四類後比對無差異」—— 需要本機安裝版，故歸 integration。

不打網路，但吃 `~/.agents/skills/generate-meeting-notes`，在別台機器與 CI 上不存在。
放進預設 `pytest` 會變成一條靠環境決定顏色的測試，所以 `pytest.ini` 的 testpaths
只收 `tests/unit`，這支要明示 `pytest tests/integration` 才跑。

作法：把腳本複製進 tmp_path 的假 repo，用真安裝版跑一次同步，再拿結果跟 repo 內的
版本比對。全程不寫真實工作樹。
"""

from __future__ import annotations

import filecmp
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "bin" / "sync-from-installed.sh"
DEST_REL = Path("skills/comms/generate-meeting-notes")
INSTALLED = Path.home() / ".agents" / "skills" / "generate-meeting-notes"

pytestmark = pytest.mark.skipif(
    not (INSTALLED / "SKILL.md").exists(), reason=f"本機沒有安裝版：{INSTALLED}"
)


def _differs(cmp: filecmp.dircmp, prefix: str = "") -> list[str]:
    out = [prefix + n for n in cmp.left_only + cmp.right_only + cmp.diff_files]
    for name, sub in cmp.subdirs.items():
        out += _differs(sub, f"{prefix}{name}/")
    return out


def test_repo_copy_equals_a_fresh_sync_of_the_installed_copy(tmp_path: Path):
    """repo 版 == 對安裝版重跑一次同步的結果。不等就是有人只改了其中一邊。"""
    (tmp_path / "bin").mkdir()
    shutil.copy2(SCRIPT, tmp_path / "bin" / SCRIPT.name)

    result = subprocess.run(
        [str(tmp_path / "bin" / SCRIPT.name), str(INSTALLED)],
        capture_output=True,
        text=True,
        cwd="/",
    )
    assert result.returncode == 0, result.stdout + result.stderr

    assert _differs(filecmp.dircmp(tmp_path / DEST_REL, REPO / DEST_REL)) == []

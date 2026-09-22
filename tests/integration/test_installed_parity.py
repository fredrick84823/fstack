"""驗收條件「fstack 與安裝版排除四類後比對無差異」—— 需要本機安裝版，故歸 integration。

不打網路，但吃 `~/.agents/skills/<skill>`，在別台機器與 CI 上不存在。放進預設 `pytest`
會變成一條靠環境決定顏色的測試，所以 `setup.cfg` 的 testpaths 只收 `tests/unit`，
這支要明示 `pytest tests/integration` 才跑。

**涵蓋哪些 skill 是資料**：`bin/parity_skills.py` 的 `SKILLS`。這支照著那份清單
parametrize，所以把一支 skill 納入保護是在那裡加一行，不是在這裡加一條測試 ——
原本三個地方各寫死一次 `generate-meeting-notes`，結果 60 幾支 skill 裡只有 1 支被守。

比對邏輯本身在 `bin/parity_skills.py`（發佈流程結束後也要跑同一套，#17），所以這裡只
呼叫 `sync_diff`，不再自己 rsync ＋ `filecmp`。**兩份比對邏輯是這條測試最糟的失敗
方式**：發佈流程那邊漂掉了，這裡照樣綠。

skip 的判斷要**逐 skill**：清單裡有兩支、本機只裝了一支時，沒裝的那支要 skip 而不是紅。
掛在 module 上的 skipif 會變成「其中一支沒裝就整包不跑」。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location("parity_skills", REPO / "bin" / "parity_skills.py")
assert _spec is not None and _spec.loader is not None
parity_skills = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = parity_skills
_spec.loader.exec_module(parity_skills)


@pytest.mark.parametrize("skill_rel", sorted(parity_skills.SKILLS))
def test_repo_copy_equals_a_fresh_sync_of_the_installed_copy(skill_rel: str):
    """repo 版 == 對安裝版重跑一次同步的結果。不等就是有人只改了其中一邊。"""
    installed = parity_skills.installed_dir(skill_rel)
    if not (installed / "SKILL.md").exists():
        pytest.skip(f"本機沒有安裝版：{installed}")

    assert parity_skills.sync_diff(skill_rel, installed, REPO) == []

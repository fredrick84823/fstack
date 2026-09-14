#!/usr/bin/env python3
"""
parity.py - 安裝版與 fstack 之間的漂移比對。

canonical 是 fstack，實際被編輯的是安裝版。中間那段「改了安裝版還沒掉齊」是正常
工作流的狀態，隨時檢查只會一直叫；**發佈當下編輯已經結束**，此時的漂移是真漂移
（裁決見 #17）。所以呼叫點只有一個：發佈流程的最後。

比對方式與 `tests/integration/test_installed_parity.py` 原本的作法同一份 ——
把安裝版重跑一次 `bin/sync-from-installed.sh` 同步進暫存目錄，再跟 repo 版比對。
走同步腳本而不是直接 diff，是因為 repo 版是 sanitize 過的：直接比會把每個佔位符
都算成差異。

**不擋流程。** Doc 這時已經發出去了，回非零沒有意義，只會讓人學會忽略它。
`report_drift()` 只印字，任何異常都吞掉。
"""

from __future__ import annotations

import filecmp
import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SYNC_SCRIPT = Path("bin/sync-from-installed.sh")
SKILL_REL = Path("skills/comms/generate-meeting-notes")

# 警告的第一行。發佈流程的輸出是交棒契約的一部分，這個字串會被斷言。
DRIFT_HEADER = "⚠️  安裝版與 fstack 已經漂移"

# 同步腳本的 guard 命中內部指涉時的退出碼。此時 rsync 已經跑完，比對照樣成立
# —— 那是另一件事，不是「沒同步到」。
GUARD_HIT = 2


def drift_warning(paths: Sequence[str]) -> str:
    """差異清單 → 要印出來的警告。沒有差異回空字串。

    回空字串而不是 None：呼叫端一律 `print(..., end="")`，不用再分一次支。
    """
    if not paths:
        return ""
    listed = "\n".join(f"   {p}" for p in sorted(paths))
    return (
        f"\n{DRIFT_HEADER}（{len(paths)} 項）：\n"
        f"{listed}\n"
        f"   掉齊：{SYNC_SCRIPT}\n"
    )


def _differs(cmp: filecmp.dircmp, prefix: str = "") -> list[str]:
    out = [prefix + n for n in cmp.left_only + cmp.right_only + cmp.diff_files]
    for name, sub in cmp.subdirs.items():
        out += _differs(sub, f"{prefix}{name}/")
    return out


def sync_diff(installed: Path, repo: Path) -> list[str]:
    """把 `installed` 同步進暫存目錄，回傳它與 `repo` 版之間的差異路徑。

    比不了的時候回空清單（`installed` 不像安裝目錄、repo 內沒有同步腳本）——
    「沒有安裝版」與「安裝版一致」在呼叫端是同一件事：沒東西要講。

    同步**跑不完**則 raise `RuntimeError`。這裡回空清單的話，一支壞掉的腳本會讓
    所有比對永遠通過 —— 連 integration test 都會跟著變成永遠綠。
    """
    script = repo / SYNC_SCRIPT
    if not (installed / "SKILL.md").is_file() or not script.is_file():
        return []

    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        (stage / SYNC_SCRIPT.parent).mkdir(parents=True)
        shutil.copy2(script, stage / SYNC_SCRIPT)
        done = subprocess.run(
            [str(stage / SYNC_SCRIPT), str(installed)],
            capture_output=True,
            text=True,
            cwd="/",
        )
        if done.returncode not in (0, GUARD_HIT):
            raise RuntimeError(
                f"{SYNC_SCRIPT.name} exit {done.returncode}\n{done.stdout}{done.stderr}"
            )
        return _differs(filecmp.dircmp(stage / SKILL_REL, repo / SKILL_REL))


def report_drift(config: dict | None = None, installed: Path = SKILL_DIR) -> None:
    """發佈流程結束時叫一次。有漂移就印警告，其餘情況什麼都不印。

    fstack 的位置只認 config 的 `fstack_repo`，沒有自動往上找 —— 從安裝版跑的時候
    往上找一定找不到（安裝目錄不在工作樹裡），而從工作樹跑的時候會找得到，於是
    **每一條碰到 `main()` 的 unit test 與每一顆 mutant 都會真的跑一次 rsync**。
    一個只在其中一種跑法下生效的 fallback，換來的是測試裡的真實 I/O。

    比對本身失敗時也什麼都不印：這支是發佈的附屬品，不該把一個已經成功的發佈
    變成看起來失敗的樣子。
    """
    repo = (config or {}).get("fstack_repo")
    if not repo:
        return
    try:
        print(drift_warning(sync_diff(installed, Path(repo).expanduser())), end="")
    except (OSError, RuntimeError):
        pass

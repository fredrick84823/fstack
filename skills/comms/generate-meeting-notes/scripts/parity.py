#!/usr/bin/env python3
"""
parity.py - 安裝版與 fstack 之間的漂移比對。

canonical 是 fstack，改動也從 repo 端開始（repo-first）；安裝版是掉齊的產物。中間那段
「改了還沒掉齊」是正常工作流的狀態，隨時檢查只會一直叫；**發佈當下編輯已經結束**，
此時的漂移是真漂移（裁決見 #17）。所以 `report_drift` 的呼叫點只有一個：發佈流程的最後。

`sync_direction` 是第二個用途：`bin/sync-from-installed.sh` 動檔案**之前**問一次方向。
那個方向帶 `--delete`，repo 比安裝版新時照跑會刪掉已合併的改動（#29）。

比對方式與 `tests/integration/test_installed_parity.py` 原本的作法同一份 ——
把安裝版重跑一次 `bin/sync-from-installed.sh` 同步進暫存目錄，再跟 repo 版比對。
走同步腳本而不是直接 diff，是因為 repo 版是 sanitize 過的：直接比會把每個佔位符
都算成差異。

**不擋流程。** Doc 這時已經發出去了，回非零沒有意義，只會讓人學會忽略它。
`report_drift()` 只印字 —— 比對成功就報漂移，比對自己壞掉就報「跳過」，兩種情況
都不拋例外。
"""

from __future__ import annotations

import filecmp
import shutil
import subprocess
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SYNC_SCRIPT = Path("bin/sync-from-installed.sh")
SKILL_REL = Path("skills/comms/generate-meeting-notes")

# 警告的第一行。發佈流程的輸出是交棒契約的一部分，這個字串會被斷言。
DRIFT_HEADER = "⚠️  安裝版與 fstack 已經漂移"

# 警告裡要印的掉齊指令。是**反向**那支：repo-first 之後，發佈當下看到漂移最可能的原因
# 是「合併了還沒掉齊」，而正向那支在這種情況會拒絕執行（exit 3）。指向正向那支等於讓
# 人先撞一次牆才知道要跑哪支。
FIX_SCRIPT = Path("bin/sync-to-installed.sh")


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
        f"   掉齊：{FIX_SCRIPT}\n"
    )


def _differs(cmp: filecmp.dircmp, prefix: str = "") -> list[str]:
    out = [prefix + n for n in cmp.left_only + cmp.right_only + cmp.diff_files]
    for name, sub in cmp.subdirs.items():
        out += _differs(sub, f"{prefix}{name}/")
    return out


def sync_diff(installed: Path, repo: Path, *, require_clean_guard: bool = True) -> list[str]:
    """把 `installed` 同步進暫存目錄，回傳它與 `repo` 版之間的差異路徑。

    比不了的時候回空清單（`installed` 不像安裝目錄、repo 內沒有同步腳本）——
    「沒有安裝版」與「安裝版一致」在呼叫端是同一件事：沒東西要講。

    同步**沒有乾淨收尾**（退出碼不是 0）則 raise `RuntimeError`。這裡回空清單的話，
    一支壞掉的腳本會讓所有比對永遠通過 —— 連 integration test 都會跟著變成永遠綠。
    退出碼 2（guard 命中內部指涉）預設也算沒收乾淨：檔案雖然同步到了，但那條 integration
    測試原本就是靠「退出碼 0」在守那件事，放行等於把它交出去。

    `require_clean_guard=False` 只給方向判斷用。那條路徑要的只有「暫存目錄裡的檔案」，
    而 exit 2 的時候檔案是齊的 —— guard 命中是 commit 前要處理的事，不該讓方向退化成
    「不知道」：真正的同步緊接著就會跑到它自己的 guard 並以 2 收場（腳本 header 文件化
    的那條安全閥），前提是閘門先讓它走到那裡。
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
        if done.returncode != 0 and (require_clean_guard or done.returncode != 2):
            why = (done.stderr or done.stdout).strip().rsplit("\n", 1)[-1]
            raise RuntimeError(f"{SYNC_SCRIPT.name} exit {done.returncode}: {why}")
        return _differs(filecmp.dircmp(stage / SKILL_REL, repo / SKILL_REL))


# `sync_direction` 的三個回傳值。
# bin/sync-from-installed.sh 的閘門是**白名單**：只認得 INSTALLED_NEWER 與 IN_SYNC 這兩個
# 字面值才放行，其餘一律拒絕。所以改 REPO_NEWER 的字面值是安全的，改另外兩個會讓那支
# 腳本從此拒絕一切同步（吵，但不會刪東西）—— 兩個都改才會靜默放行。
INSTALLED_NEWER = "安裝版較新"
REPO_NEWER = "repo 較新"
IN_SYNC = "一致"


def sync_direction(installed: Mapping[str, float], repo: Mapping[str, float]) -> str:
    """兩邊的「差異檔案 → mtime」清單 → 該往哪個方向掉齊。

    只吃**內容真的不同**的路徑 —— sanitize 造成的差異在呼叫端（`sync_diff`）就已經
    消掉了。所以「兩邊都改成一樣」在這裡是兩份空清單，跟「都沒改」同一個結果。

    平手（mtime 完全相同）算 repo 較新。這個判斷唯一的用途是擋下會刪掉已合併改動的
    那個方向，而猜錯的代價不對稱：多擋一次要人跑一次掉齊，少擋一次工作就沒了。
    """
    for rel, mtime in repo.items():
        if rel not in installed or mtime >= installed[rel]:
            return REPO_NEWER
    return INSTALLED_NEWER if installed else IN_SYNC


def _mtimes(root: Path, rels: Iterable[str]) -> dict[str, float]:
    """`rels` 之中在 `root` 底下存在的那些 → mtime。不存在的不收 —— 不存在本身就是
    方向的證據，用 `0` 之類的哨兵值填會讓它退化成一個普通的比大小。"""
    return {rel: (root / rel).stat().st_mtime for rel in rels if (root / rel).exists()}


def direction_against_installed(installed: Path, repo: Path) -> str:
    """安裝目錄與 fstack 工作樹 → 方向。動任何檔案之前問。

    差異清單走 `sync_diff`（同一份比對邏輯，#24 收斂的那份），mtime 則直接讀兩邊的
    **原始**檔案 —— 不能讀暫存基準的：sanitize 那道 `sed` 會把被替換過的檔案 mtime
    改成現在，於是每個含佔位符的檔案都會看起來像「安裝版剛改過」。

    比不了的時候 **raise**，不繼承 `sync_diff` 的「回空清單」。那個契約是為
    `report_drift` 寫的（沒有安裝版 == 沒東西要講），照搬到這裡就是：比不了 → 空清單 →
    `IN_SYNC` → 閘門放行 `rsync --delete`。兩個呼叫端要的相反，差別寫在這裡。

    ponytail: repo 側的「多新」用 mtime。剛開的 worktree 裡每個檔案的 mtime 都是
    checkout 當下，所以「安裝版被直接改過、想用正向同步撿回來」在新 worktree 幾乎一定
    被判成 repo 較新而擋掉（那個情境下正向同步本來也多半是危險的 —— 同一個工作樹裡有
    還沒掉齊的合併）。真的要分得更細，乾淨的檔案改讀 `git log -1 --format=%ct`、
    改過沒 commit 的才退回 mtime。
    """
    if not (installed / "SKILL.md").is_file():
        raise RuntimeError(f"不像 generate-meeting-notes 安裝目錄，無法判斷方向：{installed}")
    script = repo / SYNC_SCRIPT
    if not script.is_file():
        raise RuntimeError(f"repo 內找不到同步腳本，無法判斷方向：{script}")
    rels = sync_diff(installed, repo, require_clean_guard=False)
    return sync_direction(_mtimes(installed, rels), _mtimes(repo / SKILL_REL, rels))


def report_drift(config: dict, installed: Path = SKILL_DIR) -> None:
    """發佈流程結束時叫一次。有漂移就印警告，其餘情況什麼都不印。

    fstack 的位置只認 config 的 `fstack_repo`，沒有自動往上找 —— 從安裝版跑的時候
    往上找一定找不到（安裝目錄不在工作樹裡），而從工作樹跑的時候會找得到，於是
    **每一條碰到 `main()` 的 unit test 與每一顆 mutant 都會真的跑一次 rsync**。
    一個只在其中一種跑法下生效的 fallback，換來的是測試裡的真實 I/O。

    比對本身失敗時印一行「跳過」並繼續：這支是發佈的附屬品，不該把一個已經成功的
    發佈變成看起來失敗的樣子 —— 但也不能連「這次沒比成」都不講。
    """
    repo = config.get("fstack_repo")
    if not repo:
        return
    try:
        print(drift_warning(sync_diff(installed, Path(repo).expanduser())), end="")
    except (OSError, RuntimeError) as exc:
        # 比對自己壞掉時**要講一聲**。整個吞掉的話，一台沒有 guard 設定的機器
        # （同步腳本會以 1 收場）就是漂移偵測永遠不叫，而且沒有任何測試會紅
        # —— #14 點名的「驗收腳本的靜默失敗沒人守」就是這個形狀。
        print(f"\nℹ️  漂移比對跳過：{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    # `--direction INSTALLED REPO` —— 給 bin/sync-from-installed.sh 的方向閘門呼叫。
    # 比對壞掉時讓例外原地炸開（非零退出碼），不要印一個看起來像答案的字串：
    # 呼叫端拿到「一致」就會放行 rsync --delete。
    import sys

    if sys.argv[1:2] != ["--direction"] or len(sys.argv) != 4:
        sys.exit(f"用法：{Path(__file__).name} --direction INSTALLED REPO")
    print(direction_against_installed(Path(sys.argv[2]), Path(sys.argv[3])))

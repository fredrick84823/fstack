#!/usr/bin/env python3
"""parity 涵蓋哪些 skill —— 清單在這裡，下面的判斷不認得任何一支 skill 的名字。

這支的由來是兩起同根因的事故。偵測「安裝版與 repo 漂移」的整套機制是完整的，但三個
地方都寫死了 `skills/comms/generate-meeting-notes`，於是 60 幾支 skill 裡只有 1 支被
保護：

  1. improve 的三個修正直接改在安裝版，五天沒人發現 —— hook 指向安裝版，正在跑的碼
     比 repo 新，其中一個沒撿回來的後果是每個真實 session 都被靜默跳過。
  2. slack-pm 的 SKILL.md 帶著客戶名、品牌名與同事實名躺在 public repo 幾個月 ——
     去識別化只跑 generate-meeting-notes，slack-pm 從來沒經過它。

**只涵蓋一支的護欄，對其餘 59 支等於沒有護欄。** 所以涵蓋範圍做成**資料**（`SKILLS`）：
加一支 skill 是加一行，本檔與 `bin/sync-from-installed.sh` 都不用改。

兩類 skill 的比對方式不同，差別就是 `SKILLS` 的那個布林：

  True（repo 版是 sanitize 過的）
      直接 diff 會把每一個佔位符都算成差異。所以拿安裝版**重跑一次**
      `bin/sync-from-installed.sh` 到暫存目錄，再跟 repo 版比 —— sed 規則只能有一份，
      走腳本就不必在這裡再抄一次。
  False（repo 版就是安裝版的原樣）
      直接比對，排除 rsync 也排除的那四類雜訊，**再排除 repo 的 `.gitignore` 已經忽略
      的路徑** —— 執行期資料（佇列、log、lock、memory/）刻意不進版控，repo 端永遠沒有
      它們，不排除就是每次都報一串永遠修不掉的假漂移。每次都喊狼來了的護欄跟沒有護欄
      是同一件事，而那正是這張票在治的病。

沒有為這個布林建註冊表或 config schema：它只是一個布林，而 `SKILLS` 就是那一處資料。

**與 `skills/comms/generate-meeting-notes/scripts/parity.py` 暫時是兩份。**
那支不能在這條分支上改：它住在**被同步的** skill 目錄裡，安裝版只有一份、所有 worktree
共用，未合併的碼寫進去會同時弄紅 main 與其他每一張票的 parity（規則寫在
`bin/sync-to-installed.sh` 的 header）。兩份會漂，而漂掉的症狀是靜悄悄的，所以
`tests/unit/test_parity_skills.py` 有一條把兩份的答案釘在一起的測試。
# ponytail: 合併並跑過 bin/sync-to-installed.sh 之後，parity.py 的 sync_diff 與
# direction_against_installed 應該改成 delegate 到這支（它已經讀得到 config 的
# `fstack_repo`，路徑問得出來），那條釘子也就可以拆了。
"""

from __future__ import annotations

import filecmp
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SYNC_SCRIPT = Path("bin/sync-from-installed.sh")

# repo 相對路徑 → 「這支 skill 的 repo 版是 sanitize 過的嗎」。
# **加一支 skill 就是在這裡加一行**，邏輯不用動。
SKILLS: dict[str, bool] = {
    "skills/comms/generate-meeting-notes": True,
}

# rsync 排除的四類。直接比對那條路徑要套同一份，否則每一顆 __pycache__ 都算漂移。
# ponytail: 同一份清單在 sync-from-installed.sh 是 rsync 的 --exclude、在
# sync-to-installed.sh 是 find 的述詞、在這裡是 dircmp 的 ignore —— 三種語法沒辦法共用
# 一份字面值。改一邊記得改另外兩邊；漏改是無聲的（多算漂移，或漏算）。
EXCLUDES = [".venv", "__pycache__", ".pytest_cache", ".DS_Store"]


def installed_dir(skill_rel: str) -> Path:
    """skill 的安裝位置。安裝版是**攤平**的：repo 的分類目錄（`comms/`、
    `skill-evolution/`…）在 `~/.agents/skills` 底下沒有對應層級。
    同一條規則在 `bin/sync-from-installed.sh` 是 `${SKILL_REL##*/}`。"""
    return Path.home() / ".agents" / "skills" / Path(skill_rel).name


def _sanitized(skill_rel: str) -> bool:
    """`SKILLS` 的查表，附一句看得懂的理由。

    沒涵蓋的 skill **不可以**被當成「沒有漂移」放行 —— 那正是這張票在修的病，
    所以這裡 raise，而且訊息要直接說下一步在哪一行。
    """
    try:
        return SKILLS[skill_rel]
    except KeyError:
        raise KeyError(
            f"{skill_rel} 不在 parity 的涵蓋清單裡。納入保護＝在 bin/parity_skills.py "
            f"的 SKILLS 加一行（值是「repo 版是不是 sanitize 過的」）。"
        ) from None


def _gitignored(repo: Path, skill_rel: str, rels: Sequence[str]) -> set[str]:
    """`rels` 之中 repo 端已經被 `.gitignore` 忽略的那些。

    判準問 repo 自己的 git，不在這裡再維護第二份清單 —— 同一份清單散在三個地方的代價
    已經寫在 `EXCLUDES` 上面那條註記裡，不要再加第四處。

    判定對 **repo 端**的路徑做：安裝版不在 git 裡，問它等於問錯人。

    每個候選送兩次，`rel` 與 `rel/`。目錄規則（`memory/`）只在 git 認得那個路徑是目錄時
    才命中，而 repo 端**刻意沒有**那個目錄（它被忽略了），git 沒得 stat 就不會命中 ——
    加一條斜線是直接告訴它「這是目錄」。少了這一半，整個目錄的忽略規則會漏掉。

    git 自己出錯（不是 git repo、找不到 git）→ **raise**。回空集合是「什麼都沒被忽略」
    （假漂移照報），回全集是靜默吞掉真漂移 —— 兩個都不行，所以讓呼叫端知道這次沒比成。
    退出碼 1 是「一個都沒命中」，那是正常答案，不是錯誤。
    """
    if not rels:
        return set()
    probes = [f"{skill_rel}/{rel}{slash}" for rel in rels for slash in ("", "/")]
    try:
        done = subprocess.run(
            ["git", "-C", str(repo), "check-ignore", "--stdin"],
            input="\n".join(probes),
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise RuntimeError(f"問不到 .gitignore（{type(exc).__name__}: {exc}）") from None
    if done.returncode > 1:
        why = (done.stderr or done.stdout).strip().rsplit("\n", 1)[-1]
        raise RuntimeError(f"git check-ignore exit {done.returncode}: {why}")
    prefix = f"{skill_rel}/"
    return {
        line[len(prefix):].rstrip("/")
        for line in done.stdout.splitlines()
        if line.startswith(prefix)
    }


def _differs(cmp: filecmp.dircmp, prefix: str = "") -> list[str]:
    out = [prefix + n for n in cmp.left_only + cmp.right_only + cmp.diff_files]
    for name, sub in cmp.subdirs.items():
        out += _differs(sub, f"{prefix}{name}/")
    return out


def sync_diff(
    skill_rel: str,
    installed: Path,
    repo: Path = REPO,
    *,
    require_clean_guard: bool = True,
) -> list[str]:
    """某一支 skill 的安裝版與 repo 版之間的差異路徑。

    `skill_rel` 不在 `SKILLS` 裡就 `KeyError`：沒被涵蓋的 skill 不可以被讀成「沒有
    漂移」—— 那正是這張票在修的病。

    比不了的時候回空清單（`installed` 不像安裝目錄、repo 內沒有同步腳本）——
    「沒有安裝版」與「安裝版一致」在呼叫端是同一件事：沒東西要講。

    直接比對那條路徑上，repo 的 `.gitignore` 忽略掉的路徑不算漂移：執行期資料刻意不進
    版控，repo 端永遠沒有它們。sanitize 那條路徑不需要這道過濾 —— 它比的是暫存基準與
    repo 版，而基準是同步腳本產的，兩邊本來就都不含那些東西。

    sanitize 那條路徑上，同步**沒有乾淨收尾**（退出碼不是 0）則 raise `RuntimeError`。
    回空清單的話，一支壞掉的腳本會讓所有比對永遠通過 —— 連 integration test 都會跟著
    變成永遠綠。退出碼 2（guard 命中內部指涉）預設也算沒收乾淨。
    `require_clean_guard=False` 只給方向判斷用：exit 2 的時候檔案是齊的，比對本身有效。
    """
    sanitized = _sanitized(skill_rel)
    if not (installed / "SKILL.md").is_file():
        return []
    if not sanitized:
        rels = _differs(filecmp.dircmp(installed, repo / skill_rel, ignore=EXCLUDES))
        ignored = _gitignored(repo, skill_rel, rels)
        return [rel for rel in rels if rel not in ignored]

    script = repo / SYNC_SCRIPT
    if not script.is_file():
        return []
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        (stage / SYNC_SCRIPT.parent).mkdir(parents=True)
        shutil.copy2(script, stage / SYNC_SCRIPT)
        done = subprocess.run(
            [str(stage / SYNC_SCRIPT), "--skill", skill_rel, str(installed)],
            capture_output=True,
            text=True,
            cwd="/",
        )
        if done.returncode != 0 and (require_clean_guard or done.returncode != 2):
            why = (done.stderr or done.stdout).strip().rsplit("\n", 1)[-1]
            raise RuntimeError(f"{SYNC_SCRIPT.name} exit {done.returncode}: {why}")
        return _differs(filecmp.dircmp(stage / skill_rel, repo / skill_rel))


# `sync_direction` 的三個回傳值。
# bin/sync-from-installed.sh 的閘門是**白名單**：只認得 INSTALLED_NEWER 與 IN_SYNC 這兩個
# 字面值才放行，其餘一律拒絕。所以改 REPO_NEWER 的字面值是安全的，改另外兩個會讓那支
# 腳本從此拒絕一切同步（吵，但不會刪東西）—— 兩個都改才會靜默放行。
INSTALLED_NEWER = "安裝版較新"
REPO_NEWER = "repo 較新"
IN_SYNC = "一致"


def sync_direction(installed: Mapping[str, float], repo: Mapping[str, float]) -> str:
    """兩邊的「差異檔案 → mtime」清單 → 該往哪個方向掉齊。

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


def direction_against_installed(skill_rel: str, installed: Path, repo: Path = REPO) -> str:
    """安裝目錄與 fstack 工作樹 → 方向。`rsync --delete` 動任何檔案之前問。

    比不了的時候 **raise**，不繼承 `sync_diff` 的「回空清單」：那個契約是為漂移回報
    寫的（沒有安裝版 == 沒東西要講），照搬到這裡就是 比不了 → 空清單 → `IN_SYNC` →
    閘門放行 `rsync --delete`。兩個呼叫端要的相反，差別寫在這裡。

    mtime 讀的是兩邊的**原始**檔案，不是暫存基準：sanitize 那道 `sed` 會把被替換過的
    檔案 mtime 改成現在，於是每個含佔位符的檔案都會看起來像「安裝版剛改過」。
    """
    if not (installed / "SKILL.md").is_file():
        raise RuntimeError(f"不像 {Path(skill_rel).name} 安裝目錄，無法判斷方向：{installed}")
    if _sanitized(skill_rel) and not (repo / SYNC_SCRIPT).is_file():
        raise RuntimeError(f"repo 內找不到同步腳本，無法判斷方向：{repo / SYNC_SCRIPT}")
    rels = sync_diff(skill_rel, installed, repo, require_clean_guard=False)
    return sync_direction(_mtimes(installed, rels), _mtimes(repo / skill_rel, rels))


if __name__ == "__main__":
    # `--direction SKILL_REL INSTALLED REPO` —— 給 bin/sync-from-installed.sh 的方向閘門。
    # 比對壞掉時讓例外原地炸開（非零退出碼），不要印一個看起來像答案的字串：
    # 呼叫端拿到「一致」就會放行 rsync --delete。
    if sys.argv[1:2] != ["--direction"] or len(sys.argv) != 5:
        sys.exit(f"用法：{Path(__file__).name} --direction SKILL_REL INSTALLED REPO")
    try:
        print(direction_against_installed(sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])))
    except KeyError as exc:
        # 未涵蓋的 skill 是使用者錯誤，不是 bug：印一行理由就好，不要丟 traceback
        # 讓人以為方向判斷壞了。退出碼非零 → 呼叫端的閘門拒絕同步（fail closed）。
        sys.exit(exc.args[0])

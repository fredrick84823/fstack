#!/usr/bin/env python3
"""parity 涵蓋哪些 skill —— 清單在這裡，下面的判斷不認得任何一支 skill 的名字。

這支的由來是兩起同根因的事故。偵測「安裝版與 repo 漂移」的整套機制是完整的，但
`skills/comms/generate-meeting-notes` 寫死在好幾個地方，於是 60 幾支 skill 裡只有 1 支
被保護：

  1. improve 的三個修正直接改在安裝版，五天沒人發現 —— hook 指向安裝版，正在跑的碼
     比 repo 新，其中一個沒撿回來的後果是每個真實 session 都被靜默跳過。
  2. slack-pm 的 SKILL.md 帶著客戶名、品牌名與同事實名躺在 public repo 幾個月 ——
     去識別化只跑 generate-meeting-notes，slack-pm 從來沒經過它。

**只涵蓋一支的護欄，對其餘 59 支等於沒有護欄。** 所以涵蓋範圍做成**資料**（`SKILLS`）：
加一支 skill 是加一行，本檔與兩支同步腳本都不用改。腳本的「要不要跑去識別化」也是問
`SKILLS`（`--sanitize`），不是讓人在 CLI 上再抄一次那個布林。

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
    "skills/skill-evolution/improve": False,
}


def installed_dir(skill_rel: str) -> Path:
    """skill 的安裝位置。安裝版是**攤平**的：repo 的分類目錄（`comms/`、
    `skill-evolution/`…）在 `~/.agents/skills` 底下沒有對應層級。
    同一條規則在兩支同步腳本是 `${SKILL_REL##*/}`。"""
    return Path.home() / ".agents" / "skills" / Path(skill_rel).name


def _sanitized(skill_rel: str) -> bool:
    """`SKILLS` 的查表，附一句看得懂的理由。

    沒涵蓋的 skill **不可以**被當成「沒有漂移」放行 —— 那正是這張票在修的病，
    所以這裡 raise，而且訊息要直接說下一步在哪一行。
    """
    if skill_rel not in SKILLS:
        raise KeyError(
            f"{skill_rel} 不在 parity 的涵蓋清單裡。納入保護＝在 bin/parity_skills.py "
            f"的 SKILLS 加一行（值是「repo 版是不是 sanitize 過的」）。"
        )
    return SKILLS[skill_rel]


def _probes(repo_skill: Path, rel: str) -> list[str]:
    """一條候選路徑要送給 `git check-ignore` 的探針。

    送兩個，`rel` 與 `rel/`：目錄規則（`memory/`）只在 git 認得那條路徑是目錄時才命中，
    而 repo 端**刻意沒有**那個目錄可以 stat，加一條斜線就是直接告訴它「這是目錄」。
    少了帶斜線那一半，整個目錄的忽略規則會漏掉，而那是假漂移最大的一筆。

    **但 git 拒絕回答穿過 symlink 的路徑**（`fatal: pathspec '…/' is beyond a symbolic
    link`，退出碼 128），而一個壞探針會殺掉整批。所以祖先有 symlink 的整條都不送，
    路徑自己是 symlink 的只送不帶斜線那個。送不出去的路徑不會被排除，也就是照樣報成
    漂移 —— 這個方向是安全的，永遠不會靜默吞掉真漂移。

    可達路徑：跑過一次正向同步之後，`rsync -a` 會把安裝版的 symlink 原樣複製進 repo
    工作樹（improve 的執行期資料現在就是 5 個指向 private repo 的連結）。
    """
    *ancestors, name = Path(rel).parts
    here = repo_skill
    for part in ancestors:
        here = here / part
        if here.is_symlink():
            return []
    return [rel] if (here / name).is_symlink() else [rel, f"{rel}/"]


def _gitignored(repo: Path, skill_rel: str, rels: Sequence[str]) -> set[str]:
    """`rels` 之中 repo 端已經被 `.gitignore` 忽略的那些。

    判準問 repo 自己的 git，不在這裡維護第二份清單。判定對 **repo 端**的路徑做：
    安裝版不在 git 裡，問它等於問錯人。tracked 的檔案 git 一律回「未忽略」，所以這道
    排除在結構上不可能吞掉一個機制檔。

    `-z` 同時解決兩件事：非 ASCII 路徑不會被 `core.quotePath` 包成 C-quoted 字串
    （包了就對不上前綴 → 那條路徑永遠排不掉 → 每次都報一筆清不掉的假漂移，正是這張票
    在治的「喊狼來了」），以及路徑含換行時的歧義。

    git 自己出錯（不是 git repo、找不到 git）→ **raise**。回空集合是「什麼都沒被忽略」
    （假漂移照報），回全集是靜默吞掉真漂移 —— 兩個都不行，所以讓呼叫端知道這次沒比成。
    退出碼 1 是「一個都沒命中」，那是正常答案，不是錯誤。
    """
    repo_skill = repo / skill_rel
    probes = [p for rel in rels for p in _probes(repo_skill, rel)]
    if not probes:
        return set()
    try:
        done = subprocess.run(
            ["git", "-C", str(repo), "check-ignore", "-z", "--stdin"],
            input="\0".join(f"{skill_rel}/{p}" for p in probes),
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
        hit[len(prefix):].rstrip("/")
        for hit in done.stdout.split("\0")
        if hit.startswith(prefix)
    }


def _differs(cmp: filecmp.dircmp, prefix: str = "") -> list[str]:
    """`dircmp` 的五類差異，遞迴進子目錄。

    `funny_files`（兩邊都有、但比不下去）與 `common_funny`（兩邊都有、但型別不同或
    `stat` 失敗）**一定要收**。漏掉它們的症狀是靜默的資料遺失：左邊是懸空 symlink、
    右邊是一般檔，三個「正常」清單全空 → 回 `[]` → 方向判斷讀成「一致」→ 閘門放行
    `rsync -a --delete` → repo 的真實檔案被懸空連結蓋掉，全程沒有任何東西會叫。
    安裝版的 improve 現在就有 5 個指向 private repo 的 symlink，沒 clone 那個 repo 的
    機器上全部懸空 —— 這條路徑今天可達。
    """
    out = [
        prefix + n
        for n in cmp.left_only
        + cmp.right_only
        + cmp.diff_files
        + cmp.funny_files
        + cmp.common_funny
    ]
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

    比不了的時候回空清單（`installed` 不像安裝目錄、repo 內沒有同步腳本）——
    「沒有安裝版」與「安裝版一致」在呼叫端是同一件事：沒東西要講。

    **sanitize 過的**（`SKILLS` 是 True）：直接 diff 會把每個佔位符都算成差異，所以拿
    安裝版重跑一次 `bin/sync-from-installed.sh` 到暫存目錄，再跟 repo 版比 —— sed 規則
    只能有一份，走腳本就不必在這裡再抄一次。同步**沒有乾淨收尾**（退出碼不是 0）則
    raise `RuntimeError`：回空清單的話，一支壞掉的腳本會讓所有比對永遠通過，連
    integration test 都跟著變成永遠綠。退出碼 2（guard 命中內部指涉）預設也算沒收乾淨；
    `require_clean_guard=False` 只給方向判斷用 —— exit 2 的時候檔案是齊的，比對本身有效。

    **沒 sanitize 的**：直接比對，再排除 repo 的 `.gitignore` 忽略掉的路徑。執行期資料
    （佇列、log、lock、`memory/`）刻意不進版控，repo 端永遠沒有它們，不排除就是每次都報
    一串永遠修不掉的假漂移 —— 每次都喊狼來了的護欄跟沒有護欄是同一件事。sanitize 那條
    路徑不需要這道過濾：它比的是同步腳本產的暫存基準與 repo 版，兩邊本來就都不含那些。
    """
    sanitized = _sanitized(skill_rel)
    if not (installed / "SKILL.md").is_file():
        return []
    if not sanitized:
        rels = _differs(filecmp.dircmp(installed, repo / skill_rel))
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
    方向的證據，用 `0` 之類的哨兵值填會讓它退化成一個普通的比大小。

    走 `lstat` 而不是 `stat`：懸空 symlink 的 `exists()` 是 False、`stat()` 會炸，
    而它正是這裡最需要答得出來的形狀（`_differs` 新收的 funny 那兩類）。漏掉它 →
    兩邊都不收 → `IN_SYNC` → 閘門放行，正是 `_differs` 要擋的那條路徑換個地方重演。
    """
    return {rel: (root / rel).lstat().st_mtime for rel in rels if (root / rel).is_symlink()
            or (root / rel).exists()}


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
    # 兩支同步腳本的呼叫入口：
    #   --direction SKILL_REL INSTALLED REPO   動任何檔案之前問方向
    #   --sanitize  SKILL_REL                  要不要跑去識別化（印 1 或 0）
    # 兩者都順便是涵蓋檢查：未涵蓋的 skill 以非零退出碼收場，呼叫端因此拒絕同步。
    # 比對壞掉時讓例外原地炸開（非零退出碼），不要印一個看起來像答案的字串：
    # 呼叫端拿到「一致」就會放行 rsync --delete。
    usage = f"用法：{Path(__file__).name} --direction SKILL_REL INSTALLED REPO ｜ --sanitize SKILL_REL"
    try:
        if sys.argv[1:2] == ["--direction"] and len(sys.argv) == 5:
            print(direction_against_installed(sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])))
        elif sys.argv[1:2] == ["--sanitize"] and len(sys.argv) == 3:
            print(int(_sanitized(sys.argv[2])))
        else:
            sys.exit(usage)
    except KeyError as exc:
        # 未涵蓋的 skill 是使用者錯誤，不是 bug：印一行理由就好，不要丟 traceback
        # 讓人以為判斷壞了。退出碼非零 → 呼叫端 fail closed。
        sys.exit(exc.args[0])

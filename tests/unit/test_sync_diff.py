"""`parity.sync_diff` —— 把安裝版重新同步一次，回傳它與 repo 版之間的差異路徑。

**跑真的 `bin/sync-from-installed.sh`**，作法照抄 `test_sync_from_installed.py`：`HOME`、
來源、目的地全部造在 `tmp_path` 底下，所以不碰 `~/.agents` 也不碰 `~/.config`，算 unit。
假的 guard pattern 與 sanitize 表直接沿用那支的（`write_conf`）—— 兩份會漂，而那正是
這張票在講的病。

**為什麼一定要有這支**：其他每一條測試都把 `sync_diff` 換成替身。少了這支，真正的比對
路徑（子行程、退出碼判斷、遞迴、「不像安裝目錄就回空清單」）只有那條吃本機安裝版的
integration 會碰到 —— 而驗收條件 2 說的是「在安裝版植入一個 repo 版沒有的差異」，
替身永遠證明不了那件事。

正向案例（一致回 `[]`）與反向案例要成對：只有反向的話，一個永遠回非空清單的實作
也全綠；只有正向的話，一個永遠回 `[]` 的實作也全綠。
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

import pytest

from .conftest import load_script
from .test_sync_from_installed import DEST_REL, SCRIPT, write_conf

parity = load_script("parity")

# 兩邊一開始一模一樣的內容。含子目錄 —— 差異的遞迴要有東西可以遞迴。
BASE = {
    "SKILL.md": "hello\n",
    "scripts/create_gdoc_from_md.py": "# publish\n",
    "references/glossary.md": "詞彙\n",
}


def write_tree(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


@pytest.fixture
def pair(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """一組內容相同的 (installed, repo)，外加一個指向 `tmp_path` 的假 `HOME`。

    `sync_diff` 用 `subprocess.run` 跑腳本並繼承 `os.environ`，所以 `setenv` 有效 ——
    腳本讀的 `~/.config/generate-meeting-notes/` 因此也落在 `tmp_path` 底下。
    """
    monkeypatch.setenv("HOME", str(write_conf(tmp_path / "home")))

    repo = tmp_path / "repo"
    (repo / "bin").mkdir(parents=True)
    shutil.copy2(SCRIPT, repo / parity.SYNC_SCRIPT)
    write_tree(repo / DEST_REL, BASE)

    installed = write_tree(tmp_path / "installed", BASE)
    return installed, repo


# --------------------------------------------------------------------------
# 正向 —— 一致就是空清單
# --------------------------------------------------------------------------


def test_identical_trees_are_no_drift(pair: tuple[Path, Path]):
    """驗收條件 1 的函式側：兩邊一致回 `[]`。

    刪掉這條 → 比對變成永遠回非空（例如把暫存目錄自己的路徑也算進去），
    每次發佈都印一串假漂移，下面每條「有差異」的斷言也同時失去意義。
    """
    assert parity.sync_diff(*pair) == []


def test_a_placeholder_that_sanitize_produced_is_not_drift(pair: tuple[Path, Path]):
    """repo 版是**去識別化之後**的樣子 —— 佔位符不算漂移。

    刪掉這條 → 有人把比對改成直接 diff 兩個目錄（不跑同步腳本），每一個佔位符都變成
    一筆假漂移，而且是永遠修不掉的那種：修好就把內部字串推回 public repo。
    """
    installed, repo = pair
    (installed / "SKILL.md").write_text("project example-gcp-project\n", encoding="utf-8")
    (repo / DEST_REL / "SKILL.md").write_text("project <your-gcp-project>\n", encoding="utf-8")

    assert parity.sync_diff(installed, repo) == []


def test_a_newer_mtime_alone_is_not_drift(pair: tuple[Path, Path]):
    """內容一樣、只是 mtime 不同 → 不算漂移。

    刪掉這條 → 比對退化成只看 stat（大小＋時間），而安裝版每被編輯器碰一次
    mtime 就變。警告會在沒有任何內容差異時亮起，然後被當成噪音忽略。
    """
    installed, repo = pair
    os.utime(installed / "SKILL.md", (0, 0))

    assert parity.sync_diff(installed, repo) == []


# --------------------------------------------------------------------------
# 反向 —— 真的漂了要指得出是哪個路徑
# --------------------------------------------------------------------------


def test_a_file_only_in_the_installed_copy_is_drift(pair: tuple[Path, Path]):
    """驗收條件 2 的真正路徑：在安裝版植入一個 repo 版沒有的檔案，它要出現在回傳值裡。

    刪掉這條 → 整個偵測可以是 `return []`，其他每條測試都還是綠的。
    """
    installed, repo = pair
    (installed / "NOTES.md").write_text("只有安裝版有\n", encoding="utf-8")

    assert "NOTES.md" in parity.sync_diff(installed, repo)


def test_a_file_only_in_the_repo_copy_is_drift(pair: tuple[Path, Path]):
    """反方向也算：repo 版有、安裝版沒有 —— 那是「安裝版刪掉了但 repo 留成殭屍」。

    刪掉這條 → 只比對單邊（`left_only`），刪除永遠偵測不到。
    """
    installed, repo = pair
    (repo / DEST_REL / "ZOMBIE.md").write_text("只有 repo 有\n", encoding="utf-8")

    assert "ZOMBIE.md" in parity.sync_diff(installed, repo)


@pytest.mark.parametrize("rel", ["scripts/only_here.py", "references/only_here.md"])
def test_drift_inside_a_subdirectory_keeps_the_directory_prefix(pair: tuple[Path, Path], rel: str):
    """子目錄裡的差異要帶著目錄前綴 —— 這支 skill 的檔案大半都在 `scripts/`。

    刪掉這條 → 比對不遞迴（只看頂層），或路徑印成沒有前綴的檔名，
    使用者拿著一個 `only_here.py` 找不到是哪一個目錄底下的。
    """
    installed, repo = pair
    write_tree(installed, {rel: "新的\n"})

    assert rel in parity.sync_diff(installed, repo)


def test_same_name_different_content_is_drift(pair: tuple[Path, Path]):
    """同名不同內容算差異 —— 漂移最常見的樣子就是兩邊各改各的同一個檔。

    刪掉這條 → 比對只看「檔名存不存在」，兩邊同名檔案內容完全不同也判成一致，
    整道偵測只剩「有沒有新增檔案」這一半。
    """
    installed, repo = pair
    (repo / DEST_REL / "scripts/create_gdoc_from_md.py").write_text("# 改過了\n", encoding="utf-8")

    assert "scripts/create_gdoc_from_md.py" in parity.sync_diff(installed, repo)


# --------------------------------------------------------------------------
# 比不了 —— 回空清單，不是例外
# --------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["missing", "no-skill-md"])
def test_an_installed_dir_that_isnt_one_is_not_a_comparison(pair: tuple[Path, Path], kind: str):
    """驗收條件 4 的函式側：安裝版不存在／不像安裝目錄 → `[]`，不 raise。

    「沒有安裝版」與「安裝版一致」在呼叫端是同一件事：沒東西要講。
    刪掉這條 → 沒裝過這個 skill 的機器每次發佈都吃一個例外（或被那行「比對跳過」
    每天洗版），而那台機器根本沒有東西可以漂移。
    """
    installed, repo = pair
    shutil.rmtree(installed)
    if kind == "no-skill-md":
        installed.mkdir()

    assert parity.sync_diff(installed, repo) == []


def test_a_repo_without_the_sync_script_is_not_a_comparison(pair: tuple[Path, Path]):
    """repo 裡沒有同步腳本 → `[]`，不 raise。

    設定指到一個不是 fstack 的目錄就是這個樣子。
    刪掉這條 → `fstack_repo` 指錯路徑的症狀從「安靜地沒比對」變成每次發佈噴例外。
    """
    installed, repo = pair
    (repo / parity.SYNC_SCRIPT).unlink()

    assert parity.sync_diff(installed, repo) == []


# --------------------------------------------------------------------------
# 同步跑不完 —— raise，不可以回空清單
# --------------------------------------------------------------------------


def break_the_config(pair: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """沒建 guard pattern 檔 —— 腳本在 rsync 之前就以 1 收場。"""
    monkeypatch.setenv("HOME", str(write_conf(tmp_path / "bare-home", patterns=None)))


def plant_an_internal_reference(pair, tmp_path, monkeypatch):
    """安裝版帶著一個 sanitize 表換不掉的內部指涉 —— guard 命中，腳本以 2 收場。"""
    (pair[0] / "SKILL.md").write_text("我們在 AcmeCorp 的流程\n", encoding="utf-8")


# (把腳本弄壞的方法, 退出碼, 腳本自己印在 stderr 的字)
BROKEN_SYNC = [
    (break_the_config, 1, "未設定"),
    (plant_an_internal_reference, 2, "內部指涉"),
]


@pytest.mark.parametrize(
    "break_it, code, stderr_needle", BROKEN_SYNC, ids=[f"exit-{c}" for _, c, _ in BROKEN_SYNC]
)
def test_a_sync_that_cannot_finish_raises_instead_of_reporting_clean(
    pair, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, break_it, code: int, stderr_needle: str
):
    """同步腳本以非 0 收場 → `RuntimeError`，訊息帶得到退出碼與腳本說的理由。

    這是 #14 點名的陷阱：回 `[]` 的話，一支壞掉的腳本會讓比對**永遠通過** —— 沒建
    `~/.config/generate-meeting-notes/` 的機器（exit 1）上偵測從此不叫，而且連
    integration test 都跟著變成永遠綠。exit 2 同理：那不是「沒有差異」，是「這份同步
    結果裡有殘留內部指涉，不能用」，而 integration 原本就是靠「腳本回 0」在守那件事。

    刪掉這條 → 兩種壞法都被讀成「安裝版與 repo 一致」，靜悄悄的。
    """
    break_it(pair, tmp_path, monkeypatch)

    with pytest.raises(RuntimeError) as exc:
        parity.sync_diff(*pair)

    message = str(exc.value)
    assert re.search(rf"\b{code}\b", message)
    assert stderr_needle in message


# --------------------------------------------------------------------------
# `require_clean_guard=False` —— guard 命中不代表比不了
# --------------------------------------------------------------------------
#
# exit 2 是「同步結果裡有殘留內部指涉」，而那時檔案**已經**同步到暫存目錄了：比對本身
# 有效。方向判斷因此可以在 guard 髒的情況下照樣回答，否則它會變成「不知道」，而真正的
# 同步就再也走不到它自己的 guard —— 使用者拿到的是一個沒有理由的拒絕。
# exit 1 不一樣：那是同步根本沒跑起來，沒有東西可以比。


def test_a_guard_hit_still_produces_a_comparison_when_the_guard_is_not_required(
    pair, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """guard 命中（exit 2）＋ `require_clean_guard=False` → 照常回差異清單。

    刪掉這條 → 那個參數可以完全不被讀（或兩個分支都 raise），
    方向判斷在安裝版有內部指涉時永遠答不出來，正向同步從此一律被擋。
    """
    plant_an_internal_reference(pair, tmp_path, monkeypatch)

    assert parity.sync_diff(*pair, require_clean_guard=False) == ["SKILL.md"]


def test_a_sync_that_cannot_run_at_all_raises_even_when_the_guard_is_not_required(
    pair, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """exit 1（同步沒跑起來）→ 不管 `require_clean_guard` 是什麼都要 raise。

    刪掉這條 → 那個參數被當成「全部不檢查」，沒建設定檔的機器上比對回空清單，
    方向判斷讀成「一致」，`rsync --delete` 照跑 —— 正是本票要擋的那條路徑，
    只是換一個開關打開它。
    """
    break_the_config(pair, tmp_path, monkeypatch)

    with pytest.raises(RuntimeError):
        parity.sync_diff(*pair, require_clean_guard=False)
